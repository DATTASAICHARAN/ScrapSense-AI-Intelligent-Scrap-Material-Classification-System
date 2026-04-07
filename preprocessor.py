"""
preprocessor.py — Image preprocessing: resize + metallic de-glare
"""
from __future__ import annotations

import io
import logging
from typing import Tuple

import numpy as np
from PIL import Image, ImageOps

from config import TARGET_SIZE, MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)


class PreprocessingError(Exception):
    """Raised when an image cannot be preprocessed."""


def validate_file(file_bytes: bytes, filename: str) -> None:
    """Validate uploaded file size and extension."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise PreprocessingError(
            f"File size {len(file_bytes) / 1024 / 1024:.1f} MB exceeds "
            f"the {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB limit."
        )
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in {"jpg", "jpeg", "png"}:
        raise PreprocessingError(
            f"Unsupported file type '.{ext}'. Only JPG and PNG are accepted."
        )


def load_image(source) -> Image.Image:
    """Load a PIL Image from bytes, file-like object, or path."""
    try:
        if isinstance(source, bytes):
            img = Image.open(io.BytesIO(source))
        elif isinstance(source, Image.Image):
            return source.copy()
        else:
            img = Image.open(source)
        img.verify()          # Detect corrupted headers
        # Re-open after verify (verify closes the file)
        if isinstance(source, bytes):
            img = Image.open(io.BytesIO(source))
        else:
            img = Image.open(source)
        return img.convert("RGB")
    except Exception as exc:
        raise PreprocessingError(f"Cannot open image: {exc}") from exc


def apply_clahe(img: Image.Image) -> Image.Image:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) on the
    L-channel of LAB color space to reduce metallic glare while preserving
    color fidelity.
    """
    try:
        import cv2  # type: ignore

        np_img = np.array(img)
        lab = cv2.cvtColor(np_img, cv2.COLOR_RGB2LAB)
        l_ch, a_ch, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_eq = clahe.apply(l_ch)
        merged = cv2.merge([l_eq, a_ch, b_ch])
        result = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)
        return Image.fromarray(result)
    except ImportError:
        logger.warning("OpenCV not available — skipping CLAHE de-glare step.")
        return img
    except Exception as exc:
        logger.warning("CLAHE failed (%s) — returning original image.", exc)
        return img


def preprocess(source, apply_deglare: bool = True) -> Image.Image:
    """
    Full preprocessing pipeline:
    1. Load & validate pixel data
    2. Resize to TARGET_SIZE (LANCZOS)
    3. Apply CLAHE de-glare (optional)

    Args:
        source: bytes | file-like | PIL.Image | str path
        apply_deglare: whether to run CLAHE

    Returns:
        Preprocessed PIL.Image in RGB mode
    """
    img = load_image(source)
    img = img.resize(TARGET_SIZE, Image.LANCZOS)
    if apply_deglare:
        img = apply_clahe(img)
    logger.debug("Preprocessing complete — size=%s mode=%s", img.size, img.mode)
    return img


def image_to_bytes(img: Image.Image, fmt: str = "JPEG", quality: int = 90) -> bytes:
    """Convert PIL Image to raw bytes for Gemini API."""
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    return buf.getvalue()
