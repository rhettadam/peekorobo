from typing import Annotated, Optional
from time import time
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Path, Depends, Security, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from fastapi.openapi.docs import get_swagger_ui_html
from query.teams import TeamQuery, TeamResponse
from query.events import EventQuery, EventResponse
from query.event_keys import EventKeysResponse
from query.team_epas import TeamPerfRequest, TeamPerfResponse, TeamPerfListRequest, TeamPerfListResponse
from query.event_teams import EventTeamsQuery, EventTeamsResponse
from query.event_matches import EventMatchesRequest, EventMatchResponse
from query.event_awards import EventAwardsResponse
from query.event_rankings import EventRankingsResponse
from query.event_perfs import EventPerfsResponse, EventPerfInfo
from query.team_awards import TeamAwardsResponse, TeamAwardsQuery
from query.team_events import TeamEventsResponse, TeamEventsQuery
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
import data.models.event_perfs as event_perfs
import data.models.team_awards as team_awards
import data.models.team_events as team_events
import data.models.events as events

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

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
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

API_TITLE = "Peekorobo API"
API_DESCRIPTION = """
## Overview

Information and statistics about FIRST Robotics Competition teams and events. Data includes team performance metrics (ACE/RAW), event rankings, matches, awards, and more.

## Authentication

All endpoints require an API key to be passed in the header **X-API-Key**. If you do not have an API key yet, you can obtain one from your [User Page](https://www.peekorobo.com/user) on Peekorobo.
"""

TAGS_METADATA = [
    {
        "name": "Teams",
        "description": "Search teams and retrieve team performance metrics (ACE/RAW), awards, and event history. Filter by year, location, and district.",
    },
    {
        "name": "Events",
        "description": "List FRC events for a given year. Filter by location and event type.",
    },
    {
        "name": "Event Data",
        "description": "Retrieve teams, matches, awards, and rankings for a specific event. Use event keys like `2024cmp` or `2025txdal`.",
    },
    {
        "name": "Authentication",
        "description": "Verify that your API key is valid and accepted by the API.",
    },
]

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    openapi_tags=TAGS_METADATA,
)

# Header and footer for Swagger docs (matches peekorobo.com branding)
SWAGGER_HEADER_HTML = """
<header class="peekorobo-docs-header" style="
    background: #212529;
    padding: 8px 0;
    box-shadow: 0 2px 2px rgba(0,0,0,0.1);
    position: sticky;
    top: 0;
    z-index: 1020;
">
    <div style="max-width: 1460px; margin: 0 auto; padding: 0 15px; display: flex; align-items: center; justify-content: space-between;">
        <a href="https://www.peekorobo.com/" style="display: flex; align-items: center; text-decoration: none;">
            <img src="https://www.peekorobo.com/assets/logo.png" alt="Peekorobo" style="height: 40px; width: auto;" />
        </a>
        <nav style="display: flex; gap: 1.5rem;">
            <a href="https://www.peekorobo.com/teams" style="color: rgba(255,255,255,0.9); text-decoration: none;">Teams</a>
            <a href="https://www.peekorobo.com/events" style="color: rgba(255,255,255,0.9); text-decoration: none;">Events</a>
            <a href="https://www.peekorobo.com/map" style="color: rgba(255,255,255,0.9); text-decoration: none;">Map</a>
            <a href="https://www.peekorobo.com/insights" style="color: rgba(255,255,255,0.9); text-decoration: none;">Insights</a>
            <a href="https://www.peekorobo.com/user" style="color: rgba(255,255,255,0.9); text-decoration: none;">Account</a>
        </nav>
    </div>
</header>
"""

SWAGGER_FOOTER_HTML = """
<footer class="peekorobo-docs-footer" style="
    background: #212529;
    padding: 10px 0;
    box-shadow: 0 -1px 2px rgba(0,0,0,0.1);
    margin-top: auto;
">
    <div style="max-width: 1460px; margin: 0 auto; padding: 0 15px; text-align: center;">
        <p style="margin: 0; color: rgba(255,255,255,0.8); font-size: 15px;">
            Built with
            <a href="https://www.thebluealliance.com/" target="_blank" rel="noopener" style="color: #3366CC; text-decoration: none;">The Blue Alliance</a>
            &nbsp;|&nbsp;
            <a href="https://github.com/rhettadam/peekorobo" target="_blank" rel="noopener" style="color: #3366CC; text-decoration: none;">GitHub</a>
        </p>
    </div>
</footer>
"""


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with Peekorobo header and footer."""
    # Use relative path so it works when API is mounted at /api (openapi.json -> /api/openapi.json)
    openapi_url = "openapi.json"
    html_response = get_swagger_ui_html(
        openapi_url=openapi_url,
        title=f"{API_TITLE} - Swagger UI",
    )
    html_content = html_response.body.decode()
    # Inject header and body styles, footer before </body>
    body_open = '<body style="margin:0; min-height:100vh; display:flex; flex-direction:column;">'
    html_content = html_content.replace("<body>", body_open + SWAGGER_HEADER_HTML)
    html_content = html_content.replace(
        '<div id="swagger-ui"></div>',
        '<div style="flex: 1;"><div id="swagger-ui"></div></div>',
    )
    html_content = html_content.replace("</body>", SWAGGER_FOOTER_HTML + "</body>")
    return HTMLResponse(html_content)


@app.get("/")
async def hello():
    return {"message": "hello world!"}

@app.get("/teams", dependencies=[Depends(verify_api_key)], tags=["Teams"])
async def get_teams(filter_query: Annotated[TeamQuery, Query()], db : Session = Depends(get_db)) -> TeamResponse:
    return teams.get_teams(db = db, query = filter_query)

@app.get("/events/{year}/keys", dependencies=[Depends(verify_api_key)], tags=["Events"])
async def get_event_keys(year: Annotated[int, Path(title="Year")], db: Session = Depends(get_db)) -> EventKeysResponse:
    keys = events.get_event_keys(db, year)
    return EventKeysResponse(year=year, keys=keys)

@app.get("/events/{year}", response_model=EventResponse, dependencies=[Depends(verify_api_key)], tags=["Events"])
async def get_events(year : Annotated[int , Path(title="Events from this year")], query : Annotated[EventQuery, Query()]) -> EventResponse:
    return EventResponse(events=[], next=None)

@app.get("/team_perfs", dependencies=[Depends(verify_api_key)], tags=["Teams"])
async def get_team_perfs_list(query: TeamPerfListRequest = Depends(), db: Session = Depends(get_db)) -> TeamPerfListResponse:
    return team_epas.get_team_perfs_list(db, query)

@app.get("/team_perfs/{team_number}", dependencies=[Depends(verify_api_key)], tags=["Teams"])
async def get_team_perfs(team_number : Annotated[int, Path(title="Team number")], query : Annotated[TeamPerfRequest, Query()], db : Session = Depends(get_db)) -> TeamPerfResponse:
    return team_epas.get_team_epa(db, team_number, query)

@app.get("/team/{team_number}/awards", dependencies=[Depends(verify_api_key)], tags=["Teams"])
async def get_team_awards(team_number: Annotated[int, Path(title="Team number")], query: TeamAwardsQuery = Depends(), db: Session = Depends(get_db)) -> TeamAwardsResponse:
    return team_awards.get_team_awards(db, team_number, query)

@app.get("/team/{team_number}/awards/{year}", dependencies=[Depends(verify_api_key)], tags=["Teams"])
async def get_team_awards_by_year(team_number: Annotated[int, Path(title="Team number")], year: Annotated[int, Path(title="Year")], db: Session = Depends(get_db)) -> TeamAwardsResponse:
    return team_awards.get_team_awards(db, team_number, TeamAwardsQuery(year=year))

@app.get("/team/{team_number}/events", dependencies=[Depends(verify_api_key)], tags=["Teams"])
async def get_team_events(team_number: Annotated[int, Path(title="Team number")], query: TeamEventsQuery = Depends(), db: Session = Depends(get_db)) -> TeamEventsResponse:
    return team_events.get_team_events(db, team_number, query)

@app.get("/team/{team_number}/events/{year}", dependencies=[Depends(verify_api_key)], tags=["Teams"])
async def get_team_events_by_year(team_number: Annotated[int, Path(title="Team number")], year: Annotated[int, Path(title="Year")], db: Session = Depends(get_db)) -> TeamEventsResponse:
    return team_events.get_team_events(db, team_number, TeamEventsQuery(year=year))

# Event data routes (nested under /event/{event_key}/...)
@app.get("/event/{event_key}/teams", dependencies=[Depends(verify_api_key)], tags=["Event Data"])
async def get_event_teams_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: Annotated[EventTeamsQuery, Query()], db: Session = Depends(get_db)) -> EventTeamsResponse:
    return event_teams.get_event_teams(db, event_key, query)

@app.get("/event/{event_key}/matches", dependencies=[Depends(verify_api_key)], tags=["Event Data"])
async def get_event_matches_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: Annotated[EventMatchesRequest, Query()], db: Session = Depends(get_db)) -> EventMatchResponse:
    return event_matches.get_event_matches(db, event_key, query)

@app.get("/event/{event_key}/awards", dependencies=[Depends(verify_api_key)], tags=["Event Data"])
async def get_event_awards_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], db: Session = Depends(get_db)) -> EventAwardsResponse:
    return event_awards.get_event_awards(db, event_key)

@app.get("/event/{event_key}/rankings", dependencies=[Depends(verify_api_key)], tags=["Event Data"])
async def get_event_rankings_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], db: Session = Depends(get_db)) -> EventRankingsResponse:
    return event_rankings.get_event_rankings(db, event_key)

def _parse_team_key(team_key: str) -> int:
    """Parse team_key (e.g. '254' or 'frc254') to team number."""
    s = str(team_key).strip().lower()
    if s.startswith("frc"):
        s = s[3:]
    return int(s)

@app.get("/event/{event_key}/event_perfs/{team_key}", dependencies=[Depends(verify_api_key)], tags=["Event Data"])
async def get_event_perf(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], team_key: Annotated[str, Path(title="Team key (e.g. 254 or frc254)")], db: Session = Depends(get_db)) -> EventPerfInfo:
    try:
        team_number = _parse_team_key(team_key)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid team key")
    perf = event_perfs.get_event_perf(db, event_key, team_number)
    if perf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event performance not found for this team")
    return perf

@app.get("/event/{event_key}/event_perfs", dependencies=[Depends(verify_api_key)], tags=["Event Data"])
async def get_event_perfs(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], db: Session = Depends(get_db)) -> EventPerfsResponse:
    return event_perfs.get_event_perfs(db, event_key)

@app.get("/authorize", dependencies=[Depends(verify_api_key)], tags=["Authentication"])
async def authorize_user():
    return {"authorized": True}
