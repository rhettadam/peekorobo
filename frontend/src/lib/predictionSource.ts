import type { EventPerfEntry, MatchResponse, PreMatchTeamCompact, TeamPerfInfo } from "../types/api";

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

export interface PreMatchTeamDisplay {
  source: PreMatchRatingSource;
  ace: number | null;
  auto: number | null;
  teleop: number | null;
  endgame: number | null;
  raw: number | null;
  confidence: number | null;
}

export type PreMatchTeamRatings = Record<string, PreMatchTeamRating>;
export type PreMatchTeamDisplays = Record<string, PreMatchTeamDisplay>;

export const PRE_MATCH_SOURCE_LABELS: Record<PreMatchRatingSource, string> = {
  in_event: "In-event",
  carry_prior: "Prior event",
  prior_event: "Prior event",
  prior_season: "Prior season",
  unrated: "Unrated",
};

export const PRE_MATCH_SOURCE_HINTS: Record<PreMatchRatingSource, string> = {
  in_event: "Walk-forward ACE after this team's earlier matches at this event.",
  carry_prior: "Seeded from the team's most recent prior event this season.",
  prior_event: "From an earlier event this season (no in-event history yet).",
  prior_season: "Prior-year season ACE — typical for a team's first match of the season.",
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

/** Match backend event_order: (start_date, event_key), including same-day ties. */
function eventOrderKey(
  eventKey: string,
  eventsByKey: Map<string, { start_date: string }>,
  startDate?: string | null,
): string {
  return `${startDate || eventStart(eventKey, eventsByKey)}\t${eventKey}`;
}

function priorEventsThisSeason(
  eventKey: string,
  eventStartDate: string | null,
  eventsByKey: Map<string, { start_date: string }>,
  seasonPerf: TeamPerfInfo | undefined,
): string[] {
  const entries = (seasonPerf?.event_perf ?? []) as EventPerfEntry[];
  const prior: string[] = [];
  const currentKey = eventOrderKey(eventKey, eventsByKey, eventStartDate);
  for (const ep of entries) {
    const ek = ep.event_key;
    if (!ek || ek === eventKey) continue;
    if (eventOrderKey(ek, eventsByKey) < currentKey) prior.push(ek);
  }
  return prior.sort((a, b) =>
    eventOrderKey(a, eventsByKey).localeCompare(eventOrderKey(b, eventsByKey)),
  );
}

function latestPriorEventEntry(
  priorEventKeys: string[],
  seasonPerf: TeamPerfInfo | undefined,
): EventPerfEntry | null {
  if (!seasonPerf?.event_perf?.length || !priorEventKeys.length) return null;
  const byKey = new Map<string, EventPerfEntry>();
  for (const ep of seasonPerf.event_perf as EventPerfEntry[]) {
    if (ep.event_key) byKey.set(ep.event_key, ep);
  }
  for (let i = priorEventKeys.length - 1; i >= 0; i--) {
    const ep = byKey.get(priorEventKeys[i]);
    if (ep && typeof ep.ace === "number" && Number.isFinite(ep.ace)) return ep;
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
    ctx.eventKey,
    ctx.eventStartDate,
    ctx.eventsByKey,
    seasonPerf,
  );

  if (priorEvents.length > 0) {
    const ep = latestPriorEventEntry(priorEvents, seasonPerf);
    return {
      source: "carry_prior",
      rating: typeof ep?.ace === "number" ? ep.ace : null,
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

function compactToDisplay(compact: PreMatchTeamCompact): Omit<PreMatchTeamDisplay, "source"> {
  return {
    ace: compact.ace,
    auto: compact.a,
    teleop: compact.t,
    endgame: compact.e,
    raw: compact.r,
    confidence: compact.c,
  };
}

function fromSeasonPerf(perf: TeamPerfInfo | undefined): Omit<PreMatchTeamDisplay, "source"> | null {
  if (!perf) return null;
  const ace = typeof perf.ace === "number" ? perf.ace : null;
  if (ace === null) return null;
  return {
    ace,
    auto: typeof perf.auto_raw === "number" ? perf.auto_raw : null,
    teleop: typeof perf.teleop_raw === "number" ? perf.teleop_raw : null,
    endgame: typeof perf.endgame_raw === "number" ? perf.endgame_raw : null,
    raw: typeof perf.raw === "number" ? perf.raw : null,
    confidence: typeof perf.confidence === "number" ? perf.confidence : null,
  };
}

function fromEventPerf(ep: EventPerfEntry | null): Omit<PreMatchTeamDisplay, "source"> | null {
  if (!ep || typeof ep.ace !== "number") return null;
  return {
    ace: ep.ace,
    auto: typeof ep.auto_raw === "number" ? ep.auto_raw : null,
    teleop: typeof ep.teleop_raw === "number" ? ep.teleop_raw : null,
    endgame: typeof ep.endgame_raw === "number" ? ep.endgame_raw : null,
    raw: typeof ep.raw === "number" ? ep.raw : null,
    confidence: typeof ep.confidence === "number" ? ep.confidence : null,
  };
}

function numOrZero(v: number | null | undefined): number {
  return typeof v === "number" && Number.isFinite(v) ? v : 0;
}

function isZeroDisplay(d: Omit<PreMatchTeamDisplay, "source">): boolean {
  return (
    numOrZero(d.auto) === 0 &&
    numOrZero(d.teleop) === 0 &&
    numOrZero(d.endgame) === 0 &&
    numOrZero(d.raw) === 0 &&
    numOrZero(d.confidence) === 0 &&
    numOrZero(d.ace) === 0
  );
}

function phasesMissing(d: Omit<PreMatchTeamDisplay, "source">): boolean {
  return numOrZero(d.auto) === 0 && numOrZero(d.teleop) === 0 && numOrZero(d.endgame) === 0;
}

const UNRATED_DISPLAY: Omit<PreMatchTeamDisplay, "source"> = {
  ace: 0,
  auto: 0,
  teleop: 0,
  endgame: 0,
  raw: 0,
  confidence: 0,
};

function fillFromSource(
  source: PreMatchRatingSource,
  team: number,
  enrichment: PreMatchEnrichment,
): Omit<PreMatchTeamDisplay, "source"> | null {
  if (source === "prior_season") {
    return fromSeasonPerf(enrichment.teamPriorSeasonPerf.get(team));
  }
  if (source === "carry_prior" || source === "prior_event") {
    const season = enrichment.teamSeasonPerf.get(team);
    const priorKeys = priorEventsThisSeason(
      enrichment.eventKey,
      enrichment.eventStartDate,
      enrichment.eventsByKey,
      season,
    );
    return fromEventPerf(latestPriorEventEntry(priorKeys, season));
  }
  return null;
}

export interface PreMatchEnrichment {
  teamSeasonPerf: Map<number, TeamPerfInfo>;
  teamPriorSeasonPerf: Map<number, TeamPerfInfo>;
  eventKey: string;
  eventStartDate: string | null;
  eventsByKey: Map<string, { start_date: string }>;
}

/** Walk-forward snapshots for in-event / prior-event. Prior-season and unrated ignore stored junk. */
export function mergePreMatchDisplays(
  stored: Record<string, PreMatchTeamCompact> | null | undefined,
  sources: PreMatchTeamRatings | null,
  teams: number[],
  enrichment?: PreMatchEnrichment,
): PreMatchTeamDisplays | null {
  if (!sources && !stored) return null;
  const out: PreMatchTeamDisplays = {};
  for (const team of teams) {
    const key = String(team);
    const inferred = sources?.[key]?.source;
    const compact = stored?.[key];
    const storedDisplay = compact ? compactToDisplay(compact) : null;

    if (inferred === "unrated") {
      out[key] = { source: "unrated", ...UNRATED_DISPLAY };
      continue;
    }

    if (inferred === "prior_season") {
      const filled = enrichment ? fillFromSource("prior_season", team, enrichment) : null;
      out[key] = filled
        ? { source: "prior_season", ...filled }
        : { source: "prior_season", ...(storedDisplay && !isZeroDisplay(storedDisplay) ? storedDisplay : UNRATED_DISPLAY) };
      continue;
    }

    let base = storedDisplay && !isZeroDisplay(storedDisplay) ? storedDisplay : null;
    if ((!base || phasesMissing(base)) && enrichment && inferred) {
      const filled = fillFromSource(inferred, team, enrichment);
      if (filled) base = filled;
    }

    const source: PreMatchRatingSource = inferred ?? (base ? "in_event" : "unrated");
    if (!base || source === "unrated") {
      out[key] = { source: "unrated", ...UNRATED_DISPLAY };
    } else {
      out[key] = { source, ...base };
    }
  }
  return out;
}

export function sumPreMatchField(
  ratings: PreMatchTeamDisplays | null,
  teams: number[],
  field: keyof Omit<PreMatchTeamDisplay, "source">,
): number | null {
  if (!ratings) return null;
  let sum = 0;
  let known = 0;
  for (const team of teams) {
    const v = ratings[String(team)]?.[field];
    if (typeof v === "number" && Number.isFinite(v)) {
      sum += v;
      known += 1;
    }
  }
  return known > 0 ? sum : null;
}

export function meanPreMatchField(
  ratings: PreMatchTeamDisplays | null,
  teams: number[],
  field: keyof Omit<PreMatchTeamDisplay, "source">,
): number | null {
  if (!ratings) return null;
  let sum = 0;
  let known = 0;
  for (const team of teams) {
    const v = ratings[String(team)]?.[field];
    if (typeof v === "number" && Number.isFinite(v)) {
      sum += v;
      known += 1;
    }
  }
  return known > 0 ? sum / known : null;
}

/** Collect numeric values across matches' stored pre_match_teams for percentile coloring. */
export function collectEventPreMatchValues(
  matches: MatchResponse[],
  field: "a" | "t" | "e" | "r" | "c" | "ace",
): Array<number | null> {
  const out: Array<number | null> = [];
  for (const m of matches) {
    const teams = m.pre_match_teams;
    if (!teams) continue;
    for (const entry of Object.values(teams)) {
      const v = entry?.[field];
      out.push(typeof v === "number" && Number.isFinite(v) ? v : null);
    }
  }
  return out;
}
