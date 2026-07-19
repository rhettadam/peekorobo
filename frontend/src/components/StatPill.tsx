import { Badge } from "@mantine/core";
import { formatNumber } from "../lib/format";
import { METRIC_STYLES, type MetricKey } from "../lib/metrics";

interface StatPillProps {
  metric: MetricKey;
  value: number | null | undefined;
  decimals?: number;
  size?: string;
}

/**
 * Colored "Label: value" pill for a component metric (Auto/Teleop/Endgame/RAW/
 * Confidence/ACE), matching the Peekorobo team-page styling.
 */
export function StatPill({ metric, value, decimals, size = "lg" }: StatPillProps) {
  const style = METRIC_STYLES[metric];
  const dp = decimals ?? (metric === "confidence" ? 2 : 1);
  return (
    <Badge
      size={size}
      radius="sm"
      styles={{
        root: {
          backgroundColor: style.color,
          color: "#ffffff",
          textShadow: "0 1px 2px rgba(0,0,0,0.55)",
          textTransform: "none",
        },
      }}
    >
      {style.label}: {formatNumber(value, dp)}
    </Badge>
  );
}
