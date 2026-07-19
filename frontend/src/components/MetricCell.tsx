import { aceColor, type PercentileThresholds } from "../lib/epa";
import { formatNumber } from "../lib/format";

const CONFIDENCE_TINT = "#e5393575"; // production: below-median confidence gets a red tint

// Uniform pill sizing so numbers of any length line up in a column.
const PILL_MIN_WIDTH = 52;

interface MetricCellProps {
  value: number | null | undefined;
  thresholds: PercentileThresholds;
  decimals?: number;
}

/**
 * Percentile-colored metric cell (ACE/Auto/Teleop/Endgame) using the 15-stop
 * ACE color scale, matching the Dash DataTable styling (get_epa_styling).
 */
export function MetricCell({ value, thresholds, decimals = 1 }: MetricCellProps) {
  const color = aceColor(value, thresholds);
  if (!color || value === null || value === undefined) {
    return (
      <span style={{ display: "inline-block", minWidth: PILL_MIN_WIDTH, textAlign: "center" }}>
        {formatNumber(value, decimals)}
      </span>
    );
  }
  return (
    <span
      style={{
        display: "inline-block",
        minWidth: PILL_MIN_WIDTH,
        textAlign: "center",
        backgroundColor: color,
        color: "#ffffff",
        textShadow: "0 1px 2px rgba(0,0,0,0.65)",
        borderRadius: 6,
        padding: "4px 6px",
        fontWeight: 600,
      }}
    >
      {formatNumber(value, decimals)}
    </span>
  );
}

interface ConfidenceCellProps {
  value: number | null | undefined;
  median: number | null;
}

/** Confidence cell: red tint only when below the median (production special-case). */
export function ConfidenceCell({ value, median }: ConfidenceCellProps) {
  const tint =
    value !== null && value !== undefined && median !== null && value < median;
  if (!tint) return <span>{formatNumber(value, 2)}</span>;
  return (
    <span style={{ backgroundColor: CONFIDENCE_TINT, borderRadius: 6, padding: "4px 6px" }}>
      {formatNumber(value, 2)}
    </span>
  );
}
