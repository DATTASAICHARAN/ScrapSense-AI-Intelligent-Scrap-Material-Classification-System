"""
camera.py — IP Camera stream manager using OpenCV background thread
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)

_cv2_available = False
try:
    import cv2  # type: ignore
    import numpy as np
    _cv2_available = True
except ImportError:
    logger.warning("OpenCV not available — IP Camera mode will be disabled.")


class CameraError(Exception):
    """Raised for camera connection or frame-capture failures."""


class CameraStream:
    """
    Manages a persistent OpenCV VideoCapture stream in a background thread.
    Call grab_frame() to get the latest still frame on demand.
    """

    def __init__(self, url: str, timeout: float = 5.0):
        if not _cv2_available:
            raise CameraError("OpenCV is not installed. Run: pip install opencv-python-headless")
        self.url = url
        self.timeout = timeout
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_error: str = ""

    # ── Connection ──────────────────────────────────────────────────────────────
    def test_connection(self) -> bool:
        """Quick one-shot check: can we open the URL and read one frame?"""
        if not _cv2_available:
            return False
        cap = cv2.VideoCapture(self.url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self.timeout * 1000))
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(self.timeout * 1000))
        ok, frame = cap.read()
        cap.release()
        success = ok and frame is not None
        logger.info("Camera test_connection url=%s result=%s", self.url, success)
        return success

    def start(self) -> None:
        """Start background capture thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Camera stream started: %s", self.url)

    def stop(self) -> None:
        """Stop background capture thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("Camera stream stopped.")

    # ── Background loop ──────────────────────────────────────────────────────────
    def _capture_loop(self) -> None:
        self._cap = cv2.VideoCapture(self.url)
        self._cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self.timeout * 1000))
        self._cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(self.timeout * 1000))

        while self._running:
            ok, frame = self._cap.read()
            if ok and frame is not None:
                with self._lock:
                    self._latest_frame = frame
                self._last_error = ""
            else:
                self._last_error = "Frame read failed — attempting reconnect."
                logger.warning(self._last_error)
                self._cap.release()
                time.sleep(2)
                self._cap = cv2.VideoCapture(self.url)

    # ── Frame capture ────────────────────────────────────────────────────────────
    def grab_frame(self) -> Image.Image:
        """
        Return the latest captured frame as a PIL Image.
        Thread-safe snapshot — avoids motion blur by using the buffered frame.
        """
        with self._lock:
            frame = self._latest_frame

        if frame is None:
            raise CameraError(
                f"No frame available yet. Last error: {self._last_error or 'stream not started'}"
            )

        # Convert BGR (OpenCV) → RGB (PIL)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    @property
    def last_error(self) -> str:
        return self._last_error

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.stop()


# ── One-shot frame grab (no persistent thread) ─────────────────────────────────
def grab_single_frame(url: str, timeout: float = 5.0) -> Image.Image:
    """
    Capture a single frame from a URL without starting a persistent stream.
    Ideal for the 'Analyze' button click in the UI.
    """
    if not _cv2_available:
        raise CameraError("OpenCV is not installed.")

    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout * 1000))
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout * 1000))

    # Drain a few frames to get a fresh one past the buffer
    for _ in range(3):
        ok, frame = cap.read()
        if not ok:
            break

    ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        raise CameraError(
            f"Could not capture frame from '{url}'. "
            "Check the URL, port, and that the camera app is running."
        )

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)
