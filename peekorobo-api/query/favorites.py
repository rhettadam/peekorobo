from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ItemType = Literal["team", "event"]


class FavoriteRequest(BaseModel):
    item_type: ItemType
    item_key: str = Field(min_length=1, max_length=50)


class FavoriteItem(BaseModel):
    item_type: ItemType
    item_key: str


class FavoritesResponse(BaseModel):
    teams: List[str] = []
    events: List[str] = []


class FavoriteStatusResponse(BaseModel):
    item_type: ItemType
    item_key: str
    favorited: bool
    count: int = 0


class FavoriterUser(BaseModel):
    id: int
    username: str
    avatar_key: Optional[str] = None


class FavoriteItemDetailResponse(BaseModel):
    item_type: ItemType
    item_key: str
    count: int
    users: List[FavoriterUser] = []


class FavoriteCountsResponse(BaseModel):
    item_type: ItemType
    counts: Dict[str, int] = {}
