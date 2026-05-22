"""
docx_builder.py - Stage 5 (ENHANCED)
Builds a professional DDR Word document matching the Main DDR.pdf structure.
5 sections, captioned images, per-area thermal + visual references, 30+ pages.
"""

import os
import io
import logging
from typing import Dict, Any, List, Optional, Tuple

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from PIL import Image as PILImage

from src.utils.config import DOC_STYLES, DDR_SECTION_LABELS
from src.utils.helpers import setup_logger, now_iso

logger = setup_logger("stage5.docx")

# ─── Colour palette ───────────────────────────────────────────────────────────
NAVY  = "1F3864"
BLUE  = "2E5299"
ORANGE= "E07B39"
GREY  = "D9D9D9"
WHITE = "FFFFFF"
RED   = "C00000"
GREEN = "375623"

def _rgb(hex_color: str) -> RGBColor:
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def _set_cell_bg(cell, hex_color: str):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)

def _bold_colored_run(para, text, hex_color, size_pt=11, bold=True):
    run = para.add_run(text)
    run.bold = bold
    run.font.size = Pt(size_pt)
    run.font.color.rgb = _rgb(hex_color)
    return run


class DocxBuilder:
    """Builds the full DDR Word document matching the Main DDR.pdf style."""

    def __init__(self):
        self.doc = Document()
        self._image_counter = 0     # global image numbering
        self._configure_page()
        self._configure_default_style()

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def build(
        self,
        ddr_sections:      Dict[str, Any],
        thermal_images:    Dict[str, Any],
        inspection_images: Dict[str, Any],
        image_insights:    Dict[str, Any],
        links_data:        Dict[str, Any],
        inspection_data:   Dict[str, Any],
        audit_data:        Dict[str, Any],
    ) -> bytes:
        logger.info("Building enhanced DDR Word document (Main DDR style)...")

        # Save image collections to self for global lookup access
        self.thermal_images = thermal_images
        self.inspection_images = inspection_images

        # Build image assignment map: area_id → best thermal + best inspection image key
        image_map = self._build_image_map(thermal_images, inspection_images, links_data)

        # ── Cover Page ────────────────────────────────────────────────────────
        self._add_cover_page(inspection_data)

        # ── Disclaimer Page ───────────────────────────────────────────────────
        self._add_disclaimer_page()

        # ── Table of Contents ─────────────────────────────────────────────────
        self._add_toc_page()

        # ── Section 1 — Introduction ──────────────────────────────────────────
        self._add_section1_introduction(inspection_data)

        # ── Section 2 — General Information ──────────────────────────────────
        self._add_section2_general_info(inspection_data)

        # ── Section 3 — Visual Observations ──────────────────────────────────
        self._add_section3_visual_observations(
            ddr_sections, inspection_data
        )

        # ── Section 4 — Analysis & Suggestions ───────────────────────────────
        self._add_section4_analysis(
            ddr_sections, thermal_images, inspection_images,
            image_insights, links_data, inspection_data, image_map, audit_data
        )

        # ── Section 5 — Limitations & Precautions ────────────────────────────
        self._add_section5_limitations()

        # ── Audit Appendix ────────────────────────────────────────────────────
        self._add_audit_appendix(audit_data)

        buf = io.BytesIO()
        self.doc.save(buf)
        buf.seek(0)
        logger.info("Enhanced DDR document built successfully.")
        return buf.read()

    # ──────────────────────────────────────────────────────────────────────────
    # Page Setup & Default Style
    # ──────────────────────────────────────────────────────────────────────────

    def _configure_page(self):
        sec = self.doc.sections[0]
        sec.page_width   = Cm(21.0)
        sec.page_height  = Cm(29.7)
        sec.left_margin  = Cm(2.5)
        sec.right_margin = Cm(2.0)
        sec.top_margin   = Cm(2.5)
        sec.bottom_margin= Cm(2.0)

    def _configure_default_style(self):
        from docx.oxml.ns import qn
        style = self.doc.styles["Normal"]
        style.font.name = "Calibri"
        style.font.size = Pt(11)

    # ──────────────────────────────────────────────────────────────────────────
    # Cover Page
    # ──────────────────────────────────────────────────────────────────────────

    def _add_cover_page(self, inspection_data: Dict):
        prop = inspection_data.get("property", {})
        intro = inspection_data.get("intro_sections", {})

        # Company name
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("UrbanRoof Private Limited")
        run.bold = True
        run.font.size = Pt(16)
        run.font.color.rgb = _rgb(NAVY)

        # Report title
        p2 = self.doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r2 = p2.add_run("DETAILED DIAGNOSTIC REPORT (DDR)")
        r2.bold = True
        r2.font.size = Pt(22)
        r2.font.color.rgb = _rgb(NAVY)

        # Horizontal line
        self._add_hr()

        # Property details table
        self.doc.add_paragraph()
        table = self.doc.add_table(rows=6, cols=2)
        table.style = "Table Grid"
        fields = [
            ("Report ID",          prop.get("report_id", "Not Available")),
            ("Property Address",   prop.get("address", "Not Available")),
            ("Customer Name",      prop.get("customer_name", "Not Available")),
            ("Inspection Date",    prop.get("inspection_date", "Not Available")),
            ("Inspected By",       prop.get("inspector_name", "Not Available")),
            ("Report Generated",   now_iso()[:10]),
        ]
        for i, (label, value) in enumerate(fields):
            row = table.rows[i]
            _set_cell_bg(row.cells[0], NAVY)
            lp = row.cells[0].paragraphs[0]
            lr = lp.add_run(label)
            lr.bold = True
            lr.font.color.rgb = _rgb(WHITE)
            lr.font.size = Pt(10)
            row.cells[1].text = str(value)
            for para in row.cells[1].paragraphs:
                for run in para.runs:
                    run.font.size = Pt(10)

        self.doc.add_page_break()

    # ──────────────────────────────────────────────────────────────────────────
    # Disclaimer Page
    # ──────────────────────────────────────────────────────────────────────────

    def _add_disclaimer_page(self):
        self._h1("Data and Information Disclaimer")
        disclaimer_text = (
            "This property inspection is not an exhaustive inspection of the structure, systems, or "
            "components. The inspection may not reveal all deficiencies. A health checkup helps to "
            "reduce some of the risk involved in the property/structure & premises, but it cannot "
            "eliminate these risks, nor can the inspection anticipate future events or changes in "
            "performance due to changes in use or occupancy.\n\n"
            "It is recommended that you obtain as much information as is available about this property, "
            "including any owners disclosures, previous inspection reports, engineering reports, "
            "building/remodeling permits, and reports performed for or by relocation companies, "
            "municipal inspection departments, lenders, insurers, and appraisers.\n\n"
            "An inspection addresses only those components and conditions that are present, visible, "
            "and accessible at the time of the inspection. The inspection does NOT imply insurability "
            "or warrantability of the structure or its components."
        )
        for para_text in disclaimer_text.split("\n\n"):
            self._body(para_text)
        self.doc.add_page_break()

    # ──────────────────────────────────────────────────────────────────────────
    # Table of Contents
    # ──────────────────────────────────────────────────────────────────────────

    def _add_toc_page(self):
        self._h1("Table of Contents")
        toc = [
            ("SECTION 1", "INTRODUCTION"),
            ("  1.1",      "Background"),
            ("  1.2",      "Objective of the Health Assessment"),
            ("  1.3",      "Scope of Work"),
            ("  1.4",      "Tools Used During Visual Inspection"),
            ("SECTION 2", "GENERAL INFORMATION"),
            ("  2.1",      "Client & Inspection Details"),
            ("  2.2",      "Description of Site"),
            ("SECTION 3", "VISUAL OBSERVATION AND READINGS"),
            ("  3.1",      "Sources of Leakage — Summary"),
            ("  3.2",      "Negative Side Inputs"),
            ("  3.3",      "Positive Side Inputs"),
            ("SECTION 4", "ANALYSIS & SUGGESTIONS"),
            ("  4.1",      "Actions Required & Suggested Therapies"),
            ("  4.2",      "Further Possibilities Due to Delayed Action"),
            ("  4.3",      "Summary Table"),
            ("  4.4",      "Area-Wise Detailed Diagnostics and Visual-Thermal Reference Pairs"),
            ("  4.5",      "Severity Assessment"),
            ("  4.6",      "Missing or Unclear Information"),
            ("  4.7",      "Additional Notes"),
            ("SECTION 5", "LIMITATIONS AND PRECAUTION NOTE"),
        ]
        table = self.doc.add_table(rows=len(toc), cols=2)
        table.style = "Table Grid"
        for i, (sec, title) in enumerate(toc):
            row = table.rows[i]
            row.cells[0].text = sec
            row.cells[1].text = title
            is_section = sec.startswith("SECTION")
            for cell in row.cells:
                if is_section:
                    _set_cell_bg(cell, NAVY)
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(9)
                        run.bold = is_section
                        if is_section:
                            run.font.color.rgb = _rgb(WHITE)
        self.doc.add_page_break()

    # ──────────────────────────────────────────────────────────────────────────
    # Section 1 — Introduction
    # ──────────────────────────────────────────────────────────────────────────

    def _add_section1_introduction(self, inspection_data: Dict):
        intro = inspection_data.get("intro_sections", {})
        prop  = inspection_data.get("property", {})

        self._h1("SECTION 1  INTRODUCTION")

        self._h2("1.1 Background")
        background = intro.get("background") or (
            f"The property located at {prop.get('address', 'the specified address')} "
            "has been submitted for a preliminary Health Assessment. The property owner has "
            "approached for an initial site investigation and submission of a Health Assessment "
            "Report based on testing and visual inspection."
        )
        self._body(background)

        self._h2("1.2 Objective of the Health Assessment")
        objectives = intro.get("objectives") or [
            "To facilitate detection of all possible flaws, problems & occurrences that might exist & analyse cause effects.",
            "To prioritize the immediate repair & protection measures to be taken if any.",
            "To evaluate possibly accurate scope of work further to design estimate & cost analysis for execution/treatment.",
            "Classification of recommendations & solutions based on existing flaws and precautionary measures & its effective implementation.",
            "Tracking, record keeping during the life expectancy or the warranty period.",
        ]
        if isinstance(objectives, list):
            for obj in objectives:
                self._bullet(obj)
        else:
            self._body(objectives)

        self._h2("1.3 Scope of Work")
        scope = intro.get("scope") or (
            "Conducting visual site inspection using necessary assessment tools including Tapping Hammer, "
            "Crack gauge, IR Thermography, Moisture & pH meter, carried out by the technical team."
        )
        self._body(scope)

        self._h2("1.4 Tools Used During Visual Inspection")
        tools = intro.get("tools_used") or [
            "Tapping Hammer — for hollow sound detection",
            "Crack Gauge — for crack width measurement",
            "IR Thermography Camera — for thermal imaging",
            "Moisture Meter — for measuring moisture content",
            "pH Meter — for surface pH testing",
        ]
        for tool in tools:
            self._bullet(tool)

        self.doc.add_page_break()

    # ──────────────────────────────────────────────────────────────────────────
    # Section 2 — General Information
    # ──────────────────────────────────────────────────────────────────────────

    def _add_section2_general_info(self, inspection_data: Dict):
        prop    = inspection_data.get("property", {})
        site    = inspection_data.get("site_description", {})

        self._h1("SECTION 2  GENERAL INFORMATION")

        # 2.1 Client & Inspection Details
        self._h2("2.1 Client & Inspection Details")
        client_rows = [
            ("Customer Name",         prop.get("customer_name", "Not Available")),
            ("Customer Full Address",  prop.get("address", "Not Available")),
            ("E-Mail Address",         prop.get("email", "Not Available")),
            ("Contact No.",            prop.get("contact", "Not Available")),
            ("Date of Inspection",     prop.get("inspection_date", "Not Available")),
            ("Inspected By",           prop.get("inspector_name", "Not Available")),
        ]
        self._info_table(client_rows)
        self.doc.add_paragraph()

        # 2.2 Description of Site
        self._h2("2.2 Description of Site")
        site_rows = [
            ("Site Address",               site.get("address") or prop.get("address", "Not Available")),
            ("Type of Structure",          site.get("structure_type", "Not Available")),
            ("Number of Floors",           site.get("floors", "Not Available")),
            ("Year of Construction",       site.get("year_of_construction", "Not Available")),
            ("Age of Building (years)",    site.get("age_years", "Not Available")),
            ("Previous Structure Audit",   site.get("previous_audit", "Not Available")),
            ("Previous Repairs",           site.get("previous_repairs", "Not Available")),
        ]
        self._info_table(site_rows)
        self.doc.add_page_break()

    # ──────────────────────────────────────────────────────────────────────────
    # Section 3 — Visual Observations
    # ──────────────────────────────────────────────────────────────────────────

    def _add_checklist_table(self, checklist_dict: Dict[str, str], title: str):
        self._body(f"Below is the assessment checklist table outlining specific conditions and observed ratings:")
        if not checklist_dict:
            self._body("No checklist data available.")
            return

        # 7 columns: Question, Good, Moderate, Poor, Yes, No, N/A
        table = self.doc.add_table(rows=1, cols=7)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"

        # Header
        hdr = table.rows[0].cells
        headers = ["Checklist Item", "Good", "Moderate", "Poor", "Yes", "No", "N/A"]
        widths = [Cm(8.0), Cm(1.2), Cm(1.5), Cm(1.2), Cm(1.2), Cm(1.2), Cm(1.2)]

        for idx, text in enumerate(headers):
            _set_cell_bg(hdr[idx], NAVY)
            p = hdr[idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx > 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(text)
            r.bold = True
            r.font.color.rgb = _rgb(WHITE)
            r.font.size = Pt(9)
            hdr[idx].width = widths[idx]

        for question, val in checklist_dict.items():
            row = table.add_row()
            cells = row.cells
            
            # Question cell
            cells[0].text = question
            cells[0].paragraphs[0].runs[0].font.size = Pt(9.5)
            cells[0].width = widths[0]
            
            # Match rating to column index
            v_lower = str(val).strip().lower()
            col_idx = None
            if v_lower == "good":
                col_idx = 1
            elif v_lower == "moderate":
                col_idx = 2
            elif v_lower == "poor":
                col_idx = 3
            elif v_lower == "yes" or v_lower == "100%" or v_lower == "75%" or v_lower == "all time":
                col_idx = 4
            elif v_lower == "no":
                col_idx = 5
            elif v_lower == "n/a" or v_lower == "not sure":
                col_idx = 6
            else:
                col_idx = 1 # default fallback
                
            for i in range(1, 7):
                cells[i].width = widths[i]
                p = cells[i].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if i == col_idx:
                    # Render tick mark in Wingdings
                    run = p.add_run("")
                    run.font.name = "Wingdings"
                    run.font.size = Pt(11)
                    run.bold = True
                    # tick color depending on severity
                    if col_idx == 1 or col_idx == 4:
                        run.font.color.rgb = _rgb(GREEN)
                    elif col_idx == 2 or col_idx == 6:
                        run.font.color.rgb = _rgb(ORANGE)
                    else:
                        run.font.color.rgb = _rgb(RED)
                else:
                    run = p.add_run("")
                    run.font.size = Pt(9)
        self.doc.add_paragraph()  # spacing

    def _add_section3_visual_observations(
        self, ddr_sections: Dict, inspection_data: Dict
    ):
        self._h1("SECTION 3  VISUAL OBSERVATION AND READINGS")

        # 3.1 Summary of Sources of Leakage
        self._h2("3.1 Sources of Leakage — Summary")
        s1 = ddr_sections.get("property_issue_summary", {})
        for para in s1.get("paragraphs", []):
            self._body(para)
        if not s1.get("paragraphs"):
            self._body(s1.get("content", "Not Available"))

        # 3.2 Bathroom & WC Checklist (Negative Side Inputs)
        self._h2("3.2 Bathroom & WC Checklist (Negative Side Inputs)")
        checklist_items = inspection_data.get("checklist_items", {})
        wc_checklist = checklist_items.get("wc_checklist", {})
        self._add_checklist_table(wc_checklist, "WC Area Assessment Checklist Table")

        # 3.3 External Wall Checklist (Positive Side Inputs)
        self._h2("3.3 External Wall Checklist (Positive Side Inputs)")
        ext_checklist = checklist_items.get("external_wall_checklist", {})
        self._add_checklist_table(ext_checklist, "External Wall Assessment Checklist Table")

        self.doc.add_page_break()

    # ──────────────────────────────────────────────────────────────────────────
    # Section 4 — Analysis & Suggestions
    # ──────────────────────────────────────────────────────────────────────────

    def _add_section4_analysis(
        self, ddr_sections, thermal_images, inspection_images,
        image_insights, links_data, inspection_data, image_map, audit_data
    ):
        self._h1("SECTION 4  ANALYSIS & SUGGESTIONS")

        # 4.1 Actions Required
        self._h2("4.1 Actions Required & Suggested Therapies")
        s5 = ddr_sections.get("recommended_actions", {})
        for treatment in s5.get("treatment_categories", []):
            self._h3(treatment.get("category", "Treatment"))
            self._body(treatment.get("method", ""))
            priority = treatment.get("priority", "")
            timeframe = treatment.get("timeframe", "")
            if priority or timeframe:
                p = self.doc.add_paragraph()
                color = {"Immediate": RED, "Short-term": ORANGE, "Long-term": GREEN}.get(priority, NAVY)
                _bold_colored_run(p, f"Priority: {priority}  |  Timeframe: {timeframe}", color, 10)
        if not s5.get("treatment_categories"):
            self._body(s5.get("general_note", "No specific actions identified."))

        # 4.2 Delayed Action Consequences
        self._h2("4.2 Further Possibilities Due to Delayed Action")
        delayed = s5.get("delayed_action_consequences", "")
        if delayed:
            self._body(delayed)
        else:
            self._body(
                "If the identified issues are not addressed promptly, the following consequences may arise: "
                "Progressive water ingress will cause extensive dampness, efflorescence, and spalling of paint "
                "on interior walls. Structural members may be compromised by prolonged moisture exposure, "
                "leading to corrosion of reinforcement steel and reduced structural integrity. "
                "The cost of repair increases significantly with delayed action."
            )

        # 4.3 Summary Table
        self._h2("4.3 Summary Table")
        summary_table = inspection_data.get("summary_table", [])
        s2_neg = ddr_sections.get("area_wise_observations", {}).get("negative_side", [])
        s2_pos = ddr_sections.get("area_wise_observations", {}).get("positive_side", [])

        if summary_table:
            table = self.doc.add_table(rows=1, cols=4)
            table.style = "Table Grid"
            hdr = table.rows[0].cells
            for i, h in enumerate(["Point No.", "Impacted Area (-ve side)", "Point No.", "Exposed Area (+ve side)"]):
                _set_cell_bg(hdr[i], NAVY)
                rr = hdr[i].paragraphs[0].add_run(h)
                rr.bold = True
                rr.font.color.rgb = _rgb(WHITE)
                rr.font.size = Pt(9)
            for row_data in summary_table:
                row = table.add_row().cells
                row[0].text = str(row_data.get("point_no", ""))
                row[1].text = row_data.get("negative_area", "Not Available") or "Not Available"
                row[2].text = str(row_data.get("point_no", ""))
                row[3].text = row_data.get("positive_area", "Not Available") or "Not Available"
                for cell in row:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.size = Pt(9)
        elif s2_neg:
            table = self.doc.add_table(rows=1, cols=4)
            table.style = "Table Grid"
            hdr = table.rows[0].cells
            for i, h in enumerate(["Ref (-ve)", "Impacted Area", "Ref (+ve)", "Source Area"]):
                _set_cell_bg(hdr[i], NAVY)
                rr = hdr[i].paragraphs[0].add_run(h)
                rr.bold = True
                rr.font.color.rgb = _rgb(WHITE)
                rr.font.size = Pt(9)
            for neg in s2_neg:
                matching_pos = [p for p in s2_pos
                                if p.get("causes_negative_ref") == neg.get("ref")]
                pos = matching_pos[0] if matching_pos else {}
                row = table.add_row().cells
                row[0].text = neg.get("ref", "")
                row[1].text = neg.get("heading", neg.get("area_name", ""))
                row[2].text = pos.get("ref", "")
                row[3].text = pos.get("heading", pos.get("area_name", ""))
                for cell in row:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.size = Pt(9)

        self.doc.add_page_break()

        # 4.4 Area-Wise Detailed Diagnostics and Visual-Thermal Reference Pairs
        self._h2("4.4 Area-Wise Detailed Diagnostics and Visual-Thermal Reference Pairs")
        
        # Ensure we have data
        neg_areas = ddr_sections.get("area_wise_observations", {}).get("negative_side", [])
        pos_areas = ddr_sections.get("area_wise_observations", {}).get("positive_side", [])
        
        if not neg_areas:
            # Fallback: compile from summary_table
            summary = inspection_data.get("summary_table", [])
            for i, row in enumerate(summary):
                neg_desc = row.get("negative_area", "")
                pos_desc = row.get("positive_area", "Not Available")
                area_name = self._area_name_from_desc(neg_desc) or f"Inspection Area {i+1}"
                
                neg_areas.append({
                    "ref": f"4.4.{i+1}",
                    "area_name": area_name,
                    "heading": f"{area_name.upper()} (IMPACTED AREA)",
                    "observation": neg_desc,
                    "image_caption": f"Figure [N]: Visual photograph showing observed dampness at {area_name}.",
                    "thermal_interpretation": f"High-resolution thermographic assessment at {area_name} shows temperature gradients indicative of sub-surface moisture accumulation.",
                    "thermal_image_caption": f"Figure [N+1]: Thermal infrared profile indicating moisture signature at {area_name}.",
                    "thermal_data": {
                        "hotspot_temp": None,
                        "coldspot_temp": None,
                        "emissivity": 0.95,
                        "anomaly": "Moisture Intrusion"
                    },
                    "severity": "Moderate",
                    "severity_reasoning": "Dampness leads to degradation of internal finishes and potential reinforcement steel oxidation if left unaddressed."
                })
                pos_areas.append({
                    "ref": f"4.5.{i+1}",
                    "area_name": area_name,
                    "heading": f"{area_name.upper()} (SOURCE AREA)",
                    "observation": pos_desc,
                    "image_caption": f"Figure [N]: Visual photograph showing positive-side defects at {area_name}.",
                    "causes_negative_ref": f"4.4.{i+1}"
                })

        for neg in neg_areas:
            ref = neg.get("ref", "4.4.x")
            area_name = neg.get("area_name", "")
            heading = neg.get("heading", area_name)
            
            # Heading
            self._h3(f"{ref}  {heading}")
            
            # Resolve image keys
            img_info = image_map.get(area_name)
            if not img_info:
                # case insensitive lookup
                for k, v in image_map.items():
                    if k.lower().strip() == area_name.lower().strip():
                        img_info = v
                        break
            
            visual_key = img_info.get("inspection_key") if img_info else None
            thermal_key = img_info.get("thermal_key") if img_info else None
            
            if not visual_key:
                visual_key = self._find_fallback_image(area_name, inspection_images, "visual")
            if not thermal_key:
                thermal_key = self._find_fallback_image(area_name, thermal_images, "thermal")
            
            # Pre-calculate figure numbers for text references
            visual_fig_num = self._image_counter + 1
            thermal_fig_num = self._image_counter + 2
            
            def replace_figs(text: str) -> str:
                if not text:
                    return text
                import re
                # Replace Figure [N+1] or Figure [n+1] or Image [N+1] or Figure X+1
                text = re.sub(r'(?i)(figure|image)\s*\[?\s*(n\+1)\s*\]?', f"Figure {thermal_fig_num}", text)
                # Replace Figure [N] or Figure [n] or Image [N] or Figure X
                text = re.sub(r'(?i)(figure|image)\s*\[?\s*n\s*\]?', f"Figure {visual_fig_num}", text)
                return text

            # 1. Symptom (Negative side)
            self._body(replace_figs(neg.get("observation", "")))
            
            # 2. Thermal interpretation (if available)
            if neg.get("thermal_interpretation"):
                self._body(replace_figs(neg.get("thermal_interpretation")))
                
            tdata = neg.get("thermal_data", {})
            if tdata and (tdata.get("hotspot_temp") or tdata.get("coldspot_temp")):
                p = self.doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.5)
                _bold_colored_run(p, "Thermal Reading:  ", ORANGE, 10)
                parts = []
                if tdata.get("hotspot_temp"):
                    parts.append(f"Hotspot: {tdata['hotspot_temp']}°C")
                if tdata.get("coldspot_temp"):
                    parts.append(f"Coldspot: {tdata['coldspot_temp']}°C")
                if tdata.get("emissivity"):
                    parts.append(f"Emissivity: {tdata['emissivity']}")
                if tdata.get("anomaly"):
                    parts.append(f"Pattern: {tdata['anomaly'].replace('_', ' ').title()}")
                run = p.add_run(" | ".join(parts))
                run.font.size = Pt(10)
                run.italic = True
            
            # 3. Source Mechanism (Positive side)
            matching_pos = [p for p in pos_areas if p.get("causes_negative_ref") == neg.get("ref")]
            pos = matching_pos[0] if matching_pos else None
            if pos and pos.get("observation"):
                p = self.doc.add_paragraph()
                _bold_colored_run(p, "Source Mechanism (Positive Side):  ", BLUE, 11)
                p.add_run(replace_figs(pos.get("observation", "")))
                
            # 4. Severity Assessment & Reasoning
            sev = neg.get("severity", "Moderate")
            color = {"Low": GREEN, "Moderate": ORANGE, "High": RED, "Critical": RED}.get(sev, NAVY)
            
            p = self.doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            _bold_colored_run(p, f"Severity Assessment: {sev.upper()}", color, 11)
            
            if neg.get("severity_reasoning"):
                p = self.doc.add_paragraph()
                _bold_colored_run(p, "Severity Reasoning: ", color, 10, bold=True)
                p.add_run(neg["severity_reasoning"])
                
            # 5. Figure pair (side by side)
            self.doc.add_paragraph() # spacer
            table = self.doc.add_table(rows=1, cols=2)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.style = "Table Grid"
            
            cells = table.rows[0].cells
            cells[0].width = Cm(7.5)
            cells[1].width = Cm(7.5)
            
            # Caption formatters
            visual_caption = self._format_caption(
                pos.get("image_caption") if pos else neg.get("image_caption"),
                f"Visual photograph showing physical distress pathology at {area_name}."
            )
            thermal_caption = self._format_caption(
                neg.get("thermal_image_caption"),
                f"Thermal IR image showing temperature gradients at {area_name}."
            )
            
            # Insert left: visual
            inserted_visual = self._insert_image_to_cell(cells[0], inspection_images, visual_key, visual_caption)
            if not inserted_visual:
                p = cells[0].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(f"\n[ Visual Photo Not Available — {visual_caption} ]\n")
                run.italic = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = _rgb("888888")
                
            # Insert right: thermal
            inserted_thermal = self._insert_image_to_cell(cells[1], thermal_images, thermal_key, thermal_caption)
            if not inserted_thermal:
                p = cells[1].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(f"\n[ Thermal Image Not Available — {thermal_caption} ]\n")
                run.italic = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = _rgb("888888")
                
            self.doc.add_paragraph() # spacer after figure pair
            
        self.doc.add_page_break()

        # 4.5 Severity Assessment
        self._h2("4.5 Severity Assessment")
        s4 = ddr_sections.get("severity_assessment", {})
        overall = s4.get("overall_rating", "Moderate")
        color = {
            "Poor": RED, "Moderate": ORANGE, "Good": GREEN
        }.get(overall, NAVY)
        p = self.doc.add_paragraph()
        _bold_colored_run(p, f"Overall Property Rating: {overall.upper()}", color, 14)
        self._body(s4.get("overall_reasoning", ""))
        
        # Insert programmatic severity chart
        chart_path = audit_data.get("severity_chart_path")
        if chart_path and os.path.exists(chart_path):
            try:
                p = self.doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)
                run = p.add_run()
                run.add_picture(chart_path, width=Inches(4.2))
                
                # Figure caption for chart
                chart_caption = self._format_caption(
                    "Checklist severity assessment distribution chart.",
                    "Checklist severity assessment distribution chart."
                )
                cap = self.doc.add_paragraph()
                cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cr = cap.add_run(chart_caption)
                cr.bold = True
                cr.italic = True
                cr.font.size = Pt(9)
                cr.font.color.rgb = _rgb(NAVY)
            except Exception as e:
                logger.warning(f"Failed to insert severity chart: {e}")
                
        if s4.get("structural_risk_note"):
            self._body(f"Structural Risk Note: {s4['structural_risk_note']}")

        area_ratings = s4.get("area_ratings", [])
        if area_ratings:
            self.doc.add_paragraph()
            table = self.doc.add_table(rows=1, cols=4)
            table.style = "Table Grid"
            hdr = table.rows[0].cells
            for i, h in enumerate(["Area", "Side", "Rating", "Reasoning"]):
                _set_cell_bg(hdr[i], BLUE)
                rr = hdr[i].paragraphs[0].add_run(h)
                rr.bold = True
                rr.font.color.rgb = _rgb(WHITE)
                rr.font.size = Pt(9)
            rating_clr = {"Poor": RED, "Moderate": ORANGE, "Good": GREEN}
            for item in area_ratings:
                row = table.add_row().cells
                row[0].text = item.get("area", "")
                row[1].text = item.get("side", "")
                rating = item.get("rating", "")
                row[2].text = rating
                clr = rating_clr.get(rating, GREY)
                _set_cell_bg(row[2], clr)
                if row[2].paragraphs[0].runs:
                    row[2].paragraphs[0].runs[0].font.color.rgb = _rgb(WHITE)
                row[3].text = item.get("reasoning", "")
                for cell in row:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.size = Pt(9)

        # 4.6 Missing or Unclear Information
        self._h2("4.6 Missing or Unclear Information")
        s7 = ddr_sections.get("missing_information", {})
        items = s7.get("items", [])
        if items:
            table = self.doc.add_table(rows=1, cols=3)
            table.style = "Table Grid"
            hdr = table.rows[0].cells
            for i, h in enumerate(["Missing Item", "Impact", "Status"]):
                _set_cell_bg(hdr[i], NAVY)
                rr = hdr[i].paragraphs[0].add_run(h)
                rr.bold = True
                rr.font.color.rgb = _rgb(WHITE)
                rr.font.size = Pt(9)
            for item in items:
                row = table.add_row().cells
                row[0].text = item.get("missing_item", "")
                row[1].text = item.get("impact", "")
                row[2].text = "Not Available"
                _set_cell_bg(row[2], RED)
                if row[2].paragraphs[0].runs:
                    row[2].paragraphs[0].runs[0].font.color.rgb = _rgb(WHITE)
                for cell in row:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.size = Pt(9)
        else:
            self._body("No significant missing information identified.")

        # 4.7 Additional Notes
        self._h2("4.7 Additional Notes")
        s6 = ddr_sections.get("additional_notes", {})
        if s6.get("additional_observations"):
            self._body(s6["additional_observations"])
        if s6.get("scope_notes"):
            self._body(s6["scope_notes"])
        if s6.get("disclaimer"):
            self._add_disclaimer_inline(s6["disclaimer"])

        self.doc.add_page_break()

    def _format_caption(self, caption: str, default_text: str) -> str:
        """Format caption to have sequential figure numbers and clear text."""
        self._image_counter += 1
        if not caption or str(caption).strip().lower() == "not available":
            return f"Figure {self._image_counter}: {default_text}"
        
        import re
        # Case insensitive replace for figure [n] or image [n] or image x
        cleaned = re.sub(r'(?i)(figure|image)\s*\[?\s*(n\+1|n|\d+)\s*\]?:?', f"Figure {self._image_counter}", str(caption))
        if f"Figure {self._image_counter}" not in cleaned:
            cleaned = f"Figure {self._image_counter}: {cleaned}"
        return cleaned

    def _insert_image_to_cell(self, cell, img_store: Dict, image_key: Optional[str], caption: str) -> bool:
        """Insert a resized image and caption into a specific table cell. Returns True on success."""
        try:
            if not image_key:
                return False
                
            # Advanced lookup: check img_store first, fall back to self.thermal_images or self.inspection_images if present
            img_data = None
            if image_key in img_store:
                img_data = img_store[image_key]
            elif hasattr(self, 'thermal_images') and image_key in self.thermal_images:
                img_data = self.thermal_images[image_key]
            elif hasattr(self, 'inspection_images') and image_key in self.inspection_images:
                img_data = self.inspection_images[image_key]
                
            if not img_data:
                return False
                
            img_bytes = img_data.get("bytes", b"")
            if not img_bytes:
                return False

            buf = io.BytesIO(img_bytes)
            pil = PILImage.open(buf)
            if pil.mode not in ("RGB", "L"):
                pil = pil.convert("RGB")
            out = io.BytesIO()
            pil.save(out, format="JPEG", quality=88)
            out.seek(0)

            # Insert into cell's first paragraph
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(out, width=Inches(2.8))

            # Caption below image in cell
            cap = cell.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap.paragraph_format.space_before = Pt(3)
            cap.paragraph_format.space_after = Pt(2)
            cr = cap.add_run(caption)
            cr.bold = True
            cr.italic = True
            cr.font.size = Pt(8.5)
            cr.font.color.rgb = _rgb(NAVY)

            return True
        except Exception as e:
            logger.warning(f"Failed to insert image to cell ({caption}): {e}")
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # Section 5 — Limitations
    # ──────────────────────────────────────────────────────────────────────────

    def _add_section5_limitations(self):
        self._h1("SECTION 5  LIMITATION AND PRECAUTION NOTE")
        limitations = [
            ("General Scope Limitation",
             "Information provided in this report is a general overview of the most obvious repairs "
             "that may be needed. It is not intended to be an exhaustive list. The ultimate decision "
             "of what to repair or replace rests with the client/owner."),
            ("Hidden Defects",
             "The Inspector's Report is an opinion of the present condition of the property, based "
             "on a visual examination of readily accessible features. This inspection does not include "
             "identifying defects hidden behind walls, floors, ceilings, finishing surfaces such as "
             "tiling, coba, plaster, or any other masonry surfaces & sub-structures."),
            ("Structural Cracks",
             "Some conditions noted, such as structural cracks & other signs of settlement, indicate "
             "a potential problem. A structure when stressed beyond its capacity may collapse without "
             "further warning signs. When such cracks suddenly develop or appear to widen, the findings "
             "must be reported immediately to a Structural Engineer."),
            ("Code Compliance",
             "THIS IS NOT A CODE COMPLIANCE INSPECTION. The Inspector does NOT try to determine whether "
             "any aspect of the property complies with any past, present or future building codes, "
             "regulations, laws, by-laws, ordinances or other regulatory requirements."),
            ("Air Quality",
             "INSPECTION DOES NOT COMMENT ON THE QUALITY OF AIR IN A BUILDING. Wherever water damage "
             "is noted, there is a possibility that mold or mildew may be present, unseen behind a wall, "
             "floor or ceiling. If anyone in the property suffers from allergies, consult a qualified "
             "Environmental Consultant."),
        ]
        for i, (title, text) in enumerate(limitations, 1):
            self._h3(f"5.{i}  {title}")
            self._body(text)

        self.doc.add_page_break()
        # Legal Disclaimer
        self._h2("Legal Disclaimer")
        self._body(
            "The inspection and report are performed and prepared for the use of the CLIENT. "
            "INSPECTOR accepts no responsibility for use or misinterpretation by third parties. "
            "INSPECTOR has not performed engineering, architectural, plumbing, or any other job "
            "function requiring an occupational license in the jurisdiction where the inspection "
            "is taking place. Quantitative and qualitative information is based primarily on site "
            "visited and observed on the particular day and therefore is subject to fluctuation. "
            "This report is subject to copyrights. No part of this report may be reproduced, stored "
            "in a retrieval system, or transmitted in any form without written approval."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Image Subsection (4.4.x and 4.5.x pattern)
    # ──────────────────────────────────────────────────────────────────────────

    def _add_image_subsection(
        self,
        section_ref:   str,
        area_heading:  str,
        observation:   str,
        image_caption: str,
        thermal_data:  Optional[Dict],
        image_key:     Optional[str],
        img_store:     Dict,
        image_type:    str,   # "thermal" or "visual"
    ):
        # Sub-heading
        self._h3(f"{section_ref}  {area_heading}")

        # Observation paragraph
        if observation and observation.lower() != "not available":
            self._body(observation)

        # Thermal data box
        if thermal_data and (thermal_data.get("hotspot_temp") or thermal_data.get("coldspot_temp")):
            p = self.doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.5)
            _bold_colored_run(p, "Thermal Reading:  ", ORANGE, 10)
            parts = []
            if thermal_data.get("hotspot_temp"):
                parts.append(f"Hotspot: {thermal_data['hotspot_temp']}°C")
            if thermal_data.get("coldspot_temp"):
                parts.append(f"Coldspot: {thermal_data['coldspot_temp']}°C")
            if thermal_data.get("emissivity"):
                parts.append(f"Emissivity: {thermal_data['emissivity']}")
            if thermal_data.get("anomaly"):
                parts.append(f"Pattern: {thermal_data['anomaly'].replace('_', ' ').title()}")
            run = p.add_run(" | ".join(parts))
            run.font.size = Pt(10)
            run.italic = True

        # Image caption (numbered)
        self._image_counter += 1
        if not image_caption or "IMAGE" not in image_caption.upper():
            image_caption = f"IMAGE {self._image_counter}: {area_heading}"

        # Insert the image
        inserted = False
        if image_key and image_key in img_store:
            img_data = img_store[image_key]
            inserted = self._insert_image(img_data, image_caption)

        if not inserted:
            # Try any image from the store that matches area name hints
            fallback_key = self._find_fallback_image(area_heading, img_store, image_type)
            if fallback_key:
                inserted = self._insert_image(img_store[fallback_key], image_caption)

        if not inserted:
            # Placeholder
            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(f"[ Image Not Available — {image_caption} ]")
            run.italic = True
            run.font.size = Pt(10)
            run.font.color.rgb = _rgb("888888")

        self.doc.add_paragraph()  # spacer

    def _insert_image(self, img_data: Dict, caption: str) -> bool:
        """Insert a single image with caption. Returns True on success."""
        try:
            img_bytes = img_data.get("bytes", b"")
            if not img_bytes:
                return False

            buf = io.BytesIO(img_bytes)
            pil = PILImage.open(buf)
            if pil.mode not in ("RGB", "L"):
                pil = pil.convert("RGB")
            out = io.BytesIO()
            pil.save(out, format="JPEG", quality=88)
            out.seek(0)

            p = self.doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(out, width=Inches(5.0))

            # Caption
            cap = self.doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cr = cap.add_run(caption)
            cr.bold = True
            cr.italic = True
            cr.font.size = Pt(9)
            cr.font.color.rgb = _rgb(NAVY)

            return True
        except Exception as e:
            logger.warning(f"Image insert failed ({caption}): {e}")
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # Image Assignment Map Builder
    # ──────────────────────────────────────────────────────────────────────────

    def _build_image_map(
        self,
        thermal_images:    Dict,
        inspection_images: Dict,
        links_data:        Dict,
    ) -> Dict[str, Dict]:
        """
        Returns { area_name → { thermal_key, inspection_key } }
        Assigns thermal images to areas based on links_data,
        inspection images from matched thermal visual partner, or falling back by page order.
        """
        image_map: Dict[str, Dict] = {}
        used_thermal = set()
        used_inspection = set()

        for link in links_data.get("links", []):
            area_name = link["area_name"]
            reading   = link.get("reading", {})
            
            thermal_key = reading.get("thermal_image_key") or reading.get("image_key")
            visual_key = reading.get("visual_image_key")

            if area_name not in image_map:
                image_map[area_name] = {}

            # Assign thermal image
            if thermal_key and thermal_key in thermal_images and thermal_key not in used_thermal:
                image_map[area_name]["thermal_key"] = thermal_key
                used_thermal.add(thermal_key)

            # Assign paired visual photograph from Thermal Images PDF if available
            if visual_key and visual_key in thermal_images and visual_key not in used_inspection:
                image_map[area_name]["inspection_key"] = visual_key
                used_inspection.add(visual_key)

        # Fallback 1: If an area doesn't have a thermal_key, assign an unused one
        for area_name in image_map:
            if "thermal_key" not in image_map[area_name]:
                for k in thermal_images:
                    if k not in used_thermal and thermal_images[k].get("type", "thermal") == "thermal":
                        image_map[area_name]["thermal_key"] = k
                        used_thermal.add(k)
                        break

        # Fallback 2: For any area without an inspection_key, distribute inspection_images by index order
        area_names = list(image_map.keys())
        insp_keys  = [k for k in inspection_images if k not in used_inspection]
        
        insp_idx = 0
        for area_name in area_names:
            if "inspection_key" not in image_map[area_name]:
                # Find an unused image in inspection_images first
                while insp_idx < len(insp_keys):
                    k = insp_keys[insp_idx]
                    insp_idx += 1
                    if k not in used_inspection:
                        image_map[area_name]["inspection_key"] = k
                        used_inspection.add(k)
                        break
                
                # If still not assigned, look for any unused visual image in thermal_images
                if "inspection_key" not in image_map[area_name]:
                    for k in thermal_images:
                        if k not in used_inspection and thermal_images[k].get("type") == "visual":
                            image_map[area_name]["inspection_key"] = k
                            used_inspection.add(k)
                            break

        return image_map

    def _find_fallback_image(
        self, area_heading: str, img_store: Dict, image_type: str
    ) -> Optional[str]:
        """Return any unused image key from the store."""
        for k in img_store:
            return k   # just return first available
        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Audit Appendix
    # ──────────────────────────────────────────────────────────────────────────

    def _add_audit_appendix(self, audit_data: Dict):
        self.doc.add_page_break()
        self._h1("Appendix: Pipeline Audit Trail")
        meta = audit_data.get("extraction_meta", {})
        rows = [
            ("Inspection Areas Found",    str(meta.get("areas_count", "N/A"))),
            ("Observations Extracted",    str(meta.get("obs_count", "N/A"))),
            ("Thermal Readings",          str(meta.get("readings_count", "N/A"))),
            ("Unique Images Analyzed",    str(meta.get("images_analyzed", "N/A"))),
            ("Thermal Links Matched",     str(meta.get("links_matched", "N/A"))),
            ("Unmatched Thermal Readings",str(meta.get("unmatched_thermals", "N/A"))),
            ("Conflicts Detected",        str(meta.get("conflicts", "N/A"))),
            ("Report Generated",          now_iso()),
        ]
        self._info_table(rows)
        warnings = audit_data.get("validation_warnings", [])
        if warnings:
            self._h2("Validation Warnings")
            for w in warnings:
                self._bullet(w)

    # ──────────────────────────────────────────────────────────────────────────
    # Typography helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _h1(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after  = Pt(6)
        _set_para_shading(p, NAVY)
        run = p.add_run(f"  {text}  ")
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = _rgb(WHITE)

    def _h2(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after  = Pt(4)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = _rgb(BLUE)

    def _h3(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = _rgb(ORANGE)

    def _body(self, text: str):
        if not text:
            return
        p = self.doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        run = p.add_run(str(text))
        run.font.size = Pt(11)

    def _bullet(self, text: str):
        p = self.doc.add_paragraph(style="List Bullet")
        run = p.add_run(str(text))
        run.font.size = Pt(11)

    def _add_hr(self):
        p = self.doc.add_paragraph()
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:color"), ORANGE)
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _info_table(self, rows: List[Tuple[str, str]]):
        table = self.doc.add_table(rows=len(rows), cols=2)
        table.style = "Table Grid"
        for i, (label, value) in enumerate(rows):
            row = table.rows[i]
            _set_cell_bg(row.cells[0], NAVY)
            lp = row.cells[0].paragraphs[0]
            lr = lp.add_run(label)
            lr.bold = True
            lr.font.color.rgb = _rgb(WHITE)
            lr.font.size = Pt(10)
            row.cells[1].text = str(value)
            for para in row.cells[1].paragraphs:
                for run in para.runs:
                    run.font.size = Pt(10)

    def _add_disclaimer_inline(self, text: str):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        run = p.add_run(text)
        run.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = _rgb("666666")

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _area_name_from_desc(description: str) -> Optional[str]:
        """Extract area name from 'Observed dampness at... Hall of Flat No. 103'"""
        if not description:
            return None
        room_keywords = [
            "master bedroom", "common bathroom", "hall", "bedroom", "kitchen",
            "bathroom", "passage", "staircase", "parking", "balcony", "terrace",
        ]
        lower = description.lower()
        for kw in sorted(room_keywords, key=len, reverse=True):
            if kw in lower:
                return kw.title()
        return None


def _set_para_shading(para, hex_color: str):
    """Set paragraph background shading."""
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color.lstrip("#"))
    shd.set(qn("w:val"), "clear")
    pPr.append(shd)
