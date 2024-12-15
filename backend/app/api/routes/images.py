import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, UploadFile

from app.api.deps import SessionDep, get_image_metadata
from app.models.image import FluxModel
from app.services.image_uploader import LocalImageUploader

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/upload/{id}")
async def upload_image(
    file: UploadFile,
    session: SessionDep,
    uploader: Annotated[LocalImageUploader, Depends()],
    id: uuid.UUID = Path(...),
    meta: dict = Depends(get_image_metadata),
    model: FluxModel | None = Query(default=None),
):
    if not meta or not meta.get("id"):
        meta = {"id": str(id)}
    return await uploader.upload_image(file, session, meta, model)
