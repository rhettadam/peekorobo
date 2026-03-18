from pydantic import BaseModel, Field
from typing import Optional, List

# Query model for the team request
class TeamQuery(BaseModel):
    limit: Optional[int] = Field(100, gt=0, le=100)
    city: Optional[str]= None
    country : Optional[str] = None
    district_key: Optional[str] = None
    team_number: Optional[int] = Field(None,gt=0)
    next_team_number: Optional[int] = Field(None, gt=0)

#team data class that represents teams
class TeamData(BaseModel):
    team_number : int
    nickname : str
    city : str
    state_prov : str
    country : str
    website : Optional[str]
    district_key : Optional[str] = None

#The response object from the query
class TeamResponse(BaseModel):
    team_info : List[TeamData]
    next: Optional[int] #url for the next set of 100 teams
