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
import { AreaChart } from "@mantine/charts";
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

/** Y-axis metric for the all-seasons chart. */
type SeasonChartMetric = "ace" | "rank" | "normAce";

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

/** Global percentile from rank: 1 = best (rank 1), near 0 = worst. */
function normalizedAceFromRank(rank?: number | null, count?: number | null): number | null {
  if (rank == null || count == null || !Number.isFinite(rank) || !Number.isFinite(count)) return null;
  if (rank <= 0 || count <= 0) return null;
  return (count - rank + 1) / count;
}

function seasonChartValue(p: TeamPerfInfo | undefined, metric: SeasonChartMetric): number | null {
  if (!p) return null;
  if (metric === "ace") return metricValue(p, "ace");
  if (metric === "rank") return p.rank_global ?? null;
  return normalizedAceFromRank(p.rank_global, p.count_global);
}

function seasonChartLabel(metric: SeasonChartMetric): string {
  if (metric === "rank") return "Global rank";
  if (metric === "normAce") return "Normalized ACE";
  return "ACE";
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

function teamMatchLabelKey(tn: number): string {
  return `t${tn}__matchLabel`;
}

function teamRankKey(tn: number): string {
  return `t${tn}__rank`;
}

function teamNormAceKey(tn: number): string {
  return `t${tn}__normAce`;
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
  primary?: number | null,
) {
  row[teamSeriesKey(tn)] = primary !== undefined ? primary : values.ace;
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
  chartMetric,
}: {
  payload?: Array<{ payload?: CompareChartRow }>;
  teams: number[];
  chartMetric: SeasonChartMetric;
}) {
  const row = payload?.[0]?.payload;
  if (!row) return null;
  const present = teams.filter((tn) => {
    const v = row[teamSeriesKey(tn)];
    return v !== null && v !== undefined;
  });
  if (!present.length) return null;

  return (
    <Card withBorder radius="md" padding="sm" shadow="md" style={{ minWidth: 220, maxWidth: 340 }}>
      <Text fw={700} size="sm" lineClamp={2}>
        {row.title}
      </Text>
      {row.subtitle ? (
        <Text size="xs" c="dimmed" mb={6}>
          {row.subtitle}
        </Text>
      ) : null}
      <Stack gap={8}>
        {present.map((tn) => {
          const matchLabel = row[teamMatchLabelKey(tn)];
          const rank = row[teamRankKey(tn)];
          const norm = row[teamNormAceKey(tn)];
          const primary = row[teamSeriesKey(tn)];
          return (
            <Box key={tn}>
              <Group gap={6} justify="space-between" wrap="nowrap">
                <Text size="sm" fw={700}>
                  {tn}
                </Text>
                <Text size="sm" fw={700}>
                  {chartMetric === "rank"
                    ? `#${primary}`
                    : chartMetric === "normAce"
                      ? typeof primary === "number"
                        ? `${(primary * 100).toFixed(1)}%`
                        : "—"
                      : formatNumber(typeof primary === "number" ? primary : null)}
                </Text>
              </Group>
              {typeof matchLabel === "string" && matchLabel ? (
                <Text size="xs" c="dimmed" lineClamp={1}>
                  {matchLabel}
                </Text>
              ) : null}
              {rank != null || norm != null ? (
                <Text size="xs" c="dimmed">
                  {rank != null ? `World #${rank}` : null}
                  {rank != null && norm != null ? " · " : null}
                  {typeof norm === "number" ? `Norm ${(norm * 100).toFixed(1)}%` : null}
                </Text>
              ) : null}
              <Group gap={4} mt={4}>
                {SUMMARY_METRICS.filter((m) => m !== "ace").map((m) => {
                  const v = row[teamMetricKey(tn, m)];
                  if (v === null || v === undefined) return null;
                  return (
                    <Text key={m} size="xs" c="dimmed">
                      {METRIC_STYLES[m].label} {formatNumber(typeof v === "number" ? v : null)}
                    </Text>
                  );
                })}
              </Group>
            </Box>
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
  const [seasonMetric, setSeasonMetric] = useState<SeasonChartMetric>("ace");

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
          packTeamMetrics(
            row,
            tn,
            {
              ace: metricValue(p, "ace"),
              raw: metricValue(p, "raw"),
              auto: metricValue(p, "auto"),
              teleop: metricValue(p, "teleop"),
              endgame: metricValue(p, "endgame"),
              confidence: metricValue(p, "confidence"),
            },
            seasonChartValue(p, seasonMetric),
          );
          if (p?.rank_global != null) row[teamRankKey(tn)] = p.rank_global;
          const norm = normalizedAceFromRank(p?.rank_global, p?.count_global);
          if (norm != null) row[teamNormAceKey(tn)] = norm;
        }
        return row;
      });
      return { chartData: rows, series: seriesList, xTicks: years.map(String), sortedEventKeys: [] as string[] };
    }

    if (effectiveGrain === "match") {
      // Align on each team's own season match index (1st match, 2nd, …) — not a shared calendar.
      const orderedByTeam = new Map<number, TeamMatchRating[]>();
      for (const tn of teams) {
        orderedByTeam.set(
          tn,
          sortMatchesChronologically(matchesByTeam.get(tn) ?? [], eventMetaByKey),
        );
      }
      const maxLen = Math.max(0, ...teams.map((tn) => orderedByTeam.get(tn)?.length ?? 0));
      const rows: CompareChartRow[] = [];
      const ticks: string[] = [];
      for (let i = 0; i < maxLen; i++) {
        const matchNum = i + 1;
        const row: CompareChartRow = {
          x: String(matchNum),
          title: `Match ${matchNum}`,
          subtitle: "Each team’s own season match order",
        };
        for (const tn of teams) {
          const match = orderedByTeam.get(tn)?.[i];
          if (match) {
            const meta = eventMetaByKey.get(match.event_key);
            const eventName =
              meta?.event_data.name ?? match.event_key.replace(String(year), "").toUpperCase();
            row[teamMatchLabelKey(tn)] = `${eventName} · ${shortMatchLabel(match)}`;
          }
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
        // Label every match when few; otherwise every 5th + first/last.
        const showTick = maxLen <= 16 || matchNum === 1 || matchNum === maxLen || matchNum % 5 === 0;
        ticks.push(showTick ? String(matchNum) : "");
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
  }, [teams, perfByTeam, matchesByTeam, rangeMode, effectiveGrain, year, eventMetaByKey, seasonMetric]);

  const tickByX = useMemo(() => {
    const map = new Map<string, string>();
    chartData.forEach((row, i) => map.set(row.x, xTicks[i] ?? row.x));
    return map;
  }, [chartData, xTicks]);

  const axisTicks = useMemo(
    () => chartData.filter((row) => (tickByX.get(row.x) ?? "") !== "").map((row) => row.x),
    [chartData, tickByX],
  );

  const activeChartMetric: SeasonChartMetric = rangeMode === "all" ? seasonMetric : "ace";
  const yAxisLabel = rangeMode === "all" ? seasonChartLabel(seasonMetric) : "ACE";
  const chartTitle =
    rangeMode === "all"
      ? `${seasonChartLabel(seasonMetric)} by season`
      : effectiveGrain === "match"
        ? `ACE by season match # — ${year}`
        : `ACE by event — ${year}`;

  return (
    <Stack gap="md" py="md">
      <Title order={1}>Compare</Title>
      <Text c="dimmed" size="sm">
        {rangeMode === "all"
          ? "Compare ACE, global rank, or normalized ACE across seasons. Hover for component metrics."
          : effectiveGrain === "match"
            ? "ACE by each team’s own season match number (no calendar gaps). Hover for that team’s match."
            : "ACE by event. Hover a point for auto, teleop, endgame, RAW, and confidence."}
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
        {rangeMode === "all" ? (
          <Stack gap={4}>
            <Text size="sm" fw={500}>
              Metric
            </Text>
            <SegmentedControl
              value={seasonMetric}
              onChange={(v) => setSeasonMetric(v as SeasonChartMetric)}
              data={[
                { value: "ace", label: "ACE" },
                { value: "rank", label: "Rank" },
                { value: "normAce", label: "Norm ACE" },
              ]}
            />
          </Stack>
        ) : null}
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
        <Text c="dimmed">Add teams by number to compare.</Text>
      )}

      {teams.length > 0 && chartData.length > 0 ? (
        <Card withBorder padding="md" radius="md">
          <Text fw={600} mb={4}>
            {chartTitle}
          </Text>
          {rangeMode === "all" && seasonMetric === "normAce" ? (
            <Text size="xs" c="dimmed" mb="sm">
              Normalized ACE = global percentile from rank (100% ≈ #1). Comparable across years when
              raw ACE scales shift.
            </Text>
          ) : rangeMode === "single" && effectiveGrain === "match" ? (
            <Text size="xs" c="dimmed" mb="sm">
              X-axis is match number in each team’s season (1 = first match played), so lines stay
              continuous even when teams attend different events.
            </Text>
          ) : (
            <Box mb="sm" />
          )}
          <AreaChart
            h={360}
            data={chartData}
            dataKey="x"
            series={series}
            curveType="monotone"
            withDots
            withGradient
            connectNulls={rangeMode === "all" || effectiveGrain === "event"}
            withLegend
            gridAxis="xy"
            yAxisLabel={yAxisLabel}
            yAxisProps={
              seasonMetric === "rank" && rangeMode === "all"
                ? { reversed: true, allowDecimals: false, domain: [1, "dataMax"] }
                : seasonMetric === "normAce" && rangeMode === "all"
                  ? {
                      domain: [0, 1],
                      tickFormatter: (v: number) => `${Math.round(Number(v) * 100)}%`,
                    }
                  : undefined
            }
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
                  chartMetric={activeChartMetric}
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
