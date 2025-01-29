import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from loguru import logger
from sqlmodel import Session

from app.core.config import file_storage_settings
from app.models.image import FluxModel, Image, ImageUploader, Uploader, UploadResult


class LocalImageUploader(ImageUploader):
    @classmethod
    def is_valid_file(cls, filename: str) -> bool:
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower()
            in file_storage_settings.ALLOWED_EXTENSIONS
        )

    @classmethod
    def generate_unique_filename(cls, image_id: uuid.UUID, filename: str) -> str:
        ext = filename.rsplit(".", 1)[1].lower()
        return f"{str(image_id)}.{ext}"

    @classmethod
    def ensure_upload_directory(cls) -> None:
        Path(file_storage_settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_file_path(cls, unique_filename: str) -> Path:
        return Path(file_storage_settings.UPLOAD_DIR) / unique_filename

    @classmethod
    def save_file(cls, file_path: Path, file: UploadFile) -> None:
        logger.info(f"Saving file with name {file.filename} to {file_path}")
        CHUNK_SIZE = 1024 * 1024  # 1MB chunks
        file.file.seek(0)
        with open(file_path, "wb") as f:
            while chunk := file.file.read(CHUNK_SIZE):
                f.write(chunk)

    async def upload_image(
        self, file: UploadFile, session: Session, metadata: dict, model: FluxModel
    ) -> UploadResult:
        file_path = None

        try:
            if not self.is_valid_file(file.filename):
                raise HTTPException(status_code=400, detail="File type not allowed")

            self.ensure_upload_directory()
            unique_filename = self.generate_unique_filename(
                uuid.UUID(metadata.get("id")), file.filename
            )
            file_path = self.get_file_path(unique_filename)

            self.save_file(file_path, file)
            url = f"{file_storage_settings.MINIO_BASE_URL}/uploads/{unique_filename}"

            db_image = Image(
                id=uuid.UUID(metadata.get("id")),
                filename=unique_filename,
                prompt=metadata.get("prompt", ""),
                model=model,
                url=url,
                provider=Uploader.LOCAL,
            )
            Image.model_validate(db_image)

            session.add(db_image)
            await session.commit()
            await session.refresh(db_image)

            return UploadResult(
                url=url,
                provider_id=unique_filename,
                provider="local",
                upload_result_metadata={"filename": unique_filename},
            )

        except Exception as e:
            # Clean up file if operation fails
            if file_path and file_path.exists():
                file_path.unlink()
            logger.error(f"Error uploading file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error uploading file: {str(e)}",
            )
