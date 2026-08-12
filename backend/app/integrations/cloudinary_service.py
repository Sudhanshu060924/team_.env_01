"""
Cloudinary video service for VidyaRoom.

Handles upload, URL retrieval and deletion of lecture videos.
Credentials are read from application settings — never hardcoded.
"""
from __future__ import annotations

import logging
from typing import Tuple

import cloudinary
import cloudinary.uploader
import cloudinary.exceptions

from app.config import get_settings

logger = logging.getLogger(__name__)

_FOLDER = "vidyaroom/lectures"


def _init_cloudinary() -> None:
    """Configure the Cloudinary SDK from application settings."""
    settings = get_settings()
    cloudinary.config(
        cloud_name=settings.CLOUD_NAME,
        api_key=settings.CLOUD_API_KEY,
        api_secret=settings.CLOUD_API_SECRET,
        secure=True,
    )


class CloudinaryVideoService:
    """Thin wrapper around cloudinary.uploader for lecture videos."""

    def __init__(self) -> None:
        _init_cloudinary()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def upload_video(
        self,
        file_path_or_bytes: str | bytes,
        lecture_id: str,
    ) -> Tuple[str, str]:
        """
        Upload a video to Cloudinary.

        Parameters
        ----------
        file_path_or_bytes:
            Absolute path to the video file on disk, or raw bytes.
        lecture_id:
            Used to build a stable public_id so re-uploads replace the old file.

        Returns
        -------
        (secure_url, public_id)

        Raises
        ------
        CloudinaryUploadError
            Wraps any Cloudinary SDK / network error with a safe message.
        """
        public_id = f"{_FOLDER}/{lecture_id}"
        try:
            result = cloudinary.uploader.upload(
                file_path_or_bytes,
                resource_type="video",
                public_id=public_id,
                overwrite=True,
                invalidate=True,
            )
        except Exception as exc:
            logger.error("Cloudinary upload failed for lecture %s: %s", lecture_id, exc)
            raise CloudinaryUploadError("Video upload to Cloudinary failed.") from exc

        secure_url: str = result["secure_url"]
        returned_public_id: str = result["public_id"]
        logger.info("Uploaded lecture %s → %s", lecture_id, secure_url)
        return secure_url, returned_public_id

    def delete_video(self, public_id: str) -> None:
        """Delete a video from Cloudinary. Errors are logged but not re-raised."""
        try:
            cloudinary.uploader.destroy(public_id, resource_type="video", invalidate=True)
            logger.info("Deleted Cloudinary asset: %s", public_id)
        except Exception as exc:
            logger.warning("Cloudinary delete failed for %s: %s", public_id, exc)


class CloudinaryUploadError(RuntimeError):
    """Raised when a Cloudinary upload cannot be completed."""
