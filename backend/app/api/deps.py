import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = await session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


async def get_image_metadata(request: Request) -> dict:
    metadata = None

    try:
        id = request.path_params.get("id")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.FLUX_API_BASE_URL}/get_result",
                params={"id": id},
            )
        logger.info(f"response: {response.json()}")
        metadata = response.json().get("result", {})
        metadata["id"] = id
        metadata["url"] = metadata.get("sample", "")

        logger.info(f"metadata: {metadata}")
        return metadata
    except Exception as e:
        logger.error(f"Error getting image metadata: {e}")
        return metadata


ImageMetadata = Annotated[dict, Depends(get_image_metadata)]


async def get_media_metadata(
    prompt: str | None = None,
    id: uuid.UUID | None = None,
) -> dict:
    """Get metadata for media upload"""
    return {
        "prompt": prompt,
        "id": str(id) if id else None,
    }
