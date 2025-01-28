from uuid import UUID

from pydantic import BaseModel


class UserDashboardInfo(BaseModel):
    id: UUID
    full_name: str
    email: str
    is_superuser: bool


class TagDistribution(BaseModel):
    name: str
    count: int


class PopularTag(BaseModel):
    name: str
    count: int


class DashboardStats(BaseModel):
    user: UserDashboardInfo
    total_posts: int
    user_posts: int
    user_drafts: int
    popular_tags: list[PopularTag]
    tag_distribution: list[TagDistribution]
