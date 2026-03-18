from typing import List
from pydantic import BaseModel


class EventKeysResponse(BaseModel):
    year: int
    keys: List[str]
