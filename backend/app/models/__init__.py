from sqlmodel import SQLModel

# Import all models that need to be registered with SQLModel
from .image import (
    FluxModel,
    Image,
    ImageCreate,
    ImageGenerationResultStatus,
    ImageResult,
    ImageUploader,
    UploadResult,
)
from .token import NewPassword, Token, TokenPayload
from .user import (
    UpdatePassword,
    User,
    UserBase,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)

# These are the models that need to be registered with SQLModel for database tables
__models__ = [
    Image,
    User,
]

__all__ = [
    "SQLModel",  # Export SQLModel itself
    # Image related
    "FluxModel",
    "Image",
    "ImageCreate",
    "ImageGenerationResultStatus",
    "ImageResult",
    "ImageUploader",
    "UploadResult",
    # Token related
    "Token",
    "TokenPayload",
    "NewPassword",
    # User related
    "User",
    "UserBase",
    "UserCreate",
    "UserPublic",
    "UsersPublic",
    "UserRegister",
    "UserUpdate",
    "UserUpdateMe",
    "UpdatePassword",
]
