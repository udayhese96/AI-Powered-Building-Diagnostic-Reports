"""
config.py - Configuration and constants for DDR system.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ─── Model Selection ─────────────────────────────────────────────────────────
VISION_MODEL   = "gpt-4o-mini"   # for image analysis
REASON_MODEL   = "gpt-4o-mini"   # for validation + generation

# ─── DDR Sections ────────────────────────────────────────────────────────────
DDR_SECTIONS = [
    "property_issue_summary",
    "area_wise_observations",
    "probable_root_cause",
    "severity_assessment",
    "recommended_actions",
    "additional_notes",
    "missing_information",
]

DDR_SECTION_LABELS = {
    "property_issue_summary":  "1. Property Issue Summary",
    "area_wise_observations":  "2. Area-wise Observations",
    "probable_root_cause":     "3. Probable Root Cause",
    "severity_assessment":     "4. Severity Assessment",
    "recommended_actions":     "5. Recommended Actions",
    "additional_notes":        "6. Additional Notes",
    "missing_information":     "7. Missing or Unclear Information",
}

# ─── Severity Keywords ────────────────────────────────────────────────────────
SEVERITY_HIGH    = ["critical", "urgent", "severe", "damage", "failure", "dangerous", "structural"]
SEVERITY_MEDIUM  = ["concern", "issue", "deterioration", "seepage", "dampness", "crack", "spalling", "efflorescence"]
SEVERITY_LOW     = ["monitor", "minor", "note", "slight", "superficial"]

# ─── Thermal Anomaly Thresholds ───────────────────────────────────────────────
HOTSPOT_DELTA   = 5.0    # °C above ambient = hotspot
COLDSPOT_LIMIT  = 18.0   # °C below = condensation risk
MOISTURE_RANGE  = (18.0, 28.0)  # °C range typical for moisture patterns

# ─── Image Settings ───────────────────────────────────────────────────────────
MIN_IMAGE_DIM   = 100    # px — ignore tiny icons/logos
MAX_TOKENS_PER_IMAGE_CALL = 400

# ─── Output ───────────────────────────────────────────────────────────────────
DEFAULT_OUTPUT_FILENAME = "DDR_Report.docx"

# ─── Document Styling ─────────────────────────────────────────────────────────
DOC_STYLES = {
    "title_color":      "1F3864",   # dark navy
    "heading1_color":   "2E5299",   # medium blue
    "heading2_color":   "2F5496",
    "accent_color":     "E07B39",   # orange accent (matches sample DDR)
    "body_font":        "Calibri",
    "heading_font":     "Calibri",
    "body_size_pt":     11,
    "heading1_size_pt": 14,
    "heading2_size_pt": 12,
    "page_width_cm":    21.0,
    "page_height_cm":   29.7,
    "margin_cm":        2.0,
}
