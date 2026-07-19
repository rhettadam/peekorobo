import type { MatchResponse } from "../types/api";

// Diverging win-probability color scale (dark-theme values from the Dash CSS
// --table-row-prediction-* variables). Input is a probability in [0,1].
export function predictionColor(prob: number | null | undefined): string | null {
  if (prob === null || prob === undefined) return null;
  const p = prob * 100;
  if (p >= 95) return "#18583e99"; // deep green
  if (p >= 85) return "#1f4c3499"; // dark green
  if (p >= 75) return "#245c3a"; // green
  if (p >= 65) return "#2b624499"; // light green
  if (p >= 55) return "#2e6f4b99"; // lighter green
  if (p >= 50) return "#cc990099"; // high neutral (yellow)
  if (p >= 45) return "#99660099"; // low neutral (orange)
  if (p >= 35) return "#d0494999"; // lightest red
  if (p >= 25) return "#b62f2f99"; // lighter red
  if (p >= 15) return "#9a282899"; // light red
  if (p >= 5) return "#7a1f1f99"; // dark red
  return "#51151599"; // deep red
}

/** True once a match has a real result (non-zero score or an explicit winner). */
export function isPlayed(m: MatchResponse): boolean {
  return m.red_score > 0 || m.blue_score > 0 || m.winning_alliance === "red" || m.winning_alliance === "blue";
}

/**
 * Prediction accuracy for a set of matches, mirroring compute_accuracy in the
 * Dash app: only count played matches that have a prediction; ties are excluded
 * unless the model predicted an exact toss-up.
 */
export function predictionAccuracy(matches: MatchResponse[]): {
  correct: number;
  total: number;
  pct: number | null;
} {
  let correct = 0;
  let total = 0;
  for (const m of matches) {
    if (!isPlayed(m)) continue;
    if (m.red_win_prob === null || m.red_win_prob === undefined) continue;
    const predRed = m.red_win_prob > 0.5;
    const predTie = m.red_win_prob === 0.5;
    const actualTie = m.winning_alliance !== "red" && m.winning_alliance !== "blue";
    if (actualTie) {
      if (predTie) {
        total += 1;
        correct += 1;
      }
      continue;
    }
    total += 1;
    const actualRed = m.winning_alliance === "red";
    if (predRed === actualRed) correct += 1;
  }
  return { correct, total, pct: total ? (correct / total) * 100 : null };
}

export interface MatchInsights {
  numMatches: number;
  avgScore: number | null;
  avgWinningScore: number | null;
  avgLosingScore: number | null;
  avgMargin: number | null;
  highScore: { value: number; key: string } | null;
  highMargin: { value: number; key: string } | null;
}

/** Aggregate stats over a set of played matches (mirrors calculate_insights). */
export function matchInsights(matches: MatchResponse[]): MatchInsights {
  const played = matches.filter(isPlayed);
  if (played.length === 0) {
    return {
      numMatches: 0,
      avgScore: null,
      avgWinningScore: null,
      avgLosingScore: null,
      avgMargin: null,
      highScore: null,
      highMargin: null,
    };
  }
  const scores: number[] = [];
  const winning: number[] = [];
  const losing: number[] = [];
  const margins: number[] = [];
  let highScore: { value: number; key: string } | null = null;
  let highMargin: { value: number; key: string } | null = null;
  for (const m of played) {
    const hi = Math.max(m.red_score, m.blue_score);
    const lo = Math.min(m.red_score, m.blue_score);
    scores.push(m.red_score, m.blue_score);
    winning.push(hi);
    losing.push(lo);
    margins.push(hi - lo);
    if (!highScore || hi > highScore.value) highScore = { value: hi, key: m.match_key };
    if (!highMargin || hi - lo > highMargin.value) highMargin = { value: hi - lo, key: m.match_key };
  }
  const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
  return {
    numMatches: played.length,
    avgScore: mean(scores),
    avgWinningScore: mean(winning),
    avgLosingScore: mean(losing),
    avgMargin: mean(margins),
    highScore,
    highMargin,
  };
}
