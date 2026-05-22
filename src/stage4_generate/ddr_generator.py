"""
ddr_generator.py - Stage 4 (ENHANCED)
Generates all DDR sections matching the professional Main DDR.pdf structure.
Richer prompts, specific treatment methods, per-area sub-sections.
"""

import json
import logging
from typing import Dict, Any, List

from openai import OpenAI

from src.utils.config import OPENAI_API_KEY, REASON_MODEL, DDR_SECTION_LABELS
from src.utils.helpers import setup_logger

logger = setup_logger("stage4.generator")

# ─── Master System Prompt ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert building diagnostics engineer and report writer at UrbanRoof Pvt. Ltd.
You write professional Detailed Diagnostic Reports (DDR) for residential and commercial properties.

Your reports are:
- Detailed, specific, and evidence-based (cite exact areas, temperatures, measurements)
- Written in clear, client-friendly language (avoid unnecessary jargon)
- Structured exactly as requested
- Never inventing facts not present in the context JSON

STRICT RULES:
1. Use ONLY facts from the provided JSON. Do NOT invent numbers, area names, or observations.
2. If information is missing → write exactly "Not Available"  
3. If findings conflict between inspection and thermal → mention BOTH and flag the conflict explicitly
4. Do NOT repeat the same observation across multiple sections
5. Write in full professional paragraphs, not bullet points, unless the schema requests a list
6. Return ONLY valid JSON with the requested structure — no markdown, no extra text

STYLE: Match the tone of a professional building health assessment report. Be direct, factual, and thorough.
"""

# ─── Section Prompts ─────────────────────────────────────────────────────────

SECTION_PROMPTS = {

"property_issue_summary": """
Generate the "Property Issue Summary" section.

Write a detailed professional summary covering:
1. Property address and inspection date
2. What type of structure was inspected (flat, row house, etc.)
3. Summary of ALL main issue categories found (Bathrooms, Balcony, Terrace, External Walls — as applicable)
4. For EACH issue category, explain: what was observed, WHERE exactly, and what is causing it (capillary action, liquid-applied membrane breakdown, gaps in tile joints, cracks, etc.) using professional building pathology terminology.
5. The overall urgency of the situation and structural integrity implications.

Be thorough and use professional engineering terminology. This section should be 4-6 paragraphs covering all major areas.

Return JSON:
{
  "heading": "Property Issue Summary",
  "paragraphs": [
    "<paragraph 1 — overall intro and property details>",
    "<paragraph 2 — bathroom issues with pathology discussion>",
    "<paragraph 3 — balcony/terrace issues if applicable>",
    "<paragraph 4 — external wall issues if applicable>",
    "<paragraph 5 — overall conclusion and urgency assessment>"
  ],
  "key_findings": [
    {"area": "<area name>", "issue": "<concise issue>", "severity": "high|medium|low"}
  ]
}
""",

"area_wise_observations": """
Generate the "Area-wise Observations" section.

This is the MOST important and detailed section. For EACH area in the inspection:

NEGATIVE SIDE (Areas showing damage/symptoms):
- Write a full, high-density paragraph describing what was observed in professional engineering style.
- Include exact location (skirting level, ceiling, wall corner, etc.)
- Explain the visual damage (peeling paint, dampness, efflorescence, concrete spalling, micro-cracks) and the structural risk.
- Include thermal data (hotspot temp, coldspot temp, anomaly type, temperature gradients, evaporative cooling footprints) if available.
- Note the severity.
- Provide clear engineering-oriented severity reasoning (Low, Moderate, High, Critical).

POSITIVE SIDE (Source areas causing the damage):
- Write what was found on the positive side (gaps in tile joints, cracks on external wall, etc.)
- Link it explicitly to which negative-side area it is causing.
- Explain the capillary migration path or liquid ingress mechanism (e.g. gravity load path, hydraulic head).

Return JSON:
{
  "heading": "Area-wise Observations",
  "negative_side": [
    {
      "ref": "4.4.1",
      "area_name": "<exact area name>",
      "heading": "<e.g. CEILING (HALL)>",
      "observation": "<full detailed engineering-grade paragraph discussing building pathology, moisture paths, pressure heads, and gradients>",
      "image_caption": "Figure [N]: Visual photograph showing [precise defect, e.g., micro-cracks or loose grout] at [Area].",
      "thermal_interpretation": "<detailed paragraph interpreting the thermal signatures, abnormal gradients, moisture footprints, and hotspot/coldspot patterns>",
      "thermal_image_caption": "Figure [N+1]: Thermal infrared image indicating moisture signature [hotspot/coldspot temps] with evaporative cooling gradient at [Area].",
      "thermal_data": {
        "hotspot_temp": <number or null>,
        "coldspot_temp": <number or null>,
        "emissivity": <number or null>,
        "anomaly": "<description>"
      },
      "severity": "Low|Moderate|High|Critical",
      "severity_reasoning": "<clear explanation of why this severity rating was given, discussing structural risks, reinforcement corrosion potential, and material degradation>"
    }
  ],
  "positive_side": [
    {
      "ref": "4.5.1",
      "area_name": "<exact area name>",
      "heading": "<e.g. MASTER BEDROOM BATHROOM (1ST FLOOR)>",
      "observation": "<full detailed paragraph linking to negative side and explaining the source mechanism and structural pathology>",
      "image_caption": "Figure [N]: Visual photograph showing positive-side defects [precise defect] at [Area].",
      "causes_negative_ref": "4.4.1"
    }
  ]
}
""",

"probable_root_cause": """
Generate the "Probable Root Cause" section.

For EACH major issue area, provide:
1. What the root cause is (be specific — capillary action through tile joint gaps, water ingress through hairline cracks, liquid-applied membrane breakdown, etc.)
2. The mechanism of water ingress (how water travels from source to symptom area via gravity, pressure head, or capillary action)
3. What will happen if left untreated (structural decay, reinforcement corrosion, concrete spalling)

Format: Write as professional, high-density paragraphs grouped by source type (Bathroom, Balcony, Terrace, External Wall).

Return JSON:
{
  "heading": "Probable Root Cause",
  "source_groups": [
    {
      "source_type": "<e.g. BATHROOMS>",
      "root_cause_paragraph": "<detailed paragraph explaining building physics and pathology>",
      "mechanism": "<how water travels through joints/slabs>",
      "if_untreated": "<consequence on concrete/reinforcement steel>"
    }
  ],
  "overall_summary": "<1 paragraph overall root cause summary>"
}
""",

"severity_assessment": """
Generate the "Severity Assessment" section with detailed reasoning.

Rate the OVERALL property condition as Good / Moderate / Poor.
Then rate each individual area.

IMPORTANT: Use the thermal data (hotspot/coldspot temperatures) and observation severity as evidence.
Explain your reasoning for each rating using engineering-grade structural explanations.

Rating scale:
- Good = No action needed / minor cosmetic issue
- Moderate = Necessary repairs needed in near term to prevent secondary damage
- Poor = Immediate action needed / significant structural risk / reinforcement spalling

Return JSON:
{
  "heading": "Severity Assessment",
  "overall_rating": "Good|Moderate|Poor",
  "overall_reasoning": "<detailed 2-3 sentence reasoning>",
  "area_ratings": [
    {
      "area": "<area name>",
      "side": "negative|positive",
      "rating": "Good|Moderate|Poor",
      "reasoning": "<specific reasoning with evidence from thermal or visual data, focusing on building pathology>"
    }
  ],
  "structural_risk_note": "<note about structural risks if any, or 'No structural risk identified'>"
}
""",

"recommended_actions": """
Generate the "Recommended Actions" section with SPECIFIC treatment methods.

For EACH affected area, provide:
1. The specific treatment method (use industry-standard methods like grouting, waterproofing membrane, plaster repair, RCC treatment)
2. Step-by-step repair process where applicable
3. Materials recommended (if mentioned in source data)
4. Priority level and timeframe

You MUST include these standard treatment categories using the exact materials and guidelines listed below:
- BATHROOM & BALCONY GROUTING TREATMENT: Cut joints into V-shape groove. Clean surface. Fill using liquid polymer-modified mortar (Dr. Fixit URP) in a 1:1 polymer-to-cement ratio so it reaches cracks below tiles. After initial set, fill RTM grout into joints. Outlets and corners patched with Polymer Modified Mortar (PMM). Air cure 24-48 hours.
- PLUMBING: Repair/replace damaged outlets and concealed connections as required.
- PLASTER WORK: Chip off damaged/loose plaster. Apply 1 coat of bonding coat (Dr. Fixit Pidicrete URP 1:1 with cement). Apply 2-coat cement-sand plaster (first coat 12-15mm + second coat 8-10mm), adding Dr. Fixit Lw+ waterproofing compound (200ml per bag of cement) to both coats.
- RCC MEMBERS: Open cracks in V-shape. Fill with heavy-duty polymer-modified concrete spalling mortar (Dr. Fixit HB mortar). Treat exposed/corroded reinforcement steel using jacketing and strengthening.
- EXTERNAL WALL WATERPROOFING: Apply waterproof coating from exterior after surface preparation.

Also include a "Further Possibilities Due to Delayed Action" paragraph.

Return JSON:
{
  "heading": "Recommended Actions",
  "treatment_categories": [
    {
      "category": "<treatment category>",
      "applicable_areas": ["<area1>", "<area2>"],
      "method": "<detailed step-by-step method with exact materials, ratios, and air-cures>",
      "priority": "Immediate|Short-term|Long-term",
      "timeframe": "<e.g. Within 1 week | Within 1 month>"
    }
  ],
  "delayed_action_consequences": "<paragraph about what happens if repairs are delayed, including concrete carbonation, spalling, and steel oxidation>",
  "general_note": "<any general maintenance advice>"
}
""",

"additional_notes": """
Generate the "Additional Notes" section.

Include:
1. Any observations that don't fit the main sections
2. Tools used during inspection (Tapping Hammer, Crack gauge, IR Thermography, Moisture meter, pH meter)
3. Scope limitations (what was NOT inspected, e.g., hidden plumbing, sub-structures)
4. Recommendation to consult specialists if structural cracks are found
5. Professional disclaimers

Return JSON:
{
  "heading": "Additional Notes",
  "tools_used": ["<tool1>", "<tool2>"],
  "scope_notes": "<what was included/excluded from inspection>",
  "specialist_recommendation": "<when to consult a structural engineer>",
  "additional_observations": "<any other relevant notes>",
  "disclaimer": "This report is based on visual and thermal inspection conducted on the date mentioned. The findings represent conditions observed on that date only. Hidden defects not visible during inspection may exist. This is not a code compliance inspection."
}
""",

"missing_information": """
Generate the "Missing or Unclear Information" section.

List every piece of information that was EXPECTED but NOT FOUND or NOT CLEAR in the source documents.
Common expected items: exact flat number, inspector name, building age, previous repair history, plumbing configuration, exact crack measurements.

For each missing item, state its impact on the report quality.

Return JSON:
{
  "heading": "Missing or Unclear Information",
  "items": [
    {
      "missing_item": "<what is missing>",
      "section_affected": "<which DDR section this impacts>",
      "impact": "<how it affects report completeness>",
      "status": "Not Available"
    }
  ],
  "data_confidence": "high|medium|low",
  "confidence_reasoning": "<why we rate confidence as such>"
}
""",
}

# ─── Treatment Methods (verbatim from professional practice) ──────────────────
TREATMENT_KNOWLEDGE = """
STANDARD TREATMENT METHODS (use these if relevant to the findings):

GROUTING TREATMENT (for gaps in tile joints - Bathroom/Balcony):
Clean the surface. Cut the joints into V shape with electric cutter. Fill the joints using liquid polymer 
modified mortar (Dr. Fixit URP) so it reaches cracks below tiles. After initial set, clean with clean cloth. 
Further fill RTM grout into tile joints and patch. Outlets and corners to be patched with PMM (Dr. Fixit URP). 
Air cure 24-48 hours.

PLUMBING:
Repair existing damaged outlets if any & install additional new outlets as required.

PLASTER WORK:
Clean & chip off damaged and loose plaster. Moisten surface and apply 1 coat of bonding coat 
(Dr. Fixit Pidicrete URP 1:1 with cement). Apply 20-25mm thick sand faced cement plaster in two coats 
(first coat 12-15mm in 1:4 CM, second coat 8-10mm in 1:4 CM). Add Dr. Fixit Lw+ waterproofing compound 
(200ml per bag of cement) to both coats.

RCC MEMBERS TREATMENT:
Open cracks in V-shape groove. Fill with heavy duty polymer mortars. Treat any spalling concrete with 
Dr. Fixit HB mortar. Treat exposed/corroded reinforcement steel using jacketing and standardized 
strengthening of RCC members.

NOTE: Structural cracks require immediate attention. They indicate the structure may be overstressed.
Report to Structural Engineer immediately if structural cracks are found.
"""


class DDRGenerator:
    """Generates all DDR sections using GPT-4o mini with enhanced prompts."""

    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in .env file")
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def generate_all_sections(
        self,
        structured_context: Dict[str, Any],
        image_insights: Dict[str, Any],
        validation_report: Dict[str, Any],
        progress_callback=None,
    ) -> Dict[str, Any]:
        from src.utils.config import DDR_SECTIONS

        context = self._build_llm_context(structured_context, image_insights, validation_report)
        context_str = json.dumps(context, indent=2, ensure_ascii=False)

        ddr_sections = {}
        total = len(DDR_SECTIONS)

        for idx, section_key in enumerate(DDR_SECTIONS):
            if progress_callback:
                progress_callback(idx + 1, total, section_key)
            logger.info(f"Generating section [{idx+1}/{total}]: {section_key}")
            section_data = self._generate_section(section_key, context_str)
            ddr_sections[section_key] = section_data

        logger.info(f"DDR generation complete: {len(ddr_sections)} sections")
        return ddr_sections

    # ──────────────────────────────────────────────────────────────────────────
    # Context Builder — Compact but Rich
    # ──────────────────────────────────────────────────────────────────────────

    def _build_llm_context(self, structured_context, image_insights, validation_report):
        inspection = structured_context.get("inspection", {})
        thermal    = structured_context.get("thermal", {})
        links      = structured_context.get("links", {})

        # Build rich area-thermal map
        area_thermal_map = {}
        for link in links.get("links", []):
            area_id = link["area_id"]
            reading = link["reading"]
            if area_id not in area_thermal_map:
                area_thermal_map[area_id] = []
            area_thermal_map[area_id].append({
                "reading_id":    reading["reading_id"],
                "hotspot_temp":  reading.get("hotspot_temp"),
                "coldspot_temp": reading.get("coldspot_temp"),
                "emissivity":    reading.get("emissivity"),
                "ambient_temp":  reading.get("ambient_temp"),
                "camera_file":   reading.get("camera_file"),
                "anomaly_type":  reading.get("anomaly_type"),
                "confidence":    link["confidence"],
            })

        # Image insights summary
        image_summary = {
            k: {
                "description": v.get("visual_description", ""),
                "anomaly":     v.get("anomaly_type", "none"),
                "severity":    v.get("severity", "none"),
                "source":      v.get("source", "unknown"),
            }
            for k, v in image_insights.items()
        }

        # Build full area details
        areas_detail = []
        for area in inspection.get("areas", []):
            area_obs = [
                {
                    "text":     o["text"],
                    "severity": o.get("severity", "unspecified"),
                    "side":     o.get("side", "negative"),
                }
                for o in inspection.get("observations", [])
                if o["area_id"] == area["area_id"]
            ]
            tdata = area_thermal_map.get(area["area_id"], [])
            
            # ONLY include areas with actual observations or thermals
            if area_obs or tdata:
                areas_detail.append({
                    "area_id":      area["area_id"],
                    "name":         area["name"],
                    "observations": area_obs,
                    "thermal_data": tdata,
                })

        # Intro/property sections
        intro = inspection.get("intro_sections", {})

        context = {
            "property":         inspection.get("property", {}),
            "intro":            intro,
            "site_description": inspection.get("site_description", {}),
            "areas":            areas_detail,
            "summary_table":    inspection.get("summary_table", []),
            "all_observations": inspection.get("observations", []),
            "all_thermal_readings": [
                {
                    "reading_id":   r["reading_id"],
                    "location":     r.get("location"),
                    "hotspot_temp": r.get("hotspot_temp"),
                    "coldspot_temp":r.get("coldspot_temp"),
                    "anomaly_type": r.get("anomaly_type"),
                    "camera_file":  r.get("camera_file"),
                }
                for r in thermal.get("readings", [])
            ],
            "checklist_items":    inspection.get("checklist_items", {}),
            "image_insights":     image_summary,
            "unmatched_thermals": links.get("unmatched_thermals", []),
            "conflicts":          links.get("conflicts", []),
            "validation_warnings": validation_report.get("warnings", []) if validation_report else [],
            "treatment_knowledge": TREATMENT_KNOWLEDGE,
        }
        return context

    # ──────────────────────────────────────────────────────────────────────────
    # Section Generator
    # ──────────────────────────────────────────────────────────────────────────

    def _generate_section(self, section_key: str, context_str: str) -> Dict:
        section_prompt = SECTION_PROMPTS.get(section_key, "")
        try:
            response = self.client.chat.completions.create(
                model=REASON_MODEL,
                max_tokens=4000,       # increased for richer output
                temperature=0.15,      # slightly above 0 for fluency
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Here is the complete structured inspection data:\n\n"
                            f"```json\n{context_str}\n```\n\n"
                            f"{section_prompt}"
                        ),
                    },
                ],
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown fences
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:].strip()

            return json.loads(raw)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error for '{section_key}': {e}. Raw: {raw[:300]}")
            return {
                "heading": DDR_SECTION_LABELS.get(section_key, section_key),
                "content": "Content generation encountered a parsing error. Source data was received correctly.",
                "error": str(e),
            }
        except Exception as e:
            logger.error(f"Generation failed for '{section_key}': {e}")
            return {
                "heading": DDR_SECTION_LABELS.get(section_key, section_key),
                "content": f"Not Available — {str(e)[:100]}",
                "error": str(e),
            }
