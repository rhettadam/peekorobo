import type { MatchResponse, PreMatchTeamCompact } from "../types/api";
import { shortMatchLabel } from "./format";
import type { MetricKey } from "./metrics";
import { isPlayed } from "./prediction";
import { compareMatchesChronologically } from "./predictionSource";

export type PreMatchMetricField = keyof Pick<
  PreMatchTeamCompact,
  "a" | "t" | "e" | "r" | "c" | "ace"
>;

export function preMatchFieldForMetric(metric: MetricKey): PreMatchMetricField {
  switch (metric) {
    case "auto":
      return "a";
    case "teleop":
      return "t";
    case "endgame":
      return "e";
    case "raw":
      return "r";
    case "confidence":
      return "c";
    default:
      return "ace";
  }
}

export interface TrajectoryPoint {
  matchKey: string;
  label: string;
  value: number | null;
  played: boolean;
}

export interface MatchExtremum {
  matchKey: string;
  label: string;
  value: number;
  played: boolean;
}

export interface TeamTrajectory {
  points: TrajectoryPoint[];
  /** Final minus first value in the walk-forward series. */
  delta: number | null;
  /** Average change per match over the last up-to-3 points. */
  momentum: number | null;
  /** Highest metric value across matches (latest match wins ties). */
  best: MatchExtremum | null;
  /** Lowest metric value across matches (latest match wins ties). */
  worst: MatchExtremum | null;
}

export function teamMatchesAtEvent(
  teamNumber: number,
  matches: MatchResponse[],
): MatchResponse[] {
  return matches
    .filter((m) => m.red_teams.includes(teamNumber) || m.blue_teams.includes(teamNumber))
    .sort(compareMatchesChronologically);
}

function readPreMatchValue(
  match: MatchResponse,
  teamNumber: number,
  field: PreMatchMetricField,
): number | null {
  const compact = match.pre_match_teams?.[String(teamNumber)];
  if (!compact) return null;
  const v = compact[field];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function matchExtremum(points: TrajectoryPoint[], mode: "max" | "min"): MatchExtremum | null {
  let pick: TrajectoryPoint | null = null;
  for (const p of points) {
    if (p.value === null) continue;
    if (!pick) {
      pick = p;
      continue;
    }
    const better =
      mode === "max"
        ? p.value > pick.value! || p.value === pick.value
        : p.value < pick.value! || p.value === pick.value;
    if (better) pick = p;
  }
  if (!pick || pick.value === null) return null;
  return {
    matchKey: pick.matchKey,
    label: pick.label,
    value: pick.value,
    played: pick.played,
  };
}

export function buildTeamTrajectory(
  teamNumber: number,
  matches: MatchResponse[],
  metric: MetricKey,
): TeamTrajectory {
  const field = preMatchFieldForMetric(metric);
  const points: TrajectoryPoint[] = teamMatchesAtEvent(teamNumber, matches).map((m) => ({
    matchKey: m.match_key,
    label: shortMatchLabel(m.comp_level, m.set_number, m.match_number),
    value: readPreMatchValue(m, teamNumber, field),
    played: isPlayed(m),
  }));

  const series = points.map((p) => p.value).filter((v): v is number => v !== null);
  const delta = series.length >= 2 ? series[series.length - 1] - series[0] : null;

  const recent = points.filter((p) => p.value !== null).slice(-3);
  let momentum: number | null = null;
  if (recent.length >= 2) {
    const first = recent[0].value!;
    const last = recent[recent.length - 1].value!;
    momentum = (last - first) / (recent.length - 1);
  }

  return {
    points,
    delta,
    momentum,
    best: matchExtremum(points, "max"),
    worst: matchExtremum(points, "min"),
  };
}

export function buildAllTeamTrajectories(
  teamNumbers: number[],
  matches: MatchResponse[],
  metric: MetricKey,
): Map<number, TeamTrajectory> {
  const map = new Map<number, TeamTrajectory>();
  for (const tn of teamNumbers) {
    map.set(tn, buildTeamTrajectory(tn, matches, metric));
  }
  return map;
}
