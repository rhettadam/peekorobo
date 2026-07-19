// Fixed brand colors for the component-metric pills shown on team/event pages,
// mirroring the Dash UI (Auto=blue, Teleop=orange, Endgame=green, RAW=red,
// Confidence=grey, ACE=purple).

export type MetricKey = "auto" | "teleop" | "endgame" | "raw" | "confidence" | "ace";

export interface MetricStyle {
  label: string;
  color: string;
}

// Colors match the production Dash app exactly (layouts.py:548-583).
export const METRIC_STYLES: Record<MetricKey, MetricStyle> = {
  auto: { label: "Auto", color: "#1976d2" },
  teleop: { label: "Teleop", color: "#fb8c00" },
  endgame: { label: "Endgame", color: "#388e3c" },
  raw: { label: "RAW", color: "#d32f2f" },
  confidence: { label: "Confidence", color: "#555555" },
  ace: { label: "ACE", color: "#673ab7" },
};
