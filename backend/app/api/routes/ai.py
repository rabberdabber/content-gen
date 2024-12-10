import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Response, status
from loguru import logger

from app.core.config import settings
from app.models import (
    ImageCreate,
    ImageGenerationResultStatus,
)
from app.models.image import ImageResult

router = APIRouter(prefix="/ai", tags=["generate images"])

FLUX_API_BASE_URL = "https://api.bfl.ml/v1"


@router.post("/generate-image")
async def generate_image(request: ImageCreate) -> Any:
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
