import uuid
from datetime import timedelta
from typing import Any

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import RedirectResponse
from jwt.exceptions import InvalidTokenError
from loguru import logger
from sqlmodel import func, select

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import (
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import (
    generate_email_verification_email,
    generate_new_account_email,
    send_email,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
async def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = await session.scalar(count_statement)

    statement = select(User).offset(skip).limit(limit)
    users = await session.scalars(statement)
    logger.info(f"Users: {users}")
    return UsersPublic(data=users, count=count)


@router.post(
    "/", dependencies=[Depends(get_current_active_superuser)], response_model=UserPublic
)
async def create_user(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = await crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = await crud.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserPublic)
async def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = await crud.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=dict)
async def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    await session.commit()
    return {"message": "Password updated successfully"}


@router.get("/me", response_model=UserPublic)
async def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=dict)
async def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    await session.commit()
    return {"message": "User deleted successfully"}


@router.post("/signup", response_model=UserPublic)
async def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = await crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=409,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in)
    user = await crud.create_user(session=session, user_create=user_create)
    # TODO: send email to verify email
    return user

@router.get("/verify-email")
async def verify_email_redirect(
    token: str,
) -> Any:
    """
    Validates the verification token and redirects to frontend for completion.
    """
    try:
        # Validate token without modifying database
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        # Verify this is an email verification token
        if payload.get("type") != "email_verification":
            raise HTTPException(status_code=400, detail="Invalid token type")

        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        if not email or not user_id:
            raise HTTPException(status_code=400, detail="Invalid token")

        return RedirectResponse(
            url=f"{settings.FRONTEND_HOST}/verify-email?token={token}"
        )
    except InvalidTokenError as e:
        logger.error(e)
        return RedirectResponse(
            url=f"{settings.FRONTEND_HOST}/verify-email/error"
        )

@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = await session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch("/verify-email", response_model=UserPublic)
async def verify_email(
    token: str,
    session: SessionDep
) -> Any:
    """
    Complete email verification by updating the database.
    Called by frontend after redirect.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        # Verify this is an email verification token
        if payload.get("type") != "email_verification":
            raise HTTPException(status_code=400, detail="Invalid token type")

        email: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        if not email or not user_id:
            raise HTTPException(status_code=400, detail="Invalid token")

    except InvalidTokenError as e:
        raise e
        # raise HTTPException(status_code=401, detail="Not authorized")

    user = await crud.get_user_by_email(session=session, email=email)
    if not user:
        logger.info(f"User with email {email} not found")
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")

    # Verify user_id matches
    if str(user.id) != user_id:
        raise HTTPException(status_code=400, detail="Token does not match user")

    if user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    user.email_verified = True
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user

@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
async def update_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = await session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = await crud.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = await crud.update_user(session=session, db_user=db_user, user_in=user_in)
    return db_user


@router.post("/send-verification-email", response_model=dict)
async def send_verification_email(
    current_user: CurrentUser,
    background_tasks: BackgroundTasks
) -> Any:
    """
    Send verification email with token.
    """
    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    # Create a verification token with additional data
    verification_token = create_access_token(
        subject=current_user.email,
        expires_delta=timedelta(hours=24),
        type="email_verification",
        user_id=str(current_user.id)
    )

    # Generate verification email
    email_data = generate_email_verification_email(
        verification_token=verification_token,
        frontend_url=settings.FRONTEND_HOST
    )

    # Send email in background
    background_tasks.add_task(
        send_email,
        email_to=current_user.email,
        subject=email_data.subject,
        html_content=email_data.html_content
    )

    return {"message": "Verification email sent successfully"}



@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
async def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> dict:
    """
    Delete a user.
    """
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(user)
    await session.commit()
    return {"message": "User deleted successfully"}
