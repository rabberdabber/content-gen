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
from .item import Item, ItemBase, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate
from .message import Message
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
    Item,
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
    # Item related
    "Item",
    "ItemBase",
    "ItemCreate",
    "ItemPublic",
    "ItemsPublic",
    "ItemUpdate",
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
    "Message",
]
