import asyncio
import json
from collections.abc import AsyncIterator
from io import BytesIO
from typing import Any, Literal, cast

import httpx
from fastapi import HTTPException, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from openai import OpenAI

from app.core.config import settings
from app.models import (
    FluxPro11UltraCreate,
    ImageGenerationResultStatus,
    ImageResult,
)
from app.models.media import MediaType
from app.schemas.ai_content import DraftContentRequest, PostContent
from app.services.s3_uploader import S3MediaUploader


class AIGenerator:
    def __init__(self):
        self.FLUX_API_BASE_URL = "https://api.bfl.ml/v1"
        self.STATUS_RESPONSES = {
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

    async def generate_image(
        self,
        request: Request,
        request_data: FluxPro11UltraCreate
    ) -> Any:
        """Generate an image using the Flux AI API."""
        try:
            async with httpx.AsyncClient() as client:
                task_id = await self._start_image_generation(client, request_data)
                return await self._poll_generation_status(client, task_id, request_data)
        except Exception as e:
            logger.error(f"Error generating image: {str(e)}")
            return Response(
                content=f"Error generating image: {str(e)}",
                status_code=500,
                media_type="text/plain",
            )

    def generate_draft_content(
        self,
        content_request: DraftContentRequest,
        request: Request,
        tone: Literal["article", "tutorial", "academic", "casual"] = "article",
    ) -> StreamingResponse:
        """Generate draft content using OpenAI."""
        return StreamingResponse(
            self._stream_content(content_request, request, tone),
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "x-vercel-ai-data-stream": "v1"
            }
        )

    # Private methods
    async def _start_image_generation(
        self,
        client: httpx.AsyncClient,
        request: FluxPro11UltraCreate
    ) -> str:
        response = await client.post(
            f"{self.FLUX_API_BASE_URL}/{request.model.value}",
            json=request.model_dump(),
            headers={
                "Content-Type": "application/json",
                "X-Key": settings.FLUX_API_KEY,
            },
        )
        data = response.json()
        task_id = data.get("id")

        if not task_id:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start image generation: {data}",
            )
        return task_id

    async def _poll_generation_status(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        request_data: FluxPro11UltraCreate
    ) -> Any:
        attempt = 0
        while attempt < settings.IMAGE_GENERATION_POLL_MAX_ATTEMPTS:
            status, result_data = await self._check_generation_status(client, task_id)
            logger.info(f"Image generation status: {status}")

            match status:
                case ImageGenerationResultStatus.READY:
                    image_url = result_data.get("result", {}).get("sample")
                    return await self._handle_ready_status(task_id, request_data, image_url, client)
                case ImageGenerationResultStatus.PENDING:
                    await asyncio.sleep(settings.IMAGE_GENERATION_POLL_WAIT_SECONDS)
                    attempt += 1
                    continue
                case (
                    ImageGenerationResultStatus.ERROR |
                    ImageGenerationResultStatus.TASK_NOT_FOUND |
                    ImageGenerationResultStatus.REQUEST_MODERATED |
                    ImageGenerationResultStatus.CONTENT_MODERATED
                ):
                    status_code, message = self.STATUS_RESPONSES[status]
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

    def _stream_content(
        self,
        content_request: DraftContentRequest,
        request: Request,
        tone: str
    ) -> AsyncIterator[str]:
        client = cast(OpenAI, request.state.openai_client)
        with open(f"{settings.ROOT_DIR}/ai_prompts/content_draft.json") as f:
            prompt_template = json.load(f)

        prompt = prompt_template["content"].replace("{{TONE}}", tone)

        with client.beta.chat.completions.stream(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content_request.prompt}
            ],
            response_format=PostContent,
            max_completion_tokens=2000,
            temperature=0.5,
        ) as stream:
            for event in stream:
                if event.type == "content.delta":
                    if event.parsed is not None:
                        yield json.dumps(event.parsed) + "\n"
                elif event.type == "error":
                    yield json.dumps({"error": str(event.error)}) + "\n"
                elif event.type == "content.done":
                    yield json.dumps({"done": True}) + "\n"
    
    async def moderate_content(
        self,
        request: Request,
        content: str
    ) -> Any:
        pass

    async def _check_generation_status(
        self,
        client: httpx.AsyncClient,
        task_id: str,
    ) -> tuple[str, dict]:
        """Check the status of image generation"""
        response = await client.get(
            f"{self.FLUX_API_BASE_URL}/get_result?id={task_id}"
        )
        result_data = response.json()
        return result_data.get("status"), result_data

    async def _download_generated_image(
        self,
        client: httpx.AsyncClient,
        image_url: str
    ) -> tuple[bytes, str]:
        """Download the generated image from the given URL and return content and content type"""
        response = await client.get(image_url)
        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download image from {image_url}"
            )
        content_type = response.headers.get("content-type") or "image/jpeg"
        logger.info(f"Content type: {content_type}")
        return response.content, content_type

    async def _upload_to_s3(
        self,
        image_content: bytes,
        filename: str,
        content_type: str,
        metadata: dict
    ) -> dict:
        """Upload the image to S3 storage"""
        logger.info(f"Uploading to S3: {filename} with content type {content_type}")
        upload_file = UploadFile(
            filename=filename,
            file=BytesIO(image_content),
            headers={
                "Content-Type": content_type
            }
        )

        uploader = S3MediaUploader()
        return await uploader.upload_media(upload_file, metadata)

    async def _handle_ready_status(
        self,
        task_id: str,
        request_data: FluxPro11UltraCreate,
        image_url: str,
        client: httpx.AsyncClient
    ) -> ImageResult:
        """Handle the READY status of image generation"""
        # Download the generated image
        image_content, content_type = await self._download_generated_image(client, image_url)

        # Prepare for S3 upload
        filename = f"{str(task_id)}.{request_data.output_format}"
        metadata = {
            "id": task_id,
            "prompt": request_data.prompt,
            "model": request_data.model.value,
            "media_type": MediaType.IMAGE.value
        }

        # Upload to S3
        upload_result = await self._upload_to_s3(
            image_content,
            filename,
            content_type,
            metadata
        )

        return ImageResult(
            id=task_id,
            prompt=request_data.prompt,
            model=request_data.model,
            url=upload_result["url"],
        )
