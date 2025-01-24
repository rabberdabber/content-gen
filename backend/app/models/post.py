import uuid
from datetime import datetime, timezone
from typing import List

import sqlalchemy as sa
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from app.models.user import UserPublic
from app.schemas import TiptapDoc


class PostBase(SQLModel):
    title: str = Field(max_length=255, min_length=1)
    tags: list[str] | None = Field(default_factory=list)
    is_published: bool = Field(default=False)
    excerpt: str | None = Field(default=None, max_length=500)


class PostCreate(SQLModel):
    content: TiptapDoc = Field(sa_column=Column(JSON))
    title: str = Field(max_length=255, min_length=1)
    tags: list[str] | None = Field(default_factory=list)
    is_published: bool = Field(default=False)
    excerpt: str | None = Field(default=None, max_length=500)
    feature_image_url: str | None = Field(default=None, max_length=100)


class PostUpdate(SQLModel):
    content: TiptapDoc | None = Field(default=None)
    title: str | None = Field(default=None, max_length=255, min_length=1)
    tags: list[str] | None = Field(default=None)
    is_published: bool | None = None
    excerpt: str | None = Field(default=None, max_length=500)


class PostTag(SQLModel, table=True):
    __tablename__ = "post_tag"
    __table_args__ = (
        sa.Index("ix_post_tag_post_id", "post_id"),
        sa.Index("ix_post_tag_tag_id", "tag_id"),
    )

    post_id: uuid.UUID = Field(
        foreign_key="post.id",
        primary_key=True
    )
    tag_id: uuid.UUID = Field(
        foreign_key="tag.id",
        primary_key=True
    )


class TagCreate(SQLModel):
    """Schema for creating a new tag"""
    name: str = Field(max_length=50, min_length=1)


class TagResponse(SQLModel):
    """Response model for Tag data"""
    id: uuid.UUID
    name: str = Field(max_length=50)
    post_count: int | None = None


class Tag(SQLModel, table=True):
    __tablename__ = "tag"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(
        max_length=50, 
        index=True, 
        unique=True,
        nullable=False
    )

    # Relationship back to posts
    posts: List["Post"] = Relationship(
        back_populates="tags",
        link_model=PostTag
    )


class Post(SQLModel, table=True):
    __tablename__ = "post"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    content: dict = Field(
        sa_type=JSON,
        description="JSON content of the post in Tiptap format"
    )
    title: str = Field(max_length=255, min_length=1, unique=True)
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

    # Relationship to tags
    tags: list[Tag] = Relationship(
        back_populates="posts",
        link_model=PostTag
    )


class PostPublic(SQLModel):
    id: uuid.UUID
    title: str
    tags: list[str] | None = None
    is_published: bool
    excerpt: str | None = None
    created_at: datetime
    updated_at: datetime
    author_id: uuid.UUID
    feature_image_url: str | None = None


class PostPublicWithContent(PostPublic):
    content: TiptapDoc
    author: UserPublic | None = None


class PostsPublic(SQLModel):
    data: list[PostPublic]
    count: int
