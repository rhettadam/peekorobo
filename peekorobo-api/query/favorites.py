from typing import List, Literal

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
