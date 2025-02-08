from typing import Literal

from sqlmodel import Field, SQLModel


class RefreshToken(SQLModel):
    refresh_token: str


class Token(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(SQLModel):
    sub: str | None = None
    type: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
