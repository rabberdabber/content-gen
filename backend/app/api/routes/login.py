from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from sqlmodel import SQLModel

from app import crud
from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core import security
from app.core.config import settings
from app.core.magic_link import create_magic_link, verify_magic_link
from app.core.security import get_password_hash
from app.models import NewPassword, Token, UserPublic
from app.services.email_sender import send_email
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    render_email_template,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


class MagicLinkRequest(SQLModel):
    email: EmailStr

@router.post("/login/access-token")
async def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = await crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/login/test-token", response_model=UserPublic)
async def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
async def recover_password(email: str, session: SessionDep) -> dict:
    """
    Password Recovery
    """
    user = await crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    send_email(
        email_to=user.email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return {"message": "Password recovery email sent"}


@router.post("/reset-password/")
async def reset_password(session: SessionDep, body: NewPassword) -> dict:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await crud.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    session.add(user)
    await session.commit()
    return {"message": "Password updated successfully"}


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
async def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = await crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )


@router.post("/login/magic-link")
async def request_magic_link(request: MagicLinkRequest, session: SessionDep, background_tasks: BackgroundTasks) -> dict:
    """
    Request a magic link for passwordless authentication
    """
    user = await crud.get_user_by_email(session=session, email=request.email)
    if not user:
        return {"message": "If your email is registered, you'll receive a magic link"}

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    magic_link_token = create_magic_link(request.email)
    magic_link = f"{settings.FRONTEND_HOST}/auth/verify?token={magic_link_token}"

    html_content = render_email_template(
        template_name="magic_link.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "magic_link": magic_link,
        },
    )

    background_tasks.add_task(send_email, request.email, f"{settings.PROJECT_NAME} - Login Link", html_content)

    return {"message": "If your email is registered, you'll receive a magic link"}


@router.post("/login/verify-magic-link")
async def verify_magic_link_token(token: str, session: SessionDep) -> Token:
    """
    Verify magic link token and return access token
    """
    try:
        email = verify_magic_link(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = await crud.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )
