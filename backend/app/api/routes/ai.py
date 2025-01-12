import asyncio
import json
import uuid
from io import BytesIO
from typing import Any, Literal, cast

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from openai import OpenAI
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.core.config import file_storage_settings, settings
from app.models import (
    FluxPro11UltraCreate,
    ImageGenerationResultStatus,
)
from app.models.image import (
    Image,
    ImageResult,
    Uploader,
)
from app.schemas.ai_content import DraftContentRequest, PostContent
from app.services.image_uploader import LocalImageUploader

router = APIRouter(prefix="/ai", tags=["generate images"])

FLUX_API_BASE_URL = "https://api.bfl.ml/v1"


@router.post("/generate-image")
async def generate_image(request: FluxPro11UltraCreate, session: SessionDep) -> Any:
    """
    Generate an image using the Flux AI API.
    """
    image_generation_response_dict = {
        ImageGenerationResultStatus.ERROR: [
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Image generation failed",
        ],
        ImageGenerationResultStatus.TASK_NOT_FOUND: [
            status.HTTP_404_NOT_FOUND,
            "Task not found",
        ],
        ImageGenerationResultStatus.REQUEST_MODERATED: [
            status.HTTP_400_BAD_REQUEST,
            "Request was moderated due to content policy",
        ],
        ImageGenerationResultStatus.CONTENT_MODERATED: [
            status.HTTP_400_BAD_REQUEST,
            "Generated content was moderated due to content policy",
        ],
        ImageGenerationResultStatus.PENDING: [status.HTTP_200_OK, "Pending"],
    }
    try:
        async with httpx.AsyncClient() as client:
            # Step 1: Start the image generation
            generation_response = await client.post(
                f"{FLUX_API_BASE_URL}/{request.model.value}",
                json=request.model_dump(),  # Convert Pydantic model to dict
                headers={
                    "Content-Type": "application/json",
                    "X-Key": settings.FLUX_API_KEY,
                },
            )
            generation_data = generation_response.json()
            task_id = generation_data.get("id")

            if not task_id:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to start image generation: {generation_data}",
                )

            # Step 2: Poll for results
            max_attempts = settings.IMAGE_GENERATION_POLL_MAX_ATTEMPTS
            attempt = 0
            while attempt < max_attempts:
                result_response = await client.get(
                    f"{FLUX_API_BASE_URL}/get_result?id={task_id}"
                )
                result_data = result_response.json()
                image_generation_status = result_data.get("status")
                logger.info(f"Image generation status: {image_generation_status}")

                match image_generation_status:
                    case ImageGenerationResultStatus.READY:
                        # Get the image data
                        image_url = result_data.get("result").get("sample")
                        filename = f"{str(task_id)}.{request.output_format}"
                        file_path = LocalImageUploader.get_file_path(filename)

                        # Download the image from the URL
                        async with httpx.AsyncClient() as client:
                            image_response = await client.get(image_url)
                            if image_response.status_code != 200:
                                raise HTTPException(
                                    status_code=500,
                                    detail=f"Failed to download image from {image_url}"
                                )
                            image_data = BytesIO(image_response.content)

                        # Create UploadFile with the downloaded image data
                        upload_file = UploadFile(
                            filename=filename,
                            file=image_data,
                            headers=image_response.headers
                        )

                        LocalImageUploader.save_file(file_path, upload_file)
                        image_url = f"{file_storage_settings.BASE_URL}/uploads/{filename}"

                        db_image = Image(
                            id=uuid.UUID(task_id),
                            filename=filename,
                            prompt=request.prompt,
                            model=request.model,
                            url=image_url,
                            provider=Uploader.LOCAL,
                        )
                        Image.model_validate(db_image)
                        session.add(db_image)
                        await session.commit()
                        await session.refresh(db_image)
                        return ImageResult(
                            id=task_id,
                            prompt=request.prompt,
                            model=request.model,
                            url=image_url,
                        )
                    case ImageGenerationResultStatus.PENDING:
                        # Continue polling
                        await asyncio.sleep(settings.IMAGE_GENERATION_POLL_WAIT_SECONDS)
                        attempt += 1
                        logger.info(f"Attempt: {attempt}")
                        continue
                    case (
                        ImageGenerationResultStatus.ERROR
                        | ImageGenerationResultStatus.TASK_NOT_FOUND
                        | ImageGenerationResultStatus.REQUEST_MODERATED
                        | ImageGenerationResultStatus.CONTENT_MODERATED
                    ):
                        status_code, message = image_generation_response_dict[status]
                        return Response(
                            content=message,
                            status_code=status_code,
                            media_type="text/plain",
                        )
                    case _:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Image generation failed: {result_data}",
                        )

            return Response(
                content="Timeout waiting for image generation",
                status_code=408,
                media_type="text/plain",
            )

    except Exception as e:
        return Response(
            content=f"Error generating image: {str(e)}",
            status_code=500,
            media_type="text/plain",
        )

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


@router.post("/generate-draft-content")
def generate_draft_content(
    content_request: DraftContentRequest,
    request: Request,
) -> StreamingResponse:
    def stream_content():
        client = cast(OpenAI, request.state.openai_client)
        logger.info(f"ROOT_DIR: {settings.ROOT_DIR}")
        with open(f"{settings.ROOT_DIR}/ai_prompts/content_draft.json") as f:
            prompt_template = json.load(f)

        prompt = (prompt_template["content"]
                 .replace("{{TONE}}", content_request.tone)
                 .replace("{{FORMAT}}", content_request.format)
                 .replace("{{STYLE}}", content_request.style))

        with client.beta.chat.completions.stream(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content_request.prompt}
            ],
            response_format=PostContent,
            max_completion_tokens=1000,
        ) as stream:
            for event in stream:
                if event.type == "content.delta":
                    if event.parsed is not None:
                        # Send just the parsed JSON without ID prefix
                        yield json.dumps(event.parsed) + "\n"
                elif event.type == "error":
                    yield json.dumps({"error": str(event.error)}) + "\n"
                elif event.type == "content.done":
                    yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(
        stream_content(),
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-data-stream": "v1"
        }
    )

