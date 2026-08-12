"""
Vision Service — Phase 6

Processes raw video frames sent by the frontend (base64-decoded JPEG/PNG bytes):
  1. Frame-change detection — skips frames that are visually similar to the previous
     one, so OCR only runs when the slide/board actually changes.
  2. OCR — extracts text from frames that pass the change threshold using Tesseract.
  3. Formula detection — simple heuristic to tag frames that contain mathematical
     notation so the UI can render them differently.

Dependencies (optional, graceful degradation if absent):
  * opencv-python-headless >= 4.9  (pip install opencv-python-headless)
  * Pillow >= 10.3                 (pip install pillow)
  * pytesseract >= 0.3             (pip install pytesseract)
  * Tesseract OCR binary           (system dependency)
      macOS:   brew install tesseract
      Ubuntu:  sudo apt install tesseract-ocr
      Windows: https://github.com/UB-Mannheim/tesseract/wiki

If any dependency is missing the service degrades silently and returns
{"significant": False, "ocr_text": "", "is_formula": False} for every frame.

Public interface
----------------
    from app.services.vision_service import vision_service

    result = vision_service.process_frame(jpeg_bytes)
    # {"significant": bool, "ocr_text": str, "is_formula": bool}

The module-level ``process_frame`` shim keeps the existing WebSocket handler
unchanged.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional-dependency guards
# ---------------------------------------------------------------------------
try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    np = None   # type: ignore[assignment]
    _CV2_AVAILABLE = False
    logger.info("opencv-python-headless not installed — vision change detection disabled")

try:
    import pytesseract
    from PIL import Image
    _TESSERACT_AVAILABLE = True
except ImportError:
    pytesseract = None  # type: ignore[assignment]
    Image = None        # type: ignore[assignment]
    _TESSERACT_AVAILABLE = False
    logger.info("pytesseract/Pillow not installed — OCR disabled")

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
# Minimum fraction of pixels that must differ (MSE-based) to consider a frame
# "significant" relative to the previous one.
_CHANGE_THRESHOLD_MSE: float = 50.0        # mean pixel error (0-255 scale)

# Maximum dimension for the comparison thumbnail (reduces compute).
_THUMBNAIL_SIZE: tuple[int, int] = (320, 240)

# Tesseract page-segmentation mode 6 = assume a single uniform block of text.
_TESSERACT_CONFIG: str = "--psm 6"

# Characters/patterns that suggest mathematical notation.
_FORMULA_PATTERN = re.compile(
    r"[∫∑∏√∂∇∞≤≥≠±×÷∈∉⊂⊃∪∩αβγδεζηθλμπρστφψω]"
    r"|\\[a-zA-Z]+"          # LaTeX command like \frac, \sqrt
    r"|d/d[a-z]"             # derivative notation
    r"|\b[a-zA-Z]\s*[\^_]\s*[{(]"  # superscript / subscript
    r"|\d+\s*/\s*\d+",       # plain fraction like 3/4 inside a formula context
    re.UNICODE,
)

# Minimum OCR confidence (Tesseract data field) to include a word.
_MIN_WORD_CONF: int = 30


class VisionService:
    """Stateful frame processor — tracks the last seen frame for change detection."""

    def __init__(self) -> None:
        self._prev_thumb: Optional[object] = None  # numpy array or None
        self._prev_hash: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, frame_bytes: bytes) -> dict:
        """
        Analyse one video frame.

        Parameters
        ----------
        frame_bytes:
            Raw JPEG or PNG bytes as received from the browser.

        Returns
        -------
        dict with keys:
            significant (bool)  — True when the frame is visually different enough
            ocr_text    (str)   — Text extracted by Tesseract (empty if not significant)
            is_formula  (bool)  — True when OCR text contains math notation
        """
        if not frame_bytes:
            return _null_result()

        # --- quick hash shortcut: identical bytes → definitely not significant ---
        frame_hash = hashlib.md5(frame_bytes).hexdigest()
        if frame_hash == self._prev_hash:
            return _null_result()

        # --- change detection ------------------------------------------------
        if _CV2_AVAILABLE:
            significant = self._is_significant_cv2(frame_bytes)
        else:
            # Fallback: any new frame is "significant" so OCR can still run if
            # pytesseract is available, but we skip very cheap de-duplication.
            significant = True

        self._prev_hash = frame_hash

        if not significant:
            return _null_result()

        # --- OCR -------------------------------------------------------------
        ocr_text = ""
        if _TESSERACT_AVAILABLE:
            ocr_text = self._run_ocr(frame_bytes)

        is_formula = bool(ocr_text and _FORMULA_PATTERN.search(ocr_text))

        return {
            "significant": True,
            "ocr_text": ocr_text,
            "is_formula": is_formula,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_significant_cv2(self, frame_bytes: bytes) -> bool:
        """Return True when the MSE between the thumbnail and the previous frame
        exceeds the change threshold."""
        try:
            arr = np.frombuffer(frame_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
            if img is None:
                logger.warning("cv2.imdecode returned None — frame may be corrupt")
                return False

            thumb = cv2.resize(img, _THUMBNAIL_SIZE, interpolation=cv2.INTER_AREA)

            if self._prev_thumb is None:
                self._prev_thumb = thumb
                return True  # first frame is always significant

            mse = float(np.mean((thumb.astype(np.float32) - self._prev_thumb.astype(np.float32)) ** 2))
            self._prev_thumb = thumb
            return mse > _CHANGE_THRESHOLD_MSE

        except Exception as exc:
            logger.warning("Change detection error: %s", exc)
            return False

    def _run_ocr(self, frame_bytes: bytes) -> str:
        """Run Tesseract on the frame and return cleaned text."""
        try:
            arr = np.frombuffer(frame_bytes, dtype=np.uint8) if _CV2_AVAILABLE else None

            if arr is not None:
                img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img_bgr is None:
                    return ""
                # Convert BGR → RGB for Pillow
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)
            else:
                # No cv2 — let Pillow open directly from bytes
                import io
                pil_img = Image.open(io.BytesIO(frame_bytes))

            # Pre-processing: scale up small images for better OCR accuracy
            w, h = pil_img.size
            if w < 640:
                scale = 640 / w
                pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

            raw_text: str = pytesseract.image_to_string(pil_img, config=_TESSERACT_CONFIG)
            return _clean_ocr_text(raw_text)

        except Exception as exc:
            logger.warning("OCR error: %s", exc)
            return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _null_result() -> dict:
    return {"significant": False, "ocr_text": "", "is_formula": False}


def _clean_ocr_text(raw: str) -> str:
    """Strip control characters and collapse excessive whitespace."""
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Module-level singleton  (preserves the existing WebSocket handler call)
# ---------------------------------------------------------------------------
vision_service = VisionService()


def process_frame(frame_bytes: bytes) -> dict:
    """Module-level shim so the existing WS handler needs no changes."""
    return vision_service.process_frame(frame_bytes)
