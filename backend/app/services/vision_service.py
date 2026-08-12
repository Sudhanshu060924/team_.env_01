# Vision service — Phase 6
# Stub: process_frame is called by the WebSocket frame handler.

def process_frame(frame_bytes: bytes) -> dict:
    """Phase 6 will use OpenCV for change detection + Tesseract OCR.
    Returns {"significant": bool, "ocr_text": str, "is_formula": bool}.
    """
    return {"significant": False, "ocr_text": "", "is_formula": False}
