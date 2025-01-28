from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.orm import selectinload
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.models import (
    Post,
    PostCreate,
    PostPublic,
    PostPublicWithContent,
    PostsPublic,
    PostTag,
    PostUpdate,
    Tag,
    TagCreate,
    TagResponse,
    User,
    UserPublic,
)
from app.models.dashboard import DashboardStats, PopularTag, TagDistribution, UserDashboardInfo
from app.schemas import TiptapDoc

router = APIRouter(prefix="/posts", tags=["posts"])
router_drafts = APIRouter(prefix="/drafts", tags=["drafts"])

@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    *,
    session: SessionDep,
    tag_in: TagCreate,
    current_user: CurrentUser,
) -> Any:
    """
    Create a new tag.
    Only superusers can create new tags to maintain consistency.
    """
    # Check if tag with same name already exists
    statement = select(Tag).where(func.lower(Tag.name) == func.lower(tag_in.name))
    existing_tag = await session.scalar(statement)

    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tag with name '{tag_in.name}' already exists"
        )

    # Create new tag
    tag = Tag(name=tag_in.name)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)

    return tag

@router.get("/tags", response_model=list[TagResponse])
async def read_tags(
    session: SessionDep,
) -> Any:
    """
    Get all available tags.
    Returns a list of tags sorted alphabetically by name.
    and also includes the count of posts for each tag.
    """
    statement = (
        select(Tag, func.count(PostTag.post_id).label("post_count"))
        .outerjoin(PostTag)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    results = await session.execute(statement)
    return [
        TagResponse(**tag.model_dump(), post_count=count)
        for tag, count in results
    ]

@router.post("/", response_model=PostPublic)
async def create_post(
    *,
    session: SessionDep,
    post_in: PostCreate,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    Create new post.
    If tags don't exist, they will be created automatically.
    """
    # Convert post_in to dict and handle TiptapDoc serialization
    logger.info(f"Post in: {post_in}")
    post_create_data = PostCreate.model_validate(post_in)
    post_create_data.content = TiptapDoc.model_validate(post_create_data.content)
    post_data = post_create_data.model_dump()

    # Handle tags
    tags = []
    if post_data.get("tags"):
        for tag_name in post_data["tags"]:
            # Check if tag exists
            statement = select(Tag).where(func.lower(Tag.name) == func.lower(tag_name))
            existing_tag = await session.scalar(statement)

            if existing_tag:
                tags.append(existing_tag)
            else:
                # Create new tag
                new_tag = Tag(name=tag_name)
                tags.append(new_tag)

    # Remove tags from post_data as we'll handle them separately
    post_data.pop("tags", None)
    logger.info(f"Tags: {tags}")
    # Create post
    post = Post(**post_data, author_id=current_user.id, tags=tags)
    post_public = PostPublic.model_validate(post)

    session.add(post)
    await session.commit()
    await session.refresh(post)
    logger.info(f"Post created: {post.model_dump()}")
    return post_public


@router.get("/", response_model=PostsPublic)
async def read_posts(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    tags: list[str] | None = Query(None),  # Accept multiple tag names
) -> Any:
    """
    Retrieve posts.
    Parameters:
        - tags: Optional list of tag names to filter posts
        - skip: Number of posts to skip (pagination)
        - limit: Maximum number of posts to return
    """
    # Base query
    query = select(Post).options(selectinload(Post.tags)).where(Post.is_published == True)

    # Add tag filter if specified
    if tags:
        # Join with tags and filter where tag name is in the provided list
        query = (
            query
            .join(Post.tags)
            .where(Tag.name.in_(tags))
            # If multiple tags specified, ensure post has all tags
            .group_by(Post.id)
            .having(func.count(Tag.id) == len(tags))
        )

    # Get total count
    count_statement = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_statement)

    # Get paginated results
    statement = (
        query
        .offset(skip)
        .limit(limit)
        .order_by(Post.created_at.desc())
    )
    posts = await session.scalars(statement)

    return PostsPublic(
        data=posts,
        count=total
    )


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
    query = select(Post).options(selectinload(Post.tags)).where(Post.author_id == current_user.id)
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
    query = select(Post).options(selectinload(Post.tags)).where(Post.author_id == current_user.id, Post.is_published == False)  # noqa: E712  draft posts
    if tag:
        query = query.where(Post.tag == tag)


    count_statement = select(func.count()).select_from(query)
    count = await session.scalar(count_statement)

    statement = query.offset(skip).limit(limit)
    posts = await session.scalars(statement)
    posts_public = [PostPublic.model_validate(post) for post in posts]
    return PostsPublic(data=posts_public, count=count)

@router_drafts.get("/by-slug/{slug}", response_model=PostPublicWithContent)
async def read_draft_by_slug(
    session: SessionDep,
    current_user: CurrentUser,
    slug: str,
) -> Any:
    """
    Retrieve draft.
    """
    query = select(Post).options(selectinload(Post.tags)).where(Post.author_id == current_user.id, Post.is_published == False, Post.slug == slug)  # noqa: E712  draft posts


    draft = await session.scalar(query)
    draft_public = PostPublicWithContent.model_validate(draft)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft_public

@router_drafts.get("/{draft_id}", response_model=PostPublicWithContent)
async def read_draft(
    session: SessionDep,
    current_user: CurrentUser,
    draft_id: UUID,
) -> Any:
    """
    Retrieve draft.
    """
    query = select(Post).options(selectinload(Post.tags)).where(Post.author_id == current_user.id, Post.is_published == False, Post.id == draft_id)  # noqa: E712  draft posts


    draft = await session.scalar(query)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("/{post_title}", response_model=PostPublicWithContent)
async def read_post(
    *,
    session: SessionDep,
    post_title: str,
) -> Any:
    """
    Get post by ID.
    """
    post = select(Post).options(selectinload(Post.tags)).where(Post.title == post_title)
    post = await session.scalar(post)
    author = await session.get(User, post.author_id)
    post_public = PostPublicWithContent.model_validate(post)
    post_public.author = UserPublic.model_validate(author)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post_public


@router.get("/by-slug/{slug}", response_model=PostPublicWithContent)
async def read_post_by_slug(
    *,
    session: SessionDep,
    slug: str,
) -> Any:
    """
    Get post by slug.
    """
    post = select(Post).options(selectinload(Post.tags)).where(Post.slug == slug)
    post = await session.scalar(post)
    logger.info(f"Post: {post}")
    author = await session.get(User, post.author_id)
    post_public = PostPublicWithContent.model_validate(post)
    post_public.author = UserPublic.model_validate(author)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post_public


@router.patch("/{post_id}", response_model=PostPublic)
async def update_post(
    *,
    session: SessionDep,
    post_id: UUID,
    post_in: PostUpdate,
    current_user: CurrentUser,
) -> Any:
    """
    Update a post.
    """
    post = select(Post).options(selectinload(Post.tags)).where(Post.id == post_id)
    post = await session.scalar(post)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Only update fields that were actually passed
    update_data = post_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        logger.info(f"going to update {field} with {value}")
        setattr(post, field, value)

    post_public = PostPublic.model_validate(post)
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post_public


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

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Get dashboard statistics including:
    - User info
    - Total posts count
    - Current user's posts count
    - Current user's drafts count
    - Popular tags (top 5)
    - Tag distribution
    """
    # Create user info
    user_info = UserDashboardInfo(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        is_superuser=current_user.is_superuser
    )

    # Get total posts count (published only)
    total_posts_query = select(func.count()).select_from(
        select(Post).options(selectinload(Post.tags)).where(Post.is_published == True).subquery()  # noqa: E712
    )
    total_posts = await session.scalar(total_posts_query)

    # Get current user's posts count
    user_posts_query = select(func.count()).select_from(
        select(Post).options(selectinload(Post.tags)).where(
            Post.author_id == current_user.id,
            Post.is_published == True  # noqa: E712
        ).subquery()
    )
    user_posts = await session.scalar(user_posts_query)

    # Get current user's drafts count
    user_drafts_query = select(func.count()).select_from(
        select(Post).options(selectinload(Post.tags)).where(
            Post.author_id == current_user.id,
            Post.is_published == False  # noqa: E712
        ).subquery()
    )
    user_drafts = await session.scalar(user_drafts_query)

    # Get popular tags (top 5)
    popular_tags_query = (
        select(Tag.name, func.count(PostTag.post_id).label("count"))
        .join(PostTag)
        .join(Post)
        .where(Post.is_published == True)  # noqa: E712
        .group_by(Tag.id)
        .order_by(func.count(PostTag.post_id).desc())
        .limit(5)
    )
    popular_tags_result = await session.exec(popular_tags_query)
    popular_tags = [
        PopularTag(name=name, count=count)
        for name, count in popular_tags_result
    ]

    # Get tag distribution
    tag_distribution_query = (
        select(Tag.name, func.count(PostTag.post_id).label("count"))
        .join(PostTag)
        .join(Post)
        .where(Post.is_published == True)  # noqa: E712
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    tag_distribution_result = await session.exec(tag_distribution_query)
    tag_distribution = [
        TagDistribution(name=name, count=count)
        for name, count in tag_distribution_result
    ]

    return DashboardStats(
        user=user_info,
        total_posts=total_posts,
        user_posts=user_posts,
        user_drafts=user_drafts,
        popular_tags=popular_tags,
        tag_distribution=tag_distribution
    )

