from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import database_settings, settings
from app.crud import create_user
from app.models import User, UserCreate

engine = create_async_engine(
    str(database_settings.SQLALCHEMY_DATABASE_URI), echo=True, future=True
)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


async def init_db(session: AsyncSession) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = await session.scalar(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    )
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
            image_url=f"{settings.SERVER_HOST}/uploads/superuser_profile.jpg",
            full_name="Bereket Assefa"
        )
        user = await create_user(session=session, user_create=user_in)
    else:
        if not user.image_url or not user.full_name:
            user.image_url = f"{settings.SERVER_HOST}/uploads/superuser_profile.jpg"
            user.full_name = "Bereket Assefa"
            await session.commit()
