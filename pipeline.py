"""
pipeline.py - Main orchestrator for the DDR generation pipeline.
Runs all 5 stages in sequence, with validation checkpoints between each.
"""

import logging
from typing import Dict, Any, Callable, Optional

from src.stage1_extract.inspection_extractor import InspectionExtractor
from src.stage1_extract.thermal_extractor import ThermalExtractor
from src.stage1_extract.linker import ThermalAreaLinker
from src.stage2_vision.image_analyzer import ImageAnalyzer
from src.stage3_validate.validator import PipelineValidator
from src.stage4_generate.ddr_generator import DDRGenerator
from src.stage4_generate.chart_generator import generate_severity_chart
from src.stage5_assemble.docx_builder import DocxBuilder
from src.utils.helpers import setup_logger, now_iso

logger = setup_logger("pipeline")


class DDRPipeline:
    """
    Orchestrates the full 5-stage DDR generation pipeline.

    Usage:
        pipeline = DDRPipeline(
            inspection_pdf_path="Sample Report.pdf",
            thermal_pdf_path="Thermal Images.pdf",
            progress_callback=my_callback,   # optional
        )
        result = pipeline.run()
        # result["docx_bytes"] → bytes of the generated DDR Word document
        # result["audit"]      → audit trail dict
        # result["status"]     → "success" | "partial" | "failed"
        # result["errors"]     → list of errors
    """

    STAGE_NAMES = [
        "Extracting inspection report",          # 1a
        "Extracting thermal images",             # 1b
        "Linking thermal → areas",               # 1c
        "Analyzing images (Vision AI)",          # 2
        "Validating data integrity",             # 3
        "Generating DDR sections (AI)",          # 4
        "Assembling Word document",              # 5
    ]

    def __init__(
        self,
        inspection_pdf_path: str,
        thermal_pdf_path: str,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        skip_vision: bool = False,
    ):
        self.inspection_pdf = inspection_pdf_path
        self.thermal_pdf    = thermal_pdf_path
        self.progress_cb    = progress_callback
        self.skip_vision    = skip_vision  # set True to skip API calls (for testing)

        self._errors = []
        self._warnings = []
        self._stage_pct = [0, 15, 25, 35, 60, 65, 85, 100]

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """Run the complete pipeline. Returns result dict."""

        self._emit(0, "Starting DDR pipeline...")
        audit = {
            "started_at": now_iso(),
            "inspection_pdf": self.inspection_pdf,
            "thermal_pdf": self.thermal_pdf,
        }

        # ── Stage 1a: Inspection Extraction ──────────────────────────────────
        self._emit(1, "Stage 1a: Extracting inspection report...")
        try:
            inspector = InspectionExtractor(self.inspection_pdf)
            inspection_data = inspector.extract_all()
        except Exception as e:
            return self._fatal(f"Stage 1a failed: {e}")

        # ── Stage 1b: Thermal Extraction ──────────────────────────────────────
        self._emit(2, "Stage 1b: Extracting thermal data...")
        try:
            thermal_extractor = ThermalExtractor(self.thermal_pdf)
            thermal_data = thermal_extractor.extract_all()
        except Exception as e:
            return self._fatal(f"Stage 1b failed: {e}")

        # ── Validation Checkpoint 1 ──────────────────────────────────────────
        val1 = PipelineValidator.validate_extraction(inspection_data, thermal_data)
        self._handle_validation(val1)
        if val1["status"] == "FAIL":
            return self._fatal("Extraction validation failed: " + "; ".join(val1["issues"]))
        audit["validation_extraction"] = val1

        # ── Stage 1c: Linking ────────────────────────────────────────────────
        self._emit(3, "Stage 1c: Linking thermal readings to inspection areas...")
        try:
            linker = ThermalAreaLinker(inspection_data, thermal_data)
            links_data = linker.link_all()
        except Exception as e:
            return self._fatal(f"Stage 1c failed: {e}")

        # ── Validation Checkpoint 2 ──────────────────────────────────────────
        val2 = PipelineValidator.validate_links(links_data, inspection_data)
        self._handle_validation(val2)
        audit["validation_linking"] = val2

        # ── Stage 2: Vision Analysis ─────────────────────────────────────────
        image_insights: Dict[str, Any] = {}
        if not self.skip_vision:
            self._emit(4, "Stage 2: Analyzing images with GPT-4o mini Vision...")
            try:
                analyzer = ImageAnalyzer()
                image_insights = analyzer.analyze_images(
                    thermal_images    = thermal_data.get("images", {}),
                    inspection_images = inspection_data.get("images", {}),
                    progress_callback = lambda cur, tot, key:
                        self._emit(4, f"  Image {cur}/{tot}: {key}"),
                )
            except Exception as e:
                self._warn(f"Stage 2 (Vision) failed: {e}. Continuing without image insights.")
        else:
            logger.info("Skipping vision analysis (skip_vision=True)")

        # ── Stage 4: DDR Generation ──────────────────────────────────────────
        self._emit(5, "Stage 4: Generating DDR sections...")
        try:
            generator = DDRGenerator()
            ddr_sections = generator.generate_all_sections(
                structured_context = {
                    "inspection": inspection_data,
                    "thermal": thermal_data,
                    "links": links_data,
                },
                image_insights   = image_insights,
                validation_report = val2,
                progress_callback = lambda cur, tot, key:
                    self._emit(5, f"  Section {cur}/{tot}: {key}"),
            )
        except Exception as e:
            return self._fatal(f"Stage 4 (DDR Generation) failed: {e}")

        # ── Validation Checkpoint 3 ──────────────────────────────────────────
        val3 = PipelineValidator.validate_ddr_sections(ddr_sections)
        self._handle_validation(val3)
        audit["validation_ddr"] = val3

        # ── Stage 5: Document Assembly ───────────────────────────────────────
        self._emit(6, "Stage 5: Assembling Word document...")
        try:
            # Generate severity chart
            chart_path = "severity_chart.png"
            generate_severity_chart(inspection_data.get("checklist_items", {}), chart_path)

            # Build audit data for appendix
            audit_for_doc = {
                "severity_chart_path": chart_path,
                "extraction_meta": {
                    **inspection_data.get("extraction_meta", {}),
                    **thermal_data.get("extraction_meta", {}),
                    "images_analyzed": len(image_insights),
                    "links_matched": links_data["statistics"]["matched"],
                    "unmatched_thermals": links_data["statistics"]["unmatched"],
                    "conflicts": len(links_data.get("conflicts", [])),
                },
                "validation_warnings": (
                    val1.get("warnings", []) +
                    val2.get("warnings", []) +
                    val3.get("warnings", [])
                ),
            }

            builder = DocxBuilder()
            docx_bytes = builder.build(
                ddr_sections      = ddr_sections,
                thermal_images    = thermal_data.get("images", {}),
                inspection_images = inspection_data.get("images", {}),
                image_insights    = image_insights,
                links_data        = links_data,
                inspection_data   = inspection_data,
                audit_data        = audit_for_doc,
            )
        except Exception as e:
            return self._fatal(f"Stage 5 (Assembly) failed: {e}")

        self._emit(7, "[SUCCESS] DDR pipeline complete!")
        audit["completed_at"] = now_iso()
        audit["status"] = "success"

        return {
            "status": "success" if not self._errors else "partial",
            "docx_bytes": docx_bytes,
            "ddr_sections": ddr_sections,
            "inspection_data": inspection_data,
            "thermal_data": thermal_data,
            "links_data": links_data,
            "image_insights": image_insights,
            "audit": audit,
            "errors": self._errors,
            "warnings": self._warnings,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _emit(self, stage_idx: int, message: str):
        pct = self._stage_pct[stage_idx] if stage_idx < len(self._stage_pct) else 100
        logger.info(f"[{pct}%] {message}")
        if self.progress_cb:
            self.progress_cb(message, pct, stage_idx)

    def _warn(self, msg: str):
        self._warnings.append(msg)
        logger.warning(msg)

    def _handle_validation(self, val: Dict):
        for w in val.get("warnings", []):
            self._warn(w)
        for err in val.get("issues", []):
            self._errors.append(err)

    def _fatal(self, msg: str) -> Dict[str, Any]:
        logger.error(f"FATAL: {msg}")
        self._errors.append(msg)
        return {
            "status": "failed",
            "docx_bytes": None,
            "errors": self._errors,
            "warnings": self._warnings,
            "audit": {"error": msg, "timestamp": now_iso()},
        }


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="DDR Report Generator")
    parser.add_argument("--inspection", required=True, help="Path to inspection PDF")
    parser.add_argument("--thermal",    required=True, help="Path to thermal PDF")
    parser.add_argument("--output",     default="DDR_Report.docx", help="Output .docx path")
    parser.add_argument("--skip-vision", action="store_true", help="Skip Vision API calls")
    args = parser.parse_args()

    def cli_progress(message, pct, stage):
        print(f"  [{pct:3d}%] {message}")

    pipeline = DDRPipeline(
        inspection_pdf_path = args.inspection,
        thermal_pdf_path    = args.thermal,
        progress_callback   = cli_progress,
        skip_vision         = args.skip_vision,
    )

    result = pipeline.run()

    if result["status"] in ("success", "partial"):
        with open(args.output, "wb") as f:
            f.write(result["docx_bytes"])
        print(f"\n[SUCCESS] DDR saved to: {args.output}")
        if result["warnings"]:
            print(f"[WARNING] {len(result['warnings'])} warning(s):")
            for w in result["warnings"]:
                print(f"   - {w}")
    else:
        print(f"\n[ERROR] Pipeline failed:")
        for err in result["errors"]:
            print(f"   - {err}")
        sys.exit(1)
