import { useMemo, useState, type ReactNode } from "react";
import { Card, Group, SegmentedControl, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { BarChart, ScatterChart } from "@mantine/charts";
import type { EventData, EventInsightRow } from "../types/api";
import { eventTypeLabel, eventWeekLabel, formatNumber, normalizeDistrictKey } from "../lib/format";

export type InsightRow = EventInsightRow & { event: EventData };

type AceMetric = "top8_ace" | "mean_ace" | "median_ace" | "max_ace";

const METRIC_OPTIONS: Array<{ value: AceMetric; label: string }> = [
  { value: "top8_ace", label: "Top 8 ACE" },
  { value: "mean_ace", label: "Mean ACE" },
  { value: "median_ace", label: "Median ACE" },
  { value: "max_ace", label: "Max ACE" },
];

const METRIC_LABEL: Record<AceMetric, string> = {
  top8_ace: "Top 8 ACE",
  mean_ace: "Mean ACE",
  median_ace: "Median ACE",
  max_ace: "Max ACE",
};

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Card withBorder padding="md" radius="md" h="100%">
      <Text fw={700}>{title}</Text>
      {subtitle ? (
        <Text size="xs" c="dimmed" mb="sm" mt={2}>
          {subtitle}
        </Text>
      ) : (
        <Text mb="sm" mt={2} style={{ height: 0 }} />
      )}
      {children}
    </Card>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card withBorder padding="md" radius="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {label}
      </Text>
      <Text fz={24} fw={700} mt={4} lineClamp={1}>
        {value}
      </Text>
      {hint ? (
        <Text size="xs" c="dimmed" mt={2} lineClamp={1}>
          {hint}
        </Text>
      ) : null}
    </Card>
  );
}

function average(vals: number[]): number | null {
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function groupAverage(
  rows: InsightRow[],
  keyOf: (r: InsightRow) => string | null,
  valueOf: (r: InsightRow) => number | null | undefined,
): Array<{ key: string; value: number; count: number }> {
  const map = new Map<string, { sum: number; n: number }>();
  for (const r of rows) {
    const key = keyOf(r);
    const val = valueOf(r);
    if (!key || val == null || Number.isNaN(val)) continue;
    const cur = map.get(key) ?? { sum: 0, n: 0 };
    cur.sum += val;
    cur.n += 1;
    map.set(key, cur);
  }
  return [...map.entries()]
    .map(([key, { sum, n }]) => ({ key, value: sum / n, count: n }))
    .sort((a, b) => b.value - a.value);
}

function shortEventName(name: string, max = 28): string {
  if (name.length <= max) return name;
  return `${name.slice(0, max - 1)}…`;
}

interface EventFiguresProps {
  year: number;
  rows: InsightRow[];
}

export function EventFigures({ year, rows }: EventFiguresProps) {
  const [metric, setMetric] = useState<AceMetric>("top8_ace");

  const valueOf = (r: InsightRow) => r[metric];

  const eventSourceCount = useMemo(
    () => rows.filter((r) => (r.source ?? "season") === "event").length,
    [rows],
  );

  const summary = useMemo(() => {
    const vals = rows.map(valueOf).filter((v): v is number => v != null);
    const strongest = [...rows].sort((a, b) => valueOf(b) - valueOf(a))[0];
    const deepest = [...rows].sort((a, b) => b.team_count - a.team_count)[0];
    return {
      eventCount: rows.length,
      avgMetric: average(vals),
      strongest,
      deepest,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, metric]);

  const byWeek = useMemo(() => {
    const groups = groupAverage(
      rows,
      (r) => {
        const label = eventWeekLabel(r.event.week);
        return label ?? (r.event.week != null ? `Week ${r.event.week}` : null);
      },
      valueOf,
    );
    // Chronological when possible (Week 1, Week 2, …) then leftovers.
    const weekNum = (label: string) => {
      const m = /Week\s+(\d+)/i.exec(label);
      return m ? Number(m[1]) : 999;
    };
    return [...groups]
      .sort((a, b) => weekNum(a.key) - weekNum(b.key) || a.key.localeCompare(b.key))
      .map((g) => ({ week: g.key, ACE: Number(g.value.toFixed(1)), Events: g.count }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, metric]);

  const byType = useMemo(
    () =>
      groupAverage(rows, (r) => eventTypeLabel(r.event.event_data.event_type), valueOf).map((g) => ({
        type: g.key,
        ACE: Number(g.value.toFixed(1)),
        Events: g.count,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, metric],
  );

  const byDistrict = useMemo(
    () =>
      groupAverage(rows, (r) => normalizeDistrictKey(r.event.district_key ?? null), valueOf)
        .slice(0, 16)
        .map((g) => ({
          district: g.key,
          ACE: Number(g.value.toFixed(1)),
          Events: g.count,
        })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, metric],
  );

  const topEvents = useMemo(
    () =>
      [...rows]
        .sort((a, b) => valueOf(b) - valueOf(a))
        .slice(0, 12)
        .map((r) => ({
          event: shortEventName(r.event.event_data.name),
          ACE: Number(valueOf(r).toFixed(1)),
        }))
        .reverse(), // horizontal bar charts often read bottom→top
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, metric],
  );

  const scatter = useMemo(
    () =>
      rows.map((r) => ({
        teamCount: r.team_count,
        ace: Number(valueOf(r).toFixed(2)),
        name: r.event.event_data.name,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, metric],
  );

  if (!rows.length) {
    return (
      <Text size="sm" c="dimmed">
        No event insights available for these filters.
      </Text>
    );
  }

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Stack gap={2}>
          <Title order={3}>{year} event figures</Title>
          <Text size="sm" c="dimmed">
            Uses each team&apos;s event ACE when available ({eventSourceCount.toLocaleString()} of{" "}
            {rows.length.toLocaleString()} events); otherwise season totals. Respects the filters
            above.
          </Text>
        </Stack>
        <SegmentedControl
          value={metric}
          onChange={(v) => setMetric(v as AceMetric)}
          data={METRIC_OPTIONS}
        />
      </Group>

      <SimpleGrid cols={{ base: 2, md: 4 }} spacing="md">
        <StatCard label="Events" value={summary.eventCount.toLocaleString()} />
        <StatCard
          label={`Avg ${METRIC_LABEL[metric]}`}
          value={formatNumber(summary.avgMetric, 1)}
        />
        <StatCard
          label="Strongest field"
          value={summary.strongest ? formatNumber(valueOf(summary.strongest), 1) : "–"}
          hint={summary.strongest?.event.event_data.name}
        />
        <StatCard
          label="Largest field"
          value={summary.deepest ? String(summary.deepest.team_count) : "–"}
          hint={summary.deepest?.event.event_data.name}
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <ChartCard title={`ACE by week`} subtitle={`Average ${METRIC_LABEL[metric]}`}>
          {byWeek.length ? (
            <BarChart
              h={280}
              data={byWeek}
              dataKey="week"
              series={[{ name: "ACE", color: "peeko.5" }]}
              tickLine="y"
              gridAxis="y"
            />
          ) : (
            <Text size="sm" c="dimmed">
              No week data.
            </Text>
          )}
        </ChartCard>
        <ChartCard title="ACE by event type" subtitle={`Average ${METRIC_LABEL[metric]}`}>
          {byType.length ? (
            <BarChart
              h={280}
              data={byType}
              dataKey="type"
              series={[{ name: "ACE", color: "blue.5" }]}
              tickLine="y"
              gridAxis="y"
            />
          ) : (
            <Text size="sm" c="dimmed">
              No type data.
            </Text>
          )}
        </ChartCard>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <ChartCard
          title="ACE by district"
          subtitle={`Top districts by average ${METRIC_LABEL[metric]}`}
        >
          {byDistrict.length ? (
            <BarChart
              h={320}
              data={byDistrict}
              dataKey="district"
              series={[{ name: "ACE", color: "teal.5" }]}
              tickLine="y"
              gridAxis="y"
            />
          ) : (
            <Text size="sm" c="dimmed">
              No district events in this filter.
            </Text>
          )}
        </ChartCard>
        <ChartCard title="Top events" subtitle={`Highest ${METRIC_LABEL[metric]}`}>
          {topEvents.length ? (
            <BarChart
              h={320}
              data={topEvents}
              dataKey="event"
              orientation="vertical"
              series={[{ name: "ACE", color: "orange.5" }]}
              tickLine="y"
              gridAxis="y"
              yAxisProps={{ width: 140 }}
            />
          ) : (
            <Text size="sm" c="dimmed">
              No events.
            </Text>
          )}
        </ChartCard>
      </SimpleGrid>

      <ChartCard
        title="Field size vs strength"
        subtitle={`Team count vs ${METRIC_LABEL[metric]}`}
      >
        <ScatterChart
          h={300}
          data={[{ name: "Events", color: "peeko.5", data: scatter }]}
          dataKey={{ x: "teamCount", y: "ace" }}
          xAxisLabel="Teams"
          yAxisLabel={METRIC_LABEL[metric]}
          gridAxis="xy"
          withTooltip
        />
      </ChartCard>
    </Stack>
  );
}
