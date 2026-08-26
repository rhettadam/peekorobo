import type { EventPerfInfo, MatchResponse } from "../types/api";
import { isPlayed, predictedMatchScores } from "./prediction";

/** Predicted − actual. Positive = underperformance vs prediction. */
export function allianceResidual(pred: number, actual: number): number {
  return pred - actual;
}

export interface EventResidualStats {
  mean: number;
  std: number;
  meanAbs: number;
  /** Default Defense Indicator threshold X (= 1σ of residuals). */
  defaultThreshold: number;
  /** Number of alliance-side residuals used. */
  count: number;
  /** Played quals where either side's |residual| exceeds defaultThreshold. */
  largeImpactMatchCount: number;
}

export interface MatchDefenseRow {
  match: MatchResponse;
  redPred: number;
  bluePred: number;
  /** Defensive impact attributed to red (opp blue underperformed). */
  redImpact: number;
  /** Defensive impact attributed to blue (opp red underperformed). */
  blueImpact: number;
  redFlagged: boolean;
  blueFlagged: boolean;
}

export interface TeamImpactPoint {
  matchKey: string;
  matchNumber: number;
  impact: number;
  flagged: boolean;
}

export interface TeamDefenseRow {
  teamNumber: number;
  defensePct: number | null;
  flaggedCount: number;
  matchCount: number;
  meanImpact: number | null;
  medianImpact: number | null;
  maxImpact: number | null;
  sumImpact: number | null;
  stdImpact: number | null;
  impactSeries: TeamImpactPoint[];
  raw: number | null;
  confidence: number | null;
  ace: number | null;
  auto_raw: number | null;
  teleop_raw: number | null;
  endgame_raw: number | null;
}

function mean(xs: number[]): number | null {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
}

function stdDev(xs: number[]): number | null {
  if (xs.length < 2) return xs.length === 1 ? 0 : null;
  const m = mean(xs)!;
  const variance = xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1);
  return Math.sqrt(variance);
}

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const sorted = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function playedQuals(matches: MatchResponse[]): MatchResponse[] {
  return matches.filter((m) => m.comp_level === "qm" && isPlayed(m));
}

/**
 * Collect residuals (pred − actual) for both alliances across played quals.
 * Used for event σ and the default Defense Indicator threshold.
 */
export function eventResidualStats(
  matches: MatchResponse[],
  aceByTeam: Map<number, number | null | undefined> | undefined,
): EventResidualStats | null {
  const quals = playedQuals(matches);
  const residuals: number[] = [];
  let largeImpactMatchCount = 0;

  for (const m of quals) {
    const pred = predictedMatchScores(m, aceByTeam);
    if (!pred) continue;
    const redR = allianceResidual(pred.red, m.red_score);
    const blueR = allianceResidual(pred.blue, m.blue_score);
    residuals.push(redR, blueR);
  }

  if (residuals.length === 0) return null;

  const m = mean(residuals)!;
  const s = stdDev(residuals) ?? 0;
  const defaultThreshold = Math.max(1, Math.round(s * 10) / 10);
  const meanAbs = mean(residuals.map(Math.abs))!;

  for (const match of quals) {
    const pred = predictedMatchScores(match, aceByTeam);
    if (!pred) continue;
    const redR = Math.abs(allianceResidual(pred.red, match.red_score));
    const blueR = Math.abs(allianceResidual(pred.blue, match.blue_score));
    if (redR > defaultThreshold || blueR > defaultThreshold) largeImpactMatchCount += 1;
  }

  return {
    mean: m,
    std: s,
    meanAbs,
    defaultThreshold,
    count: residuals.length,
    largeImpactMatchCount,
  };
}

/** Suggested slider max based on event residual spread. */
export function thresholdSliderMax(stats: EventResidualStats | null, matchRows: MatchDefenseRow[]): number {
  const fromStats = stats ? Math.max(stats.std * 3, stats.defaultThreshold * 2) : 40;
  let maxImpact = 0;
  for (const r of matchRows) {
    maxImpact = Math.max(maxImpact, Math.abs(r.redImpact), Math.abs(r.blueImpact));
  }
  return Math.max(20, Math.ceil(Math.max(fromStats, maxImpact * 0.75) / 5) * 5);
}

export function matchDefenseRows(
  matches: MatchResponse[],
  aceByTeam: Map<number, number | null | undefined> | undefined,
  threshold: number,
): MatchDefenseRow[] {
  const rows: MatchDefenseRow[] = [];
  for (const m of playedQuals(matches)) {
    const pred = predictedMatchScores(m, aceByTeam);
    if (!pred) continue;
    // Red's defensive impact = how much blue underperformed prediction
    const redImpact = allianceResidual(pred.blue, m.blue_score);
    // Blue's defensive impact = how much red underperformed prediction
    const blueImpact = allianceResidual(pred.red, m.red_score);
    rows.push({
      match: m,
      redPred: pred.red,
      bluePred: pred.blue,
      redImpact,
      blueImpact,
      redFlagged: redImpact > threshold,
      blueFlagged: blueImpact > threshold,
    });
  }
  rows.sort((a, b) => a.match.match_number - b.match.match_number);
  return rows;
}

export function teamDefenseRows(
  matches: MatchResponse[],
  teamNumbers: number[],
  perfsByTeam: Map<number, EventPerfInfo>,
  aceByTeam: Map<number, number | null | undefined> | undefined,
  threshold: number,
): TeamDefenseRow[] {
  const quals = playedQuals(matches);
  const rows: TeamDefenseRow[] = [];

  for (const tn of teamNumbers) {
    const impacts: number[] = [];
    const series: TeamImpactPoint[] = [];
    let flaggedCount = 0;

    for (const m of quals) {
      const onRed = m.red_teams.includes(tn);
      const onBlue = m.blue_teams.includes(tn);
      if (!onRed && !onBlue) continue;
      const pred = predictedMatchScores(m, aceByTeam);
      if (!pred) continue;
      const impact = onRed
        ? allianceResidual(pred.blue, m.blue_score)
        : allianceResidual(pred.red, m.red_score);
      const flagged = impact > threshold;
      if (flagged) flaggedCount += 1;
      impacts.push(impact);
      series.push({
        matchKey: m.match_key,
        matchNumber: m.match_number,
        impact,
        flagged,
      });
    }

    series.sort((a, b) => a.matchNumber - b.matchNumber);
    const matchCount = impacts.length;
    const perf = perfsByTeam.get(tn);

    rows.push({
      teamNumber: tn,
      defensePct: matchCount ? (flaggedCount / matchCount) * 100 : null,
      flaggedCount,
      matchCount,
      meanImpact: mean(impacts),
      medianImpact: median(impacts),
      maxImpact: impacts.length ? Math.max(...impacts) : null,
      sumImpact: impacts.length ? impacts.reduce((a, b) => a + b, 0) : null,
      stdImpact: stdDev(impacts),
      impactSeries: series,
      raw: perf?.raw ?? null,
      confidence: perf?.confidence ?? null,
      ace: perf?.ace ?? null,
      auto_raw: perf?.auto_raw ?? null,
      teleop_raw: perf?.teleop_raw ?? null,
      endgame_raw: perf?.endgame_raw ?? null,
    });
  }

  return rows
    .filter((r) => r.matchCount > 0)
    .sort((a, b) => (b.defensePct ?? 0) - (a.defensePct ?? 0));
}

/** Top-quartile cutoff for defensePct among teams with data. */
export function defensePctTopQuartile(rows: TeamDefenseRow[]): number | null {
  const pcts = rows
    .map((r) => r.defensePct)
    .filter((v): v is number => v !== null)
    .sort((a, b) => a - b);
  if (pcts.length === 0) return null;
  const idx = Math.max(0, Math.ceil(pcts.length * 0.75) - 1);
  return pcts[idx];
}

export function countHighDefenseTeams(rows: TeamDefenseRow[], minPct = 50): number {
  return rows.filter((r) => (r.defensePct ?? 0) >= minPct).length;
}
