import { Badge } from "@mantine/core";
import { aceColor, contrastText, type PercentileThresholds } from "../lib/epa";
import { formatNumber } from "../lib/format";

interface AceBadgeProps {
  value: number | null | undefined;
  thresholds?: PercentileThresholds;
  label?: string;
  size?: string;
}

/**
 * Colored badge for an ACE (or ACE-like) value. When percentile thresholds are
 * supplied the background is colored by the ACE scale from utils.get_epa_styling.
 */
export function AceBadge({ value, thresholds, label, size = "md" }: AceBadgeProps) {
  const color = thresholds ? aceColor(value, thresholds) : undefined;
  const text = formatNumber(value);
  const display = label ? `${label} ${text}` : text;

  if (!color) {
    return (
      <Badge size={size} variant="light" color="gray">
        {display}
      </Badge>
    );
  }

  return (
    <Badge
      size={size}
      styles={{ root: { backgroundColor: color, color: contrastText(color) } }}
    >
      {display}
    </Badge>
  );
}
