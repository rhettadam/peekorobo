from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class EventQuery(BaseModel):
    city : Optional[str] = None
    state_prov : Optional[str] = None
    country : Optional[str] = None
    limit : Optional[int] = None

class EventMetaInfo(BaseModel):
    name : str
    start_date : datetime
    end_date : datetime
    event_type : str

class LocationInfo(BaseModel):
    city : str
    state_prov : str
    country : str

class EventData(BaseModel):
    event_key : str
    event_data : EventMetaInfo
    location_info : LocationInfo
    website : Optional[str]
    webcast_type : Optional[str]
    webcast_channel : Optional[str]

class EventResponse(BaseModel):
    events : List[EventData]
    next : Optional[str]
