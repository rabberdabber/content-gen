import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from io import BytesIO
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from loguru import logger
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletion
from pydantic import BaseModel
from pydantic_ai import Agent

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

# Content node models
class TextNode(BaseModel):
    type: Literal["text"]
    text: str

class ImageNode(BaseModel):
    type: Literal["image"]
    src: str
    alt: str

class CodeBlockNode(BaseModel):
    type: Literal["codeBlock"]
    content: TextNode

class HeadingAttributes(BaseModel):
    textAlign: Literal["left"]
    level: Literal[1, 2, 3, 4, 5, 6]

class ParagraphAttributes(BaseModel):
    textAlign: Literal["left"]

class ParagraphNode(BaseModel):
    type: Literal["paragraph"]
    attrs: ParagraphAttributes
    content: list[TextNode]


class HeadingNode(BaseModel):
    type: Literal["heading"]
    attrs: HeadingAttributes
    content: list[TextNode]

class ListItemNode(BaseModel):
    type: Literal["listItem"]
    content: ParagraphNode

class OrderedListNode(BaseModel):
    type: Literal["orderedList"]
    content: ListItemNode

class BlogContent(BaseModel):
    type: Literal["doc"]
    content: list[HeadingNode | ParagraphNode]

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class ContentRequest(BaseModel):
    # messages: list[Message]
    prompt: str
    style: str | None = "blog post"
    tone: Literal["professional", "casual", "academic"] = "professional"
    format: Literal["article", "chat", "tutorial"] = "article"

def inject_attributes(node: dict) -> dict:
    """
    Inject the appropriate attributes based on node type.
    """
    node_type = node["type"]

    if node_type == "heading":
        node["attrs"] = {"level": 1, "textAlign": "left"}

    elif node_type == "paragraph":
        node["attrs"] = {"textAlign": "left"}

    elif node_type == "image":
        node["attrs"] = {
            "src": node.pop("src"),  # Move src to attrs
            "alt": node.pop("alt"),  # Move alt to attrs
            "title": None,
            "width": 700,
            "height": 400
        }

    elif node_type == "codeBlock":
        node["attrs"] = {"language": "python"}

    elif node_type == "orderedList":
        node["attrs"] = {"start": 1}

    elif node_type == "listItem":
        node["attrs"] = {"color": ""}

    # Recursively process content
    if "content" in node:
        node["content"] = [inject_attributes(child) for child in node["content"]]

    return node


@router.post("/generate-content")
async def generate_content(request: ContentRequest) -> StreamingResponse:
    """
    Generate structured blog content using GPT-4 with streaming response.
    Compatible with Vercel AI SDK, using data stream protocol.
    """
    async def content_stream() -> AsyncGenerator[str, None]:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        base_system_message = {
            "role": "system",
            "content": f"""You are a {request.tone} content creator.
            Generate content in a {request.format} format using a {request.style} style and prompt: {request.prompt}.
            
            For articles and tutorials, include:
            - A clear heading
            - Well-structured paragraphs
            - Ordered lists where appropriate
            - Code blocks when relevant
            """
        }

        messages = [base_system_message]
        index = 1

        try:
            async with client.beta.chat.completions.stream(
                model="gpt-4o-2024-08-06",
                messages=messages,
                response_format=BlogContent,
            ) as stream:
                async for event in stream:
                    if event.type == "content.delta":
                        if event.parsed and hasattr(event.parsed, "content"):
                            logger.info(f"content {index}: {event.parsed.content}")
                            index += 1
                            for node in event.parsed.content:
                                node_dict = node.model_dump()
                                processed_node = inject_attributes(node_dict)
                                # Data stream format: 2:Array<JSONValue>\n
                                yield f"{json.dumps(processed_node)}\n"

                    elif event.type == "content.done":
                        final_completion: ChatCompletion = await stream.get_final_completion()
                        # final_content: BlogContent = final_completion.choices[0].message.parsed

                        # for node in final_content.content:
                        #     node_dict = node.model_dump()
                        #     processed_node = inject_attributes(node_dict)
                        #     yield f"0:{json.dumps(processed_node)}\n"

                        # Send finish message with metadata
                        finish_data = {
                            "finishReason": "stop",
                        }
                        yield f"d:{json.dumps(finish_data)}\n"

        except Exception as e:
            logger.exception("Error generating content")
            # Error stream format: 3:string\n
            yield f'3:"{str(e)}"\n'

    return StreamingResponse(
        content_stream(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-data-stream": "v1"
        }
    )

client = OpenAI()
class EntitiesModel(BaseModel):
    attributes: list[str]
    colors: list[str]
    animals: list[str]


@router.post("/generate-content-v2")
def generate_content_v2(request: ContentRequest) -> StreamingResponse:
    def stream_content():
        id = 1
        with client.beta.chat.completions.stream(
            model="gpt-4o-2024-08-06",
            messages=[
            {"role": "system", "content": f"""You are a {request.tone} content creator.
            Generate content in a {request.format} format using a {request.style} style.
            The content should not be longer than 300 words.

            For articles and tutorials, include:
            - A clear heading
            - Well-structured paragraphs
            """},
            {"role": "user", "content": request.prompt}
        ],
            response_format=BlogContent,
            max_completion_tokens=1000,
            ) as stream:
            for event in stream:
                    if event.type == "content.delta":
                        if event.parsed is not None:
                            # Print the parsed data as JSON
                            yield f"{id}:{json.dumps(event.parsed)}\n"
                            id += 1
                    elif event.type == "content.done":
                        yield f"d:{json.dumps({'finishReason': 'stop'})}\n"
                    elif event.type == "error":
                        yield f"3:{json.dumps(str(event.error))}\n"

    # agent = Agent('openai:gpt-4o-2024-08-06', result_type=BlogContent, system_prompt=f"""You are a {request.tone} content creator.
    #             Generate content in a {request.format} format using a {request.style} style and prompt: {request.prompt}.
    #             For articles and tutorials, include:
    #             - A clear heading
    #             - Well-structured paragraphs
    #             - Ordered lists where appropriate
    #             - Code blocks when relevant
    #             """)
    #     }
    # async def generate_content_stream():
    #     async with agent.run_stream(
    #         "How to implement a basic CRUD API in Python using FastAPI. Include the id, step, and code for each step.",
    #     ) as result:
    #         async for message, last in result.stream_structured(debounce_by=0.1):
    #             logger.info(f"message: {message}")
    #             try:
    #                 content = await result.validate_structured_result(message, allow_partial=not last)
    #                 for partial_content in content:
    #                     print(partial_content)
    #                     yield f"{partial_content}\n"
    #             except Exception as e:
    #                 logger.exception(f"Error validating structured result: {e}")
    #                 yield

    return StreamingResponse(
        stream_content(),
        # generate_content_stream(),
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-data-stream": "v1"
        }
    )

@router.post("/generate-content-v3")
def generate_content_v3(request: ContentRequest):
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=[
            {"role": "system", "content": f"""You are a {request.tone} content creator.
            Generate content in a {request.format} format using a {request.style} style.

            For articles and tutorials, include:
            - A clear heading
            - Well-structured paragraphs
            - Ordered lists where appropriate
            - Code blocks when relevant
            """},
            {"role": "user", "content": request.prompt}
        ],
        response_format=BlogContent,
    )

    output = completion.choices[0].message.parsed
    return output
