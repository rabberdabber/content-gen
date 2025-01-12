import uuid
from typing import Any

from aiobotocore.session import get_session
from fastapi import HTTPException, UploadFile
from loguru import logger
from sqlmodel import Session

from app.core.config import file_storage_settings
from app.models.media import FluxModel, MediaType


class S3MediaUploader:
    def __init__(self):
        self.session = get_session()
        self.endpoint_url = "http://minio:9000"
        self.aws_access_key_id = file_storage_settings.MINIO_ROOT_USER
        self.aws_secret_access_key = file_storage_settings.MINIO_ROOT_PASSWORD
        self.bucket_name = file_storage_settings.MINIO_BUCKET_NAME

    async def _get_client(self):
        return await self.session.create_client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        ).__aenter__()

    async def _ensure_bucket_exists(self, client) -> None:
        """Ensure the bucket exists, create it if it doesn't"""
        try:
            await client.head_bucket(Bucket=self.bucket_name)
        except client.exceptions.ClientError:
            await client.create_bucket(Bucket=self.bucket_name)
            logger.info(f"Created bucket: {self.bucket_name}")

    @classmethod
    def generate_unique_filename(cls, file_id: uuid.UUID, filename: str) -> str:
        ext = filename.rsplit(".", 1)[1].lower()
        return f"{str(file_id)}.{ext}"

    async def upload_media(
        self, file: UploadFile, session: Session, meta: dict, model: FluxModel | None = None
    ) -> dict[str, Any]:
        file_id = uuid.UUID(meta.get("id"))
        unique_filename = self.generate_unique_filename(file_id, file.filename)
        content = await file.read()

        try:
            client = await self._get_client()
            await self._ensure_bucket_exists(client)

            # Upload file with metadata
            await client.put_object(
                Bucket=self.bucket_name,
                Key=unique_filename,
                Body=content,
                ContentType=file.content_type,
                Metadata={
                    "media_type": meta.get("media_type", MediaType.IMAGE.value),
                    "prompt": meta.get("prompt", ""),
                    "model": model.value if model else FluxModel.FLUX_PRO_1_1.value,
                }
            )

            # Get object metadata
            response = await client.head_object(
                Bucket=self.bucket_name,
                Key=unique_filename
            )

            return {
                "key": unique_filename,
                "url": f"{file_storage_settings.BASE_URL}/uploads/{unique_filename}",
                "content_type": file.content_type,
                "size": response["ContentLength"],
                "metadata": response.get("Metadata", {}),
                "last_modified": response["LastModified"].isoformat(),
            }

        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise HTTPException(status_code=500, detail="Error uploading file")

    async def list_media(
        self,
        prefix: str | None = None,
        max_keys: int = 1000,
        continuation_token: str | None = None,
        media_type: MediaType | None = None,
    ) -> dict[str, Any]:
        try:
            client = await self._get_client()
            await self._ensure_bucket_exists(client)

            params = {
                "Bucket": self.bucket_name,
                "MaxKeys": max_keys,
            }
            if prefix:
                params["Prefix"] = prefix
            if continuation_token:
                params["ContinuationToken"] = continuation_token

            response = await client.list_objects_v2(**params)

            contents = []
            for obj in response.get("Contents", []):
                head = await client.head_object(
                    Bucket=self.bucket_name,
                    Key=obj["Key"]
                )
                metadata = head.get("Metadata", {})

                if media_type and metadata.get("media_type") != media_type.value:
                    continue

                contents.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "url": f"{file_storage_settings.BASE_URL}/uploads/{obj['Key']}",
                    "metadata": metadata,
                })

            return {
                "contents": contents,
                "key_count": response.get("KeyCount", 0),
                "is_truncated": response.get("IsTruncated", False),
                "next_continuation_token": response.get("NextContinuationToken"),
            }

        except Exception as e:
            logger.error(f"Error listing files: {str(e)}")
            raise HTTPException(status_code=500, detail="Error listing files")

    async def get_media(self, key: str) -> dict[str, Any]:
        try:
            client = await self._get_client()
            await self._ensure_bucket_exists(client)

            response = await client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )

            return {
                "key": key,
                "url": f"{file_storage_settings.BASE_URL}/uploads/{key}",
                "content_type": response.get("ContentType"),
                "size": response["ContentLength"],
                "metadata": response.get("Metadata", {}),
                "last_modified": response["LastModified"].isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting file metadata: {str(e)}")
            raise HTTPException(status_code=404, detail="File not found")

    async def delete_media(self, key: str) -> None:
        try:
            client = await self._get_client()
            await self._ensure_bucket_exists(client)

            await client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            raise HTTPException(status_code=404, detail="File not found")
