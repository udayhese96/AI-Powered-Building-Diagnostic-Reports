"""
image_analyzer.py - Stage 2
Sends each significant image to GPT-4o mini Vision for analysis.
Returns structured descriptions, anomaly types, severity estimates.
"""

import base64
import logging
from typing import Dict, Any, List, Optional

from openai import OpenAI

from src.utils.config import OPENAI_API_KEY, VISION_MODEL, MAX_TOKENS_PER_IMAGE_CALL
from src.utils.helpers import setup_logger, image_to_base64

logger = setup_logger("stage2.vision")

VISION_SYSTEM_PROMPT = """You are a building diagnostics expert analyzing inspection and thermal images.
For each image, provide a concise structured analysis. Be factual, do not guess.
Respond ONLY with a JSON object with these exact keys:
{
  "visual_description": "<1-2 sentences describing what is visible>",
  "anomaly_present": true|false,
  "anomaly_type": "hotspot"|"coldspot"|"moisture"|"crack"|"dampness"|"spalling"|"hollow"|"none",
  "severity": "high"|"medium"|"low"|"none",
  "confidence": 0.0-1.0,
  "notes": "<any additional observations or 'None'>"
}"""


class ImageAnalyzer:
    """
    Analyzes images using GPT-4o mini Vision API.

    Takes the images dict from Stage 1 (both inspection + thermal images).
    Returns enriched image_insights dict.
    """

    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. Please add it to your .env file."
            )
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def analyze_images(
        self,
        thermal_images: Dict[str, Any],
        inspection_images: Dict[str, Any],
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Analyze all thermal and key inspection images.

        Args:
            thermal_images:    dict from ThermalExtractor.data["images"]
            inspection_images: dict from InspectionExtractor.data["images"]
            progress_callback: optional fn(current, total, image_key)

        Returns:
            image_insights dict keyed by image_key:
            {
              "th_abc123": {
                "visual_description": "...",
                "anomaly_present": True,
                "anomaly_type": "hotspot",
                "severity": "high",
                "confidence": 0.92,
                "notes": "...",
                "source": "thermal",
              },
              ...
            }
        """
        insights: Dict[str, Any] = {}

        # Prioritize thermal images, then inspection images
        all_images = [
            (k, v, "thermal") for k, v in thermal_images.items()
        ] + [
            (k, v, "inspection") for k, v in inspection_images.items()
        ]

        total = len(all_images)
        logger.info(f"Starting vision analysis of {total} images")

        for idx, (key, img_data, source) in enumerate(all_images):
            if progress_callback:
                progress_callback(idx + 1, total, key)

            analysis = self._analyze_single(key, img_data, source)
            if analysis:
                analysis["source"] = source
                insights[key] = analysis

            logger.info(f"  [{idx+1}/{total}] {key}: {analysis.get('anomaly_type','?')} "
                        f"severity={analysis.get('severity','?')}" if analysis else
                        f"  [{idx+1}/{total}] {key}: skipped")

        logger.info(f"Vision analysis complete: {len(insights)} images analyzed")
        return insights

    # ──────────────────────────────────────────────────────────────────────────
    # Single Image Analysis
    # ──────────────────────────────────────────────────────────────────────────

    def _analyze_single(
        self,
        key: str,
        img_data: Dict[str, Any],
        source: str,
    ) -> Optional[Dict[str, Any]]:
        """Send one image to GPT-4o mini Vision. Returns parsed JSON or None."""
        try:
            img_bytes = img_data.get("bytes", b"")
            if not img_bytes:
                return None

            ext = img_data.get("ext", "jpeg").lower()
            if ext == "jpg":
                ext = "jpeg"
            mime = f"image/{ext}"

            b64 = base64.b64encode(img_bytes).decode("utf-8")
            data_url = f"data:{mime};base64,{b64}"

            context = (
                "thermal inspection image" if source == "thermal"
                else "building inspection site photo"
            )

            response = self.client.chat.completions.create(
                model=VISION_MODEL,
                max_tokens=MAX_TOKENS_PER_IMAGE_CALL,
                messages=[
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Analyze this {context}. Respond with the JSON object only.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url, "detail": "low"},
                            },
                        ],
                    },
                ],
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            import json
            return json.loads(raw)

        except Exception as e:
            logger.warning(f"Vision analysis failed for {key}: {e}")
            return {
                "visual_description": "Analysis unavailable",
                "anomaly_present": False,
                "anomaly_type": "none",
                "severity": "none",
                "confidence": 0.0,
                "notes": f"Error: {str(e)[:100]}",
            }
