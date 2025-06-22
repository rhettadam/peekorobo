-- PostgreSQL schema for EPA data
-- This replaces the SQLite schema in epa.py

-- Events table (replaces 'e' table)
CREATE TABLE IF NOT EXISTS events (
    event_key TEXT PRIMARY KEY,
    name TEXT,
    year INTEGER,
    start_date TEXT,
    end_date TEXT,
    event_type TEXT,
    city TEXT,
    state_prov TEXT,
    country TEXT,
    website TEXT
);

-- Event teams table (replaces 'et' table)
CREATE TABLE IF NOT EXISTS event_teams (
    event_key TEXT,
    team_number INTEGER,
    nickname TEXT,
    city TEXT,
    state_prov TEXT,
    country TEXT,
    PRIMARY KEY (event_key, team_number)
);

-- Rankings table (replaces 'r' table)
CREATE TABLE IF NOT EXISTS event_rankings (
    event_key TEXT,
    team_number INTEGER,
    rank INTEGER,
    wins INTEGER,
    losses INTEGER,
    ties INTEGER,
    dq INTEGER,
    PRIMARY KEY (event_key, team_number)
);

-- OPRs table (replaces 'o' table)
CREATE TABLE IF NOT EXISTS event_oprs (
    event_key TEXT,
    team_number INTEGER,
    opr REAL,
    PRIMARY KEY (event_key, team_number)
);

-- Matches table (replaces 'm' table)
CREATE TABLE IF NOT EXISTS event_matches (
    match_key TEXT PRIMARY KEY,
    event_key TEXT,
    comp_level TEXT,
    match_number INTEGER,
    set_number INTEGER,
    red_teams TEXT,
    blue_teams TEXT,
    red_score INTEGER,
    blue_score INTEGER,
    winning_alliance TEXT,
    youtube_key TEXT
);

-- Awards table (replaces 'a' table)
CREATE TABLE IF NOT EXISTS event_awards (
    event_key TEXT,
    team_number INTEGER,
    award_name TEXT,
    year INTEGER,
    PRIMARY KEY (event_key, team_number, award_name)
);

-- EPA data table (replaces epa_YYYY tables)
CREATE TABLE IF NOT EXISTS team_epas (
    team_number INTEGER,
    year INTEGER,
    nickname TEXT,
    city TEXT,
    state_prov TEXT,
    country TEXT,
    website TEXT,
    normal_epa REAL,
    epa REAL,
    confidence REAL,
    auto_epa REAL,
    teleop_epa REAL,
    endgame_epa REAL,
    wins INTEGER,
    losses INTEGER,
    event_epas JSONB,
    PRIMARY KEY (team_number, year)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_events_year ON events(year);
CREATE INDEX IF NOT EXISTS idx_event_teams_event ON event_teams(event_key);
CREATE INDEX IF NOT EXISTS idx_event_teams_team ON event_teams(team_number);
CREATE INDEX IF NOT EXISTS idx_event_rankings_event ON event_rankings(event_key);
CREATE INDEX IF NOT EXISTS idx_event_oprs_event ON event_oprs(event_key);
CREATE INDEX IF NOT EXISTS idx_event_matches_event ON event_matches(event_key);
CREATE INDEX IF NOT EXISTS idx_event_awards_event ON event_awards(event_key);
CREATE INDEX IF NOT EXISTS idx_team_epas_year ON team_epas(year);
CREATE INDEX IF NOT EXISTS idx_team_epas_team ON team_epas(team_number); 