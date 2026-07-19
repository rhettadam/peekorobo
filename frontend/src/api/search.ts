// Loads the static search index (teams.json, events.json) once and caches it.
// These files are large and rarely change, so they are served from a CDN/static
// host (VITE_SEARCH_BASE_URL) rather than through the API.

import type { EventSearchIndex, TeamSearchIndex, TeamPerfResponse } from "../types/api";

const SEARCH_BASE = (import.meta.env.VITE_SEARCH_BASE_URL ?? "/data").replace(/\/$/, "");

export interface SearchIndex {
  teams: TeamSearchIndex;
  events: EventSearchIndex;
}

let cache: SearchIndex | null = null;
let inflight: Promise<SearchIndex> | null = null;

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${SEARCH_BASE}${path}`, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`Failed to load ${path} (${res.status})`);
  return (await res.json()) as T;
}

export async function loadSearchIndex(): Promise<SearchIndex> {
  if (cache) return cache;
  if (inflight) return inflight;
  inflight = (async () => {
    const [teams, events] = await Promise.all([
      fetchJson<TeamSearchIndex>("/teams.json").catch(() => ({}) as TeamSearchIndex),
      fetchJson<EventSearchIndex>("/events.json").catch(() => ({}) as EventSearchIndex),
    ]);
    cache = { teams, events };
    return cache;
  })();
  return inflight;
}

// A row in a static per-year leaderboard snapshot (data/leaderboards/<year>.json).
interface StaticLeaderboardRow {
  team_number: number;
  ace: number | null;
  raw: number | null;
  confidence: number | null;
  auto_raw: number | null;
  teleop_raw: number | null;
  endgame_raw: number | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
  rank_global: number | null;
  rank_country: number | null;
  rank_state: number | null;
  rank_district: number | null;
  count_global: number | null;
  count_country: number | null;
  count_state: number | null;
  count_district: number | null;
}

interface StaticLeaderboard {
  year: number;
  generated_at: string;
  teams: StaticLeaderboardRow[];
}

/**
 * Try to load a static per-year leaderboard snapshot from the CDN. Returns the
 * rows shaped like the API's TeamPerfResponse[] so callers can use it directly,
 * or null when the snapshot is not available (caller should fall back to the API).
 */
export async function loadStaticLeaderboard(year: number): Promise<TeamPerfResponse[] | null> {
  try {
    const res = await fetch(`${SEARCH_BASE}/leaderboards/${year}.json`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as StaticLeaderboard;
    if (!data || !Array.isArray(data.teams)) return null;
    return data.teams.map((r) => ({
      team_number: r.team_number,
      team_perfs: [
        {
          year: data.year,
          raw: r.raw,
          ace: r.ace,
          confidence: r.confidence,
          auto_raw: r.auto_raw,
          teleop_raw: r.teleop_raw,
          endgame_raw: r.endgame_raw,
          wins: r.wins,
          losses: r.losses,
          ties: r.ties,
          rank_global: r.rank_global,
          rank_country: r.rank_country,
          rank_state: r.rank_state,
          rank_district: r.rank_district,
          count_global: r.count_global,
          count_country: r.count_country,
          count_state: r.count_state,
          count_district: r.count_district,
        },
      ],
    }));
  } catch {
    return null;
  }
}

// ---- Leaderboard filter options (data/countries.json, states.json, district_definitions.json) ----
export interface FilterOption {
  label: string;
  value: string;
}

export interface FilterOptions {
  countries: FilterOption[];
  statesByCountry: Record<string, FilterOption[]>;
  districts: FilterOption[];
}

let filterCache: FilterOptions | null = null;
let filterInflight: Promise<FilterOptions> | null = null;

export async function loadFilterOptions(): Promise<FilterOptions> {
  if (filterCache) return filterCache;
  if (filterInflight) return filterInflight;
  filterInflight = (async () => {
    const [countries, states, districtDefs] = await Promise.all([
      fetchJson<FilterOption[]>("/countries.json").catch(() => [] as FilterOption[]),
      fetchJson<Record<string, FilterOption[]>>("/states.json").catch(
        () => ({}) as Record<string, FilterOption[]>,
      ),
      fetchJson<Record<string, { display_name?: string; name?: string }>>(
        "/district_definitions.json",
      ).catch(() => ({}) as Record<string, { display_name?: string; name?: string }>),
    ]);
    const districts: FilterOption[] = [
      { label: "All Districts", value: "All" },
      ...Object.entries(districtDefs)
        .map(([key, def]) => ({ label: def.display_name || def.name || key, value: key }))
        .sort((a, b) => a.label.localeCompare(b.label)),
    ];
    filterCache = { countries, statesByCountry: states, districts };
    return filterCache;
  })();
  return filterInflight;
}

export interface TeamSuggestion {
  type: "team";
  teamNumber: number;
  nickname: string;
  lastYear: number | null;
}

export interface EventSuggestion {
  type: "event";
  eventKey: string;
  name: string;
}

export type Suggestion = TeamSuggestion | EventSuggestion;

/** Fast client-side prefix/substring search over the loaded index. */
export function searchIndex(index: SearchIndex, rawQuery: string, limit = 12): Suggestion[] {
  const query = rawQuery.trim().toLowerCase();
  if (!query) return [];

  const teamResults: Array<{ score: number; s: TeamSuggestion }> = [];
  for (const [numStr, info] of Object.entries(index.teams)) {
    const nickname = info.nickname || "";
    const nickLower = nickname.toLowerCase();
    let score = -1;
    if (numStr === query) score = 0;
    else if (numStr.startsWith(query)) score = 1;
    else if (nickLower.startsWith(query)) score = 2;
    else if (nickLower.includes(query)) score = 3;
    else if (numStr.includes(query)) score = 4;
    if (score >= 0) {
      teamResults.push({
        score,
        s: {
          type: "team",
          teamNumber: Number(numStr),
          nickname,
          lastYear: info.last_year ?? null,
        },
      });
    }
  }

  // Token-based event matching so queries like "2025 bayou regional" or
  // "bayou regional 2024" resolve: every term must appear somewhere in
  // "<year> <name> <key>". The year prefix of the event key is searchable.
  const terms = query.split(/\s+/).filter(Boolean);
  const eventResults: Array<{ score: number; s: EventSuggestion }> = [];
  for (const [key, name] of Object.entries(index.events)) {
    const keyLower = key.toLowerCase();
    const nameLower = (name || "").toLowerCase();
    const year = /^\d{4}/.test(key) ? key.slice(0, 4) : "";
    const haystack = `${year} ${nameLower} ${keyLower}`;
    if (!terms.every((t) => haystack.includes(t))) continue;
    let score = 4;
    if (keyLower === query) score = 0;
    else if (keyLower.startsWith(query)) score = 1;
    else if (nameLower.startsWith(query)) score = 2;
    else if (nameLower.includes(query)) score = 3;
    const label = year ? `${year} ${name || key}` : name || key;
    eventResults.push({ score, s: { type: "event", eventKey: key, name: label } });
  }

  teamResults.sort((a, b) => a.score - b.score || a.s.teamNumber - b.s.teamNumber);
  // Same relevance first, then newest event (key is year-prefixed) first.
  eventResults.sort((a, b) => a.score - b.score || b.s.eventKey.localeCompare(a.s.eventKey));

  const half = Math.ceil(limit / 2);
  const teams = teamResults.slice(0, half).map((r) => r.s);
  const events = eventResults.slice(0, limit - teams.length).map((r) => r.s);
  return [...teams, ...events];
}
