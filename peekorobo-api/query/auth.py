from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    # Accepts a username or an email address.
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class UpdateProfileRequest(BaseModel):
    """All fields optional; only provided fields are updated."""
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default=None, max_length=100)
    team: Optional[str] = Field(default=None, max_length=50)
    bio: Optional[str] = Field(default=None, max_length=2000)
    avatar_key: Optional[str] = Field(default=None, max_length=100)
    color: Optional[str] = Field(default=None, max_length=20)


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: Optional[str] = None
    team: Optional[str] = None
    bio: Optional[str] = None
    avatar_key: Optional[str] = None
    color: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PublicProfileResponse(BaseModel):
    user: UserResponse
    favorite_teams: list[str] = []
    favorite_events: list[str] = []
    is_following: bool = False
    is_self: bool = False


class FollowStatusResponse(BaseModel):
    username: str
    is_following: bool
    followers_count: int
    following_count: int


class UserSummary(BaseModel):
    id: int
    username: str
    avatar_key: Optional[str] = None


class UserListResponse(BaseModel):
    users: list[UserSummary] = []


class ApiKeyResponse(BaseModel):
    api_key: Optional[str] = None
