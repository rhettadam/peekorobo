import { useEffect, useMemo, useState } from "react";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconPlus, IconX } from "@tabler/icons-react";
import { LineChart } from "@mantine/charts";
import { useQueries } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { apiGet } from "../api/client";
import { useEvents, useSearchIndex } from "../api/queries";
import { TeamName } from "../components/TeamName";
import { TeamAvatar } from "../components/TeamAvatar";
import { StatPill } from "../components/StatPill";
import type {
  EventData,
  EventPerfEntry,
  TeamMatchRating,
  TeamMatchRatingsResponse,
  TeamPerfInfo,
  TeamPerfResponse,
} from "../types/api";
import { availableYears, CURRENT_YEAR } from "../lib/constants";
import { METRIC_STYLES, type MetricKey } from "../lib/metrics";
import { contrastText } from "../lib/epa";
import { eventWeekLabel, formatNumber, recordString } from "../lib/format";

const TEAM_COLORS = [
  "#FFDD00",
  "#29B6F6",
  "#EC407A",
  "#66BB6A",
  "#AB47BC",
  "#FF7043",
  "#5C6BC0",
  "#8D6E63",
];
const MAX_TEAMS = 8;
const SUMMARY_METRICS: MetricKey[] = ["ace", "raw", "auto", "teleop", "endgame", "confidence"];
const RANK_PILL = "#455a64";
const COMP_LEVEL_ORDER: Record<string, number> = { qm: 0, ef: 1, qf: 2, sf: 3, f: 4 };

function metricValue(
  perf: TeamPerfInfo | EventPerfEntry | undefined,
  metric: MetricKey,
): number | null {
  if (!perf) return null;
  switch (metric) {
    case "ace":
      return (perf.ace as number) ?? null;
    case "raw":
      return (perf.raw as number) ?? null;
    case "confidence":
      return (perf.confidence as number) ?? null;
    case "auto":
      return (perf.auto_raw as number) ?? null;
    case "teleop":
      return (perf.teleop_raw as number) ?? null;
    case "endgame":
      return (perf.endgame_raw as number) ?? null;
    default:
      return null;
  }
}

function matchMetricValue(match: TeamMatchRating | undefined, metric: MetricKey): number | null {
  if (!match) return null;
  switch (metric) {
    case "ace":
      return match.ace ?? null;
    case "raw":
      return match.r ?? null;
    case "confidence":
      return match.c ?? null;
    case "auto":
      return match.a ?? null;
    case "teleop":
      return match.t ?? null;
    case "endgame":
      return match.e ?? null;
    default:
      return null;
  }
}

function sortEventKeysChronologically(keys: string[], metaByKey: Map<string, EventData>): string[] {
  return [...keys].sort((a, b) => {
    const metaA = metaByKey.get(a);
    const metaB = metaByKey.get(b);
    const da = metaA?.event_data.start_date ?? a;
    const db = metaB?.event_data.start_date ?? b;
    const cmp = da.localeCompare(db);
    if (cmp !== 0) return cmp;
    const wa = metaA?.week ?? Infinity;
    const wb = metaB?.week ?? Infinity;
    if (wa !== wb) return wa - wb;
    return a.localeCompare(b);
  });
}

function matchSortKey(m: TeamMatchRating): number {
  return (COMP_LEVEL_ORDER[m.comp_level] ?? 9) * 1_000_000 + (m.set_number ?? 0) * 1000 + m.match_number;
}

function sortMatchesChronologically(
  matches: TeamMatchRating[],
  metaByKey: Map<string, EventData>,
): TeamMatchRating[] {
  return [...matches].sort((a, b) => {
    const da = metaByKey.get(a.event_key)?.event_data.start_date ?? a.event_key;
    const db = metaByKey.get(b.event_key)?.event_data.start_date ?? b.event_key;
    const cmp = da.localeCompare(db);
    if (cmp !== 0) return cmp;
    if (a.event_key !== b.event_key) return a.event_key.localeCompare(b.event_key);
    return matchSortKey(a) - matchSortKey(b);
  });
}

function chartEventLabel(eventKey: string, year: number, meta?: EventData): string {
  const suffix = eventKey.replace(String(year), "").toUpperCase();
  const week = eventWeekLabel(meta?.week);
  return week ? `${week} · ${suffix}` : suffix;
}

function shortMatchLabel(m: Pick<TeamMatchRating, "comp_level" | "set_number" | "match_number">): string {
  const c = (m.comp_level || "qm").toLowerCase();
  if (c === "qm") return `QM${m.match_number}`;
  return `${c.toUpperCase()}${m.set_number}-${m.match_number}`;
}

function teamSeriesKey(tn: number): string {
  return `t${tn}`;
}

function teamMetricKey(tn: number, metric: MetricKey): string {
  return `t${tn}__${metric}`;
}

interface CompareChartRow {
  x: string;
  title: string;
  subtitle?: string;
  [key: string]: string | number | null | undefined;
}

function packTeamMetrics(
  row: CompareChartRow,
  tn: number,
  values: Record<MetricKey, number | null>,
) {
  row[teamSeriesKey(tn)] = values.ace;
  for (const m of SUMMARY_METRICS) row[teamMetricKey(tn, m)] = values[m];
}

function RankPill({ label, rank, count }: { label: string; rank?: number | null; count?: number | null }) {
  if (!rank) return null;
  return (
    <Badge
      radius="sm"
      styles={{ root: { backgroundColor: RANK_PILL, color: contrastText(RANK_PILL), textTransform: "none" } }}
    >
      {label}: {rank}
      {count ? ` / ${count}` : ""}
    </Badge>
  );
}

function CompareTooltip({
  payload,
  teams,
}: {
  payload?: Array<{ payload?: CompareChartRow }>;
  teams: number[];
}) {
  const row = payload?.[0]?.payload;
  if (!row) return null;
  const present = teams.filter((tn) => {
    const v = row[teamSeriesKey(tn)];
    return v !== null && v !== undefined;
  });
  if (!present.length) return null;

  return (
    <Card withBorder radius="md" padding="sm" shadow="md" style={{ minWidth: 220, maxWidth: 320 }}>
      <Text fw={700} size="sm" lineClamp={2}>
        {row.title}
      </Text>
      {row.subtitle ? (
        <Text size="xs" c="dimmed" mb={4}>
          {row.subtitle}
        </Text>
      ) : null}
      <Stack gap="xs" mt={6}>
        {present.map((tn) => {
          const color = TEAM_COLORS[teams.indexOf(tn) % TEAM_COLORS.length];
          return (
            <Stack key={tn} gap={2}>
              <Group gap={6} wrap="nowrap">
                <Box
                  style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }}
                />
                <Text size="xs" fw={700}>
                  {tn}
                </Text>
              </Group>
              {SUMMARY_METRICS.map((m) => {
                const raw = row[teamMetricKey(tn, m)];
                const value =
                  m === "confidence" && typeof raw === "number"
                    ? `${Math.round(raw * 100)}%`
                    : formatNumber(typeof raw === "number" ? raw : null);
                return (
                  <Group key={m} justify="space-between" gap="lg" wrap="nowrap" pl={14}>
                    <Text size="xs" c="dimmed">
                      {METRIC_STYLES[m].label}
                    </Text>
                    <Text size="xs" fw={600}>
                      {value}
                    </Text>
                  </Group>
                );
              })}
            </Stack>
          );
        })}
      </Stack>
    </Card>
  );
}

export function Compare() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [input, setInput] = useState("");
  const { data: index } = useSearchIndex();

  const teams = useMemo(() => {
    const raw = searchParams.get("teams") ?? "";
    return raw
      .split(",")
      .map((s) => Number(s.trim()))
      .filter((n) => Number.isFinite(n) && n > 0)
      .slice(0, MAX_TEAMS);
  }, [searchParams]);

  const year = Number(searchParams.get("year")) || CURRENT_YEAR;
  const [rangeMode, setRangeMode] = useState<"single" | "all">("single");
  const [grain, setGrain] = useState<"event" | "match">("match");

  useEffect(() => {
    document.title = "Compare Teams - Peekorobo";
  }, []);

  function setTeams(next: number[]) {
    const params = new URLSearchParams(searchParams);
    if (next.length) params.set("teams", next.join(","));
    else params.delete("teams");
    setSearchParams(params);
  }

  function addTeam() {
    const n = Number(input.trim());
    if (Number.isFinite(n) && n > 0 && !teams.includes(n) && teams.length < MAX_TEAMS) {
      setTeams([...teams, n]);
    }
    setInput("");
  }

  const results = useQueries({
    queries: teams.map((tn) => ({
      queryKey: ["team-perfs", tn, "all"],
      queryFn: () => apiGet<TeamPerfResponse>(`/team_perfs/${tn}`),
      staleTime: 5 * 60 * 1000,
    })),
  });

  const matchRatingQueries = useQueries({
    queries: teams.map((tn) => ({
      queryKey: ["team-match-ratings", tn, year],
      queryFn: () => apiGet<TeamMatchRatingsResponse>(`/team/${tn}/match_ratings/${year}`),
      staleTime: 5 * 60 * 1000,
      enabled: rangeMode === "single" && tn > 0,
    })),
  });

  const perfByTeam = useMemo(() => {
    const map = new Map<number, TeamPerfResponse | undefined>();
    teams.forEach((tn, i) => map.set(tn, results[i]?.data));
    return map;
  }, [teams, results]);

  const matchesByTeam = useMemo(() => {
    const map = new Map<number, TeamMatchRating[]>();
    teams.forEach((tn, i) => map.set(tn, matchRatingQueries[i]?.data?.matches ?? []));
    return map;
  }, [teams, matchRatingQueries]);

  const hasMatchSeries = useMemo(
    () => teams.some((tn) => (matchesByTeam.get(tn)?.length ?? 0) > 0),
    [teams, matchesByTeam],
  );
  const effectiveGrain = rangeMode === "single" && hasMatchSeries ? grain : "event";

  const yearEventsQuery = useEvents(year);
  const eventMetaByKey = useMemo(() => {
    const map = new Map<string, EventData>();
    for (const e of yearEventsQuery.data?.events ?? []) map.set(e.event_key, e);
    return map;
  }, [yearEventsQuery.data]);

  const { chartData, series, xTicks, sortedEventKeys } = useMemo(() => {
    const seriesList = teams.map((tn, i) => ({
      name: teamSeriesKey(tn),
      label: String(tn),
      color: TEAM_COLORS[i % TEAM_COLORS.length],
    }));

    if (rangeMode === "all") {
      const yearSet = new Set<number>();
      for (const tn of teams) {
        for (const p of perfByTeam.get(tn)?.team_perfs ?? []) {
          if (p.year !== 2020 && p.year !== 2021) yearSet.add(p.year);
        }
      }
      const years = [...yearSet].sort((a, b) => a - b);
      const rows: CompareChartRow[] = years.map((y) => {
        const row: CompareChartRow = { x: String(y), title: String(y) };
        for (const tn of teams) {
          const p = perfByTeam.get(tn)?.team_perfs.find((item) => item.year === y);
          packTeamMetrics(row, tn, {
            ace: metricValue(p, "ace"),
            raw: metricValue(p, "raw"),
            auto: metricValue(p, "auto"),
            teleop: metricValue(p, "teleop"),
            endgame: metricValue(p, "endgame"),
            confidence: metricValue(p, "confidence"),
          });
        }
        return row;
      });
      return { chartData: rows, series: seriesList, xTicks: years.map(String), sortedEventKeys: [] as string[] };
    }

    if (effectiveGrain === "match") {
      const byKey = new Map<string, TeamMatchRating>();
      for (const tn of teams) {
        for (const m of matchesByTeam.get(tn) ?? []) {
          if (m.match_key && !byKey.has(m.match_key)) byKey.set(m.match_key, m);
        }
      }
      const timeline = sortMatchesChronologically([...byKey.values()], eventMetaByKey);
      const ratingsAt = new Map<number, Map<string, TeamMatchRating>>();
      for (const tn of teams) {
        const map = new Map<string, TeamMatchRating>();
        for (const m of matchesByTeam.get(tn) ?? []) map.set(m.match_key, m);
        ratingsAt.set(tn, map);
      }

      const rows: CompareChartRow[] = [];
      const ticks: string[] = [];
      for (let i = 0; i < timeline.length; i++) {
        const m = timeline[i];
        const meta = eventMetaByKey.get(m.event_key);
        const eventName = meta?.event_data.name ?? m.event_key.replace(String(year), "").toUpperCase();
        const firstOfEvent = i === 0 || timeline[i - 1].event_key !== m.event_key;
        const row: CompareChartRow = {
          x: m.match_key,
          title: `${eventName} · ${shortMatchLabel(m)}`,
          subtitle: [eventWeekLabel(meta?.week), m.event_key.replace(String(year), "").toUpperCase()]
            .filter(Boolean)
            .join(" · "),
        };
        for (const tn of teams) {
          const match = ratingsAt.get(tn)?.get(m.match_key);
          packTeamMetrics(row, tn, {
            ace: matchMetricValue(match, "ace"),
            raw: matchMetricValue(match, "raw"),
            auto: matchMetricValue(match, "auto"),
            teleop: matchMetricValue(match, "teleop"),
            endgame: matchMetricValue(match, "endgame"),
            confidence: matchMetricValue(match, "confidence"),
          });
        }
        rows.push(row);
        ticks.push(firstOfEvent ? m.event_key.replace(String(year), "").toUpperCase() : "");
      }
      return { chartData: rows, series: seriesList, xTicks: ticks, sortedEventKeys: [] as string[] };
    }

    const eventKeys = new Set<string>();
    for (const tn of teams) {
      const p = perfByTeam.get(tn)?.team_perfs.find((item) => item.year === year);
      for (const ep of p?.event_perf ?? []) if (ep.event_key) eventKeys.add(ep.event_key);
    }
    const keys = sortEventKeysChronologically([...eventKeys], eventMetaByKey);
    const rows: CompareChartRow[] = keys.map((ek) => {
      const meta = eventMetaByKey.get(ek);
      const label = chartEventLabel(ek, year, meta);
      const row: CompareChartRow = {
        x: ek,
        title: meta?.event_data.name ?? label,
        subtitle: label,
      };
      for (const tn of teams) {
        const p = perfByTeam.get(tn)?.team_perfs.find((item) => item.year === year);
        const ep = p?.event_perf?.find((e) => e.event_key === ek);
        packTeamMetrics(row, tn, {
          ace: metricValue(ep, "ace"),
          raw: metricValue(ep, "raw"),
          auto: metricValue(ep, "auto"),
          teleop: metricValue(ep, "teleop"),
          endgame: metricValue(ep, "endgame"),
          confidence: metricValue(ep, "confidence"),
        });
      }
      return row;
    });
    return {
      chartData: rows,
      series: seriesList,
      xTicks: keys.map((ek) => chartEventLabel(ek, year, eventMetaByKey.get(ek))),
      sortedEventKeys: keys,
    };
  }, [teams, perfByTeam, matchesByTeam, rangeMode, effectiveGrain, year, eventMetaByKey]);

  const tickByX = useMemo(() => {
    const map = new Map<string, string>();
    chartData.forEach((row, i) => map.set(row.x, xTicks[i] ?? row.x));
    return map;
  }, [chartData, xTicks]);

  const axisTicks = useMemo(
    () => chartData.filter((row) => (tickByX.get(row.x) ?? "") !== "").map((row) => row.x),
    [chartData, tickByX],
  );

  return (
    <Stack gap="md" py="md">
      <Title order={1}>Compare</Title>
      <Text c="dimmed" size="sm">
        ACE over time. Hover a point for auto, teleop, endgame, RAW, and confidence.
      </Text>

      <Group align="flex-end" gap="sm" wrap="wrap">
        <TextInput
          label="Add a team"
          placeholder="Team number"
          value={input}
          onChange={(e) => setInput(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addTeam();
            }
          }}
          w={150}
        />
        <Button
          leftSection={<IconPlus size={16} />}
          onClick={addTeam}
          disabled={teams.length >= MAX_TEAMS}
          variant="default"
        >
          Add
        </Button>
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            Range
          </Text>
          <SegmentedControl
            value={rangeMode}
            onChange={(v) => setRangeMode(v as "single" | "all")}
            data={[
              { value: "single", label: "One season" },
              { value: "all", label: "All seasons" },
            ]}
          />
        </Stack>
        {rangeMode === "single" && hasMatchSeries ? (
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              Grain
            </Text>
            <SegmentedControl
              value={effectiveGrain}
              onChange={(v) => setGrain(v as "event" | "match")}
              data={[
                { value: "match", label: "By match" },
                { value: "event", label: "By event" },
              ]}
            />
          </Stack>
        ) : null}
        <Select
          label="Season"
          value={String(year)}
          data={availableYears().map((y) => ({ value: String(y), label: String(y) }))}
          onChange={(val) => {
            if (!val) return;
            const params = new URLSearchParams(searchParams);
            params.set("year", val);
            setSearchParams(params);
          }}
          allowDeselect={false}
          disabled={rangeMode === "all"}
          w={130}
        />
      </Group>

      {teams.length > 0 ? (
        <Group gap="xs">
          {teams.map((tn) => (
            <Badge
              key={tn}
              size="lg"
              variant="light"
              pl={4}
              leftSection={<TeamAvatar teamNumber={tn} size={20} radius={4} />}
              rightSection={
                <ActionIcon
                  size="xs"
                  variant="transparent"
                  onClick={() => setTeams(teams.filter((t) => t !== tn))}
                >
                  <IconX size={12} />
                </ActionIcon>
              }
              style={{ textTransform: "none" }}
            >
              {tn}
              {index?.teams[String(tn)]?.nickname ? ` | ${index.teams[String(tn)].nickname}` : ""}
            </Badge>
          ))}
        </Group>
      ) : (
        <Text c="dimmed">Add teams by number to compare their ACE.</Text>
      )}

      {teams.length > 0 && chartData.length > 0 ? (
        <Card withBorder padding="md" radius="md">
          <Text fw={600} mb="sm">
            {rangeMode === "all"
              ? `ACE by season`
              : effectiveGrain === "match"
                ? `ACE by match — ${year}`
                : `ACE by event — ${year}`}
          </Text>
          <LineChart
            h={360}
            data={chartData}
            dataKey="x"
            series={series}
            curveType="monotone"
            withDots
            connectNulls
            withLegend
            gridAxis="xy"
            yAxisLabel="ACE"
            xAxisProps={{
              ticks: axisTicks,
              interval: 0,
              minTickGap: 8,
              tickFormatter: (v: string) => tickByX.get(String(v)) ?? "",
            }}
            tooltipProps={{
              content: ({ payload }) => (
                <CompareTooltip
                  payload={payload as Array<{ payload?: CompareChartRow }>}
                  teams={teams}
                />
              ),
            }}
          />
        </Card>
      ) : null}

      {rangeMode === "single" && teams.length > 0 && sortedEventKeys.length > 0 ? (
        <Card withBorder padding="md" radius="md">
          <Text fw={600} mb="sm">
            Event breakdown — {year}
          </Text>
          <Table.ScrollContainer minWidth={480}>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Event</Table.Th>
                  {teams.map((tn) => (
                    <Table.Th key={tn}>{tn}</Table.Th>
                  ))}
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sortedEventKeys.map((ek) => {
                  const meta = eventMetaByKey.get(ek);
                  return (
                    <Table.Tr key={ek}>
                      <Table.Td>
                        <Text size="sm" fw={500} lineClamp={2}>
                          {meta?.event_data.name ?? ek.replace(String(year), "").toUpperCase()}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {[eventWeekLabel(meta?.week), ek.replace(String(year), "").toUpperCase()]
                            .filter(Boolean)
                            .join(" · ")}
                        </Text>
                      </Table.Td>
                      {teams.map((tn) => {
                        const p = perfByTeam.get(tn)?.team_perfs.find((item) => item.year === year);
                        const ep = p?.event_perf?.find((e) => e.event_key === ek);
                        return (
                          <Table.Td key={tn}>
                            {ep ? (
                              <StatPill metric="ace" value={metricValue(ep, "ace")} size="sm" />
                            ) : (
                              <Text size="sm" c="dimmed">
                                —
                              </Text>
                            )}
                          </Table.Td>
                        );
                      })}
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Card>
      ) : null}

      {teams.length > 0 ? (
        <Card withBorder padding="md" radius="md">
          <Text fw={700} mb="md">
            Season {year}
          </Text>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
            {teams.map((tn) => {
              const p = perfByTeam.get(tn)?.team_perfs.find((item) => item.year === year);
              return (
                <Stack key={tn} gap={8}>
                  <Group gap="sm" wrap="nowrap">
                    <TeamAvatar teamNumber={tn} size={36} radius={6} bordered />
                    <div>
                      <TeamName teamNumber={tn} year={year} />
                      <Text size="xs" c="dimmed">
                        {p
                          ? `Record ${recordString(p.wins, p.losses, p.ties)}`
                          : "No data this season"}
                      </Text>
                    </div>
                  </Group>
                  {p ? (
                    <>
                      <Group gap={6}>
                        {SUMMARY_METRICS.map((m) => (
                          <StatPill key={m} metric={m} value={metricValue(p, m)} size="sm" />
                        ))}
                      </Group>
                      <Group gap={6}>
                        <RankPill label="World" rank={p.rank_global} count={p.count_global} />
                        <RankPill label="Country" rank={p.rank_country} count={p.count_country} />
                        <RankPill label="District" rank={p.rank_district} count={p.count_district} />
                        <RankPill label="State" rank={p.rank_state} count={p.count_state} />
                      </Group>
                    </>
                  ) : null}
                </Stack>
              );
            })}
          </SimpleGrid>
        </Card>
      ) : null}
    </Stack>
  );
}
