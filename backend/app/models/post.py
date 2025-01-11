import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import JSON, Column, Field, SQLModel

from app.schemas import TiptapDoc


class PostBase(SQLModel):
    title: str = Field(max_length=255, min_length=1)
    tag: str | None = Field(default=None, max_length=50)
    is_published: bool = Field(default=False)
    excerpt: str | None = Field(default=None, max_length=500)


class PostCreate(SQLModel):
    content: TiptapDoc = Field(sa_column=Column(JSON))
    title: str = Field(max_length=255, min_length=1)
    tag: str | None = Field(default=None, max_length=50)
    is_published: bool = Field(default=False)
    excerpt: str | None = Field(default=None, max_length=500)
    feature_image_url: str | None = Field(default=None, max_length=100)


class PostUpdate(SQLModel):
    content: TiptapDoc | None = Field(default=None)
    title: str | None = Field(default=None, max_length=255, min_length=1)
    tag: str | None = Field(default=None, max_length=50)
    is_published: bool | None = None
    excerpt: str | None = Field(default=None, max_length=500)


class Post(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    content: dict = Field(  # Store as raw JSON in database
        sa_type=JSON,
        description="JSON content of the post in Tiptap format"
    )
    title: str = Field(max_length=255, min_length=1)
    tag: str | None = Field(default=None, max_length=50)
    is_published: bool = Field(default=False)
    excerpt: str | None = Field(default=None, max_length=500)
    feature_image_url: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    updated_at: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )
    author_id: uuid.UUID = Field(foreign_key="user.id")


class PostPublic(SQLModel):
    id: uuid.UUID
    content: TiptapDoc
    title: str
    tag: str | None = None
    is_published: bool
    excerpt: str | None = None
    created_at: datetime
    updated_at: datetime
    author_id: uuid.UUID
    feature_image_url: str | None = None


class PostsPublic(SQLModel):
    data: list[PostPublic]
    count: int
