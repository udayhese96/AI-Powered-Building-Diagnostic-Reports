"""
validator.py - Stage 3
Data integrity and linking validation at each checkpoint of the pipeline.
"""

import logging
from typing import Dict, Any, List

from src.utils.helpers import setup_logger

logger = setup_logger("stage3.validator")


class PipelineValidator:
    """
    Validates data at three checkpoints:
      1. After extraction (Stage 1)
      2. After linking (Stage 1c)
      3. After DDR generation (Stage 4)

    Returns structured validation reports with PASS / WARN / FAIL status.
    """

    # ──────────────────────────────────────────────────────────────────────────
    # Checkpoint 1: Extraction Integrity
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def validate_extraction(inspection_data: Dict, thermal_data: Dict) -> Dict[str, Any]:
        """
        Validates that both extracted data blobs have minimum required content.
        """
        issues = []
        warnings = []

        # --- Inspection checks ---
        if not inspection_data.get("areas"):
            issues.append("No inspection areas found — PDF may have a non-standard layout.")

        if not inspection_data.get("observations"):
            warnings.append("No observations extracted from inspection PDF.")

        if not inspection_data.get("images"):
            warnings.append("No images extracted from inspection PDF.")

        # Duplicate area names
        area_names = [a["name"] for a in inspection_data.get("areas", [])]
        if len(area_names) != len(set(area_names)):
            warnings.append("Duplicate area names detected in inspection data.")

        # --- Thermal checks ---
        if not thermal_data.get("readings"):
            warnings.append("No thermal readings found — thermal PDF may be image-only.")

        if not thermal_data.get("images"):
            issues.append("No images found in thermal PDF.")

        status = "FAIL" if issues else ("WARN" if warnings else "PASS")

        report = {
            "checkpoint": "extraction",
            "status": status,
            "issues": issues,
            "warnings": warnings,
            "summary": {
                "inspection_areas": len(inspection_data.get("areas", [])),
                "inspection_obs": len(inspection_data.get("observations", [])),
                "inspection_images": len(inspection_data.get("images", {})),
                "thermal_readings": len(thermal_data.get("readings", [])),
                "thermal_images": len(thermal_data.get("images", {})),
            },
        }
        logger.info(f"[Checkpoint 1 - Extraction] Status: {status} | "
                    f"Issues: {len(issues)}, Warnings: {len(warnings)}")
        return report

    # ──────────────────────────────────────────────────────────────────────────
    # Checkpoint 2: Linking Integrity
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def validate_links(links_data: Dict, inspection_data: Dict) -> Dict[str, Any]:
        """
        Validates that thermal-to-area linking is reasonable.
        """
        issues = []
        warnings = []

        links = links_data.get("links", [])
        unmatched = links_data.get("unmatched_thermals", [])
        conflicts = links_data.get("conflicts", [])
        stats = links_data.get("statistics", {})

        if not links:
            issues.append("No thermal-to-area links created. DDR will lack thermal context.")

        unmatched_pct = (
            stats.get("unmatched", 0) / max(stats.get("total_readings", 1), 1) * 100
        )
        if unmatched_pct > 50:
            warnings.append(
                f"{unmatched_pct:.0f}% of thermal readings could not be linked to areas. "
                "Consider improving location labels in the thermal PDF."
            )

        if conflicts:
            warnings.append(
                f"{len(conflicts)} conflict(s) detected between inspection and thermal findings."
            )

        low_conf_links = [l for l in links if l["confidence"] < 0.6]
        if low_conf_links:
            warnings.append(
                f"{len(low_conf_links)} link(s) have confidence < 0.6 (positional guesses). "
                "Review these in the DDR."
            )

        # Areas with no thermal link
        all_area_ids = {a["area_id"] for a in inspection_data.get("areas", [])}
        linked_area_ids = {l["area_id"] for l in links}
        unlinked_areas = all_area_ids - linked_area_ids
        if unlinked_areas:
            warnings.append(
                f"{len(unlinked_areas)} area(s) have no thermal reading linked."
            )

        status = "FAIL" if issues else ("WARN" if warnings else "PASS")
        report = {
            "checkpoint": "linking",
            "status": status,
            "issues": issues,
            "warnings": warnings,
            "unmatched_thermals": unmatched,
            "conflicts": conflicts,
            "low_confidence_links": low_conf_links,
            "unlinked_area_ids": list(unlinked_areas),
            "statistics": stats,
        }
        logger.info(f"[Checkpoint 2 - Linking] Status: {status} | "
                    f"Matched: {stats.get('matched',0)}, Unmatched: {stats.get('unmatched',0)}")
        return report

    # ──────────────────────────────────────────────────────────────────────────
    # Checkpoint 3: DDR Content Integrity
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def validate_ddr_sections(ddr_sections: Dict) -> Dict[str, Any]:
        """
        Validates that all 7 DDR sections are present and non-empty.
        """
        from src.utils.config import DDR_SECTIONS

        issues = []
        warnings = []

        for section_key in DDR_SECTIONS:
            if section_key not in ddr_sections:
                issues.append(f"Missing DDR section: {section_key}")
            else:
                section = ddr_sections[section_key]
                content = (
                    section.get("content") or
                    section.get("areas") or
                    section.get("actions") or
                    section.get("items") or
                    section.get("paragraphs") or
                    section.get("source_groups") or
                    section.get("overall_rating") or
                    section.get("treatment_categories") or
                    section.get("tools_used") or
                    section.get("negative_side")
                )
                if not content:
                    warnings.append(f"DDR section '{section_key}' appears empty.")

        status = "FAIL" if issues else ("WARN" if warnings else "PASS")
        report = {
            "checkpoint": "ddr_content",
            "status": status,
            "issues": issues,
            "warnings": warnings,
            "sections_present": [s for s in DDR_SECTIONS if s in ddr_sections],
            "sections_missing": issues,
        }
        logger.info(f"[Checkpoint 3 - DDR Content] Status: {status} | "
                    f"Sections: {len(ddr_sections)}/7")
        return report
