from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.security import ALGORITHM


def create_magic_link(email: str, expires_delta: timedelta | None = None) -> str:
    """
    Create a magic link token for email authentication
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": email,
        "type": "magic_link"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_magic_link(token: str) -> str:
    """
    Verify magic link token and return the email if valid
    """
    try:
        payload: dict[str, dict] = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "magic_link":
            raise ValueError("Invalid token type")
        email = payload.get("sub")
        return email
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.JWTError:
        raise ValueError("Invalid token")
