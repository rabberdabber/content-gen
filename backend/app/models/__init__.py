from sqlmodel import SQLModel

# Import all models that need to be registered with SQLModel
from .image import (
    FluxModel,
    FluxPro10CannyCreate,
    FluxPro10DepthCreate,
    FluxPro10FillCreate,
    FluxPro11Create,
    FluxPro11UltraCreate,
    FluxProCreate,
    Image,
    ImageCreate,
    ImageGenerationResultStatus,
    ImageResult,
    ImageUploader,
    UploadResult,
)
from .post import (
    Post,
    PostCreate,
    PostPublic,
    PostPublicWithContent,
    PostsPublic,
    PostTag,
    PostUpdate,
    Tag,
    TagCreate,
    TagResponse,
)
from .dashboard import (
    UserDashboardInfo,
    PopularTag,
    TagDistribution,
    DashboardStats,
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
    Post,
]

__all__ = [
    "SQLModel",  # Export SQLModel itself
    # Image related
    "FluxModel",
    "Image",
    "ImageCreate",
    "FluxProCreate",
    "FluxPro11Create",
    "FluxPro11UltraCreate",
    "FluxPro10FillCreate",
    "FluxPro10CannyCreate",
    "FluxPro10DepthCreate",
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
    # Post related
    "Post",
    "PostCreate",
    "PostUpdate",
    "PostPublic",
    "PostsPublic",
    "PostPublicWithContent",
    "Tag",
    "PostTag",
    "TagResponse",
    "TagCreate",
    "UserDashboardInfo",
    "PopularTag",
    "TagDistribution",
    "DashboardStats",
]
