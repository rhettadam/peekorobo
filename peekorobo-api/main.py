import os
import threading
from typing import Annotated, Optional
from time import time
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Path, Depends, Security, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from query.teams import TeamQuery, TeamResponse
from query.events import EventQuery, EventResponse
from query.event_keys import EventKeysResponse
from query.team_epas import TeamPerfRequest, TeamPerfResponse, TeamPerfListRequest, TeamPerfListResponse
from query.event_teams import EventTeamsQuery, EventTeamsResponse
from query.event_matches import EventMatchesRequest, EventMatchResponse
from query.event_awards import EventAwardsResponse, EventAwardsQuery
from query.event_rankings import EventRankingsResponse, EventRankingsQuery
from query.event_perfs import EventPerfsResponse, EventPerfInfo
from query.team_awards import TeamAwardsResponse, TeamAwardsQuery
from query.team_events import TeamEventsResponse, TeamEventsQuery
from query.notables import TeamNotablesResponse
from query.frc_games import FrcGamesResponse
from query.event_insights import EventInsightsResponse
from query.insights_overview import InsightsOverviewResponse
from query.map import MapTeamsResponse, MapEventsResponse
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
import data.models.notables as notables
import data.models.events as events
import data.models.frc_games as frc_games
import data.models.event_insights as event_insights
import data.models.insights_overview as insights_overview
import data.models.map as map_data
import data.models.users as users_model
import data.models.favorites as favorites_model
import security
from query.auth import (
    RegisterRequest,
    LoginRequest,
    UpdateProfileRequest,
    UserResponse,
    TokenResponse,
    PublicProfileResponse,
    FollowStatusResponse,
    UserListResponse,
    UserSummary,
    ApiKeyResponse,
)
import secrets
from query.favorites import FavoriteRequest, FavoritesResponse, FavoriteStatusResponse

load_dotenv()

AUTH_TIMEOUT_MS = 2000  # 2 seconds
AUTH_CACHE_TTL_SECONDS = 300  # 5 min

# When PUBLIC_READ is enabled the read endpoints the SPA needs are served without
# an API key (rate-limited + CDN-cached). The keyed developer API, /docs and
# /authorize keep working; a valid key simply gets its own rate-limit bucket.
PUBLIC_READ = os.getenv("PUBLIC_READ", "true").strip().lower() not in ("false", "0", "no")

# How long clients/CDN may cache read responses. Matches the "few minutes is fine"
# freshness target; the CDN absorbs the vast majority of reads.
CACHE_MAX_AGE = int(os.getenv("CACHE_MAX_AGE", "300"))
CACHE_SWR = int(os.getenv("CACHE_STALE_WHILE_REVALIDATE", "600"))
CACHE_CONTROL_VALUE = f"public, max-age={CACHE_MAX_AGE}, stale-while-revalidate={CACHE_SWR}"

# Map coordinates change rarely (teams are geocoded offline; event locations are
# fixed once set), so they can be cached far longer than the default read window.
MAP_CACHE_MAX_AGE = int(os.getenv("MAP_CACHE_MAX_AGE", "86400"))
MAP_CACHE_SWR = int(os.getenv("MAP_CACHE_STALE_WHILE_REVALIDATE", "604800"))
MAP_CACHE_CONTROL_VALUE = f"public, max-age={MAP_CACHE_MAX_AGE}, stale-while-revalidate={MAP_CACHE_SWR}"

# Insights overview is expensive to compute but only changes when the pipeline runs.
INSIGHTS_CACHE_MAX_AGE = int(os.getenv("INSIGHTS_CACHE_MAX_AGE", "3600"))
INSIGHTS_CACHE_SWR = int(os.getenv("INSIGHTS_CACHE_STALE_WHILE_REVALIDATE", "86400"))
INSIGHTS_CACHE_CONTROL_VALUE = (
    f"public, max-age={INSIGHTS_CACHE_MAX_AGE}, stale-while-revalidate={INSIGHTS_CACHE_SWR}"
)

# Comma-separated list of allowed SPA origins, or "*" for any (read-only, no cookies).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

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
    """Strict API-key check. Used by the keyed developer API (/authorize)."""
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

def read_access(
    api_key: Optional[str] = Security(api_key_header),
    db: Session = Depends(get_db)
):
    """Access control for read endpoints.

    - When PUBLIC_READ is on (default), reads are public: no key required.
    - When PUBLIC_READ is off, falls back to strict key verification, so the
      change is fully reversible via the PUBLIC_READ env var.
    """
    if PUBLIC_READ:
        return
    verify_api_key(api_key, db)


# --- User authentication (JWT Bearer) -------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Resolve the logged-in user from a ``Authorization: Bearer <jwt>`` header."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = security.decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = users_model.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> Optional[UserResponse]:
    """Like get_current_user, but returns None instead of raising when there is
    no (valid) token. Used by endpoints that are public but personalize output."""
    if credentials is None or not credentials.credentials:
        return None
    payload = security.decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    return users_model.get_user_by_id(db, user_id)

API_TITLE = "Peekorobo API"
API_DESCRIPTION = """
## Overview

Information and statistics about FIRST Robotics Competition teams and events. Data includes team performance metrics (ACE/RAW), event rankings, matches, awards, and more.

## Access

Read endpoints are publicly accessible and rate-limited. Registered developers can pass an API key in the **X-API-Key** header to receive a dedicated rate-limit bucket. Get a key from your [User Page](https://www.peekorobo.com/user) on Peekorobo.
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
        "name": "Map",
        "description": "Lightweight team and event coordinates for rendering an on-the-fly map.",
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

# CORS so the React SPA (a different origin) can call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    # POST/PUT/DELETE are needed for the auth + favorites (write) endpoints the
    # SPA calls with a Bearer token. Reads remain GET.
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Optional rate limiting (safety net behind the CDN). slowapi is optional so the
# API still runs if it isn't installed. Keyed by API key when present, else IP.
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    def _rate_limit_key(request: Request) -> str:
        return request.headers.get("X-API-Key") or get_remote_address(request)

    limiter = Limiter(
        key_func=_rate_limit_key,
        default_limits=[os.getenv("RATE_LIMIT_DEFAULT", "240/minute")],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
except ImportError:
    limiter = None


NO_CACHE_PREFIXES = ("/authorize", "/docs", "/openapi.json", "/redoc", "/auth", "/favorites")


@app.middleware("http")
async def add_cache_headers(request: Request, call_next):
    """Attach Cache-Control so a CDN can serve most reads without hitting the API."""
    response = await call_next(request)
    path = request.url.path
    if request.method == "GET" and response.status_code == 200:
        if any(path == p or path.startswith(p) for p in NO_CACHE_PREFIXES):
            response.headers["Cache-Control"] = "no-store"
        else:
            response.headers.setdefault("Cache-Control", CACHE_CONTROL_VALUE)
    return response

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

@app.get("/teams", dependencies=[Depends(read_access)], tags=["Teams"])
async def get_teams(filter_query: Annotated[TeamQuery, Query()], db : Session = Depends(get_db)) -> TeamResponse:
    return teams.get_teams(db = db, query = filter_query)

@app.get("/events/{year}/keys", dependencies=[Depends(read_access)], tags=["Events"])
async def get_event_keys(year: Annotated[int, Path(title="Year")], query: Annotated[EventQuery, Query()], db: Session = Depends(get_db)) -> EventKeysResponse:
    keys = events.get_event_keys(db, year, query)
    return EventKeysResponse(year=year, keys=keys)

@app.get("/events/{year}/insights", dependencies=[Depends(read_access)], tags=["Events"])
async def get_event_insights(year: Annotated[int, Path(title="Year")], db: Session = Depends(get_db)) -> EventInsightsResponse:
    return event_insights.get_event_insights(db, year)

@app.get("/insights/overview", dependencies=[Depends(read_access)], tags=["Insights"])
def get_insights_overview(
    response: Response,
    db: Session = Depends(get_db),
) -> InsightsOverviewResponse:
    """Career / all-time Insights: season series, prediction accuracy, leaderboards."""
    response.headers["Cache-Control"] = INSIGHTS_CACHE_CONTROL_VALUE
    return insights_overview.get_insights_overview(db)

@app.get("/events/{year}", response_model=EventResponse, dependencies=[Depends(read_access)], tags=["Events"])
async def get_events(year : Annotated[int , Path(title="Events from this year")], query : Annotated[EventQuery, Query()], db: Session = Depends(get_db)) -> EventResponse:
    return events.get_events(db, year, query)

@app.get("/team_perfs", dependencies=[Depends(read_access)], tags=["Teams"])
async def get_team_perfs_list(query: TeamPerfListRequest = Depends(), db: Session = Depends(get_db)) -> TeamPerfListResponse:
    return team_epas.get_team_perfs_list(db, query)

@app.get("/team_perfs/{team_number}", dependencies=[Depends(read_access)], tags=["Teams"])
async def get_team_perfs(team_number : Annotated[int, Path(title="Team number")], query : Annotated[TeamPerfRequest, Query()], db : Session = Depends(get_db)) -> TeamPerfResponse:
    return team_epas.get_team_epa(db, team_number, query)

@app.get("/team/{team_number}/awards", dependencies=[Depends(read_access)], tags=["Teams"])
async def get_team_awards(team_number: Annotated[int, Path(title="Team number")], query: TeamAwardsQuery = Depends(), db: Session = Depends(get_db)) -> TeamAwardsResponse:
    return team_awards.get_team_awards(db, team_number, query)

@app.get("/team/{team_number}/awards/{year}", dependencies=[Depends(read_access)], tags=["Teams"])
async def get_team_awards_by_year(team_number: Annotated[int, Path(title="Team number")], year: Annotated[int, Path(title="Year")], db: Session = Depends(get_db)) -> TeamAwardsResponse:
    return team_awards.get_team_awards(db, team_number, TeamAwardsQuery(year=year))

@app.get("/team/{team_number}/notables", dependencies=[Depends(read_access)], tags=["Teams"])
async def get_team_notables(team_number: Annotated[int, Path(title="Team number")], db: Session = Depends(get_db)) -> TeamNotablesResponse:
    return notables.get_team_notables(db, team_number)

@app.get("/team/{team_number}/events", dependencies=[Depends(read_access)], tags=["Teams"])
async def get_team_events(team_number: Annotated[int, Path(title="Team number")], query: TeamEventsQuery = Depends(), db: Session = Depends(get_db)) -> TeamEventsResponse:
    return team_events.get_team_events(db, team_number, query)

@app.get("/team/{team_number}/events/{year}", dependencies=[Depends(read_access)], tags=["Teams"])
async def get_team_events_by_year(team_number: Annotated[int, Path(title="Team number")], year: Annotated[int, Path(title="Year")], db: Session = Depends(get_db)) -> TeamEventsResponse:
    return team_events.get_team_events(db, team_number, TeamEventsQuery(year=year))

# Event data routes (nested under /event/{event_key}/...)
@app.get("/event/{event_key}/teams", dependencies=[Depends(read_access)], tags=["Event Data"])
async def get_event_teams_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: Annotated[EventTeamsQuery, Query()], db: Session = Depends(get_db)) -> EventTeamsResponse:
    return event_teams.get_event_teams(db, event_key, query)

@app.get("/event/{event_key}/matches", dependencies=[Depends(read_access)], tags=["Event Data"])
async def get_event_matches_nested(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: Annotated[EventMatchesRequest, Query()], db: Session = Depends(get_db)) -> EventMatchResponse:
    return event_matches.get_event_matches(db, event_key, query)

@app.get("/event/{event_key}/awards/{team_number}", dependencies=[Depends(read_access)], tags=["Event Data"])
async def get_event_awards_by_team(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], team_number: Annotated[int, Path(title="Team number")], db: Session = Depends(get_db)) -> EventAwardsResponse:
    return event_awards.get_event_awards(db, event_key, EventAwardsQuery(team_number=team_number))

@app.get("/event/{event_key}/awards", dependencies=[Depends(read_access)], tags=["Event Data"])
async def get_event_awards(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: EventAwardsQuery = Depends(), db: Session = Depends(get_db)) -> EventAwardsResponse:
    return event_awards.get_event_awards(db, event_key, query)

@app.get("/event/{event_key}/rankings/{team_number}", dependencies=[Depends(read_access)], tags=["Event Data"])
async def get_event_rankings_by_team(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], team_number: Annotated[int, Path(title="Team number")], db: Session = Depends(get_db)) -> EventRankingsResponse:
    return event_rankings.get_event_rankings(db, event_key, EventRankingsQuery(team_number=team_number))

@app.get("/event/{event_key}/rankings", dependencies=[Depends(read_access)], tags=["Event Data"])
async def get_event_rankings(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], query: EventRankingsQuery = Depends(), db: Session = Depends(get_db)) -> EventRankingsResponse:
    return event_rankings.get_event_rankings(db, event_key, query)

def _parse_team_key(team_key: str) -> int:
    """Parse team_key (e.g. '254' or 'frc254') to team number."""
    s = str(team_key).strip().lower()
    if s.startswith("frc"):
        s = s[3:]
    return int(s)

@app.get("/event/{event_key}/event_perfs/{team_key}", dependencies=[Depends(read_access)], tags=["Event Data"])
async def get_event_perf(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], team_key: Annotated[str, Path(title="Team key (e.g. 254 or frc254)")], db: Session = Depends(get_db)) -> EventPerfInfo:
    try:
        team_number = _parse_team_key(team_key)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid team key")
    perf = event_perfs.get_event_perf(db, event_key, team_number)
    if perf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event performance not found for this team")
    return perf

@app.get("/event/{event_key}/event_perfs", dependencies=[Depends(read_access)], tags=["Event Data"])
async def get_event_perfs(event_key: Annotated[str, Path(title="Event key (e.g. 2024cmp)")], db: Session = Depends(get_db)) -> EventPerfsResponse:
    return event_perfs.get_event_perfs(db, event_key)

@app.get("/frc_games", dependencies=[Depends(read_access)], tags=["Events"])
async def get_frc_games(db: Session = Depends(get_db)) -> FrcGamesResponse:
    return frc_games.get_frc_games(db)

@app.get("/map/teams", dependencies=[Depends(read_access)], tags=["Map"])
async def get_map_teams(response: Response, db: Session = Depends(get_db)) -> MapTeamsResponse:
    response.headers["Cache-Control"] = MAP_CACHE_CONTROL_VALUE
    return map_data.get_map_teams(db)

@app.get("/map/events", dependencies=[Depends(read_access)], tags=["Map"])
async def get_map_events(response: Response, year: Annotated[Optional[int], Query(title="Season year")] = None, db: Session = Depends(get_db)) -> MapEventsResponse:
    response.headers["Cache-Control"] = MAP_CACHE_CONTROL_VALUE
    resolved_year = year if year is not None else datetime.now().year
    return map_data.get_map_events(db, resolved_year)

@app.get("/authorize", dependencies=[Depends(verify_api_key)], tags=["Authentication"])
async def authorize_user():
    return {"authorized": True}


@app.on_event("startup")
def _startup_init_tables():
    """Ensure the users/saved_items tables exist (no-op on production)."""
    db = SessionLocal()
    try:
        users_model.init_user_tables(db)
    except Exception as e:  # pragma: no cover - defensive
        print("User table init failed:", e)
    finally:
        db.close()

    def _prewarm():
        try:
            insights_overview.prewarm_insights_cache()
        except Exception as e:  # pragma: no cover - defensive
            print("Insights cache prewarm failed:", e)

    threading.Thread(target=_prewarm, daemon=True).start()


# --- Auth endpoints -------------------------------------------------------
def _email_is_valid(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1]


@app.post("/auth/register", tags=["Accounts"])
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    username = payload.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")

    pw_error = security.validate_password_strength(payload.password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    email = payload.email.lower().strip() if payload.email else None
    if email:
        if not _email_is_valid(email):
            raise HTTPException(status_code=400, detail="Invalid email format.")
        if users_model.email_exists(db, email):
            raise HTTPException(status_code=409, detail="Email already in use.")

    if users_model.username_exists(db, username):
        raise HTTPException(status_code=409, detail="Username already exists.")

    password_hash = security.hash_password(payload.password)
    user_id = users_model.create_user(db, username, password_hash, email)
    user = users_model.get_user_by_id(db, user_id)
    token = security.create_access_token(user_id, user.username)
    return TokenResponse(access_token=token, user=user)


@app.post("/auth/login", tags=["Accounts"])
async def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    row = users_model.get_login_row(db, payload.username)
    if row is None or not security.verify_password(payload.password, row.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    user = users_model.get_user_by_id(db, row.id)
    token = security.create_access_token(row.id, user.username)
    return TokenResponse(access_token=token, user=user)


@app.post("/auth/logout", tags=["Accounts"])
async def logout():
    """Stateless logout: the client discards the token. Provided for symmetry."""
    return {"ok": True}


@app.get("/auth/me", tags=["Accounts"])
async def get_me(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    return current_user


@app.put("/auth/me", tags=["Accounts"])
async def update_me(
    payload: UpdateProfileRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    fields: dict = {}

    if payload.username is not None:
        new_username = payload.username.strip()
        if len(new_username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
        if users_model.username_exists(db, new_username, exclude_id=current_user.id):
            raise HTTPException(status_code=409, detail="Username already exists.")
        fields["username"] = new_username.lower()

    if payload.email is not None:
        email = payload.email.lower().strip()
        if email:
            if not _email_is_valid(email):
                raise HTTPException(status_code=400, detail="Invalid email format.")
            if users_model.email_exists(db, email, exclude_id=current_user.id):
                raise HTTPException(status_code=409, detail="Email already in use.")
            fields["email"] = email
        else:
            fields["email"] = None

    if payload.password is not None and payload.password.strip():
        pw_error = security.validate_password_strength(payload.password.strip())
        if pw_error:
            raise HTTPException(status_code=400, detail=pw_error)
        fields["password_hash"] = security.hash_password(payload.password.strip())

    for col in ("role", "team", "bio", "avatar_key", "color"):
        val = getattr(payload, col)
        if val is not None:
            fields[col] = val

    users_model.update_user(db, current_user.id, fields)
    return users_model.get_user_by_id(db, current_user.id)


@app.get("/users/{username}", tags=["Accounts"])
async def get_public_profile(
    username: Annotated[str, Path(title="Username")],
    db: Session = Depends(get_db),
    viewer: Optional[UserResponse] = Depends(get_optional_user),
) -> PublicProfileResponse:
    target_id = users_model.get_user_id_by_username(db, username)
    if target_id is None:
        raise HTTPException(status_code=404, detail="User not found")
    user = users_model.get_user_by_id(db, target_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.email = None  # don't leak email addresses on the public profile
    favs = favorites_model.list_favorites(db, user.id)
    is_self = viewer is not None and viewer.id == target_id
    is_following = (
        viewer is not None and not is_self and users_model.is_following(db, viewer.id, target_id)
    )
    return PublicProfileResponse(
        user=user,
        favorite_teams=favs.teams,
        favorite_events=favs.events,
        is_following=is_following,
        is_self=is_self,
    )


# --- Follows (user-to-user) ----------------------------------------------
def _follow_status(db: Session, username: str, target_id: int, is_following: bool) -> FollowStatusResponse:
    followers, following = users_model.get_follow_lists(db, target_id)
    return FollowStatusResponse(
        username=username,
        is_following=is_following,
        followers_count=len(followers),
        following_count=len(following),
    )


@app.post("/users/{username}/follow", tags=["Accounts"])
async def follow_user(
    username: Annotated[str, Path(title="Username")],
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FollowStatusResponse:
    target_id = users_model.get_user_id_by_username(db, username)
    if target_id is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself.")
    users_model.set_follow(db, current_user.id, target_id, True)
    return _follow_status(db, username, target_id, True)


@app.delete("/users/{username}/follow", tags=["Accounts"])
async def unfollow_user(
    username: Annotated[str, Path(title="Username")],
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FollowStatusResponse:
    target_id = users_model.get_user_id_by_username(db, username)
    if target_id is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot unfollow yourself.")
    users_model.set_follow(db, current_user.id, target_id, False)
    return _follow_status(db, username, target_id, False)


@app.get("/users/{username}/followers", tags=["Accounts"])
async def get_followers(
    username: Annotated[str, Path(title="Username")], db: Session = Depends(get_db)
) -> UserListResponse:
    target_id = users_model.get_user_id_by_username(db, username)
    if target_id is None:
        raise HTTPException(status_code=404, detail="User not found")
    followers, _ = users_model.get_follow_lists(db, target_id)
    users = users_model.list_users_by_ids(db, followers)
    return UserListResponse(users=[UserSummary(**u) for u in users])


@app.get("/users/{username}/following", tags=["Accounts"])
async def get_following(
    username: Annotated[str, Path(title="Username")], db: Session = Depends(get_db)
) -> UserListResponse:
    target_id = users_model.get_user_id_by_username(db, username)
    if target_id is None:
        raise HTTPException(status_code=404, detail="User not found")
    _, following = users_model.get_follow_lists(db, target_id)
    users = users_model.list_users_by_ids(db, following)
    return UserListResponse(users=[UserSummary(**u) for u in users])


# --- API keys (developer API) --------------------------------------------
def _generate_unique_api_key(db: Session) -> str:
    for _ in range(6):
        key = secrets.token_urlsafe(32)
        if not users_model.api_key_exists(db, key):
            return key
    raise HTTPException(status_code=500, detail="Unable to generate a unique API key.")


@app.get("/auth/api-key", tags=["Accounts"])
async def get_api_key(
    current_user: UserResponse = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiKeyResponse:
    return ApiKeyResponse(api_key=users_model.get_api_key(db, current_user.id))


@app.post("/auth/api-key", tags=["Accounts"])
async def generate_api_key(
    current_user: UserResponse = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiKeyResponse:
    """Generate a new key. Also used to regenerate: the previous key is replaced."""
    old_key = users_model.get_api_key(db, current_user.id)
    new_key = _generate_unique_api_key(db)
    users_model.set_api_key(db, current_user.id, new_key)
    if old_key:
        _auth_cache.pop(old_key, None)  # invalidate the replaced key immediately
    return ApiKeyResponse(api_key=new_key)


@app.delete("/auth/api-key", tags=["Accounts"])
async def revoke_api_key(
    current_user: UserResponse = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiKeyResponse:
    old_key = users_model.get_api_key(db, current_user.id)
    users_model.set_api_key(db, current_user.id, None)
    if old_key:
        _auth_cache.pop(old_key, None)
    return ApiKeyResponse(api_key=None)


# --- Favorites endpoints --------------------------------------------------
@app.get("/favorites", tags=["Favorites"])
async def list_favorites(
    current_user: UserResponse = Depends(get_current_user), db: Session = Depends(get_db)
) -> FavoritesResponse:
    return favorites_model.list_favorites(db, current_user.id)


@app.get("/favorites/status", tags=["Favorites"])
async def favorite_status(
    item_type: Annotated[str, Query()],
    item_key: Annotated[str, Query()],
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FavoriteStatusResponse:
    if item_type not in ("team", "event"):
        raise HTTPException(status_code=400, detail="item_type must be 'team' or 'event'")
    return FavoriteStatusResponse(
        item_type=item_type,
        item_key=item_key,
        favorited=favorites_model.is_favorited(db, current_user.id, item_type, item_key),
        count=favorites_model.favorite_count(db, item_type, item_key),
    )


@app.post("/favorites", tags=["Favorites"])
async def add_favorite(
    payload: FavoriteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FavoriteStatusResponse:
    favorites_model.add_favorite(db, current_user.id, payload.item_type, payload.item_key)
    return FavoriteStatusResponse(
        item_type=payload.item_type,
        item_key=payload.item_key,
        favorited=True,
        count=favorites_model.favorite_count(db, payload.item_type, payload.item_key),
    )


@app.delete("/favorites", tags=["Favorites"])
async def remove_favorite(
    item_type: Annotated[str, Query()],
    item_key: Annotated[str, Query()],
    current_user: UserResponse = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FavoriteStatusResponse:
    if item_type not in ("team", "event"):
        raise HTTPException(status_code=400, detail="item_type must be 'team' or 'event'")
    favorites_model.remove_favorite(db, current_user.id, item_type, item_key)
    return FavoriteStatusResponse(
        item_type=item_type,
        item_key=item_key,
        favorited=False,
        count=favorites_model.favorite_count(db, item_type, item_key),
    )
