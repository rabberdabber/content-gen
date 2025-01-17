import json

import httpx
from loguru import logger

from app.core.config import email_settings


async def send_email(
    to_email: str,
    subject: str,
    body: str
):
    """
    Asynchronously sends an email through Postmark SMTP using your server token.
    :param to_email: Recipient email address.
    :param subject: Email subject line.
    :param body: Email body text.
    """
    headers = {
        "X-Postmark-Server-Token": email_settings.SMTP_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    logger.info(f"json request body: {json.dumps({'From': email_settings.EMAILS_FROM_EMAIL, 'To': to_email, 'Subject': subject, 'HtmlBody': body})}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.postmarkapp.com/email",
            headers=headers,
            json={"From": email_settings.EMAILS_FROM_EMAIL, "To": to_email, "Subject": subject, "HtmlBody": body},
        )
        logger.info(response.json())
