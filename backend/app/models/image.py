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


# Pro 1.1 Models
class FluxProCreate(ImageCreate):
    model: Literal[FluxModel.FLUX_PRO] = Field(
        default=FluxModel.FLUX_PRO,
        description="Flux Pro model"
    )
    image_prompt: str | None = Field(
        default=None,
        description="Optional base64 encoded image to use with Flux Redux."
    )

class FluxPro11Create(ImageCreate):
    model: Literal[FluxModel.FLUX_PRO_1_1] = Field(
        default=FluxModel.FLUX_PRO_1_1,
        description="Flux Pro 1.1 model"
    )
    image_prompt: str | None = Field(
        default=None,
        description="Optional base64 encoded image to use with Flux Redux."
    )


class FluxPro11UltraCreate(ImageCreate):
    model: Literal[FluxModel.FLUX_PRO_1_1_ULTRA] = Field(
        default=FluxModel.FLUX_PRO_1_1_ULTRA,
        description="Flux Pro 1.1 Ultra model"
    )
    image_prompt: str | None = None
    raw: bool = Field(
        default=False,
        description="Whether to return the raw image data"
    )
    image_prompt_strength: float = Field(
        default=0.1,
        ge=0,
        le=1,
        description="Strength of the image prompt"
    )
    aspect_ratio: Literal["16:9", "9:16", "21:9", "9:21", "3:4", "4:3", "1:1"] = Field(
        default="16:9",
        description="Aspect ratio of the generated image"
    )


# Pro 1.0 Models
class FluxPro10FillCreate(ImageCreate):
    model: Literal[FluxModel.FLUX_PRO_1_0_FILL] = Field(
        default=FluxModel.FLUX_PRO_1_0_FILL,
        description="Flux Pro 1.0 Fill model"
    )
    mask: str | None = None
    steps: int | None = Field(
        default=None,
        ge=15,
        le=100,
        description="Number of steps to use for the image generation"
    )
    image: str = Field(description="Base64 encoded input image")


class FluxPro10CannyCreate(ImageCreate):
    model: Literal[FluxModel.FLUX_PRO_1_0_CANYON] = Field(
        default=FluxModel.FLUX_PRO_1_0_CANYON,
        description="Flux Pro 1.0 Canny model"
    )
    control_image: str = Field(description="Base64 encoded input image")
    steps: int | None = Field(
        default=None,
        ge=15,
        le=100,
        description="Number of steps to use for the image generation"
    )


class FluxPro10DepthCreate(ImageCreate):
    model: Literal[FluxModel.FLUX_PRO_1_0_DEPTH] = Field(
        default=FluxModel.FLUX_PRO_1_0_DEPTH,
        description="Flux Pro 1.0 Depth model"
    )
    image: str = Field(description="Base64 encoded input image")



# Dev Models
class FluxDevCreate(ImageCreate):
    model: Literal[FluxModel.FLUX_DEV] = Field(
        default=FluxModel.FLUX_DEV,
        description="Flux Dev model"
    )
    experimental: bool = Field(
        default=False,
        description="Enable experimental features"
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
    prompt: str | None = None
    model: str | None = Field(
        default=FluxModel.FLUX_PRO_1_1.value, max_length=20, min_length=1
    )
    url: str
    provider: str = Field(default=Uploader.LOCAL.value, max_length=20, min_length=1)
    provider_id: str | None = None  # Provider-specific identifier
