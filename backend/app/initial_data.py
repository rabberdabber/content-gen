import asyncio
import json
import logging
import pathlib

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.db import engine, init_db
from app.models.post import Post
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



async def create_100_posts():
    with open(pathlib.Path(__file__).parent / "sample_demo.json") as f:
        POST_CONTENT = json.load(f)
    async with AsyncSession(engine) as session:
        posts = []
        super_user = (await session.execute(select(User).where(User.email == settings.FIRST_SUPERUSER))).scalar_one()
        for i in range(13, 113):
            post = Post(
                content=POST_CONTENT,
                title=f"Post #{i}",
                slug=f"post-{i}",
                is_published=True,
                excerpt="This is an example excerpt",
                author_id=super_user.id,
                feature_image_url="http://localhost:9000/uploads/fdc94ee0-68e0-45af-b761-33ed75c5de6c.jpg",
            )
            posts.append(post)

        session.add_all(posts)
        await session.commit()
        print("Successfully created 100 posts in the database!")

# ------------------------------------------------------------
# Main entrypoint
# ------------------------------------------------------------

async def init() -> None:
    async with AsyncSession(bind=engine) as session:
        await init_db(session)


async def main() -> None:
    logger.info("Creating initial data")
    await init()
    if settings.ENVIRONMENT == "local":
        await create_100_posts()
    logger.info("Initial data created")


if __name__ == "__main__":
    asyncio.run(main())
