import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Literal

from fastapi import UploadFile
from sqlmodel import Field, SQLModel


class ImageGenerationResultStatus(StrEnum):
    TASK_NOT_FOUND = "Task not found"
    PENDING = "Pending"
    REQUEST_MODERATED = "Request Moderated"
    CONTENT_MODERATED = "Content Moderated"
    READY = "Ready"
    ERROR = "Error"


class FluxModel(StrEnum):
    FLUX_PRO_1_1 = "flux-pro-1.1"
    FLUX_PRO = "flux-pro"
    FLUX_DEV = "flux-dev"
    FLUX_PRO_1_1_ULTRA = "flux-pro-1.1-ultra"
    FLUX_PRO_1_0_FILL = "flux-pro-1.0-fill"
    FLUX_PRO_1_0_CANYON = "flux-pro-1.0-canny"
    FLUX_PRO_1_0_DEPTH = "flux-pro-1.0-depth"


class Uploader(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"


class ImageCreate(SQLModel):
    prompt: str
    width: int = Field(
        default=512, ge=64, le=2048, description="Width of the image in pixels"
    )
    height: int = Field(
        default=512, ge=64, le=2048, description="Height of the image in pixels"
    )
    model: FluxModel = Field(
        default=FluxModel.FLUX_PRO_1_1, description="Model to use for image generation"
    )
    prompt_upsampling: bool = Field(
        default=False, description="Whether to use prompt upsampling"
    )
    seed: int | None = Field(
        default=None, description="Random seed for reproducible generations"
    )
    safety_tolerance: int = Field(
        default=2, ge=0, le=3, description="Safety filter tolerance level (0-3)"
    )
    output_format: str = Field(
        default="jpeg",
        regex="^(jpeg|png)$",
        description="Output format of the generated image",
    )


class ImageResult(SQLModel):
    id: uuid.UUID | None
    prompt: str
    model: FluxModel
    url: str
    created_at: datetime = Field(default_factory=datetime.now)


class UploadResult(SQLModel):
    url: str
    provider_id: str  # This could be object_name for S3 or UUID for local storage
    provider: Literal["local", "s3", "gcs"]  # e.g., "local", "s3", "gcs"
    upload_result_metadata: dict  # Additional provider-specific metadata


class ImageUploader(ABC):
    @abstractmethod
    def upload_image(self, file: UploadFile, **kwargs) -> UploadResult:
        """
        Upload an image and return the result

        Args:
            image_data: Raw image bytes
            filename: Original filename or desired filename

        Returns:
            UploadResult containing url and provider-specific details
        """
        pass


class Image(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str
    prompt: str
    model: str = Field(
        default=FluxModel.FLUX_PRO_1_1.value, max_length=20, min_length=1
    )
    url: str
    provider: str = Field(default=Uploader.LOCAL.value, max_length=20, min_length=1)
    provider_id: str | None = None  # Provider-specific identifier
