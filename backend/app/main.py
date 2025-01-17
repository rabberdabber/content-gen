import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from starlette.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import file_storage_settings, settings


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize OpenAI client on startup
    state = {"openai_client": OpenAI(api_key=settings.OPENAI_API_KEY)}
    yield state
    # Clean up on shutdown
    await state["openai_client"].close()

if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

# Ensure upload directory exists
Path(file_storage_settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

app.mount(
    "/uploads",
    StaticFiles(directory=file_storage_settings.UPLOAD_DIR),
    name="uploads",
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

security = HTTPBasic()

@app.get("/", tags=["root"])
async def root():
    return {"message": "Hello From ContentGen"}

@app.get("/favicon.ico", tags=["favicon"])
async def favicon():
    return FileResponse(file_storage_settings.UPLOAD_DIR + "/logo.svg")

@app.get("/docs", tags=["docs"])
async def docs(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, settings.FIRST_SUPERUSER)
    correct_password = secrets.compare_digest(credentials.password, settings.FIRST_SUPERUSER_PASSWORD)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")

@app.get("/openapi.json", tags=["openapi"])
async def openapi(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, settings.FIRST_SUPERUSER)
    correct_password = secrets.compare_digest(credentials.password, settings.FIRST_SUPERUSER_PASSWORD)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return get_openapi(title=settings.PROJECT_NAME, version="1.0.0", routes=app.routes)

app.include_router(api_router, prefix=settings.API_V1_STR)
