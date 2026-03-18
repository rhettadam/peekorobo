from typing import Annotated, Optional
from time import time
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Path, Depends, Header, HTTPException, status
from query.teams import TeamQuery, TeamResponse
from query.events import EventQuery, EventResponse
from query.team_epas import TeamPerfRequest, TeamPerfResponse, TeamPerfListRequest, TeamPerfListResponse
from query.event_teams import EventTeamsQuery, EventTeamsResponse
from query.event_matches import EventMatchesRequest, EventMatchResponse
from query.event_awards import EventAwardsResponse
from query.event_rankings import EventRankingsResponse
from query.team_awards import TeamAwardsResponse
from query.team_events import TeamEventsResponse
from data.db import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
import data.models.teams as teams
import data.models.team_epas as team_epas
import data.models.event_teams as event_teams
import data.models.event_matches as event_matches
import data.models.event_awards as event_awards
import data.models.event_rankings as event_rankings
import data.models.team_awards as team_awards
import data.models.team_events as team_events

load_dotenv()

AUTH_TIMEOUT_MS = 2000  # 2 seconds
AUTH_CACHE_TTL_SECONDS = 300  # 5 min 

_auth_cache: dict[str, float] = {}  # api_key -> cached_at

def _apply_auth_timeout(db: Session) -> None:
    bind = db.get_bind()
    if bind is None:
        return
    if bind.dialect.name == "postgresql":
        db.execute(
            text("SET LOCAL statement_timeout = :timeout_ms"),
            {"timeout_ms": AUTH_TIMEOUT_MS}
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_api_key(
    api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
    db: Session = Depends(get_db)
):
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    now = time()
    cached_at = _auth_cache.get(api_key)
    if cached_at is not None and (now - cached_at) < AUTH_CACHE_TTL_SECONDS:
        return

    _apply_auth_timeout(db)
    try:
        result = db.execute(
            text("SELECT 1 FROM users WHERE api_key = :api_key"),
            {"api_key": api_key}
        ).first()
    except DBAPIError as exc:
        message = str(getattr(exc, "orig", exc)).lower()
        if "statement timeout" in message or "query canceled" in message:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Authentication timed out"
            )
        raise
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    _auth_cache[api_key] = now

app = FastAPI()

@app.get("/")
async def hello():
    return {"message": "hello world!"}

@app.get("/teams", dependencies=[Depends(verify_api_key)])
async def get_teams(filter_query: Annotated[TeamQuery, Query()], db : Session = Depends(get_db)) -> TeamResponse:
    return teams.get_teams(db = db, query = filter_query)

@app.get("/events/{year}", response_model=EventResponse, dependencies=[Depends(verify_api_key)])
async def get_events(year : Annotated[int , Path(title="Events from this year")], query : Annotated[EventQuery, Query()]) -> EventResponse:
    return EventResponse(events=[], next=None)

@app.get("/team_perfs", dependencies=[Depends(verify_api_key)])
async def get_team_perfs_list(query: TeamPerfListRequest = Depends(), db: Session = Depends(get_db)) -> TeamPerfListResponse:
    return team_epas.get_team_perfs_list(db, query)

@app.get("/team_perfs/{team_number}", dependencies=[Depends(verify_api_key)])
async def get_team_perfs(team_number : Annotated[int, Path(title="Team number")], query : Annotated[TeamPerfRequest, Query()], db : Session = Depends(get_db)) -> TeamPerfResponse:
    return team_epas.get_team_epa(db, team_number, query)

@app.get("/team/{team_number}/awards", dependencies=[Depends(verify_api_key)])
async def get_team_awards(team_number: Annotated[int, Path(title="Team number")], db: Session = Depends(get_db)) -> TeamAwardsResponse:
    return team_awards.get_team_awards(db, team_number)

@app.get("/team/{team_number}/events", dependencies=[Depends(verify_api_key)])
async def get_team_events(team_number: Annotated[int, Path(title="Team number")], db: Session = Depends(get_db)) -> TeamEventsResponse:
    return team_events.get_team_events(db, team_number)

@app.get("/event_teams/{event_key}", dependencies=[Depends(verify_api_key)])
async def get_event_teams(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: Annotated[EventTeamsQuery, Query()], db: Session = Depends(get_db)) -> EventTeamsResponse:
    return event_teams.get_event_teams(db, event_key, query)

@app.get("/event_rankings/{event_key}", dependencies=[Depends(verify_api_key)])
async def get_event_rankings(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], db: Session = Depends(get_db)) -> EventRankingsResponse:
    return event_rankings.get_event_rankings(db, event_key)

@app.get("/event_matches/{event_key}", dependencies=[Depends(verify_api_key)])
async def get_event_matches(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: Annotated[EventMatchesRequest, Query()], db: Session = Depends(get_db)) -> EventMatchResponse:
    return event_matches.get_event_matches(db, event_key, query)

@app.get("/event_awards/{event_key}", dependencies=[Depends(verify_api_key)])
async def get_event_awards(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], db: Session = Depends(get_db)) -> EventAwardsResponse:
    return event_awards.get_event_awards(db, event_key)

# Nested /event/{event_key}/... routes
@app.get("/event/{event_key}/teams", dependencies=[Depends(verify_api_key)])
async def get_event_teams_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: Annotated[EventTeamsQuery, Query()], db: Session = Depends(get_db)) -> EventTeamsResponse:
    return event_teams.get_event_teams(db, event_key, query)

@app.get("/event/{event_key}/matches", dependencies=[Depends(verify_api_key)])
async def get_event_matches_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: Annotated[EventMatchesRequest, Query()], db: Session = Depends(get_db)) -> EventMatchResponse:
    return event_matches.get_event_matches(db, event_key, query)

@app.get("/event/{event_key}/awards", dependencies=[Depends(verify_api_key)])
async def get_event_awards_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], db: Session = Depends(get_db)) -> EventAwardsResponse:
    return event_awards.get_event_awards(db, event_key)

@app.get("/event/{event_key}/rankings", dependencies=[Depends(verify_api_key)])
async def get_event_rankings_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], db: Session = Depends(get_db)) -> EventRankingsResponse:
    return event_rankings.get_event_rankings(db, event_key)

@app.get("/authorize", dependencies=[Depends(verify_api_key)])
async def authorize_user():
    return {"authorized": True}
