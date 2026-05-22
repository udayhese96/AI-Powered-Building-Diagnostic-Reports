"""
thermal_extractor.py - Stage 1b
Extracts thermal readings, parameters, and images from the Thermal Report PDF.
Handles the quirk where every page contains ALL images (deduplicates by hash).
"""

import re
import hashlib
import fitz  # PyMuPDF
import logging
from typing import Dict, Any, List, Optional

from src.utils.helpers import (
    normalize_text, is_large_enough, setup_logger, extract_by_keyword
)
from src.utils.config import MIN_IMAGE_DIM, HOTSPOT_DELTA, COLDSPOT_LIMIT

logger = setup_logger("stage1.thermal")


class ThermalExtractor:
    """
    Extracts structured data from the Thermal Images PDF.

    Output schema:
    {
      "readings": [
        {
          "reading_id": "T1",
          "page": int,
          "location": str,
          "camera_file": str,           # e.g. RB02380X.JPG
          "hotspot_temp": float | None,
          "coldspot_temp": float | None,
          "emissivity": float | None,
          "ambient_temp": float | None,
          "anomaly_type": str,          # "hotspot" | "coldspot" | "normal"
          "image_key": str | None,      # key into self.data["images"]
          "raw_text": str,
        }
      ],
      "images": {
        "th_<hash8>": {
          "bytes": bytes,
          "ext": str,
          "width": int,
          "height": int,
          "pages": [int, ...],          # which pages contain this image
          "assigned_reading": None,     # filled in by linker
        }
      },
      "metadata": { ... },
      "extraction_meta": { ... }
    }
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.data: Dict[str, Any] = {
            "readings": [],
            "images": {},
            "metadata": {},
            "raw_text_by_page": {},
        }
        self._reading_counter = 0

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def extract_all(self) -> Dict[str, Any]:
        logger.info(f"Opening thermal PDF: {self.pdf_path} ({self.doc.page_count} pages)")

        # 1. Extract unique images first (solves the ALL-IMAGES-ON-EVERY-PAGE quirk)
        self._extract_unique_images()

        # 2. Extract text per page and parse readings
        for page_num in range(self.doc.page_count):
            text = self.doc[page_num].get_text("text")
            self.data["raw_text_by_page"][page_num] = text
            reading = self._parse_page_reading(text, page_num)
            if reading:
                self.data["readings"].append(reading)

        # 3. Assign image to reading by page proximity
        self._assign_images_to_readings()

        self.data["extraction_meta"] = {
            "pages": self.doc.page_count,
            "readings_count": len(self.data["readings"]),
            "unique_images": len(self.data["images"]),
        }
        logger.info(
            f"Thermal extraction complete: "
            f"{self.data['extraction_meta']['readings_count']} readings, "
            f"{self.data['extraction_meta']['unique_images']} unique images"
        )
        return self.data

    # ──────────────────────────────────────────────────────────────────────────
    # Image Extraction (with deduplication)
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_unique_images(self):
        """
        Extract all images across all pages, deduplicating by MD5 hash.
        Classifies images into thermal (top, y0 < 200) and visual (bottom, y0 >= 200) pairs.
        Also records which pages each unique image appears on.
        """
        hash_to_key: Dict[str, str] = {}

        for page_num in range(self.doc.page_count):
            page = self.doc[page_num]
            
            # Fetch placements using get_image_info to know exact coordinates (bbox)
            image_placements = page.get_image_info(xrefs=True)
            
            for placement in image_placements:
                xref = placement.get("xref")
                if not xref:
                    continue
                    
                w = placement.get("width", 0)
                h = placement.get("height", 0)
                bbox = placement.get("bbox", (0, 0, 0, 0)) # [x0, y0, x1, y1]
                y0 = bbox[1]
                
                # Filter out crosshairs/icons (they are small, e.g., w < 300 or h < 300)
                if w < 300 or h < 300:
                    continue

                base_img = self.doc.extract_image(xref)
                img_bytes = base_img["image"]

                img_hash = hashlib.md5(img_bytes).hexdigest()
                short_hash = img_hash[:8]
                
                # Classify by y0 coordinate (top vs bottom)
                image_type = "thermal" if y0 < 200 else "visual"
                prefix = "th" if image_type == "thermal" else "vi"
                key = f"{prefix}_{short_hash}"

                if key not in self.data["images"]:
                    self.data["images"][key] = {
                        "bytes": img_bytes,
                        "ext": base_img["ext"],
                        "width": w,
                        "height": h,
                        "type": image_type,
                        "pages": [],
                        "assigned_reading": None,
                    }
                    hash_to_key[img_hash] = key

                if page_num not in self.data["images"][key]["pages"]:
                    self.data["images"][key]["pages"].append(page_num)

        logger.info(f"Extracted {len(self.data['images'])} unique large images from thermal report")

    # ──────────────────────────────────────────────────────────────────────────
    # Page-level Reading Parsing
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_page_reading(self, text: str, page_num: int) -> Optional[Dict]:
        """
        Parse one thermal reading from a page's text.
        Actual format observed:
          28.8 \u00b0C\n23.4 \u00b0C\nHotspot : \n28.8 \u00b0C\nColdspot : \n23.4 \u00b0C
          Emissivity : \n0.94\nThermal image : RB02380X.JPG
        """
        # Skip pages with no meaningful thermal data
        has_temp = re.search(r"\d+\.?\d*", text)
        if not has_temp or len(text.strip()) < 10:
            return None

        self._reading_counter += 1
        reading: Dict[str, Any] = {
            "reading_id": f"T{self._reading_counter}",
            "page": page_num,
            "location": None,
            "camera_file": None,
            "hotspot_temp": None,
            "coldspot_temp": None,
            "emissivity": None,
            "ambient_temp": None,
            "anomaly_type": "moisture_pattern",
            "image_key": None,
            "raw_text": text[:500],
        }

        # Hotspot temperature — format: "Hotspot : \n28.8 \u00b0C" or "Hotspot : 28.8"
        # The degree sign comes out as various encodings, so we strip non-numeric chars
        m = re.search(r"Hotspot\s*:\s*\n?\s*([\d]+\.?[\d]*)", text, re.IGNORECASE)
        if m:
            reading["hotspot_temp"] = float(m.group(1))
        else:
            # Fallback: first number on page (usually the hotspot shown large)
            m = re.search(r"^([\d]+\.?[\d]*)", text.strip())
            if m:
                reading["hotspot_temp"] = float(m.group(1))

        # Coldspot temperature
        m = re.search(r"Coldspot\s*:\s*\n?\s*([\d]+\.?[\d]*)", text, re.IGNORECASE)
        if m:
            reading["coldspot_temp"] = float(m.group(1))
        else:
            # Fallback: second standalone number
            nums = re.findall(r"^([\d]+\.?[\d]*)", text, re.MULTILINE)
            if len(nums) >= 2:
                reading["coldspot_temp"] = float(nums[1])

        # Emissivity
        m = re.search(r"Emissivity\s*:\s*\n?\s*([\d]+\.?[\d]*)", text, re.IGNORECASE)
        if m:
            reading["emissivity"] = float(m.group(1))

        # Reflected / ambient temperature
        m = re.search(r"(?:Reflected|Ambient|Reference)\s*(?:temperature)?\s*:\s*\n?\s*([\d]+\.?[\d]*)",
                      text, re.IGNORECASE)
        if m:
            reading["ambient_temp"] = float(m.group(1))

        # Camera filename (e.g. RB02380X.JPG)
        m = re.search(r"([A-Z0-9_\-]{4,20}\.(?:JPG|JPEG|PNG|IR|IRF))", text, re.IGNORECASE)
        if m:
            reading["camera_file"] = m.group(1)

        # Location
        loc = self._extract_location(text)
        reading["location"] = loc

        # Classify anomaly
        reading["anomaly_type"] = self._classify_anomaly(
            reading["hotspot_temp"],
            reading["coldspot_temp"],
            reading["ambient_temp"],
        )

        return reading

    def _extract_location(self, text: str) -> str:
        """
        Try several patterns to find a location label in the page text.
        """
        # Explicit location label
        for pattern in [
            r"location\s*[:\-]\s*([^\n]+)",
            r"area\s*[:\-]\s*([^\n]+)",
            r"room\s*[:\-]\s*([^\n]+)",
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()[:80]

        # Area keywords in text
        area_keywords = [
            "hall", "bedroom", "kitchen", "bathroom", "passage",
            "staircase", "parking", "balcony", "terrace",
            "ceiling", "skirting", "wall", "master bedroom",
            "common bathroom", "external wall"
        ]
        lower = text.lower()
        for kw in sorted(area_keywords, key=len, reverse=True):
            if kw in lower:
                return kw.title()

        return "Unspecified"

    @staticmethod
    def _classify_anomaly(
        hotspot: Optional[float],
        coldspot: Optional[float],
        ambient: Optional[float],
    ) -> str:
        """Classify the anomaly type from temperature data."""
        if hotspot is not None and ambient is not None:
            if hotspot - ambient >= HOTSPOT_DELTA:
                return "hotspot"
        if coldspot is not None:
            if coldspot <= COLDSPOT_LIMIT:
                return "coldspot"
        if hotspot is not None:
            if hotspot >= 35:
                return "hotspot"
        return "moisture_pattern"

    # ──────────────────────────────────────────────────────────────────────────
    # Image Assignment
    # ──────────────────────────────────────────────────────────────────────────

    def _assign_images_to_readings(self):
        """
        Assign representative thermal and visual images to each thermal reading
        based on exact page match.
        """
        # Build maps: page → thermal_image_key, page → visual_image_key
        page_thermal_map: Dict[int, str] = {}
        page_visual_map: Dict[int, str] = {}
        
        for key, img in self.data["images"].items():
            img_type = img.get("type", "thermal")
            for page in img["pages"]:
                if img_type == "thermal":
                    page_thermal_map[page] = key
                else:
                    page_visual_map[page] = key

        for reading in self.data["readings"]:
            page = reading["page"]
            
            # 1. Thermal image key assignment
            thermal_key = None
            if page in page_thermal_map:
                thermal_key = page_thermal_map[page]
            else:
                # Fallback to nearest page
                if page_thermal_map:
                    nearest = min(page_thermal_map.keys(), key=lambda p: abs(p - page))
                    if abs(nearest - page) <= 2:
                        thermal_key = page_thermal_map[nearest]
            
            # 2. Visual image key assignment
            visual_key = None
            if page in page_visual_map:
                visual_key = page_visual_map[page]
            else:
                # Fallback to nearest page
                if page_visual_map:
                    nearest = min(page_visual_map.keys(), key=lambda p: abs(p - page))
                    if abs(nearest - page) <= 2:
                        visual_key = page_visual_map[nearest]
            
            # Set values
            reading["image_key"] = thermal_key  # backward compatibility
            reading["thermal_image_key"] = thermal_key
            reading["visual_image_key"] = visual_key
            
            if thermal_key:
                self.data["images"][thermal_key]["assigned_reading"] = reading["reading_id"]
            if visual_key:
                self.data["images"][visual_key]["assigned_reading"] = reading["reading_id"]
