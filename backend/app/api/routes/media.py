import uuid
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile
from sqlmodel import select

from app.api.deps import SessionDep, get_media_metadata
from app.models.media import FluxModel, Media, MediaType
from app.services.s3_uploader import S3MediaUploader

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload/{id}")
async def upload_media(
    file: UploadFile,
    session: SessionDep,
    uploader: Annotated[S3MediaUploader, Depends()],
    id: uuid.UUID = Path(...),
    meta: dict = Depends(get_media_metadata),
    model: FluxModel | None = Query(default=None),
    media_type: MediaType = Query(default=MediaType.IMAGE),
):
    """Upload a media file"""
    if not meta or not meta.get("id"):
        meta = {"id": str(id)}
    meta["media_type"] = media_type.value
    return await uploader.upload_media(file, session, meta, model)


@router.get("")
async def list_media(
    uploader: Annotated[S3MediaUploader, Depends()],
    prefix: str | None = None,
    max_keys: int = 1000,
    continuation_token: str | None = None,
    media_type: MediaType | None = None,
):
    """List all media files directly from S3 with optional filtering"""
    return await uploader.list_media(
        prefix=prefix,
        max_keys=max_keys,
        continuation_token=continuation_token,
        media_type=media_type
    )


@router.get("/{key}")
async def get_media(
    uploader: Annotated[S3MediaUploader, Depends()],
    key: str = Path(...),
):
    """Get a specific media file metadata from S3"""
    try:
        return await uploader.get_media(key)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{key}")
async def delete_media(
    uploader: Annotated[S3MediaUploader, Depends()],
    key: str = Path(...),
):
    """Delete a media file from S3"""
    try:
        await uploader.delete_media(key)
        return {"message": "Media deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
