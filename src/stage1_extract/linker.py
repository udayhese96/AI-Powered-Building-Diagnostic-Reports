"""
linker.py - Stage 1c
Links thermal readings to inspection areas using 3-tier matching.
Produces a list of links with confidence scores plus conflict/missing reports.
"""

import re
import logging
from typing import Dict, Any, List, Optional

from src.utils.helpers import normalize_text, setup_logger

logger = setup_logger("stage1.linker")


class ThermalAreaLinker:
    """
    Links thermal readings → inspection areas using three matching strategies:
      Tier 1: Exact normalized name match (confidence 0.95)
      Tier 2: Keyword overlap match       (confidence 0.75)
      Tier 3: Page-order positional guess (confidence 0.50)

    Output:
    {
      "links": [
        {
          "thermal_id": "T1",
          "area_id": 1,
          "area_name": "Hall",
          "confidence": 0.95,
          "method": "exact_name",
          "reading": { ... }
        }, ...
      ],
      "unmatched_thermals": [ { reading_id, location, reason } ],
      "conflicts": [ { area_id, area_name, inspection_finding, thermal_finding } ],
      "statistics": { total, matched, unmatched, avg_confidence }
    }
    """

    def __init__(self, inspection_data: Dict, thermal_data: Dict):
        self.inspection = inspection_data
        self.thermal = thermal_data
        self.areas: List[Dict] = inspection_data.get("areas", [])
        self.summary_table: List[Dict] = inspection_data.get("summary_table", [])
        self.readings: List[Dict] = thermal_data.get("readings", [])

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def link_all(self) -> Dict[str, Any]:
        links = []
        unmatched = []

        for reading in self.readings:
            link = self._match_reading(reading)
            if link:
                links.append(link)
            else:
                unmatched.append({
                    "reading_id": reading["reading_id"],
                    "location": reading.get("location", "Unspecified"),
                    "camera_file": reading.get("camera_file"),
                    "reason": "No matching inspection area found",
                })

        conflicts = self._detect_conflicts(links)

        avg_conf = (
            sum(l["confidence"] for l in links) / len(links) if links else 0
        )

        result = {
            "links": links,
            "unmatched_thermals": unmatched,
            "conflicts": conflicts,
            "statistics": {
                "total_readings": len(self.readings),
                "matched": len(links),
                "unmatched": len(unmatched),
                "avg_confidence": round(avg_conf, 3),
            },
        }

        logger.info(
            f"Linking complete: {len(links)} matched, "
            f"{len(unmatched)} unmatched, "
            f"{len(conflicts)} conflicts, "
            f"avg confidence={avg_conf:.2f}"
        )
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Matching Tiers
    # ──────────────────────────────────────────────────────────────────────────

    def _match_reading(self, reading: Dict) -> Optional[Dict]:
        location = reading.get("location", "")

        # Tier 1: exact normalized match
        match = self._tier1_exact(location)
        if match:
            return self._make_link(reading, match, 0.95, "exact_name")

        # Tier 2: keyword overlap
        match = self._tier2_keyword(location)
        if match:
            return self._make_link(reading, match, 0.75, "keyword_overlap")

        # Tier 3: summary table alignment (order-based)
        match = self._tier3_summary_table(reading)
        if match:
            return self._make_link(reading, match, 0.55, "summary_table_order")

        # Tier 4: positional page heuristic
        match = self._tier4_positional(reading)
        if match:
            return self._make_link(reading, match, 0.40, "positional_page")

        return None

    def _tier1_exact(self, location: str) -> Optional[Dict]:
        """Exact normalized area name match."""
        norm_loc = normalize_text(location)
        for area in self.areas:
            if normalize_text(area["name"]) == norm_loc:
                return area
        return None

    def _tier2_keyword(self, location: str) -> Optional[Dict]:
        """
        At least half the significant words in location appear in area name
        (or vice versa).
        """
        loc_words = set(self._keywords(location))
        if not loc_words:
            return None

        best_area = None
        best_score = 0.0

        for area in self.areas:
            area_words = set(self._keywords(area["name"]))
            if not area_words:
                continue
            overlap = loc_words & area_words
            score = len(overlap) / max(len(loc_words), len(area_words))
            if score > best_score and score >= 0.4:
                best_score = score
                best_area = area

        return best_area

    def _tier3_summary_table(self, reading: Dict) -> Optional[Dict]:
        """
        Use the summary table to match thermal reading by order.
        Thermal readings are assumed to follow the same order as summary table rows.
        """
        if not self.summary_table:
            return None

        # reading_id is T1, T2, ... map to summary table row index
        reading_idx = int(reading["reading_id"][1:]) - 1
        if reading_idx < len(self.summary_table):
            row = self.summary_table[reading_idx]
            neg_area_desc = row.get("negative_area", "")
            area_name = self._extract_area_name_from_obs(neg_area_desc)
            if area_name:
                match = self._find_area_by_name(area_name)
                if match:
                    return match
        return None

    def _tier4_positional(self, reading: Dict) -> Optional[Dict]:
        """
        If reading is on the same page (or ±2 pages) as an area, link them.
        """
        r_page = reading.get("page", -1)
        best_area = None
        best_dist = 999

        for area in self.areas:
            a_page = area.get("page")
            if a_page is None:
                continue
            dist = abs(a_page - r_page)
            if dist < best_dist and dist <= 2:
                best_dist = dist
                best_area = area

        return best_area

    # ──────────────────────────────────────────────────────────────────────────
    # Conflict Detection
    # ──────────────────────────────────────────────────────────────────────────

    def _detect_conflicts(self, links: List[Dict]) -> List[Dict]:
        """
        Flag conflicts: e.g., inspection says 'dry' but thermal shows coldspot.
        """
        conflicts = []
        dry_words = {"dry", "no moisture", "clean", "intact", "no dampness"}

        for link in links:
            reading = link["reading"]
            area_id = link["area_id"]

            # Get observations for this area
            obs_texts = [
                o["text"].lower()
                for o in self.inspection.get("observations", [])
                if o["area_id"] == area_id
            ]

            obs_says_dry = any(
                any(dw in obs for dw in dry_words)
                for obs in obs_texts
            )

            thermal_anomaly = reading.get("anomaly_type") in ("hotspot", "coldspot", "moisture_pattern")

            if obs_says_dry and thermal_anomaly:
                conflicts.append({
                    "area_id": area_id,
                    "area_name": link["area_name"],
                    "inspection_finding": "Visual inspection indicates no significant moisture",
                    "thermal_finding": (
                        f"Thermal reading {reading['reading_id']} shows "
                        f"{reading['anomaly_type']} "
                        f"(hotspot: {reading.get('hotspot_temp')}°C, "
                        f"coldspot: {reading.get('coldspot_temp')}°C)"
                    ),
                    "confidence": link["confidence"],
                })

        return conflicts

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _keywords(text: str) -> List[str]:
        """Extract significant words (length ≥ 3, not stopwords)."""
        stop = {"the", "of", "at", "in", "on", "and", "a", "an", "to", "for",
                "no", "flat", "observed", "level", "area", "side"}
        words = re.findall(r"[a-z]+", text.lower())
        return [w for w in words if len(w) >= 3 and w not in stop]

    @staticmethod
    def _extract_area_name_from_obs(description: str) -> Optional[str]:
        """From 'Observed dampness at Hall' extract 'Hall'."""
        room_kws = [
            "master bedroom", "common bathroom", "hall", "bedroom", "kitchen",
            "bathroom", "passage", "staircase", "parking", "balcony", "terrace",
        ]
        lower = description.lower()
        for kw in sorted(room_kws, key=len, reverse=True):
            if kw in lower:
                return kw.title()
        return None

    def _find_area_by_name(self, name: str) -> Optional[Dict]:
        norm = normalize_text(name)
        for area in self.areas:
            if normalize_text(area["name"]) == norm:
                return area
            if norm in normalize_text(area["name"]):
                return area
        return None

    @staticmethod
    def _make_link(reading: Dict, area: Dict, confidence: float, method: str) -> Dict:
        return {
            "thermal_id": reading["reading_id"],
            "area_id": area["area_id"],
            "area_name": area["name"],
            "confidence": confidence,
            "method": method,
            "reading": reading,
        }
