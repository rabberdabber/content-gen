import json
from typing import Literal

import google.generativeai as genai
import instructor
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.rate_limit import ai_protected_rate_limit, ai_public_rate_limit
from app.models import FluxPro11UltraCreate
from app.schemas.ai_content import DraftContentRequest, PostContent
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

genai.configure(api_key=settings.GEMINI_API_KEY)
client = instructor.from_gemini(
    client=genai.GenerativeModel(
        model_name="models/gemini-1.5-flash-latest",
    ),
)


@router.post("/public/generate-content-with-gemini")
@ai_public_rate_limit()
async def generate_content_with_gemini(
    request: Request,
    content_request: DraftContentRequest,
):
    stream = client.chat.completions.create_iterable(
        messages=[{
            "role": "user",
            "content": f"""
            Generate a blog post with the following prompt: {content_request.prompt}
            Make sure to include a title, content sections with headers, and a conclusion.
            """,
        }],
        response_model=PostContent,
    )

    async def content_generator():
        try:
            for chunk in stream:
                if chunk:
                    yield json.dumps(chunk.model_dump()) + "\n"
            yield json.dumps({"done": True}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(
        content_generator(),
         headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "x-vercel-ai-data-stream": "v1"
        }
    )


@router.post("/private/generate-content-with-gemini")
@ai_protected_rate_limit()
async def generate_content_with_gemini(
    request: Request,
    content_request: DraftContentRequest,
    current_user: CurrentUser,  # noqa: ARG001
):
    stream = client.chat.completions.create_iterable(
        messages=[{
            "role": "user",
            "content": f"""
            Generate a blog post with the following prompt: {content_request.prompt}
            Make sure to include a title, content sections with headers, and a conclusion.
            """,
        }],
        response_model=PostContent,
    )

    async def content_generator():
        try:
            for chunk in stream:
                if chunk:
                    yield json.dumps(chunk.model_dump()) + "\n"
            yield json.dumps({"done": True}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(
        content_generator(),
         headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "x-vercel-ai-data-stream": "v1"
        }
    )
