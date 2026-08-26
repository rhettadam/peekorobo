import type { EventPerfInfo, MatchResponse } from "../types/api";
import { isPlayed, predictedMatchScores } from "./prediction";

/** Predicted − actual. Positive = underperformance vs prediction. */
export function allianceResidual(pred: number, actual: number): number {
  return pred - actual;
}

/**
 * Flag an alliance only when opponents underperformed by more than `threshold`
 * AND this alliance did not also collapse (asymmetric underperformance).
 *
 * Filters mutual-failure / weird matches where both alliances miss prediction —
 * those are usually not useful defense review targets.
 */
export function isAsymmetricDefenseFlag(
  oppImpact: number,
  ownResidual: number,
  threshold: number,
): boolean {
  if (!(oppImpact > threshold)) return false;
  // Own alliance must underperform less than half the opponent shortfall
  // (and not more than half the threshold). Overperformance (negative residual) always passes.
  return ownResidual < oppImpact * 0.5 && ownResidual <= threshold * 0.5;
}

/** Qualification matches vs elimination / playoff matches. */
export type DefenseStage = "qm" | "playoff";

const COMP_LEVEL_ORDER: Record<string, number> = { qm: 0, ef: 1, qf: 2, sf: 3, f: 4 };

/** Default multiplier on residual σ for the Defense Indicator threshold. */
export const DEFAULT_THRESHOLD_SIGMA = 1.5;

/** Min matches before Defense % / Focus are treated as reliable. */
export const MIN_MATCHES_FOR_INDICATOR = 3;

function matchSortKey(m: MatchResponse): number {
  return (COMP_LEVEL_ORDER[m.comp_level] ?? 9) * 1_000_000 + m.set_number * 1000 + m.match_number;
}

export function playedMatchesForStage(
  matches: MatchResponse[],
  stage: DefenseStage,
): MatchResponse[] {
  return matches
    .filter((m) => {
      if (!isPlayed(m)) return false;
      if (stage === "qm") return m.comp_level === "qm";
      return m.comp_level !== "qm";
    })
    .sort((a, b) => matchSortKey(a) - matchSortKey(b));
}

export interface EventResidualStats {
  mean: number;
  std: number;
  meanAbs: number;
  /** Default Defense Indicator threshold X (= 1.5σ of residuals). */
  defaultThreshold: number;
  /** Number of alliance-side residuals used. */
  count: number;
  /** Played matches with at least one asymmetric defense flag at default X. */
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
  /** Red alliance residual (red pred − red actual). */
  redOwnResidual: number;
  /** Blue alliance residual (blue pred − blue actual). */
  blueOwnResidual: number;
  redFlagged: boolean;
  blueFlagged: boolean;
}

export interface TeamImpactPoint {
  matchKey: string;
  matchNumber: number;
  compLevel: string;
  setNumber: number;
  impact: number;
  ownResidual: number;
  flagged: boolean;
}

export interface TeamDefenseRow {
  teamNumber: number;
  /** % of matches with an asymmetric defense flag. Null if too few matches. */
  defensePct: number | null;
  /**
   * Scout-focus score: mean flagged impact × √flaggedCount.
   * Rewards consistent, large asymmetric underperformance vs noisy one-offs.
   */
  focusScore: number | null;
  flaggedCount: number;
  matchCount: number;
  meanImpact: number | null;
  /** Mean impact on flagged matches only. */
  meanFlaggedImpact: number | null;
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

/**
 * Collect residuals (pred − actual) for both alliances across played matches
 * in the selected stage. Used for stage σ and the default Defense Indicator threshold.
 */
export function eventResidualStats(
  matches: MatchResponse[],
  aceByTeam: Map<number, number | null | undefined> | undefined,
  stage: DefenseStage = "qm",
): EventResidualStats | null {
  const staged = playedMatchesForStage(matches, stage);
  const residuals: number[] = [];

  for (const m of staged) {
    const pred = predictedMatchScores(m, aceByTeam);
    if (!pred) continue;
    residuals.push(
      allianceResidual(pred.red, m.red_score),
      allianceResidual(pred.blue, m.blue_score),
    );
  }

  if (residuals.length === 0) return null;

  const m = mean(residuals)!;
  const s = stdDev(residuals) ?? 0;
  // 1.5σ cuts a lot of normal prediction noise vs 1σ (~16% one-tail flags).
  const defaultThreshold = Math.max(1, Math.round(DEFAULT_THRESHOLD_SIGMA * s * 10) / 10);
  const meanAbs = mean(residuals.map(Math.abs))!;

  let largeImpactMatchCount = 0;
  for (const match of staged) {
    const pred = predictedMatchScores(match, aceByTeam);
    if (!pred) continue;
    const redOwn = allianceResidual(pred.red, match.red_score);
    const blueOwn = allianceResidual(pred.blue, match.blue_score);
    const redImpact = blueOwn; // red's defensive impact = blue underperformance
    const blueImpact = redOwn;
    if (
      isAsymmetricDefenseFlag(redImpact, redOwn, defaultThreshold) ||
      isAsymmetricDefenseFlag(blueImpact, blueOwn, defaultThreshold)
    ) {
      largeImpactMatchCount += 1;
    }
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

/** Suggested slider max based on residual spread. */
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
  stage: DefenseStage = "qm",
): MatchDefenseRow[] {
  const rows: MatchDefenseRow[] = [];
  for (const m of playedMatchesForStage(matches, stage)) {
    const pred = predictedMatchScores(m, aceByTeam);
    if (!pred) continue;
    const redOwnResidual = allianceResidual(pred.red, m.red_score);
    const blueOwnResidual = allianceResidual(pred.blue, m.blue_score);
    // Red's defensive impact = how much blue underperformed prediction
    const redImpact = blueOwnResidual;
    // Blue's defensive impact = how much red underperformed prediction
    const blueImpact = redOwnResidual;
    rows.push({
      match: m,
      redPred: pred.red,
      bluePred: pred.blue,
      redImpact,
      blueImpact,
      redOwnResidual,
      blueOwnResidual,
      redFlagged: isAsymmetricDefenseFlag(redImpact, redOwnResidual, threshold),
      blueFlagged: isAsymmetricDefenseFlag(blueImpact, blueOwnResidual, threshold),
    });
  }
  return rows;
}

export function teamDefenseRows(
  matches: MatchResponse[],
  teamNumbers: number[],
  perfsByTeam: Map<number, EventPerfInfo>,
  aceByTeam: Map<number, number | null | undefined> | undefined,
  threshold: number,
  stage: DefenseStage = "qm",
): TeamDefenseRow[] {
  const staged = playedMatchesForStage(matches, stage);
  const rows: TeamDefenseRow[] = [];

  for (const tn of teamNumbers) {
    const impacts: number[] = [];
    const flaggedImpacts: number[] = [];
    const series: TeamImpactPoint[] = [];
    let flaggedCount = 0;

    for (const m of staged) {
      const onRed = m.red_teams.includes(tn);
      const onBlue = m.blue_teams.includes(tn);
      if (!onRed && !onBlue) continue;
      const pred = predictedMatchScores(m, aceByTeam);
      if (!pred) continue;
      const redOwn = allianceResidual(pred.red, m.red_score);
      const blueOwn = allianceResidual(pred.blue, m.blue_score);
      const impact = onRed ? blueOwn : redOwn;
      const ownResidual = onRed ? redOwn : blueOwn;
      const flagged = isAsymmetricDefenseFlag(impact, ownResidual, threshold);
      if (flagged) {
        flaggedCount += 1;
        flaggedImpacts.push(impact);
      }
      impacts.push(impact);
      series.push({
        matchKey: m.match_key,
        matchNumber: m.match_number,
        compLevel: m.comp_level,
        setNumber: m.set_number,
        impact,
        ownResidual,
        flagged,
      });
    }

    const matchCount = impacts.length;
    const perf = perfsByTeam.get(tn);
    const meanFlaggedImpact = mean(flaggedImpacts);
    const reliable = matchCount >= MIN_MATCHES_FOR_INDICATOR;
    const defensePct = reliable && matchCount ? (flaggedCount / matchCount) * 100 : null;
    // Focus: size of flagged shortfalls × consistency (√count). Null until enough matches.
    const focusScore =
      reliable && meanFlaggedImpact !== null && flaggedCount > 0
        ? meanFlaggedImpact * Math.sqrt(flaggedCount)
        : reliable
          ? 0
          : null;

    rows.push({
      teamNumber: tn,
      defensePct,
      focusScore,
      flaggedCount,
      matchCount,
      meanImpact: mean(impacts),
      meanFlaggedImpact,
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
    .sort((a, b) => (b.focusScore ?? -1) - (a.focusScore ?? -1));
}

/** Top-quartile cutoff for focusScore among teams with enough matches. */
export function defenseFocusTopQuartile(rows: TeamDefenseRow[]): number | null {
  const scores = rows
    .map((r) => r.focusScore)
    .filter((v): v is number => v !== null && v > 0)
    .sort((a, b) => a - b);
  if (scores.length === 0) return null;
  const idx = Math.max(0, Math.ceil(scores.length * 0.75) - 1);
  return scores[idx];
}

export function countHighDefenseTeams(rows: TeamDefenseRow[], minPct = 40): number {
  return rows.filter((r) => (r.defensePct ?? 0) >= minPct).length;
}
