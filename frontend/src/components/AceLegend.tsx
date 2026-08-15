import { Group, Paper, Text } from "@mantine/core";
import { ACE_LEGEND, contrastText } from "../lib/epa";

/** ACE percentile color key, mirroring ace_legend_layout in the Dash app. */
export function AceLegend() {
  return (
    <Paper withBorder p="xs" radius="md">
      <Text size="xs" fw={700} mb={6} c="dimmed">
        ACE Color Key (Percentiles)
      </Text>
      <Group gap={4} wrap="wrap">
        {ACE_LEGEND.map((row) => {
          const fg = contrastText(row.color);
          return (
            <span
              key={row.label}
              style={{
                backgroundColor: row.color,
                color: fg,
                textShadow: fg === "#FFFFFF" ? "0 1px 2px rgba(0,0,0,0.65)" : undefined,
                borderRadius: 4,
                padding: "2px 6px",
                fontSize: 11,
                fontWeight: 600,
                whiteSpace: "nowrap",
              }}
            >
              {row.label}
            </span>
          );
        })}
      </Group>
    </Paper>
  );
}
