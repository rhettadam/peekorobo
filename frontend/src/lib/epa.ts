// ACE/EPA color + percentile logic, ported from utils.py (get_epa_styling,
// compute_percentiles, get_contrast_text_color).

// (percentile, color) stops. A value is colored by the highest percentile bucket
// whose threshold it meets or exceeds.
const ACE_COLOR_STOPS: Array<[number, string]> = [
  [99, "#6a1b9a"],
  [97, "#8e24aa"],
  [95, "#3949ab"],
  [93, "#1565c0"],
  [91, "#1e88e5"],
  [89, "#2e7d32"],
  [85, "#43a047"],
  [80, "#c0ca33"],
  [75, "#ffb300"],
  [65, "#f9a825"],
  [55, "#fb8c00"],
  [40, "#e53935"],
  [25, "#b71c1c"],
  [10, "#7b0000"],
  [0, "#4d0000"],
];

const PERCENTILE_KEYS = ACE_COLOR_STOPS.map(([p]) => p);

// Legend rows for the ACE color key (mirrors ace_legend_layout in layouts.py).
export const ACE_LEGEND: Array<{ label: string; color: string }> = ACE_COLOR_STOPS.map(
  ([p, color], i) => ({
    label: i === ACE_COLOR_STOPS.length - 1 ? `< ${ACE_COLOR_STOPS[i - 1][0]}%` : `\u2265 ${p}%`,
    color,
  }),
);

/** Median of a numeric array (linear interpolation), ignoring nullish/NaN. */
export function median(values: Array<number | null | undefined>): number | null {
  const nums = values.filter((v): v is number => typeof v === "number" && !Number.isNaN(v));
  if (nums.length === 0) return null;
  const sorted = [...nums].sort((a, b) => a - b);
  return percentileOf(sorted, 50);
}

/** numpy-style linear-interpolation percentile over a sorted ascending array. */
function percentileOf(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  const rank = (p / 100) * (sorted.length - 1);
  const low = Math.floor(rank);
  const high = Math.ceil(rank);
  if (low === high) return sorted[low];
  const frac = rank - low;
  return sorted[low] * (1 - frac) + sorted[high] * frac;
}

export type PercentileThresholds = Record<number, number>;

/** Compute the percentile thresholds used by the color scale from raw values. */
export function computePercentiles(values: Array<number | null | undefined>): PercentileThresholds {
  const nums = values.filter((v): v is number => typeof v === "number" && !Number.isNaN(v));
  const sorted = [...nums].sort((a, b) => a - b);
  const out: PercentileThresholds = {};
  for (const p of PERCENTILE_KEYS) out[p] = percentileOf(sorted, p);
  return out;
}

/** Pick the ACE color for a value given precomputed percentile thresholds. */
export function aceColor(
  value: number | null | undefined,
  thresholds: PercentileThresholds,
): string | undefined {
  if (value === null || value === undefined || Number.isNaN(value)) return undefined;
  for (const [p, color] of ACE_COLOR_STOPS) {
    if (value >= (thresholds[p] ?? 0)) return color;
  }
  return ACE_COLOR_STOPS[ACE_COLOR_STOPS.length - 1][1];
}

/** Return black or white text for readable contrast against a hex background (WCAG). */
export function contrastText(hex: string): string {
  const clean = hex.replace("#", "").slice(0, 6);
  if (clean.length < 6) return "#000000";
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);

  const channel = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const lum = 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
  const ratio = (l1: number, l2: number) => (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  const withBlack = ratio(lum, 0);
  const withWhite = ratio(lum, 1);
  if (withBlack >= 3.0) return "#000000";
  if (withWhite >= 3.0) return "#FFFFFF";
  return withBlack > withWhite ? "#000000" : "#FFFFFF";
}

/** Simple percentile-bucket color (mirrors utils.get_user_epa_color). */
export function simpleEpaColor(value: number, allValues: number[]): string {
  if (allValues.length === 0) return "#000000";
  const sorted = [...allValues].sort((a, b) => b - a);
  const rank = sorted.indexOf(value) + 1;
  const percentile = rank / sorted.length;
  if (percentile <= 0.01) return "#800080";
  if (percentile <= 0.05) return "#0000ff";
  if (percentile <= 0.1) return "#008000";
  if (percentile <= 0.25) return "orange";
  if (percentile <= 0.5) return "#ff0000";
  return "#8B4513";
}
