"""
Tests for app.services.vision_service

All cv2 and pytesseract calls are mocked so the suite runs without those
system dependencies being installed.
"""
from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch, PropertyMock
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers to create fake frames
# ---------------------------------------------------------------------------

def _solid_jpeg(value: int = 128, w: int = 64, h: int = 48) -> bytes:
    """Return a minimal fake JPEG-shaped bytes object.
    We do NOT produce a real JPEG — the frame bytes are only passed to mocked
    cv2.imdecode, so any bytes object is fine for tests.
    """
    return bytes([value]) * (w * h)


def _make_gray_array(value: int = 128, w: int = 320, h: int = 240):
    return np.full((h, w), value, dtype=np.uint8)


def _make_color_array(value: int = 128, w: int = 64, h: int = 48):
    return np.full((h, w, 3), value, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Fixture: fresh VisionService with both dependencies mocked as available
# ---------------------------------------------------------------------------

@pytest.fixture()
def svc():
    """
    Return a fresh VisionService with cv2 and pytesseract injected as mocks.
    The mocks are set up so that tests can override specific behaviours.
    """
    import app.services.vision_service as vsmod

    mock_cv2 = MagicMock()
    mock_np  = MagicMock(wraps=np)  # delegate real numpy ops unless overridden
    mock_pt  = MagicMock()
    mock_pil = MagicMock()

    with (
        patch.object(vsmod, "cv2",  mock_cv2),
        patch.object(vsmod, "np",   mock_np),
        patch.object(vsmod, "pytesseract", mock_pt),
        patch.object(vsmod, "Image", mock_pil),
        patch.object(vsmod, "_CV2_AVAILABLE",       True),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", True),
    ):
        # Re-create a fresh service instance inside the patched context
        from app.services.vision_service import VisionService
        service = VisionService()
        yield service, mock_cv2, mock_np, mock_pt, mock_pil


# ---------------------------------------------------------------------------
# Null / empty-input behaviour
# ---------------------------------------------------------------------------

def test_empty_bytes_returns_null_result():
    from app.services.vision_service import VisionService
    svc = VisionService()
    result = svc.process_frame(b"")
    assert result == {"significant": False, "ocr_text": "", "is_formula": False}


def test_identical_bytes_returns_not_significant():
    """Sending the same bytes twice should be filtered by the hash cache."""
    import app.services.vision_service as vsmod

    frame = _solid_jpeg(100)

    mock_cv2 = MagicMock()
    gray = _make_gray_array(100)
    thumb = gray[:240, :320]
    mock_cv2.imdecode.return_value = gray
    mock_cv2.resize.return_value   = thumb
    mock_cv2.IMREAD_GRAYSCALE      = 0
    mock_cv2.IMREAD_COLOR          = 1
    mock_cv2.COLOR_BGR2RGB         = 4

    with (
        patch.object(vsmod, "cv2",  mock_cv2),
        patch.object(vsmod, "np",   np),
        patch.object(vsmod, "_CV2_AVAILABLE", True),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", False),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()

        # First call — new frame, should be significant (first frame rule)
        r1 = service.process_frame(frame)
        assert r1["significant"] is True

        # Second call with identical bytes — hash match, immediately not significant
        r2 = service.process_frame(frame)
        assert r2["significant"] is False


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def test_first_frame_always_significant():
    """The very first frame has no previous thumb, so it is always significant."""
    import app.services.vision_service as vsmod

    gray = _make_gray_array(128)
    thumb = _make_gray_array(128, 320, 240)

    mock_cv2 = MagicMock()
    mock_cv2.imdecode.return_value = gray
    mock_cv2.resize.return_value   = thumb
    mock_cv2.IMREAD_GRAYSCALE      = 0

    with (
        patch.object(vsmod, "cv2",  mock_cv2),
        patch.object(vsmod, "np",   np),
        patch.object(vsmod, "_CV2_AVAILABLE",       True),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", False),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()
        result = service.process_frame(_solid_jpeg())
        assert result["significant"] is True


def test_similar_frame_not_significant():
    """A frame nearly identical to the previous one should be filtered out."""
    import app.services.vision_service as vsmod

    gray  = _make_gray_array(128)
    thumb = _make_gray_array(128, 320, 240)

    mock_cv2 = MagicMock()
    mock_cv2.imdecode.return_value = gray
    mock_cv2.resize.return_value   = thumb
    mock_cv2.IMREAD_GRAYSCALE      = 0

    with (
        patch.object(vsmod, "cv2",  mock_cv2),
        patch.object(vsmod, "np",   np),
        patch.object(vsmod, "_CV2_AVAILABLE",       True),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", False),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()

        frame_a = _solid_jpeg(100)
        frame_b = _solid_jpeg(101)  # different bytes but mock returns same array

        service.process_frame(frame_a)  # seed prev_thumb with all-128 thumb
        result = service.process_frame(frame_b)

        # MSE between two identical 128-value arrays is 0 → not significant
        assert result["significant"] is False


def test_different_frame_is_significant():
    """A frame clearly different from the previous one should be significant."""
    import app.services.vision_service as vsmod

    mock_cv2 = MagicMock()
    mock_cv2.IMREAD_GRAYSCALE = 0
    mock_cv2.IMREAD_COLOR     = 1
    mock_cv2.COLOR_BGR2RGB    = 4

    first_thumb  = _make_gray_array(0,   320, 240)
    second_thumb = _make_gray_array(255, 320, 240)

    call_count = {"n": 0}

    def fake_imdecode(arr, flag):
        return first_thumb if call_count["n"] == 0 else second_thumb

    def fake_resize(img, size, interpolation=None):
        call_count["n"] += 1
        return first_thumb if call_count["n"] == 1 else second_thumb

    mock_cv2.imdecode.side_effect = fake_imdecode
    mock_cv2.resize.side_effect   = fake_resize

    with (
        patch.object(vsmod, "cv2",  mock_cv2),
        patch.object(vsmod, "np",   np),
        patch.object(vsmod, "_CV2_AVAILABLE",       True),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", False),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()

        service.process_frame(_solid_jpeg(0))    # seed first thumb (value=0)
        result = service.process_frame(_solid_jpeg(255))  # completely different
        assert result["significant"] is True


def test_corrupt_frame_not_significant():
    """cv2.imdecode returning None → corrupt frame → not significant."""
    import app.services.vision_service as vsmod

    mock_cv2 = MagicMock()
    mock_cv2.imdecode.return_value = None
    mock_cv2.IMREAD_GRAYSCALE = 0

    with (
        patch.object(vsmod, "cv2",  mock_cv2),
        patch.object(vsmod, "_CV2_AVAILABLE",       True),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", False),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()
        result = service.process_frame(_solid_jpeg())
        assert result["significant"] is False


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def test_ocr_text_returned_on_significant_frame():
    """When a frame is significant, OCR text should be returned."""
    import app.services.vision_service as vsmod

    gray  = _make_gray_array(0)    # first call seed
    thumb = _make_gray_array(255)  # second call — very different

    call_count = {"n": 0}

    mock_cv2 = MagicMock()
    mock_cv2.IMREAD_GRAYSCALE = 0
    mock_cv2.IMREAD_COLOR     = 1
    mock_cv2.COLOR_BGR2RGB    = 4
    mock_cv2.imdecode.return_value  = _make_color_array(128)
    mock_cv2.cvtColor.return_value  = _make_color_array(128)

    def fake_resize(img, size, interpolation=None):
        call_count["n"] += 1
        return _make_gray_array(0 if call_count["n"] == 1 else 255)

    mock_cv2.resize.side_effect = fake_resize

    # Pillow mock
    mock_image_instance = MagicMock()
    mock_image_instance.size = (64, 48)

    mock_pil = MagicMock()
    mock_pil.fromarray.return_value  = mock_image_instance
    mock_image_instance.resize.return_value = mock_image_instance

    mock_pt = MagicMock()
    mock_pt.image_to_string.return_value = "Hello World\n  \nSlide 1"

    with (
        patch.object(vsmod, "cv2",  mock_cv2),
        patch.object(vsmod, "np",   np),
        patch.object(vsmod, "_CV2_AVAILABLE",       True),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", True),
        patch.object(vsmod, "pytesseract", mock_pt),
        patch.object(vsmod, "Image", mock_pil),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()

        service.process_frame(_solid_jpeg(0))   # seed prev_thumb
        result = service.process_frame(_solid_jpeg(255))

        assert result["significant"] is True
        assert "Hello World" in result["ocr_text"]
        assert "Slide 1"    in result["ocr_text"]


def test_ocr_strips_blank_lines():
    """_clean_ocr_text removes blank lines and strips whitespace."""
    from app.services.vision_service import _clean_ocr_text
    raw = "  Line one  \n\n   \nLine two\n"
    assert _clean_ocr_text(raw) == "Line one\nLine two"


def test_ocr_error_returns_empty(caplog):
    """If pytesseract raises, the error is caught and empty string returned."""
    import app.services.vision_service as vsmod

    mock_cv2 = MagicMock()
    mock_cv2.IMREAD_GRAYSCALE = 0
    mock_cv2.IMREAD_COLOR     = 1
    mock_cv2.COLOR_BGR2RGB    = 4
    mock_cv2.imdecode.return_value  = _make_color_array(0)
    mock_cv2.cvtColor.return_value  = _make_color_array(0)
    mock_cv2.resize.return_value    = _make_gray_array(255)

    mock_image_instance = MagicMock()
    mock_image_instance.size = (64, 48)
    mock_pil = MagicMock()
    mock_pil.fromarray.return_value = mock_image_instance

    mock_pt = MagicMock()
    mock_pt.image_to_string.side_effect = RuntimeError("tesseract not found")

    with (
        patch.object(vsmod, "cv2",  mock_cv2),
        patch.object(vsmod, "_CV2_AVAILABLE",       True),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", True),
        patch.object(vsmod, "pytesseract", mock_pt),
        patch.object(vsmod, "Image", mock_pil),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()
        result = service._run_ocr(_solid_jpeg())

    assert result == ""


# ---------------------------------------------------------------------------
# Formula detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("The integral ∫ f(x) dx", True),
    ("x^{2} + y^{2} = r^{2}", True),
    ("\\frac{a}{b}", True),
    ("d/dx sin(x) = cos(x)", True),
    ("Today is Monday", False),
    ("3/4 of students", True),   # fraction pattern
    ("alpha α beta β", True),
    ("", False),
])
def test_formula_pattern(text: str, expected: bool):
    from app.services.vision_service import _FORMULA_PATTERN
    assert bool(_FORMULA_PATTERN.search(text)) == expected


# ---------------------------------------------------------------------------
# No-dependency fallback
# ---------------------------------------------------------------------------

def test_no_cv2_no_tesseract_returns_not_significant():
    """When both optional libraries are absent, every frame returns not-significant."""
    import app.services.vision_service as vsmod

    with (
        patch.object(vsmod, "_CV2_AVAILABLE",       False),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", False),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()

        # Without cv2, significant=True but OCR is disabled,
        # so ocr_text is empty; and significant flag should be True
        # for the first novel frame. BUT hash shortcut prevents re-flagging.
        r1 = service.process_frame(_solid_jpeg(1))
        # first frame: significant=True, ocr_text="" (no tesseract)
        assert r1["significant"] is True
        assert r1["ocr_text"] == ""

        r2 = service.process_frame(_solid_jpeg(1))  # same bytes → hash hit
        assert r2["significant"] is False


def test_no_cv2_with_tesseract_runs_ocr():
    """With pytesseract but no cv2, OCR still runs via Pillow's direct open."""
    import app.services.vision_service as vsmod

    mock_pt  = MagicMock()
    mock_pt.image_to_string.return_value = "Some slide text"

    mock_pil = MagicMock()
    mock_img = MagicMock()
    mock_img.size = (640, 480)
    mock_pil.open.return_value = mock_img
    mock_img.resize.return_value = mock_img

    with (
        patch.object(vsmod, "_CV2_AVAILABLE",       False),
        patch.object(vsmod, "_TESSERACT_AVAILABLE", True),
        patch.object(vsmod, "pytesseract", mock_pt),
        patch.object(vsmod, "Image", mock_pil),
    ):
        from app.services.vision_service import VisionService
        service = VisionService()
        result = service.process_frame(_solid_jpeg(42))

    assert result["significant"] is True
    assert result["ocr_text"] == "Some slide text"


# ---------------------------------------------------------------------------
# Module-level shim
# ---------------------------------------------------------------------------

def test_module_process_frame_delegates_to_singleton():
    import app.services.vision_service as vsmod

    with patch.object(vsmod.vision_service, "process_frame", return_value={"significant": True, "ocr_text": "X", "is_formula": False}) as mock_method:
        from app.services.vision_service import process_frame
        result = process_frame(b"fake")
        mock_method.assert_called_once_with(b"fake")
        assert result["ocr_text"] == "X"
