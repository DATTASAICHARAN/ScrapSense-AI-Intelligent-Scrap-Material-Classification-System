"""
config.py — Central configuration for Scrap Detection System
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ── API ────────────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Model rotation list (tried in order on rate-limit hit)
GEMINI_MODELS = [
    "gemini-3-flash",          # Primary
    "gemini-3.1-flash-lite",   # Fallback
    "gemini-2.5-flash",        # Last resort
]

# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert industrial material classifier for scrap metal recycling facilities.

Analyze the provided image and segment visible materials into exactly three categories:
1. Metal – any ferrous or non-ferrous metallic objects
2. Non-Metal – plastics, rubber, wood, paper, fabric, or other non-metallic materials
3. Background – empty space, containers, conveyor belts, or non-classifiable areas

Rules:
- Percentages must sum to exactly 100
- Base your estimate on the visible pixel area each category occupies
- Return ONLY valid JSON, no markdown, no explanation

Required output format:
{
  "metal": <integer 0-100>,
  "non_metal": <integer 0-100>,
  "background": <integer 0-100>,
  "dominant_material": "<Metal|Non-Metal|Background>",
  "confidence": "<High|Medium|Low>",
  "notes": "<optional one-sentence observation>"
}"""

# ── Storage ────────────────────────────────────────────────────────────────────
DB_PATH = BASE_DIR / "scrap_history.db"
IMAGES_DIR = BASE_DIR / "saved_images"
IMAGES_DIR.mkdir(exist_ok=True)

# ── Preprocessing ──────────────────────────────────────────────────────────────
TARGET_SIZE = (1024, 1024)
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# ── Camera ─────────────────────────────────────────────────────────────────────
CAMERA_TIMEOUT_SEC = 5
CAMERA_RECONNECT_ATTEMPTS = 3

# ── UI ─────────────────────────────────────────────────────────────────────────
APP_TITLE = "ScrapVision AI"
APP_ICON = "⚡"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Scrap metal classification interface focusing on premium aesthetics and real-time visualization."
HISTORY_PAGE_SIZE = 20
