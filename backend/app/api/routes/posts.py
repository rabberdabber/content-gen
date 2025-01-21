from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import (
    Post,
    PostCreate,
    PostPublic,
    PostPublicWithContent,
    PostsPublic,
    PostUpdate,
    User,
)
from app.schemas import TiptapDoc

router = APIRouter(prefix="/posts", tags=["posts"])
router_drafts = APIRouter(prefix="/drafts", tags=["drafts"])


@router.post("/",) #response_model=PostPublic)
async def create_post(
    *,
    session: SessionDep,
    post_in: PostCreate,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Create new post.
    """
    # Convert post_in to dict and handle TiptapDoc serialization
    logger.info(f"Post in: {post_in}")
    post_create_data = PostCreate.model_validate(post_in)
    post_create_data.content = TiptapDoc.model_validate(post_create_data.content)
    post_data = post_create_data.model_dump()
    logger.info(f"Post data: {post_data}")
    post = Post(**post_data, author_id=current_user.id)
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post_data


@router.get("/", response_model=PostsPublic)
async def read_posts(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    tag: str | None = None,
    published: bool = True,
) -> Any:
    """
    Retrieve posts.
    """
    query = select(Post)
    if tag:
        query = query.where(Post.tag == tag)
    if published:
        query = query.where(Post.is_published == published)
    else:
        query = query.where(Post.is_published == False)  # noqa: E712  draft posts

    count_statement = select(func.count()).select_from(query)
    count = await session.scalar(count_statement)

    statement = query.offset(skip).limit(limit)
    posts = await session.scalars(statement)
    return PostsPublic(data=posts, count=count)


@router.get("/me", response_model=PostsPublic)
async def read_published_posts(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    tag: str | None = None,
    published: bool = True,
) -> Any:
    """
    Retrieve posts.
    """
    query = select(Post).where(Post.author_id == current_user.id)
    if tag:
        query = query.where(Post.tag == tag)
    if published:
        query = query.where(Post.is_published == published)
    else:
        query = query.where(Post.is_published == False)  # noqa: E712  draft posts

    count_statement = select(func.count()).select_from(query)
    count = await session.scalar(count_statement)

    statement = query.offset(skip).limit(limit)
    posts = await session.scalars(statement)
    return PostsPublic(data=posts, count=count)


@router_drafts.get("/", response_model=PostsPublic)
async def read_drafts(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    tag: str | None = None,
) -> Any:
    """
    Retrieve posts.
    """
    query = select(Post).where(Post.author_id == current_user.id, Post.is_published == False)  # noqa: E712  draft posts
    if tag:
        query = query.where(Post.tag == tag)


    count_statement = select(func.count()).select_from(query)
    count = await session.scalar(count_statement)

    statement = query.offset(skip).limit(limit)
    posts = await session.scalars(statement)
    return PostsPublic(data=posts, count=count)


@router_drafts.get("/{draft_id}", response_model=PostPublicWithContent)
async def read_draft(
    session: SessionDep,
    current_user: CurrentUser,
    draft_id: UUID,
) -> Any:
    """
    Retrieve draft.
    """
    query = select(Post).where(Post.author_id == current_user.id, Post.is_published == False, Post.id == draft_id)  # noqa: E712  draft posts


    draft = await session.scalar(query)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("/{post_id}", response_model=PostPublicWithContent)
async def read_post(
    *,
    session: SessionDep,
    post_id: UUID,
) -> Any:
    """
    Get post by ID.
    """
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.put("/{post_id}", response_model=PostPublic)
async def update_post(
    *,
    session: SessionDep,
    post_id: UUID,
    post_in: PostUpdate,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Update a post.
    """
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Only update fields that were actually passed
    update_data = post_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post


@router.delete("/{post_id}")
async def delete_post(
    *,
    session: SessionDep,
    post_id: UUID,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Delete a post.
    """
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    await session.delete(post)
    await session.commit()
    return {"ok": True}


@router.delete("/")
async def delete_all_posts(
    *,
    session: SessionDep,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Delete all posts.
    """
    query = select(Post)
    posts = await session.exec(query)
    for post in posts:
        await session.delete(post)
    await session.commit()
    return {"ok": True}
