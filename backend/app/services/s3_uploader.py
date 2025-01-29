import uuid
from typing import Any

from aiobotocore.session import AioSession, get_session
from fastapi import HTTPException, UploadFile
from loguru import logger
from types_aiobotocore_s3 import S3Client
from types_aiobotocore_s3.type_defs import (
    HeadObjectOutputTypeDef,
    ListObjectsV2OutputTypeDef,
)

from app.core.config import file_storage_settings
from app.models.media import FluxModel, MediaType


class S3MediaUploader:
    def __init__(self):
        self.session: AioSession = get_session()
        self.endpoint_url = "http://minio:9000"
        self.aws_access_key_id = file_storage_settings.MINIO_ROOT_USER
        self.aws_secret_access_key = file_storage_settings.MINIO_ROOT_PASSWORD
        self.bucket_name = file_storage_settings.MINIO_BUCKET_NAME

    async def _get_client(self) -> S3Client:
        return self.session.create_client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
        )

    async def _ensure_bucket_exists(self, client: S3Client) -> None:
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

    @classmethod
    def get_object_url(cls, endpoint_url: str, bucket_name: str, key: str) -> str:
        """Generate a consistent object URL"""
        return f"{file_storage_settings.MINIO_BASE_URL}/{bucket_name}/{key}"

    async def _generate_presigned_url(
        self,
        client: S3Client,
        key: str,
        expires_in: int = file_storage_settings.SIGNED_URL_EXPIRATION
    ) -> str:
        """Generate a presigned URL for the given key that expires in 6 hours by default"""
        try:
            url = await client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            return f"{file_storage_settings.MINIO_BASE_URL}/uploads/{key}"

    async def upload_media(
        self, file: UploadFile, meta: dict
    ) -> dict[str, Any]:
        file_id = uuid.UUID(meta.get("id"))
        unique_filename = self.generate_unique_filename(file_id, file.filename)
        content = await file.read()

        try:
            client = await self._get_client()
            async with client as s3:  # Use async context manager
                await self._ensure_bucket_exists(s3)

                # Ensure metadata values are strings and not None
                metadata = {
                    "media_type": str(meta.get("media_type", MediaType.IMAGE.value)),
                    "prompt": str(meta.get("prompt", "")),
                    "model": str(meta.get("model", FluxModel.FLUX_PRO_1_1.value)),
                }

                # Upload file with metadata
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=unique_filename,
                    Body=content,
                    ContentType=file.headers.get("Content-Type") or file.content_type,
                    Metadata=metadata
                )

                # Get object metadata
                response = await s3.head_object(
                    Bucket=self.bucket_name,
                    Key=unique_filename
                )

                return {
                    "key": unique_filename,
                    "url": self.get_object_url(self.endpoint_url, self.bucket_name, unique_filename),
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
            async with client as s3:  # Use async context manager
                await self._ensure_bucket_exists(s3)

                params: dict[str, Any] = {
                    "Bucket": self.bucket_name,
                    "MaxKeys": max_keys,
                }
                if prefix:
                    params["Prefix"] = prefix
                if continuation_token:
                    params["ContinuationToken"] = continuation_token

                response: ListObjectsV2OutputTypeDef = await s3.list_objects_v2(**params)

                contents = []
                for obj in response.get("Contents", []):
                    head: HeadObjectOutputTypeDef = await s3.head_object(
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
                        "url": self.get_object_url(self.endpoint_url, self.bucket_name, obj["Key"]),
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
            client: S3Client = await self._get_client()
            await self._ensure_bucket_exists(client)

            response: HeadObjectOutputTypeDef = await client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )

            return {
                "key": key,
                "url": self.get_object_url(self.endpoint_url, self.bucket_name, key),
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
