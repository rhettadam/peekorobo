import { useEffect, useMemo, useState } from "react";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Group,
  MultiSelect,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconPlus, IconX } from "@tabler/icons-react";
import { LineChart } from "@mantine/charts";
import { useQueries } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { apiGet } from "../api/client";
import { useSearchIndex } from "../api/queries";
import { TeamName } from "../components/TeamName";
import { TeamAvatar } from "../components/TeamAvatar";
import { StatPill } from "../components/StatPill";
import type { EventPerfEntry, TeamPerfInfo, TeamPerfResponse } from "../types/api";
import { availableYears, CURRENT_YEAR } from "../lib/constants";
import { METRIC_STYLES, type MetricKey } from "../lib/metrics";
import { contrastText } from "../lib/epa";
import { recordString } from "../lib/format";

// Team trace palette from the production Dash compare chart.
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

const METRIC_OPTIONS: Array<{ value: MetricKey; label: string }> = [
  { value: "ace", label: "ACE" },
  { value: "raw", label: "RAW" },
  { value: "auto", label: "Auto" },
  { value: "teleop", label: "Teleop" },
  { value: "endgame", label: "Endgame" },
  { value: "confidence", label: "Confidence" },
];

const SUMMARY_METRICS: MetricKey[] = ["ace", "raw", "auto", "teleop", "endgame", "confidence"];

const RANK_PILL = "#455a64";

// Field on a season/event perf object for a given metric key.
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
  const [metrics, setMetrics] = useState<MetricKey[]>(["ace"]);

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

  const perfByTeam = useMemo(() => {
    const map = new Map<number, TeamPerfResponse | undefined>();
    teams.forEach((tn, i) => map.set(tn, results[i]?.data));
    return map;
  }, [teams, results]);

  const activeMetrics = metrics.length ? metrics : (["ace"] as MetricKey[]);

  // Build chart rows + series depending on range mode.
  const { chartData, series, xKey } = useMemo(() => {
    const seriesList: Array<{ name: string; color: string; key: string }> = [];
    let ci = 0;
    for (let ti = 0; ti < teams.length; ti++) {
      for (const m of activeMetrics) {
        seriesList.push({
          name:
            activeMetrics.length > 1
              ? `${teams[ti]} ${METRIC_STYLES[m].label}`
              : String(teams[ti]),
          color: TEAM_COLORS[ci % TEAM_COLORS.length],
          key: `${teams[ti]}__${m}`,
        });
        ci++;
      }
    }

    if (rangeMode === "all") {
      const yearSet = new Set<number>();
      for (const tn of teams) {
        for (const p of perfByTeam.get(tn)?.team_perfs ?? []) {
          if (p.year !== 2020 && p.year !== 2021) yearSet.add(p.year);
        }
      }
      const years = [...yearSet].sort((a, b) => a - b);
      const rows = years.map((y) => {
        const row: Record<string, number | string | null> = { x: String(y) };
        for (const tn of teams) {
          const p = perfByTeam.get(tn)?.team_perfs.find((x) => x.year === y);
          for (const m of activeMetrics) row[`${tn}__${m}`] = metricValue(p, m);
        }
        return row;
      });
      return { chartData: rows, series: seriesList, xKey: "x" };
    }

    // single-season: x-axis = union of event keys for the selected year.
    const eventKeys = new Set<string>();
    for (const tn of teams) {
      const p = perfByTeam.get(tn)?.team_perfs.find((x) => x.year === year);
      for (const ep of p?.event_perf ?? []) if (ep.event_key) eventKeys.add(ep.event_key);
    }
    const keys = [...eventKeys].sort();
    const rows = keys.map((ek) => {
      const row: Record<string, number | string | null> = { x: ek.replace(String(year), "") };
      for (const tn of teams) {
        const p = perfByTeam.get(tn)?.team_perfs.find((x) => x.year === year);
        const ep = p?.event_perf?.find((e) => e.event_key === ek);
        for (const m of activeMetrics) row[`${tn}__${m}`] = metricValue(ep, m);
      }
      return row;
    });
    return { chartData: rows, series: seriesList, xKey: "x" };
  }, [teams, perfByTeam, rangeMode, year, activeMetrics]);

  const chartSeries = series.map((s) => ({ name: s.key, label: s.name, color: s.color }));

  return (
    <Stack gap="md" py="md">
      <Title order={1}>Compare</Title>
      <Text c="dimmed" size="sm">
        Metrics by event (one season) or by year (all seasons). Add 2–8 teams.
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
          variant="light"
        >
          Add
        </Button>
        <MultiSelect
          label="Metrics"
          data={METRIC_OPTIONS}
          value={activeMetrics}
          onChange={(v) => setMetrics((v.length ? v : ["ace"]) as MetricKey[])}
          w={280}
          clearable={false}
        />
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
        <Text c="dimmed">Add teams by number to compare their metrics.</Text>
      )}

      {teams.length > 0 && chartData.length > 0 ? (
        <Card withBorder padding="md" radius="md">
          <Text fw={600} mb="sm">
            {rangeMode === "all"
              ? `${activeMetrics.map((m) => METRIC_STYLES[m].label).join(", ")} by season`
              : `${activeMetrics.map((m) => METRIC_STYLES[m].label).join(", ")} by event — ${year}`}
          </Text>
          <LineChart
            h={360}
            data={chartData}
            dataKey={xKey}
            series={chartSeries}
            curveType="monotone"
            withDots
            connectNulls
            withLegend
            gridAxis="xy"
          />
        </Card>
      ) : null}

      {teams.length > 0 ? (
        <Card withBorder padding="md" radius="md">
          <Text fw={700} mb="md">
            Season {year}
          </Text>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
            {teams.map((tn) => {
              const p = perfByTeam.get(tn)?.team_perfs.find((x) => x.year === year);
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
