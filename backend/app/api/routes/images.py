import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, UploadFile

from app.api.deps import SessionDep, get_image_metadata
from app.models.image import FluxModel
from app.services.image_uploader import LocalImageUploader

router = APIRouter(prefix="/images", tags=["images"])


@router.post("/upload")
def upload_image(
    file: UploadFile,
    session: SessionDep,
    uploader: Annotated[LocalImageUploader, Depends()],
    id: uuid.UUID = Query(...),  # noqa
    meta: dict = Depends(get_image_metadata),
    model: FluxModel = Query(default=FluxModel.FLUX_PRO_1_1.value),
):
    return uploader.upload_image(file, session, meta, model)
