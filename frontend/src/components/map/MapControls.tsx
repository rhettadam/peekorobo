import { useMemo, useState } from "react";
import {
  ActionIcon,
  Checkbox,
  Divider,
  Group,
  Paper,
  ScrollArea,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { IconGlobe, IconMap, IconStack2, IconX } from "@tabler/icons-react";
import { EVENT_LEGEND, eventTypeBucket } from "../../lib/map";
import { eventWeekLabel, normalizeDistrictKey } from "../../lib/format";
import type { MapEvent, MapTeam } from "../../types/api";

export type Projection = "mercator" | "globe";

export interface LayerState {
  teams: boolean;
  events: boolean;
  heatmap: boolean;
  districts: boolean;
}

export interface MapFilters {
  teamCountry: string | null;
  teamState: string | null;
  teamDistrict: string | null;
  eventCountry: string | null;
  eventState: string | null;
  eventDistrict: string | null;
  eventWeek: string | null;
  /** Empty set = all types visible. */
  eventTypes: Set<string>;
}

export const EMPTY_MAP_FILTERS: MapFilters = {
  teamCountry: null,
  teamState: null,
  teamDistrict: null,
  eventCountry: null,
  eventState: null,
  eventDistrict: null,
  eventWeek: null,
  eventTypes: new Set(),
};

interface MapControlsProps {
  projection: Projection;
  onProjectionChange: (p: Projection) => void;
  layers: LayerState;
  onLayerChange: (key: keyof LayerState, value: boolean) => void;
  filters: MapFilters;
  onFiltersChange: (next: MapFilters) => void;
  teams: MapTeam[];
  events: MapEvent[];
  filteredTeamCount: number;
  filteredEventCount: number;
}

const ALL = "__all__";

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

function uniqueSorted(values: Array<string | null | undefined>): string[] {
  const set = new Set<string>();
  for (const v of values) {
    const s = (v || "").trim();
    if (s) set.add(s);
  }
  return [...set].sort((a, b) => a.localeCompare(b));
}

export function MapControls({
  projection,
  onProjectionChange,
  layers,
  onLayerChange,
  filters,
  onFiltersChange,
  teams,
  events,
  filteredTeamCount,
  filteredEventCount,
}: MapControlsProps) {
  const [expanded, setExpanded] = useState(false);

  const teamCountries = useMemo(() => uniqueSorted(teams.map((t) => t.country)), [teams]);
  const teamStates = useMemo(() => {
    const scoped = filters.teamCountry
      ? teams.filter((t) => (t.country || "").trim() === filters.teamCountry)
      : teams;
    return uniqueSorted(scoped.map((t) => t.state_prov));
  }, [teams, filters.teamCountry]);
  const teamDistricts = useMemo(
    () => uniqueSorted(teams.map((t) => normalizeDistrictKey(t.district_key))),
    [teams],
  );

  const eventCountries = useMemo(() => uniqueSorted(events.map((e) => e.country)), [events]);
  const eventStates = useMemo(() => {
    const scoped = filters.eventCountry
      ? events.filter((e) => (e.country || "").trim() === filters.eventCountry)
      : events;
    return uniqueSorted(scoped.map((e) => e.state_prov));
  }, [events, filters.eventCountry]);
  const eventDistricts = useMemo(
    () => uniqueSorted(events.map((e) => normalizeDistrictKey(e.district_key))),
    [events],
  );
  const eventWeeks = useMemo(() => {
    const weeks = new Set<number>();
    for (const e of events) {
      if (e.week !== null && e.week !== undefined) weeks.add(e.week);
    }
    return [...weeks].sort((a, b) => a - b);
  }, [events]);

  const typeFilterActive = filters.eventTypes.size > 0;
  const filterActive =
    Boolean(
      filters.teamCountry ||
        filters.teamState ||
        filters.teamDistrict ||
        filters.eventCountry ||
        filters.eventState ||
        filters.eventDistrict ||
        filters.eventWeek ||
        typeFilterActive,
    );

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
            Controls{filterActive ? " · filtered" : ""}
          </Text>
        </Group>
      </UnstyledButton>
    );
  }

  const selectData = (values: string[]) => [
    { value: ALL, label: "All" },
    ...values.map((v) => ({ value: v, label: v })),
  ];

  const patch = (partial: Partial<MapFilters>) => onFiltersChange({ ...filters, ...partial });

  const toggleType = (bucket: string) => {
    const allBuckets = EVENT_LEGEND.map((item) => item.bucket);
    let next: Set<string>;
    if (filters.eventTypes.size === 0) {
      // Currently "all" → uncheck this one.
      next = new Set(allBuckets.filter((b) => b !== bucket));
    } else {
      next = new Set(filters.eventTypes);
      if (next.has(bucket)) next.delete(bucket);
      else next.add(bucket);
    }
    // Selecting every type is equivalent to no filter.
    if (next.size === allBuckets.length) next = new Set();
    onFiltersChange({ ...filters, eventTypes: next });
  };

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
        width: "min(280px, calc(100vw - 28px))",
        maxWidth: "calc(100vw - 28px)",
        background: "rgba(26, 26, 26, 0.94)",
        border: "1px solid #333",
        backdropFilter: "blur(6px)",
      }}
    >
      <ScrollArea.Autosize mah="min(70dvh, 560px)" type="scroll" offsetScrollbars>
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
                  ({filteredTeamCount.toLocaleString()}
                  {filteredTeamCount !== teams.length ? `/${teams.length.toLocaleString()}` : ""})
                </Text>
              </Text>
            }
          />
          {layers.teams ? (
            <Stack gap={6} pl={4}>
              <Select
                size="xs"
                label="Country"
                placeholder="All"
                searchable
                clearable
                data={selectData(teamCountries)}
                value={filters.teamCountry ?? ALL}
                onChange={(v) =>
                  patch({
                    teamCountry: !v || v === ALL ? null : v,
                    teamState: null,
                  })
                }
              />
              <Select
                size="xs"
                label="State / province"
                placeholder="All"
                searchable
                clearable
                data={selectData(teamStates)}
                value={filters.teamState ?? ALL}
                onChange={(v) => patch({ teamState: !v || v === ALL ? null : v })}
              />
              <Select
                size="xs"
                label="District"
                placeholder="All"
                searchable
                clearable
                data={selectData(teamDistricts)}
                value={filters.teamDistrict ?? ALL}
                onChange={(v) => patch({ teamDistrict: !v || v === ALL ? null : v })}
              />
            </Stack>
          ) : null}

          <Switch
            size="sm"
            color="peeko"
            checked={layers.events}
            onChange={(e) => onLayerChange("events", e.currentTarget.checked)}
            label={
              <Text size="sm">
                Events{" "}
                <Text span size="xs" c="dimmed">
                  ({filteredEventCount.toLocaleString()}
                  {filteredEventCount !== events.length ? `/${events.length.toLocaleString()}` : ""})
                </Text>
              </Text>
            }
          />
          {layers.events ? (
            <Stack gap={6} pl={4}>
              <Select
                size="xs"
                label="Country"
                placeholder="All"
                searchable
                clearable
                data={selectData(eventCountries)}
                value={filters.eventCountry ?? ALL}
                onChange={(v) =>
                  patch({
                    eventCountry: !v || v === ALL ? null : v,
                    eventState: null,
                  })
                }
              />
              <Select
                size="xs"
                label="State / province"
                placeholder="All"
                searchable
                clearable
                data={selectData(eventStates)}
                value={filters.eventState ?? ALL}
                onChange={(v) => patch({ eventState: !v || v === ALL ? null : v })}
              />
              <Select
                size="xs"
                label="District"
                placeholder="All"
                searchable
                clearable
                data={selectData(eventDistricts)}
                value={filters.eventDistrict ?? ALL}
                onChange={(v) => patch({ eventDistrict: !v || v === ALL ? null : v })}
              />
              <Select
                size="xs"
                label="Week"
                placeholder="All"
                clearable
                data={[
                  { value: ALL, label: "All" },
                  ...eventWeeks.map((w) => ({
                    value: String(w),
                    label: eventWeekLabel(w) ?? `Week ${w + 1}`,
                  })),
                ]}
                value={filters.eventWeek ?? ALL}
                onChange={(v) => patch({ eventWeek: !v || v === ALL ? null : v })}
              />

              <Text size="xs" c="dimmed" fw={600} mt={2}>
                Event types
              </Text>
              <Stack gap={4}>
                {EVENT_LEGEND.map((item) => {
                  const checked = !typeFilterActive || filters.eventTypes.has(item.bucket);
                  return (
                    <Checkbox
                      key={item.bucket}
                      size="xs"
                      color="peeko"
                      checked={checked}
                      onChange={() => toggleType(item.bucket)}
                      label={
                        <Group gap={8} wrap="nowrap">
                          <LegendDot color={item.color} />
                          <Text size="xs">{item.label}</Text>
                        </Group>
                      }
                    />
                  );
                })}
              </Stack>
            </Stack>
          ) : null}

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

          {filterActive ? (
            <UnstyledButton
              onClick={() => onFiltersChange({ ...EMPTY_MAP_FILTERS, eventTypes: new Set() })}
              style={{ alignSelf: "flex-start" }}
            >
              <Text size="xs" c="peeko" fw={600}>
                Clear filters
              </Text>
            </UnstyledButton>
          ) : null}
        </Stack>
      </ScrollArea.Autosize>
    </Paper>
  );
}

/** Apply map filters client-side to already-fetched payloads. */
export function filterMapTeams(teams: MapTeam[], filters: MapFilters): MapTeam[] {
  return teams.filter((t) => {
    if (filters.teamCountry && (t.country || "").trim() !== filters.teamCountry) return false;
    if (filters.teamState && (t.state_prov || "").trim() !== filters.teamState) return false;
    if (
      filters.teamDistrict &&
      normalizeDistrictKey(t.district_key) !== filters.teamDistrict
    ) {
      return false;
    }
    return true;
  });
}

export function filterMapEvents(events: MapEvent[], filters: MapFilters): MapEvent[] {
  const typeFilter = filters.eventTypes;
  return events.filter((e) => {
    if (filters.eventCountry && (e.country || "").trim() !== filters.eventCountry) return false;
    if (filters.eventState && (e.state_prov || "").trim() !== filters.eventState) return false;
    if (
      filters.eventDistrict &&
      normalizeDistrictKey(e.district_key) !== filters.eventDistrict
    ) {
      return false;
    }
    if (filters.eventWeek != null && String(e.week ?? "") !== filters.eventWeek) return false;
    if (typeFilter.size > 0 && !typeFilter.has(eventTypeBucket(e.event_type))) return false;
    return true;
  });
}
