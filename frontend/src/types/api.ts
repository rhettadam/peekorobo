// TypeScript types mirroring the Pydantic response schemas in peekorobo-api/query/*.py.
// Keep these in sync with the backend.

// ---- Teams (query/teams.py) ----
export interface TeamData {
  team_number: number;
  nickname: string;
  city: string;
  state_prov: string;
  country: string;
  website: string | null;
  district_key?: string | null;
  team_colors?: Record<string, unknown> | null;
}

export interface TeamResponse {
  team_info: TeamData[];
  next: number | null;
}

// ---- Team performance / EPA (query/team_epas.py) ----
export interface EventPerfEntry {
  // The pipeline stores per-event perf objects as free-form JSON. Common keys
  // include event_key, ace, raw, etc. Kept loose on purpose.
  event_key?: string;
  ace?: number | null;
  raw?: number | null;
  confidence?: number | null;
  auto_raw?: number | null;
  teleop_raw?: number | null;
  endgame_raw?: number | null;
  [key: string]: unknown;
}

export interface TeamPerfInfo {
  year: number;
  raw: number | null;
  ace: number | null;
  confidence: number | null;
  auto_raw: number | null;
  teleop_raw: number | null;
  endgame_raw: number | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
  event_perf?: EventPerfEntry[] | null;
  rank_global?: number | null;
  rank_country?: number | null;
  rank_state?: number | null;
  rank_district?: number | null;
  count_global?: number | null;
  count_country?: number | null;
  count_state?: number | null;
  count_district?: number | null;
}

export interface TeamPerfResponse {
  team_number: number;
  team_perfs: TeamPerfInfo[];
}

export interface TeamPerfListResponse {
  team_perfs: TeamPerfResponse[];
  next: number | null;
}

// ---- Events (query/events.py) ----
export interface EventMetaInfo {
  name: string;
  start_date: string; // ISO datetime
  end_date: string;
  event_type: string;
}

export interface LocationInfo {
  city: string;
  state_prov: string;
  country: string;
}

export interface EventData {
  event_key: string;
  event_data: EventMetaInfo;
  location_info: LocationInfo;
  website: string | null;
  webcast_type: string | null;
  webcast_channel: string | null;
  week?: number | null;
  district_key?: string | null;
  district_name?: string | null;
}

export interface EventResponse {
  events: EventData[];
  next: string | null;
}

export interface EventKeysResponse {
  year: number;
  keys: string[];
}

// ---- Event data (event_teams / matches / rankings / awards / perfs) ----
export interface EventTeamEntry {
  team_number: number;
  nickname: string;
  city: string;
  state_prov: string;
  country: string;
}

export interface EventTeamsResponse {
  event_key: string;
  teams: EventTeamEntry[];
}

export interface MatchResponse {
  match_key: string;
  comp_level: string;
  match_number: number;
  set_number: number;
  red_teams: number[];
  blue_teams: number[];
  red_score: number;
  blue_score: number;
  winning_alliance: string;
  youtube_key?: string | null;
  predicted_time?: number | null;
  red_win_prob?: number | null;
  blue_win_prob?: number | null;
}

export interface EventMatchResponse {
  event_key: string;
  matches: MatchResponse[];
}

export interface TeamRankingInfo {
  team_number: number;
  rank: number;
  wins: number;
  losses: number;
  ties: number;
  dq: number;
}

export interface EventRankingsResponse {
  event_key: string;
  event_rankings: TeamRankingInfo[];
}

export interface AwardData {
  team_number: number;
  award_name: string;
}

export interface EventAwardsResponse {
  event_key: string;
  teams_and_awards: AwardData[];
}

export interface EventPerfInfo {
  team_number: number;
  event_key: string;
  raw: number | null;
  ace: number | null;
  confidence: number | null;
  auto_raw: number | null;
  teleop_raw: number | null;
  endgame_raw: number | null;
}

export interface EventPerfsResponse {
  event_key: string;
  perfs: EventPerfInfo[];
}

// ---- Team awards / events (query/team_awards.py, query/team_events.py) ----
export interface TeamAwardData {
  event_key: string;
  award_name: string;
}

export interface TeamAwardsResponse {
  team_number: number;
  awards: TeamAwardData[];
}

export interface EventInsightRow {
  event_key: string;
  team_count: number;
  max_ace: number;
  top8_ace: number;
  top24_ace: number;
  mean_ace: number;
  median_ace: number;
  iqr_ace: number;
  std_ace: number;
}

export interface EventInsightsResponse {
  year: number;
  events: EventInsightRow[];
}

export interface TeamEventsResponse {
  team_number: number;
  events: string[];
}

// ---- Map (query/map.py) ----
export interface MapTeam {
  team_number: number;
  nickname: string | null;
  city: string | null;
  state_prov: string | null;
  country: string | null;
  lat: number;
  lng: number;
}

export interface MapTeamsResponse {
  count: number;
  teams: MapTeam[];
}

export interface MapEvent {
  event_key: string;
  name: string | null;
  city: string | null;
  state_prov: string | null;
  country: string | null;
  lat: number;
  lng: number;
  event_type: string | null;
  week: number | null;
  start_date: string | null;
  end_date: string | null;
}

export interface MapEventsResponse {
  year: number;
  count: number;
  events: MapEvent[];
}

// ---- Season game info (query/frc_games.py) ----
export interface FrcGameInfo {
  year: number;
  name: string | null;
  video: string | null;
  logo: string | null;
  manual: string | null;
  summary: string | null;
}

export interface FrcGamesResponse {
  games: FrcGameInfo[];
}

// ---- Accounts / auth (query/auth.py) ----
export interface AuthUser {
  id: number;
  username: string;
  email: string | null;
  role: string | null;
  team: string | null;
  bio: string | null;
  avatar_key: string | null;
  color: string | null;
  followers_count: number;
  following_count: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface PublicProfileResponse {
  user: AuthUser;
  favorite_teams: string[];
  favorite_events: string[];
  is_following: boolean;
  is_self: boolean;
}

export interface FollowStatusResponse {
  username: string;
  is_following: boolean;
  followers_count: number;
  following_count: number;
}

export interface UserSummary {
  id: number;
  username: string;
  avatar_key: string | null;
}

export interface UserListResponse {
  users: UserSummary[];
}

export interface ApiKeyResponse {
  api_key: string | null;
}

export interface RegisterPayload {
  username: string;
  password: string;
  email?: string | null;
}

export interface LoginPayload {
  username: string;
  password: string;
}

export interface UpdateProfilePayload {
  username?: string;
  email?: string | null;
  password?: string;
  role?: string;
  team?: string;
  bio?: string;
  avatar_key?: string;
  color?: string;
}

// ---- Favorites (query/favorites.py) ----
export type FavoriteItemType = "team" | "event";

export interface FavoritesResponse {
  teams: string[];
  events: string[];
}

export interface FavoriteStatusResponse {
  item_type: FavoriteItemType;
  item_key: string;
  favorited: boolean;
  count: number;
}

// ---- Static search index (data/teams.json, data/events.json) ----
export interface SearchTeamEntry {
  nickname: string;
  last_year: number | null;
}

export type TeamSearchIndex = Record<string, SearchTeamEntry>;
export type EventSearchIndex = Record<string, string>;

// ---- Team notables (query/notables.py): Hall of Fame + World Champions ----
export interface TeamNotable {
  category: string;
  label: string;
  years: number[];
  /** Impact/Hall of Fame reveal video (Hall of Fame only). */
  video: string | null;
}

export interface TeamNotablesResponse {
  team_number: number;
  notables: TeamNotable[];
}
