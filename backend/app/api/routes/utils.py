from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic.networks import EmailStr

from app.api.deps import get_current_active_superuser
from app.core.config import settings
from app.services.email_sender import send_email
from app.utils import render_email_template

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
async def test_email(email_to: EmailStr, background_tasks: BackgroundTasks) -> dict:
    """
    Test emails.
    """
    subject = f"{settings.PROJECT_NAME}"
    html_content = render_email_template(
        template_name="login.html",
        context={"name": "test", "invite_sender_name": "test", "invite_sender_organization_name": "test", "product_name": "test", "support_email": settings.EMAILS_FROM_EMAIL, "action_url": "https://example.com"},
    )
    background_tasks.add_task(send_email, email_to, subject, html_content)
    return {"message": "Test email sent in the background"}


@router.get("/health-check/")
async def health_check() -> bool:
    return True
