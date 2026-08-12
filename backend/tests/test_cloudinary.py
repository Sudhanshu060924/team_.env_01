"""
Tests for Cloudinary video service and the video upload endpoint.

All tests use mocked Cloudinary calls — no real credentials are required.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.lecture import LectureRead
from app.database.models import User

# Pre-import the cloudinary_service module so patch paths resolve.
import app.integrations.cloudinary_service as _cld_svc  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lecture(
    lecture_id: str | None = None,
    teacher_id: str | None = None,
    video_url: str | None = None,
    cloudinary_public_id: str | None = None,
) -> LectureRead:
    return LectureRead(
        lecture_id=lecture_id or str(uuid.uuid4()),
        title="Test Lecture",
        video_name="test.mp4",
        status="completed",
        teacher_id=teacher_id,
        created_at=datetime.now(timezone.utc),
        video_url=video_url,
        cloudinary_public_id=cloudinary_public_id,
    )


def _make_user(user_id: str | None = None, role: str = "teacher") -> User:
    user = MagicMock(spec=User)
    user.id = user_id or str(uuid.uuid4())
    user.role = role
    return user


def _mp4_bytes() -> bytes:
    """Minimal non-empty byte string that represents a fake MP4 file."""
    return b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100


# ---------------------------------------------------------------------------
# Cloudinary service unit tests
# ---------------------------------------------------------------------------


class TestCloudinaryVideoService:
    """Unit tests for CloudinaryVideoService — Cloudinary SDK fully mocked."""

    def test_init_configures_cloudinary(self) -> None:
        """CloudinaryVideoService.__init__ calls cloudinary.config with credentials."""
        import app.integrations.cloudinary_service as svc_mod
        from app.config import get_settings

        fake_settings = MagicMock(
            CLOUD_NAME="test-cloud",
            CLOUD_API_KEY="key123",
            CLOUD_API_SECRET="secret456",
        )

        with (
            patch.object(svc_mod.cloudinary, "config") as mock_cfg,
            patch.object(svc_mod, "get_settings", return_value=fake_settings),
        ):
            svc_mod.CloudinaryVideoService()

        mock_cfg.assert_called_once_with(
            cloud_name="test-cloud",
            api_key="key123",
            api_secret="secret456",
            secure=True,
        )

    def test_upload_video_returns_url_and_public_id(self) -> None:
        """upload_video returns (secure_url, public_id) from the Cloudinary response."""
        import app.integrations.cloudinary_service as svc_mod

        fake_result = {
            "secure_url": "https://res.cloudinary.com/test/video/upload/v1/vidyaroom/lectures/abc123.mp4",
            "public_id": "vidyaroom/lectures/abc123",
        }
        with (
            patch.object(svc_mod.cloudinary, "config"),
            patch.object(
                svc_mod.cloudinary.uploader, "upload",
                return_value=fake_result,
            ) as mock_upload,
        ):
            svc = svc_mod.CloudinaryVideoService()
            url, pid = svc.upload_video("/tmp/fake.mp4", "abc123")

        assert url == fake_result["secure_url"]
        assert pid == fake_result["public_id"]
        mock_upload.assert_called_once()
        call_kwargs = mock_upload.call_args
        assert call_kwargs.kwargs.get("resource_type") == "video"
        assert "abc123" in call_kwargs.kwargs.get("public_id", "")

    def test_upload_video_raises_cloudinary_upload_error_on_failure(self) -> None:
        """upload_video wraps Cloudinary exceptions in CloudinaryUploadError."""
        import app.integrations.cloudinary_service as svc_mod

        with (
            patch.object(svc_mod.cloudinary, "config"),
            patch.object(
                svc_mod.cloudinary.uploader, "upload",
                side_effect=Exception("network timeout"),
            ),
        ):
            svc = svc_mod.CloudinaryVideoService()
            with pytest.raises(svc_mod.CloudinaryUploadError):
                svc.upload_video("/tmp/fake.mp4", "abc123")

    def test_delete_video_does_not_raise_on_error(self) -> None:
        """delete_video swallows exceptions (logs a warning instead)."""
        import app.integrations.cloudinary_service as svc_mod

        with (
            patch.object(svc_mod.cloudinary, "config"),
            patch.object(
                svc_mod.cloudinary.uploader, "destroy",
                side_effect=Exception("forbidden"),
            ),
        ):
            svc = svc_mod.CloudinaryVideoService()
            svc.delete_video("vidyaroom/lectures/abc123")  # must not raise


# ---------------------------------------------------------------------------
# Upload endpoint integration tests (FastAPI / httpx)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_video_saves_video_url_and_public_id():
    """POST /lectures/{id}/video → persists video_url and cloudinary_public_id."""
    import app.integrations.cloudinary_service as svc_mod

    user_id = str(uuid.uuid4())
    lecture_id = str(uuid.uuid4())
    teacher = _make_user(user_id)

    original_lecture = _make_lecture(lecture_id=lecture_id, teacher_id=user_id)
    updated_lecture = _make_lecture(
        lecture_id=lecture_id,
        teacher_id=user_id,
        video_url="https://res.cloudinary.com/test/video/upload/v1/vidyaroom/lectures/x.mp4",
        cloudinary_public_id="vidyaroom/lectures/" + lecture_id,
    )

    with (
        patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=original_lecture),
        patch("app.api.lectures.lecture_svc.attach_video", new_callable=AsyncMock, return_value=updated_lecture),
        patch("app.api.deps.get_user_id_from_session", return_value=user_id),
        patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher),
        patch.object(svc_mod.cloudinary, "config"),
        patch.object(
            svc_mod.cloudinary.uploader, "upload",
            return_value={
                "secure_url": updated_lecture.video_url,
                "public_id": updated_lecture.cloudinary_public_id,
            },
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/lectures/{lecture_id}/video",
                files={"video": ("test.mp4", _mp4_bytes(), "video/mp4")},
                cookies={"session_token": "fake-token"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["video_url"] == updated_lecture.video_url
    assert body["cloudinary_public_id"] == updated_lecture.cloudinary_public_id


@pytest.mark.asyncio
async def test_upload_video_unauthorized_rejected():
    """POST /lectures/{id}/video without session cookie → 401."""
    lecture_id = str(uuid.uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/lectures/{lecture_id}/video",
            files={"video": ("test.mp4", _mp4_bytes(), "video/mp4")},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_video_missing_video_field():
    """POST /lectures/{id}/video with no file → 422."""
    user_id = str(uuid.uuid4())
    teacher = _make_user(user_id)

    with (
        patch("app.api.deps.get_user_id_from_session", return_value=user_id),
        patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/lectures/{str(uuid.uuid4())}/video",
                cookies={"session_token": "fake-token"},
            )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_video_lecture_not_found():
    """POST /lectures/{id}/video for non-existent lecture → 404."""
    import app.integrations.cloudinary_service as svc_mod

    user_id = str(uuid.uuid4())
    teacher = _make_user(user_id)

    with (
        patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=None),
        patch("app.api.deps.get_user_id_from_session", return_value=user_id),
        patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher),
        patch.object(svc_mod.cloudinary, "config"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/lectures/{str(uuid.uuid4())}/video",
                files={"video": ("test.mp4", _mp4_bytes(), "video/mp4")},
                cookies={"session_token": "fake-token"},
            )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_video_cloudinary_failure_returns_502():
    """When Cloudinary upload fails the endpoint returns 502 (not a stack trace)."""
    import app.integrations.cloudinary_service as svc_mod

    user_id = str(uuid.uuid4())
    lecture_id = str(uuid.uuid4())
    teacher = _make_user(user_id)
    lecture = _make_lecture(lecture_id=lecture_id, teacher_id=user_id)

    with (
        patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=lecture),
        patch("app.api.deps.get_user_id_from_session", return_value=user_id),
        patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=teacher),
        patch.object(svc_mod.cloudinary, "config"),
        patch.object(
            svc_mod.cloudinary.uploader, "upload",
            side_effect=Exception("Cloudinary down"),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/lectures/{lecture_id}/video",
                files={"video": ("test.mp4", _mp4_bytes(), "video/mp4")},
                cookies={"session_token": "fake-token"},
            )

    assert resp.status_code == 502
    body = resp.json()
    # Must not expose internal errors to the caller
    assert "detail" in body
    assert "Unable to upload" in body["detail"]


@pytest.mark.asyncio
async def test_upload_video_wrong_owner_rejected():
    """A teacher who does not own the lecture should receive 403."""
    import app.integrations.cloudinary_service as svc_mod

    owner_id = str(uuid.uuid4())
    requester_id = str(uuid.uuid4())
    lecture_id = str(uuid.uuid4())

    # The lecture is owned by a *different* teacher
    lecture = _make_lecture(lecture_id=lecture_id, teacher_id=owner_id)
    requester = _make_user(requester_id, role="teacher")

    with (
        patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=lecture),
        patch("app.api.deps.get_user_id_from_session", return_value=requester_id),
        patch("app.api.deps.get_user_by_id", new_callable=AsyncMock, return_value=requester),
        patch.object(svc_mod.cloudinary, "config"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/lectures/{lecture_id}/video",
                files={"video": ("test.mp4", _mp4_bytes(), "video/mp4")},
                cookies={"session_token": "fake-token"},
            )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_lecture_api_returns_video_url():
    """GET /lectures/{id} response includes the video_url field."""
    lecture = _make_lecture(
        video_url="https://res.cloudinary.com/test/video/upload/v1/test.mp4",
        cloudinary_public_id="vidyaroom/lectures/abc",
    )
    with patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=lecture):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/lectures/{lecture.lecture_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["video_url"] == lecture.video_url
    assert body["cloudinary_public_id"] == lecture.cloudinary_public_id


@pytest.mark.asyncio
async def test_existing_lecture_data_intact():
    """Fetching a lecture that has no video still returns all other fields intact."""
    lecture = _make_lecture()  # no video_url
    with patch("app.api.lectures.lecture_svc.get_lecture", new_callable=AsyncMock, return_value=lecture):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/lectures/{lecture.lecture_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["lecture_id"] == lecture.lecture_id
    assert body["title"] == lecture.title
    assert body["status"] == lecture.status
    # video fields are null when not yet uploaded
    assert body["video_url"] is None
    assert body["cloudinary_public_id"] is None
