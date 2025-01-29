import asyncio
import logging

from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from app.core.config import redis_settings
from app.core.db import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
async def init(db_engine: AsyncEngine) -> None:
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with async_session() as session:
            # Try to create session to check if DB is awake
            await session.exec(select(1))
    except Exception as e:
        logger.error(e)
        raise e


async def init_redis() -> None:
    try:
        redis = aioredis.from_url(redis_settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await redis.ping()
    except Exception as e:
        logger.error(f"Error connecting to Redis: {e}")
        raise e


async def main() -> None:
    logger.info("Initializing service")
    await init(engine)
    await init_redis()
    logger.info("Service finished initializing")


if __name__ == "__main__":
    asyncio.run(main())
