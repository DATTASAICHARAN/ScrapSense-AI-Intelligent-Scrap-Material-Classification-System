"""
gemini_client.py — Gemini API wrapper with model rotation + validation
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai
from PIL import Image

from config import GEMINI_MODELS, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ── Result dataclass ───────────────────────────────────────────────────────────
@dataclass
class AnalysisResult:
    metal: float
    non_metal: float
    background: float
    dominant_material: str = ""
    confidence: str = "Low"
    notes: str = ""
    model_used: str = ""
    raw_response: str = ""
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return {
            "metal": self.metal,
            "non_metal": self.non_metal,
            "background": self.background,
            "dominant_material": self.dominant_material,
            "confidence": self.confidence,
            "notes": self.notes,
            "model_used": self.model_used,
        }


# ── Helpers ────────────────────────────────────────────────────────────────────
def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a response string (handles markdown fences)."""
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or start > end:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    json_str = text[start:end+1]
    return json.loads(json_str)


def _normalize_percentages(data: dict) -> dict:
    """Ensure metal + non_metal + background == 100."""
    metal = float(data.get("metal", 0))
    non_metal = float(data.get("non_metal", 0))
    background = float(data.get("background", 0))
    total = metal + non_metal + background
    if total == 0:
        raise ValueError("All percentages are zero.")
    # Normalize
    factor = 100.0 / total
    return {
        "metal": round(metal * factor, 1),
        "non_metal": round(non_metal * factor, 1),
        "background": round(100.0 - round(metal * factor, 1) - round(non_metal * factor, 1), 1),
        "dominant_material": data.get("dominant_material", ""),
        "confidence": data.get("confidence", "Low"),
        "notes": data.get("notes", ""),
    }


# ── Main client ────────────────────────────────────────────────────────────────
class GeminiClient:
    def __init__(self, api_key: str, models: list[str] | None = None):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self.api_key = api_key
        self.models = models or GEMINI_MODELS
        genai.configure(api_key=api_key)

    def _call_model(self, model_name: str, pil_image: Image.Image) -> str:
        """Send image to a specific model and return text response."""
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
        )
        response = model.generate_content(
            [pil_image, "Analyze this scrap material image and return JSON classification."],
            generation_config=genai.GenerationConfig(
                temperature=0.1,     # Low temperature for consistent JSON
                max_output_tokens=1024,
            ),
        )
        return response.text

    def analyze_image(self, pil_image: Image.Image) -> AnalysisResult:
        """
        Analyze a PIL image with automatic model fallback on rate limits.
        Returns a validated AnalysisResult.
        """
        last_error = None

        for model_name in self.models:
            raw_text = ""
            try:
                logger.info("Trying model: %s", model_name)
                raw_text = self._call_model(model_name, pil_image)
                data = _extract_json(raw_text)
                normalized = _normalize_percentages(data)

                return AnalysisResult(
                    metal=normalized["metal"],
                    non_metal=normalized["non_metal"],
                    background=normalized["background"],
                    dominant_material=normalized.get("dominant_material", ""),
                    confidence=normalized.get("confidence", "Low"),
                    notes=normalized.get("notes", ""),
                    model_used=model_name,
                    raw_response=raw_text,
                )

            except Exception as exc:
                err_str = str(exc)
                logger.warning("Model %s failed: %s", model_name, err_str)

                # Check if it's a rate limit error — try next model
                if any(k in err_str.lower() for k in ("429", "quota", "resource_exhausted", "rate")):
                    logger.info("Rate limit hit on %s — trying next model.", model_name)
                    time.sleep(1)  # Brief pause before retry
                    last_error = exc
                    continue
                else:
                    # Non-rate-limit error — return immediately with error
                    return AnalysisResult(
                        metal=0, non_metal=0, background=0,
                        error=f"Analysis failed: {exc}",
                        raw_response=raw_text if raw_text else err_str,
                    )

        return AnalysisResult(
            metal=0, non_metal=0, background=0,
            error=f"All models exhausted. Last error: {last_error}",
        )


# ── Convenience factory ────────────────────────────────────────────────────────
def create_client(api_key: str) -> GeminiClient:
    return GeminiClient(api_key=api_key)
