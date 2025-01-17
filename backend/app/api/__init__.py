from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.routes import ai, images, login, media, posts, private, users, utils
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(ai.router)
api_router.include_router(images.router)
api_router.include_router(posts.router)
api_router.include_router(media.router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
