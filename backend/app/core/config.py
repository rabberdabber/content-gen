import pathlib
import secrets
import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class FileStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    UPLOAD_DIR: str = str(pathlib.Path(__file__).parent.parent / "uploads")
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set[str] = {"png", "jpg", "jpeg", "gif", "mp4", "webp"}
    MINIO_BASE_URL: str = "http://localhost:9000"
    MINIO_API_BASE_URL: str = "http://minio:9000"
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_BUCKET_NAME: str
    SIGNED_URL_EXPIRATION: int = 3600  # 1 hour in seconds


class EmailSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_TOKEN: str
    EMAILS_FROM_EMAIL: str
    SMTP_STARTTLS: bool
    SMTP_STARTSSL: bool

class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    REDIS_URL: str

    # Rate limiting settings
    RATE_LIMIT_LOGIN_MINUTE: int = 5
    RATE_LIMIT_LOGIN_HOUR: int = 20

    # Public AI rate limits (unauthenticated)
    PUBLIC_RATE_LIMIT_AI_MINUTE: int = 2
    PUBLIC_RATE_LIMIT_AI_HOUR: int = 5

    # Protected AI rate limits (authenticated)
    PROTECTED_RATE_LIMIT_AI_MINUTE: int = 5
    PROTECTED_RATE_LIMIT_AI_HOUR: int = 10


    @model_validator(mode="after")
    def _check_redis_url(self) -> Self:
        if not self.REDIS_URL.startswith("redis://"):
            raise ValueError("REDIS_URL must start with 'redis://'")
        return self

class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_HOST: str = "http://localhost:3000"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    SERVER_HOST: str = "http://localhost:8000"

    BACKEND_CORS_ORIGINS: Annotated[list[AnyUrl] | str, BeforeValidator(parse_cors)] = (
        []
    )
    ALLOWED_HOSTS: Annotated[list[str] | str, BeforeValidator(parse_cors)] = (
        []
    )
    FLUX_API_BASE_URL: str = "https://api.bfl.ml/v1"
    FLUX_API_KEY: str
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str
    IMAGE_GENERATION_POLL_MAX_ATTEMPTS: int = 30
    IMAGE_GENERATION_POLL_WAIT_SECONDS: float = 0.3
    ROOT_DIR: str = str(pathlib.Path(__file__).parent.parent)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.FRONTEND_HOST
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_allowed_hosts(self) -> list[str]:
        return self.ALLOWED_HOSTS

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    # TODO: update type to EmailStr when sqlmodel supports it
    EMAILS_FROM_EMAIL: str | None = None
    EMAILS_FROM_NAME: str | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    # TODO: update type to EmailStr when sqlmodel supports it
    EMAIL_TEST_USER: str = "test@example.com"
    # TODO: update type to EmailStr when sqlmodel supports it
    FIRST_SUPERUSER: str
    FIRST_SUPERUSER_PASSWORD: str

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
file_storage_settings = FileStorageSettings()  # type: ignore
email_settings = EmailSettings()  # type: ignore
redis_settings = RedisSettings()  # type: ignore
database_settings = DatabaseSettings()  # type: ignore
