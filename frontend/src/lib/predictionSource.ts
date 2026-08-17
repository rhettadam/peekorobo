import type { EventPerfEntry, MatchResponse, TeamPerfInfo } from "../types/api";

export type PreMatchRatingSource =
  | "in_event"
  | "carry_prior"
  | "prior_event"
  | "prior_season"
  | "unrated";

export interface PreMatchTeamRating {
  source: PreMatchRatingSource;
  rating?: number | null;
}

export type PreMatchTeamRatings = Record<string, PreMatchTeamRating>;

export const PRE_MATCH_SOURCE_LABELS: Record<PreMatchRatingSource, string> = {
  in_event: "In-event walk-forward",
  carry_prior: "Carried from prior event",
  prior_event: "Earlier event this season",
  prior_season: "Prior season ACE",
  unrated: "No rating history",
};

export const PRE_MATCH_SOURCE_HINTS: Record<PreMatchRatingSource, string> = {
  in_event: "This team already played earlier matches at this event before this one.",
  carry_prior: "First match at this event; model seeds from the team's most recent prior event this season.",
  prior_event: "First match at this event; rating comes from an earlier event this season.",
  prior_season: "First event of the season for this team; model uses prior-year ACE.",
  unrated: "No prior matches or ACE history were found for this team.",
};

export const PRE_MATCH_SOURCE_COLORS: Record<PreMatchRatingSource, string> = {
  in_event: "green",
  carry_prior: "violet",
  prior_event: "cyan",
  prior_season: "orange",
  unrated: "gray",
};

const COMP_LEVEL_ORDER: Record<string, number> = { qm: 0, ef: 1, qf: 2, sf: 3, f: 4 };

export function compareMatchesChronologically(a: MatchResponse, b: MatchResponse): number {
  const lvl = (COMP_LEVEL_ORDER[a.comp_level] ?? 9) - (COMP_LEVEL_ORDER[b.comp_level] ?? 9);
  if (lvl !== 0) return lvl;
  if (a.set_number !== b.set_number) return a.set_number - b.set_number;
  return a.match_number - b.match_number;
}

function teamPriorMatchesAtEvent(
  team: number,
  match: MatchResponse,
  eventMatches: MatchResponse[],
): number {
  const sorted = [...eventMatches].sort(compareMatchesChronologically);
  const idx = sorted.findIndex((m) => m.match_key === match.match_key);
  if (idx <= 0) return 0;
  let count = 0;
  for (let i = 0; i < idx; i++) {
    const m = sorted[i];
    if (m.red_teams.includes(team) || m.blue_teams.includes(team)) count++;
  }
  return count;
}

function eventStart(
  eventKey: string,
  eventsByKey: Map<string, { start_date: string }>,
): string {
  return eventsByKey.get(eventKey)?.start_date ?? eventKey;
}

function priorEventsThisSeason(
  team: number,
  eventKey: string,
  eventStartDate: string | null,
  eventsByKey: Map<string, { start_date: string }>,
  seasonPerf: TeamPerfInfo | undefined,
): string[] {
  const entries = (seasonPerf?.event_perf ?? []) as EventPerfEntry[];
  const prior: string[] = [];
  const currentStart = eventStartDate ?? eventStart(eventKey, eventsByKey);
  for (const ep of entries) {
    const ek = ep.event_key;
    if (!ek || ek === eventKey) continue;
    const otherStart = eventStart(ek, eventsByKey);
    if (otherStart < currentStart) prior.push(ek);
  }
  return prior.sort((a, b) => eventStart(a, eventsByKey).localeCompare(eventStart(b, eventsByKey)));
}

function latestPriorEventAce(
  priorEventKeys: string[],
  seasonPerf: TeamPerfInfo | undefined,
): number | null {
  if (!seasonPerf?.event_perf?.length || !priorEventKeys.length) return null;
  const byKey = new Map<string, EventPerfEntry>();
  for (const ep of seasonPerf.event_perf as EventPerfEntry[]) {
    if (ep.event_key) byKey.set(ep.event_key, ep);
  }
  for (let i = priorEventKeys.length - 1; i >= 0; i--) {
    const ace = byKey.get(priorEventKeys[i])?.ace;
    if (typeof ace === "number" && Number.isFinite(ace)) return ace;
  }
  return null;
}

export interface PreMatchSourceContext {
  match: MatchResponse;
  eventMatches: MatchResponse[];
  eventKey: string;
  eventStartDate: string | null;
  eventsByKey: Map<string, { start_date: string }>;
  teamSeasonPerf: Map<number, TeamPerfInfo>;
  teamPriorSeasonPerf: Map<number, TeamPerfInfo>;
}

function inferPreMatchSource(
  team: number,
  ctx: PreMatchSourceContext,
): PreMatchTeamRating {
  const priorInEvent = teamPriorMatchesAtEvent(team, ctx.match, ctx.eventMatches);
  if (priorInEvent > 0) {
    return { source: "in_event" };
  }

  const seasonPerf = ctx.teamSeasonPerf.get(team);
  const priorEvents = priorEventsThisSeason(
    team,
    ctx.eventKey,
    ctx.eventStartDate,
    ctx.eventsByKey,
    seasonPerf,
  );

  if (priorEvents.length > 0) {
    const ace = latestPriorEventAce(priorEvents, seasonPerf);
    return {
      source: "carry_prior",
      rating: ace,
    };
  }

  const priorYear = ctx.teamPriorSeasonPerf.get(team);
  if (priorYear && typeof priorYear.ace === "number" && Number.isFinite(priorYear.ace)) {
    return { source: "prior_season", rating: priorYear.ace };
  }

  return { source: "unrated" };
}

export function computePreMatchTeamSources(ctx: PreMatchSourceContext): PreMatchTeamRatings | null {
  const teams = [...ctx.match.red_teams, ...ctx.match.blue_teams];
  if (!teams.length) return null;
  const out: PreMatchTeamRatings = {};
  for (const team of teams) {
    out[String(team)] = inferPreMatchSource(team, ctx);
  }
  return out;
}

export function teamPreMatchRating(
  ratings: PreMatchTeamRatings | null | undefined,
  teamNumber: number,
): PreMatchTeamRating | null {
  if (!ratings) return null;
  return ratings[String(teamNumber)] ?? null;
}
