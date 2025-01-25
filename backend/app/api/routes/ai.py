from typing import Literal

from fastapi import APIRouter, Depends, Request

from app.api.deps import CurrentUser
from app.core.rate_limit import ai_protected_rate_limit, ai_public_rate_limit
from app.models import FluxPro11UltraCreate
from app.schemas.ai_content import DraftContentRequest
from app.services.ai_generator import AIGenerator

router = APIRouter(prefix="/ai", tags=["AI Generation"])

# Public routes with stricter rate limiting
@router.post("/public/generate-image")
@ai_public_rate_limit()
async def generate_image_public(
    request: Request,
    request_data: FluxPro11UltraCreate,
    ai_generator: AIGenerator = Depends()
):
    return await ai_generator.generate_image(request, request_data)

@router.post("/public/generate-draft-content")
@ai_public_rate_limit()
async def generate_draft_content_public(
    content_request: DraftContentRequest,
    request: Request,
    tone: Literal["article", "tutorial", "academic", "casual"] = "article",
    ai_generator: AIGenerator = Depends()
):
    return ai_generator.generate_draft_content(content_request, request, tone)

@router.post("/public/generate-sandbox-content")
@ai_public_rate_limit()
async def generate_sandbox_content_public(
    content_request: DraftContentRequest,
    request: Request,
    ai_generator: AIGenerator = Depends()
):
    return ai_generator.generate_sandbox_content(content_request, request)

# Protected routes with higher rate limits
@router.post("/private/generate-image")
@ai_protected_rate_limit()
async def generate_image_private(
    request: Request,
    request_data: FluxPro11UltraCreate,
    current_user: CurrentUser,  # noqa: ARG001
    ai_generator: AIGenerator = Depends()
):
    return await ai_generator.generate_image(request, request_data)

@router.post("/private/generate-draft-content")
@ai_protected_rate_limit()
async def generate_draft_content_private(
    content_request: DraftContentRequest,
    request: Request,
    current_user: CurrentUser,  # noqa: ARG001
    tone: Literal["article", "tutorial", "academic", "casual"] = "article",
    ai_generator: AIGenerator = Depends()
):
    return ai_generator.generate_draft_content(content_request, request, tone)

@router.post("/private/generate-sandbox-content")
@ai_protected_rate_limit()
async def generate_sandbox_content_private(
    content_request: DraftContentRequest,
    request: Request,
    current_user: CurrentUser,  # noqa: ARG001
    ai_generator: AIGenerator = Depends()
):
    return ai_generator.generate_sandbox_content(content_request, request)

@ai_protected_rate_limit()
@router.post("/private/moderate-content")
async def moderate_authenticated_content(
    request: Request,
    content: str,
    ai_generator: AIGenerator = Depends()
):
    return ai_generator.moderate_content(request, content)

@ai_public_rate_limit()
@router.post("/public/moderate-content")
async def moderate_public_content(
    request: Request,
    content: str,
    ai_generator: AIGenerator = Depends()
):
    return ai_generator.moderate_content(request, content)

