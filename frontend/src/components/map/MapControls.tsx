import { useState } from "react";
import {
  ActionIcon,
  Divider,
  Group,
  Paper,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { IconGlobe, IconMap, IconStack2, IconX } from "@tabler/icons-react";
import { EVENT_LEGEND } from "../../lib/map";

export type Projection = "mercator" | "globe";

export interface LayerState {
  teams: boolean;
  events: boolean;
  heatmap: boolean;
  districts: boolean;
}

interface MapControlsProps {
  projection: Projection;
  onProjectionChange: (p: Projection) => void;
  layers: LayerState;
  onLayerChange: (key: keyof LayerState, value: boolean) => void;
  teamCount: number;
  eventCount: number;
}

function LegendDot({ color }: { color: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 10,
        height: 10,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
      }}
    />
  );
}

export function MapControls({
  projection,
  onProjectionChange,
  layers,
  onLayerChange,
  teamCount,
  eventCount,
}: MapControlsProps) {
  const [expanded, setExpanded] = useState(false);

  if (!expanded) {
    return (
      <UnstyledButton
        onClick={() => setExpanded(true)}
        aria-label="Open map controls"
        style={{
          position: "absolute",
          top: 12,
          left: 12,
          zIndex: 5,
          background: "rgba(26, 26, 26, 0.92)",
          border: "1px solid #333",
          borderRadius: 8,
          backdropFilter: "blur(6px)",
          padding: "8px 12px",
        }}
      >
        <Group gap={8} wrap="nowrap">
          <IconStack2 size={16} color="#ffdd00" />
          <Text size="xs" fw={700} c="#ffdd00" tt="uppercase" style={{ letterSpacing: 0.5 }}>
            Controls
          </Text>
        </Group>
      </UnstyledButton>
    );
  }

  return (
    <Paper
      shadow="md"
      radius="md"
      p="sm"
      style={{
        position: "absolute",
        top: 12,
        left: 12,
        zIndex: 5,
        width: 230,
        background: "rgba(26, 26, 26, 0.92)",
        border: "1px solid #333",
        backdropFilter: "blur(6px)",
      }}
    >
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap">
          <Text size="xs" fw={700} c="#ffdd00" tt="uppercase" style={{ letterSpacing: 0.5 }}>
            Map Controls
          </Text>
          <ActionIcon
            size="sm"
            variant="subtle"
            color="gray"
            onClick={() => setExpanded(false)}
            aria-label="Collapse map controls"
          >
            <IconX size={16} />
          </ActionIcon>
        </Group>

        <SegmentedControl
          fullWidth
          size="xs"
          value={projection}
          onChange={(v) => onProjectionChange(v as Projection)}
          data={[
            {
              value: "mercator",
              label: (
                <Group gap={4} justify="center" wrap="nowrap">
                  <IconMap size={14} />
                  <span>2D</span>
                </Group>
              ),
            },
            {
              value: "globe",
              label: (
                <Group gap={4} justify="center" wrap="nowrap">
                  <IconGlobe size={14} />
                  <span>Globe</span>
                </Group>
              ),
            },
          ]}
        />

        <Divider my={2} color="#333" />

        <Switch
          size="sm"
          color="peeko"
          checked={layers.teams}
          onChange={(e) => onLayerChange("teams", e.currentTarget.checked)}
          label={
            <Text size="sm">
              Teams{" "}
              <Text span size="xs" c="dimmed">
                ({teamCount.toLocaleString()})
              </Text>
            </Text>
          }
        />
        <Switch
          size="sm"
          color="peeko"
          checked={layers.events}
          onChange={(e) => onLayerChange("events", e.currentTarget.checked)}
          label={
            <Text size="sm">
              Events{" "}
              <Text span size="xs" c="dimmed">
                ({eventCount.toLocaleString()})
              </Text>
            </Text>
          }
        />
        <Switch
          size="sm"
          color="peeko"
          checked={layers.heatmap}
          onChange={(e) => onLayerChange("heatmap", e.currentTarget.checked)}
          label={<Text size="sm">Team density heatmap</Text>}
        />
        <Switch
          size="sm"
          color="peeko"
          checked={layers.districts}
          onChange={(e) => onLayerChange("districts", e.currentTarget.checked)}
          label={<Text size="sm">District boundaries</Text>}
        />

        {layers.events ? (
          <>
            <Divider my={2} color="#333" />
            <Text size="xs" c="dimmed" fw={600}>
              Event types
            </Text>
            <Stack gap={4}>
              {EVENT_LEGEND.map((item) => (
                <Group key={item.label} gap={8} wrap="nowrap">
                  <LegendDot color={item.color} />
                  <Text size="xs">{item.label}</Text>
                </Group>
              ))}
            </Stack>
          </>
        ) : null}
      </Stack>
    </Paper>
  );
}
