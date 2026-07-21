// TanStack Query hooks. One hook per data need. This is the replacement for the
// old Dash "callback hell": components declare what data they want and get
// caching, de-duplication, background refetch, and loading/error states for free.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiGet, type QueryParams } from "./client";
import {
  loadFilterOptions,
  loadSearchIndex,
  loadStaticLeaderboard,
  type FilterOptions,
  type SearchIndex,
} from "./search";
import type {
  EventAwardsResponse,
  EventData,
  EventInsightsResponse,
  EventMatchResponse,
  EventPerfsResponse,
  EventRankingsResponse,
  EventResponse,
  EventTeamsResponse,
  FrcGamesResponse,
  InsightsOverviewResponse,
  MapEventsResponse,
  MapTeamsResponse,
  TeamAwardsResponse,
  TeamData,
  TeamEventsResponse,
  TeamNotablesResponse,
  TeamPerfListResponse,
  TeamPerfResponse,
} from "../types/api";
import { yearFromEventKey } from "../lib/format";

// Read data is cached ~5 min to match the backend/CDN freshness target.
const FIVE_MIN = 5 * 60 * 1000;

// ---- Search index ----
export function useSearchIndex(): UseQueryResult<SearchIndex> {
  return useQuery({
    queryKey: ["search-index"],
    queryFn: loadSearchIndex,
    staleTime: 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });
}

// ---- Season game info ----
export function useFrcGames(): UseQueryResult<FrcGamesResponse> {
  return useQuery({
    queryKey: ["frc-games"],
    queryFn: () => apiGet<FrcGamesResponse>("/frc_games"),
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });
}

export function useInsightsOverview(): UseQueryResult<InsightsOverviewResponse> {
  return useQuery({
    queryKey: ["insights-overview"],
    queryFn: () => apiGet<InsightsOverviewResponse>("/insights/overview"),
    staleTime: FIVE_MIN,
  });
}

// ---- Leaderboard filter options ----
export function useFilterOptions(): UseQueryResult<FilterOptions> {
  return useQuery({
    queryKey: ["filter-options"],
    queryFn: loadFilterOptions,
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });
}

// ---- Team ----
export function useTeamInfo(teamNumber: number): UseQueryResult<TeamData | null> {
  return useQuery({
    queryKey: ["team-info", teamNumber],
    enabled: Number.isFinite(teamNumber) && teamNumber > 0,
    staleTime: FIVE_MIN,
    queryFn: async () => {
      const res = await apiGet<{ team_info: TeamData[] }>("/teams", { team_number: teamNumber });
      return res.team_info.find((t) => t.team_number === teamNumber) ?? res.team_info[0] ?? null;
    },
  });
}

export function useTeamPerfs(
  teamNumber: number,
  year?: number,
): UseQueryResult<TeamPerfResponse> {
  return useQuery({
    queryKey: ["team-perfs", teamNumber, year ?? "all"],
    enabled: Number.isFinite(teamNumber) && teamNumber > 0,
    staleTime: FIVE_MIN,
    queryFn: () =>
      apiGet<TeamPerfResponse>(`/team_perfs/${teamNumber}`, year ? { year } : undefined),
  });
}

export function useTeamEvents(
  teamNumber: number,
  year?: number,
): UseQueryResult<TeamEventsResponse> {
  const path = year ? `/team/${teamNumber}/events/${year}` : `/team/${teamNumber}/events`;
  return useQuery({
    queryKey: ["team-events", teamNumber, year ?? "all"],
    enabled: Number.isFinite(teamNumber) && teamNumber > 0,
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<TeamEventsResponse>(path),
  });
}

export function useTeamNotables(teamNumber: number): UseQueryResult<TeamNotablesResponse> {
  return useQuery({
    queryKey: ["team-notables", teamNumber],
    enabled: Number.isFinite(teamNumber) && teamNumber > 0,
    staleTime: 24 * 60 * 60 * 1000,
    queryFn: () => apiGet<TeamNotablesResponse>(`/team/${teamNumber}/notables`),
  });
}

export function useTeamAwards(
  teamNumber: number,
  year?: number,
): UseQueryResult<TeamAwardsResponse> {
  const path = year ? `/team/${teamNumber}/awards/${year}` : `/team/${teamNumber}/awards`;
  return useQuery({
    queryKey: ["team-awards", teamNumber, year ?? "all"],
    enabled: Number.isFinite(teamNumber) && teamNumber > 0,
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<TeamAwardsResponse>(path),
  });
}

// ---- Events ----
export function useEvents(year: number, params?: QueryParams): UseQueryResult<EventResponse> {
  return useQuery({
    queryKey: ["events", year, params ?? {}],
    enabled: Number.isFinite(year),
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<EventResponse>(`/events/${year}`, params),
  });
}

/** Season-wide per-event ACE statistics ("Event Insights"). */
export function useEventInsights(
  year: number,
  options: { enabled?: boolean } = {},
): UseQueryResult<EventInsightsResponse> {
  return useQuery({
    queryKey: ["event-insights", year],
    enabled: Number.isFinite(year) && (options.enabled ?? true),
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<EventInsightsResponse>(`/events/${year}/insights`),
  });
}

/** Single event metadata. Derived from the year's event list (no single-event endpoint). */
export function useEvent(eventKey: string): UseQueryResult<EventData | null> {
  const year = yearFromEventKey(eventKey);
  return useQuery({
    queryKey: ["event", eventKey],
    enabled: Boolean(eventKey) && year !== null,
    staleTime: FIVE_MIN,
    queryFn: async () => {
      const res = await apiGet<EventResponse>(`/events/${year}`);
      return res.events.find((e) => e.event_key === eventKey) ?? null;
    },
  });
}

export function useEventTeams(eventKey: string): UseQueryResult<EventTeamsResponse> {
  return useQuery({
    queryKey: ["event-teams", eventKey],
    enabled: Boolean(eventKey),
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<EventTeamsResponse>(`/event/${eventKey}/teams`),
  });
}

export function useEventMatches(
  eventKey: string,
  params?: QueryParams,
): UseQueryResult<EventMatchResponse> {
  return useQuery({
    queryKey: ["event-matches", eventKey, params ?? {}],
    enabled: Boolean(eventKey),
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<EventMatchResponse>(`/event/${eventKey}/matches`, params),
  });
}

export function useEventRankings(eventKey: string): UseQueryResult<EventRankingsResponse> {
  return useQuery({
    queryKey: ["event-rankings", eventKey],
    enabled: Boolean(eventKey),
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<EventRankingsResponse>(`/event/${eventKey}/rankings`),
  });
}

export function useEventAwards(eventKey: string): UseQueryResult<EventAwardsResponse> {
  return useQuery({
    queryKey: ["event-awards", eventKey],
    enabled: Boolean(eventKey),
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<EventAwardsResponse>(`/event/${eventKey}/awards`),
  });
}

export function useEventPerfs(eventKey: string): UseQueryResult<EventPerfsResponse> {
  return useQuery({
    queryKey: ["event-perfs", eventKey],
    enabled: Boolean(eventKey),
    staleTime: FIVE_MIN,
    queryFn: () => apiGet<EventPerfsResponse>(`/event/${eventKey}/event_perfs`),
  });
}

// ---- Map: located teams and events for the interactive map ----
export function useMapTeams(): UseQueryResult<MapTeamsResponse> {
  return useQuery({
    queryKey: ["map-teams"],
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    queryFn: () => apiGet<MapTeamsResponse>("/map/teams"),
  });
}

export function useMapEvents(year: number): UseQueryResult<MapEventsResponse> {
  return useQuery({
    queryKey: ["map-events", year],
    enabled: Number.isFinite(year),
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    queryFn: () => apiGet<MapEventsResponse>("/map/events", { year }),
  });
}

// ---- Leaderboard: all team performances for a year (paginated under the hood) ----
export interface LeaderboardFilters {
  country?: string;
  state_prov?: string;
  district_key?: string;
}

async function fetchAllTeamPerfs(year: number, filters: LeaderboardFilters) {
  const pageSize = 500;
  const rows: TeamPerfResponse[] = [];
  let cursor: number | null | undefined = undefined;
  // Safety cap: at 500/page this covers >10k teams.
  for (let i = 0; i < 40; i++) {
    const res: TeamPerfListResponse = await apiGet<TeamPerfListResponse>("/team_perfs", {
      year,
      limit: pageSize,
      next_team_number: cursor ?? undefined,
      ...filters,
    });
    rows.push(...res.team_perfs);
    if (res.next === null || res.next === undefined) break;
    cursor = res.next;
  }
  return rows;
}

export function useLeaderboard(
  year: number,
  filters: LeaderboardFilters = {},
  options: { enabled?: boolean } = {},
): UseQueryResult<TeamPerfResponse[]> {
  const hasFilters = Boolean(filters.country || filters.state_prov || filters.district_key);
  return useQuery({
    queryKey: ["leaderboard", year, filters],
    enabled: Number.isFinite(year) && (options.enabled ?? true),
    staleTime: FIVE_MIN,
    queryFn: async () => {
      // Prefer the static per-year snapshot (served from the CDN) when unfiltered;
      // fall back to paginating the API. Filtered views always use the API.
      if (!hasFilters) {
        const staticRows = await loadStaticLeaderboard(year);
        if (staticRows) return staticRows;
      }
      return fetchAllTeamPerfs(year, filters);
    },
  });
}

/**
 * Fast "top N by global rank" leaderboard for the initial paint. This is a
 * single small request, so the page renders instantly; the full year is loaded
 * separately (see useLeaderboard) only once the user interacts.
 */
export function useLeaderboardPreview(
  year: number,
  limit = 100,
): UseQueryResult<TeamPerfResponse[]> {
  return useQuery({
    queryKey: ["leaderboard-preview", year, limit],
    enabled: Number.isFinite(year),
    staleTime: FIVE_MIN,
    queryFn: async () => {
      const res = await apiGet<TeamPerfListResponse>("/team_perfs", {
        year,
        limit,
        sort: "rank",
      });
      return res.team_perfs;
    },
  });
}
