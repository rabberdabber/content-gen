import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum

from fastapi import UploadFile
from sqlmodel import Field, SQLModel


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


class FluxModel(str, Enum):
    FLUX_PRO_1_1 = "flux_pro_1_1"
    FLUX_PRO_2_1 = "flux_pro_2_1"


class Uploader(str, Enum):
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"


class Media(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str
    media_type: str = Field(default=MediaType.IMAGE.value)
    prompt: str | None = None
    model: str | None = Field(
        default=FluxModel.FLUX_PRO_1_1.value, max_length=20, min_length=1
    )
    url: str
    provider: str = Field(default=Uploader.S3.value, max_length=20, min_length=1)
    provider_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class MediaUploader(ABC):
    @abstractmethod
    async def upload_media(
        self, file: UploadFile, **kwargs
    ) -> Media:
        pass

    @abstractmethod
    async def delete_media(self, media: Media) -> None:
        pass
