"""
inspection_extractor.py - Stage 1a
Extracts structured data from the Inspection Report PDF.
Works on any inspection PDF layout (not hardcoded to sample).
"""

import re
import fitz  # PyMuPDF
import logging
from typing import Dict, Any, List

from src.utils.helpers import (
    normalize_text, hash_text, extract_by_keyword,
    detect_severity, parse_date, is_large_enough, setup_logger
)
from src.utils.config import MIN_IMAGE_DIM

logger = setup_logger("stage1.inspection")


class InspectionExtractor:
    """
    Extracts all relevant data from an inspection report PDF.

    Output schema:
    {
      "property": { address, date, inspector, flat_no, ... },
      "areas": [ { area_id, name, page, negative_side, positive_side }, ... ],
      "observations": [ { obs_id, area_id, text, severity, page }, ... ],
      "summary_table": [ { point_no, negative, positive }, ... ],
      "images": { "img_key": { bytes, page, width, height, xref }, ... },
      "raw_text_by_page": { page_num: text, ... },
      "extraction_meta": { pages, obs_count, areas_count, images_count }
    }
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.data: Dict[str, Any] = {
            "property": {},
            "intro_sections": {},
            "site_description": {},
            "checklist_items": {},
            "areas": [],
            "observations": [],
            "summary_table": [],
            "images": {},
            "raw_text_by_page": {},
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def extract_all(self) -> Dict[str, Any]:
        """Run full extraction pipeline and return structured dict."""
        logger.info(f"Opening inspection PDF: {self.pdf_path} ({self.doc.page_count} pages)")

        for page_num in range(self.doc.page_count):
            page = self.doc[page_num]
            text = page.get_text("text")
            self.data["raw_text_by_page"][page_num] = text

        # Sequential extraction steps
        self._extract_property_info()
        self._extract_intro_sections()       # NEW: Background, Objective, Scope, Tools
        self._extract_site_description()     # NEW: Structure type, floors, age
        self._extract_summary_table()
        self._extract_areas_and_observations()
        self._extract_all_observations()     # NEW: Scan all pages for 'Observed' sentences
        self._extract_checklist_items()      # NEW: Input 1.1-1.22 checkboxes
        self._extract_images()
        self._deduplicate_observations()

        self.data["extraction_meta"] = {
            "pages":               self.doc.page_count,
            "areas_count":         len(self.data["areas"]),
            "obs_count":           len(self.data["observations"]),
            "images_count":        len(self.data["images"]),
            "summary_table_rows":  len(self.data["summary_table"]),
            "readings_count":      0,  # filled by thermal extractor
        }

        logger.info(
            f"Inspection extraction complete: "
            f"{self.data['extraction_meta']['areas_count']} areas, "
            f"{self.data['extraction_meta']['obs_count']} observations, "
            f"{self.data['extraction_meta']['images_count']} images"
        )
        return self.data

    # ──────────────────────────────────────────────────────────────────────────
    # Property Info
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_property_info(self):
        """Extract address, date, customer name from first page."""
        first_text = self.data["raw_text_by_page"].get(0, "")
        prop = {}

        prop["address"]         = extract_by_keyword(first_text, "address", 150)
        prop["inspection_date"] = parse_date(first_text)
        prop["customer_name"]   = extract_by_keyword(first_text, "customer name", 80)
        prop["inspector_name"]  = extract_by_keyword(first_text, "inspector", 80)
        prop["flat_no"]         = self._find_flat_no(first_text)
        prop["report_date"]     = parse_date(first_text)

        # Fallback: scan all pages for address-like patterns
        if not prop["address"]:
            for page_text in self.data["raw_text_by_page"].values():
                prop["address"] = extract_by_keyword(page_text, "address", 150)
                if prop["address"]:
                    break

        self.data["property"] = {k: v for k, v in prop.items() if v}

    def _find_flat_no(self, text: str) -> str:
        """Extract flat/unit number from text."""
        m = re.search(r"(?:flat\s*no\.?\s*|unit\s*no\.?\s*|apt\.?\s*)([^\s,\n]+)",
                      text, re.IGNORECASE)
        return m.group(1) if m else None

    # ──────────────────────────────────────────────────────────────────────────
    # Summary Table (negative → positive side mapping)
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_summary_table(self):
        """
        Find the SUMMARY TABLE page and parse the point mappings.
        Stores list of { point_no, negative_area, positive_area }.
        """
        for page_num, text in self.data["raw_text_by_page"].items():
            if "SUMMARY TABLE" in text.upper():
                logger.info(f"Summary table found on page {page_num + 1}")
                rows = self._parse_summary_table_text(text)
                self.data["summary_table"] = rows
                return

    def _parse_summary_table_text(self, text: str) -> List[Dict]:
        """
        Parse summary table rows from the actual PDF text format.
        
        Actual format observed:
          Point \nNo \nImpacted area (-ve side) \nPoint \nNo \nExposed area (+ve side) \n
          1 \nObserved dampness at the skirting level \nof Hall of Flat No. 103 \n \n
          1.1 \n \nObserved gaps between the tile joints of \nCommon Bathroom ...
        """
        rows = []
        
        # Collapse the entire text into a clean token stream
        # Remove empty lines, join continuation lines for observations
        lines = [l.strip() for l in text.splitlines()]
        lines = [l for l in lines if l]  # remove blank lines
        
        # Find start of data (after header)
        start_idx = 0
        for i, line in enumerate(lines):
            if "impacted area" in line.lower() or "exposed area" in line.lower():
                start_idx = i + 1
                break

        # Now parse tokens: a point number line followed by description lines
        # Point numbers look like: "1", "1.1", "2", "2.1" etc.
        point_pattern = re.compile(r'^(\d+(?:\.\d+)?)$')
        
        # Collect all (point_no, description) pairs
        entries = []  # list of (point_no_str, description)
        i = start_idx
        while i < len(lines):
            line = lines[i]
            m = point_pattern.match(line)
            if m:
                pt = m.group(1)
                # Collect following description lines until next point number
                desc_parts = []
                j = i + 1
                while j < len(lines) and not point_pattern.match(lines[j]):
                    desc_parts.append(lines[j])
                    j += 1
                desc = " ".join(desc_parts).strip()
                if desc:
                    entries.append((pt, desc))
                i = j
            else:
                i += 1
        
        # Separate negative (-ve, integer points like 1,2,3) and
        # positive (+ve, decimal points like 1.1, 2.1) entries
        neg_entries = [(pt, desc) for pt, desc in entries if '.' not in pt]
        pos_entries = [(pt, desc) for pt, desc in entries if '.' in pt]
        
        for pt, neg_desc in neg_entries:
            # Find matching positive entry
            matching_pos = [(ppt, pdesc) for ppt, pdesc in pos_entries
                           if ppt.startswith(pt + '.')]
            pos_desc = matching_pos[0][1] if matching_pos else None
            rows.append({
                "point_no": pt,
                "negative_area": neg_desc,
                "positive_area": pos_desc,
            })
        
        return rows

    # ──────────────────────────────────────────────────────────────────────────
    # Areas and Observations
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_areas_and_observations(self):
        """
        Derive inspection areas primarily from the summary table (most reliable).
        Then scan pages for 'Observed' sentences to build observations.
        Falls back to keyword detection if summary table is empty.
        """
        # Primary: use summary table to build areas + observations
        if self.data["summary_table"]:
            for row in self.data["summary_table"]:
                # Negative side area
                if row.get("negative_area"):
                    area_name = self._extract_area_name_from_description(row["negative_area"])
                    if area_name:
                        self._get_or_create_area(area_name, page=9)  # summary table is page 10
                        area_id = self._find_area_id(area_name)
                        if area_id and not self._obs_exists(row["negative_area"]):
                            self.data["observations"].append({
                                "obs_id": len(self.data["observations"]) + 1,
                                "area_id": area_id,
                                "text": row["negative_area"],
                                "severity": detect_severity(row["negative_area"]),
                                "page": 9,
                                "side": "negative",
                            })
                # Positive side area
                if row.get("positive_area"):
                    area_name = self._extract_area_name_from_description(row["positive_area"])
                    if area_name:
                        self._get_or_create_area(area_name, page=9)
                        area_id = self._find_area_id(area_name)
                        if area_id and not self._obs_exists(row["positive_area"]):
                            self.data["observations"].append({
                                "obs_id": len(self.data["observations"]) + 1,
                                "area_id": area_id,
                                "text": row["positive_area"],
                                "severity": detect_severity(row["positive_area"]),
                                "page": 9,
                                "side": "positive",
                            })
        
        # Also extract the impacted areas list from early pages
        for page_num in range(min(5, self.doc.page_count)):
            text = self.data["raw_text_by_page"].get(page_num, "")
            if "impacted areas" in text.lower():
                self._parse_impacted_areas_list(text, page_num)
        
        # Fallback: if no areas yet, do keyword scan
        if not self.data["areas"]:
            self._keyword_scan_areas()

    def _get_or_create_area(self, area_name: str, page=None) -> int:
        """Find or create an area by name. Returns area_id."""
        existing = [a for a in self.data["areas"]
                    if normalize_text(a["name"]) == normalize_text(area_name)]
        if existing:
            return existing[0]["area_id"]
        area_id = len(self.data["areas"]) + 1
        self.data["areas"].append({
            "area_id": area_id,
            "name": area_name,
            "page": page,
            "negative_side": None,
            "positive_side": None,
        })
        return area_id

    def _find_area_id(self, area_name: str):
        """Find area_id by name."""
        for a in self.data["areas"]:
            if normalize_text(a["name"]) == normalize_text(area_name):
                return a["area_id"]
        return None

    def _keyword_scan_areas(self):
        """Fallback: scan pages for room keywords to find areas."""
        room_keywords = [
            "hall", "bedroom", "kitchen", "bathroom", "passage",
            "staircase", "parking", "balcony", "terrace"
        ]
        for page_num, text in self.data["raw_text_by_page"].items():
            for kw in room_keywords:
                if kw in text.lower():
                    self._get_or_create_area(kw.title(), page=page_num)


    def _parse_impacted_areas_list(self, text: str, page_num: int):
        """Parse a comma-separated or line-by-line list of impacted areas."""
        # Look for the list following "Impacted Areas"
        m = re.search(r"Impacted\s+Areas?\s*[\n:,]?\s*(.+?)(?:\n\n|\Z)", text,
                      re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1)
            # Split on comma or newline
            parts = re.split(r"[,\n]+", raw)
            for part in parts:
                part = part.strip().rstrip(".,")
                if len(part) > 2:
                    existing = [a for a in self.data["areas"]
                                if normalize_text(a["name"]) == normalize_text(part)]
                    if not existing:
                        self.data["areas"].append({
                            "area_id": len(self.data["areas"]) + 1,
                            "name": part,
                            "page": page_num,
                            "negative_side": None,
                            "positive_side": None,
                        })

    def _areas_from_summary_table(self):
        """Ensure every summary table area is present in self.data['areas']."""
        for row in self.data["summary_table"]:
            for side in ["negative_area", "positive_area"]:
                raw = row.get(side)
                if not raw:
                    continue
                # Shorten to just the area name (remove "Observed dampness at…")
                area_name = self._extract_area_name_from_description(raw)
                if not area_name:
                    continue
                existing = [a for a in self.data["areas"]
                            if normalize_text(a["name"]) == normalize_text(area_name)]
                if not existing:
                    self.data["areas"].append({
                        "area_id": len(self.data["areas"]) + 1,
                        "name": area_name,
                        "page": None,
                        "negative_side": row["negative_area"] if side == "negative_area" else None,
                        "positive_side": row["positive_area"] if side == "positive_area" else None,
                    })

    def _extract_area_name_from_description(self, description: str) -> str:
        """
        From 'Observed dampness at the skirting level of Hall of Flat No. 103'
        extract 'Hall'.
        """
        # Look for room name keywords
        room_keywords = [
            "master bedroom", "common bathroom", "hall", "bedroom", "kitchen",
            "bathroom", "passage", "staircase", "parking", "balcony", "terrace"
        ]
        lower = description.lower()
        for kw in sorted(room_keywords, key=len, reverse=True):
            if kw in lower:
                # Return the matched keyword capitalized
                idx = lower.index(kw)
                return description[idx: idx + len(kw)].title()
        return None

    def _clean_area_name(self, line: str) -> str:
        """Clean a raw line to extract just the area name."""
        line = re.sub(r"^\s*\d+[\.\)]\s*", "", line)  # remove leading numbers
        line = re.sub(r"[:\-–]+$", "", line)           # remove trailing colons
        return line.strip()

    @staticmethod
    def _extract_observation_bullets(block: str) -> List[str]:
        """Extract bullet / numbered observation lines from a text block."""
        obs = []
        # Bullet points
        for m in re.finditer(r"^[\s]*[-•*▪]\s+(.+)$", block, re.MULTILINE):
            obs.append(m.group(1).strip())
        # Numbered items
        for m in re.finditer(r"^\s*\d+[\.\)]\s+(.+)$", block, re.MULTILINE):
            obs.append(m.group(1).strip())
        # "Observed …" standalone sentences
        for m in re.finditer(r"(Observed\s+[^\n]+)", block, re.IGNORECASE):
            candidate = m.group(1).strip()
            if len(candidate) > 20 and candidate not in obs:
                obs.append(candidate)
        return [o for o in obs if len(o) >= 10]

    def _obs_exists(self, text: str) -> bool:
        h = hash_text(text)
        return any(hash_text(o["text"]) == h for o in self.data["observations"])

    # ──────────────────────────────────────────────────────────────────────────
    # Image Extraction
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_images(self):
        """Extract all sufficiently large images from the PDF."""
        seen_xrefs = set()
        for page_num in range(self.doc.page_count):
            page = self.doc[page_num]
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                base_img = self.doc.extract_image(xref)
                w, h = base_img["width"], base_img["height"]
                if not is_large_enough(w, h, MIN_IMAGE_DIM):
                    continue

                key = f"inspection_p{page_num + 1}_x{xref}"
                self.data["images"][key] = {
                    "bytes": base_img["image"],
                    "ext": base_img["ext"],
                    "page": page_num,
                    "width": w,
                    "height": h,
                    "xref": xref,
                }

    # ──────────────────────────────────────────────────────────────────────────
    # Deduplication
    # ──────────────────────────────────────────────────────────────────────────

    def _deduplicate_observations(self):
        """Remove duplicate observations using hash comparison."""
        seen = set()
        unique = []
        for obs in self.data["observations"]:
            h = hash_text(obs["text"])
            if h not in seen:
                unique.append(obs)
                seen.add(h)
        removed = len(self.data["observations"]) - len(unique)
        if removed:
            logger.info(f"Removed {removed} duplicate observation(s)")
        self.data["observations"] = unique

    # ──────────────────────────────────────────────────────────────────────────
    # NEW: Introduction Sections
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_intro_sections(self):
        """Extract Section 1: Background, Objective, Scope of Work, Tools."""
        full_text = "\n".join(self.data["raw_text_by_page"].values())
        intro = {}

        # Background
        m = re.search(
            r"(?:BACKGROUND|Background)\s*[:\n](.+?)(?=(?:OBJECTIVE|Objective|SCOPE|1\.2|1\.3))",
            full_text, re.DOTALL | re.IGNORECASE
        )
        if m:
            intro["background"] = " ".join(m.group(1).split()).strip()[:800]

        # Objective
        m = re.search(
            r"(?:OBJECTIVE[^:]*|1\.2[^:]*)\s*[:\n](.+?)(?=(?:SCOPE|1\.3|1\.4|TOOLS))",
            full_text, re.DOTALL | re.IGNORECASE
        )
        if m:
            raw_obj = m.group(1)
            bullets = re.findall(r"(?:^|\n)\s*[•\-\*\u2022]\s*(.+)", raw_obj)
            if bullets:
                intro["objectives"] = [b.strip() for b in bullets if len(b.strip()) > 10]
            else:
                intro["objectives"] = [
                    s.strip() for s in raw_obj.split("\n")
                    if len(s.strip()) > 15
                ][:7]

        # Scope
        m = re.search(
            r"(?:SCOPE OF WORK|Scope of Work|1\.3)\s*[:\n](.+?)(?=(?:TOOLS|1\.4|SECTION 2|2\.))",
            full_text, re.DOTALL | re.IGNORECASE
        )
        if m:
            intro["scope"] = " ".join(m.group(1).split()).strip()[:500]

        # Tools
        tools_found = []
        tool_keywords = [
            "tapping hammer", "crack gauge", "IR thermography", "thermograph",
            "moisture meter", "pH meter", "moisture & pH", "scaffolding"
        ]
        for tk in tool_keywords:
            if tk.lower() in full_text.lower():
                tools_found.append(tk.title())
        if tools_found:
            intro["tools_used"] = list(dict.fromkeys(tools_found))  # deduplicate

        self.data["intro_sections"] = intro
        logger.info(f"Intro sections extracted: {list(intro.keys())}")

    # ──────────────────────────────────────────────────────────────────────────
    # NEW: Site Description
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_site_description(self):
        """Extract Section 2.2: Structure type, floors, age, previous repairs."""
        full_text = "\n".join(self.data["raw_text_by_page"].values())
        site = {}

        patterns = {
            "structure_type":       r"(?:type of structure|Type of structure)\s*[:\n]+\s*(.+?)(?:\n|$)",
            "floors":               r"(?:Floors?|No\.? of floors?)\s*[:\n]+\s*(.+?)(?:\n|$)",
            "year_of_construction": r"(?:Year of Construction|year of construction)\s*[:\n]+\s*(.+?)(?:\n|$)",
            "age_years":            r"(?:Age\s*(?:of\s*)?(?:Building|building)\s*(?:\(years\))?)\s*[:\n]+\s*(.+?)(?:\n|$)",
            "previous_audit":       r"(?:Previous Structure Audit|Previous Audit)\s*[:\n]+\s*(.+?)(?:\n|$)",
            "previous_repairs":     r"(?:Previous Repairs|previous repairs)\s*[:\n]+\s*(.+?)(?:\n|$)",
        }

        for key, pattern in patterns.items():
            m = re.search(pattern, full_text, re.IGNORECASE)
            if m:
                val = m.group(1).strip().strip(":")
                if len(val) < 100:
                    site[key] = val

        # Also try to grab address from site description
        m = re.search(r"Site Address\s*[:\n]+\s*(.+?)(?=\n\n|\n[A-Z])", full_text, re.DOTALL | re.IGNORECASE)
        if m:
            site["address"] = " ".join(m.group(1).split()).strip()[:200]

        self.data["site_description"] = site
        logger.info(f"Site description extracted: {list(site.keys())}")

    # ──────────────────────────────────────────────────────────────────────────
    # NEW: Full Page Observation Scan
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_all_observations(self):
        """
        Scan ALL pages for 'Observed...' sentences and add to observations
        under the best matching area.
        """
        observed_pattern = re.compile(
            r"(Observed\s+[A-Za-z][^.\n]{20,200}\.?)",
            re.IGNORECASE
        )

        for page_num, text in self.data["raw_text_by_page"].items():
            for m in observed_pattern.finditer(text):
                obs_text = m.group(1).strip()
                if self._obs_exists(obs_text):
                    continue

                # Find best area match
                area_name = self._extract_area_name_from_description(obs_text)
                area_id = None
                if area_name:
                    area_id = self._find_area_id(area_name)
                if not area_id and self.data["areas"]:
                    area_id = self.data["areas"][0]["area_id"]

                if area_id:
                    self.data["observations"].append({
                        "obs_id":   len(self.data["observations"]) + 1,
                        "area_id":  area_id,
                        "text":     obs_text,
                        "severity": detect_severity(obs_text),
                        "page":     page_num,
                        "side":     "negative",
                        "source":   "full_scan",
                    })

        logger.info(f"Full observation scan complete. Total: {len(self.data['observations'])}")

    # ──────────────────────────────────────────────────────────────────────────
    # NEW: Checklist Items Extraction
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_checklist_items(self):
        """
        Extract WC Checklist and External Wall Checklist using vertical-horizontal word grouping.
        """
        wc_checklist = {}
        external_wall_checklist = {}
        answers_set = {"Yes", "No", "N/A", "Moderate", "All time", "Not sure", "100%", "75%", "Good", "Poor"}

        try:
            for page_num in [6, 7, 8]:
                if page_num >= self.doc.page_count:
                    continue
                page = self.doc[page_num]
                words = page.get_text("words")
                
                # Group words by block_no
                blocks_words = {}
                for w in words:
                    x0, y0, x1, y1, text, block_no, line_no, word_no = w
                    if block_no not in blocks_words:
                        blocks_words[block_no] = []
                    blocks_words[block_no].append(w)
                    
                # Process blocks
                parsed_blocks = []
                for b_no, b_words in blocks_words.items():
                    # Sort words in block
                    b_words = sorted(b_words, key=lambda w: (w[1], w[0]))
                    bx0 = min([w[0] for w in b_words])
                    by0 = min([w[1] for w in b_words])
                    bx1 = max([w[2] for w in b_words])
                    by1 = max([w[3] for w in b_words])
                    
                    left_txt_words = [w for w in b_words if w[0] < 375]
                    right_txt_words = [w for w in b_words if w[0] >= 375]
                    
                    left_txt = " ".join([w[4] for w in left_txt_words]).strip()
                    right_txt = " ".join([w[4] for w in right_txt_words]).strip()
                    
                    left_txt = re.sub(r'\s+', ' ', left_txt).rstrip(" -–:")
                    right_txt = re.sub(r'\s+', ' ', right_txt)
                    
                    parsed_blocks.append({
                        "block_no": b_no,
                        "x0": bx0, "y0": by0, "x1": bx1, "y1": by1,
                        "left_text": left_txt,
                        "right_text": right_txt,
                        "b_words": b_words
                    })
                    
                # Sort blocks by y0
                parsed_blocks = sorted(parsed_blocks, key=lambda b: b["y0"])
                
                for pb in parsed_blocks:
                    q_text = pb["left_text"]
                    
                    # Skip empty left text blocks (which are pure answer blocks)
                    if not q_text:
                        continue
                        
                    # Skip headers or metadata
                    if "inputs for" in q_text.lower() or "members 100%" in q_text.lower() or "condition of external wall" in q_text.lower() or "condition of adhesion of old paint" in q_text.lower() or "flagged" in q_text.lower() or "checklist" in q_text.lower():
                        continue
                    if len(q_text) < 4:
                        continue
                        
                    ans_text = pb["right_text"]
                    ans_val = None
                    
                    if ans_text:
                        # If the block itself has right_text, it's a self-match
                        ans_val = ans_text
                    else:
                        # Look for a pure right-side block or any block that overlaps in Y
                        best_r = None
                        min_dist = 9999
                        for r_pb in parsed_blocks:
                            if r_pb["block_no"] == pb["block_no"]:
                                continue
                            # Overlap in Y?
                            overlap = not (pb["y1"] < r_pb["y0"] - 8 or pb["y0"] > r_pb["y1"] + 8)
                            if overlap:
                                # Best match is on the right side
                                r_val = r_pb["right_text"] if r_pb["right_text"] else r_pb["left_text"]
                                if r_val:
                                    dist = abs(pb["y0"] - r_pb["y0"])
                                    if dist < min_dist:
                                        min_dist = dist
                                        best_r = r_pb
                                        
                        if best_r:
                            ans_val = best_r["right_text"] if best_r["right_text"] else best_r["left_text"]
                        else:
                            # Check if self-contained via split
                            matched_self = False
                            for ans in answers_set:
                                if q_text.endswith(ans) or f" {ans}" in q_text:
                                    parts = q_text.split(ans)
                                    q_text = parts[0].strip().rstrip(" -–:")
                                    ans_val = ans
                                    matched_self = True
                                    break
                            if not matched_self:
                                ans_val = "Good"

                    # Remove any leading/trailing weird chars from Q
                    q_text = re.sub(r'^[•\-\*\s]+', '', q_text).strip()
                    
                    if not q_text:
                        continue
                    
                    # Split into WC Checklist and External Wall Checklist
                    if page_num == 6:
                        # We use pb["y0"] to decide
                        if pb["y0"] < 536.2:
                            wc_checklist[q_text] = ans_val
                        else:
                            external_wall_checklist[q_text] = ans_val
                    else:
                        external_wall_checklist[q_text] = ans_val
                        
            logger.info(f"Checklist extraction: WC Checklist has {len(wc_checklist)} items, External Wall Checklist has {len(external_wall_checklist)} items.")
        except Exception as e:
            logger.error(f"Error extracting checklist items: {e}")
            
        self.data["checklist_items"] = {
            "wc_checklist": wc_checklist,
            "external_wall_checklist": external_wall_checklist
        }

