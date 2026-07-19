import { useEffect, useMemo, useState } from "react";
import {
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Group,
  SimpleGrid,
  Select,
  Stack,
  Tabs,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconArrowsSort, IconSearch } from "@tabler/icons-react";
import { Link, useSearchParams } from "react-router-dom";
import { useEvents, useEventInsights } from "../api/queries";
import { ErrorState, LoadingState, EmptyState } from "../components/StateWrappers";
import { DataTable, type Column } from "../components/DataTable";
import { MetricCell } from "../components/MetricCell";
import { AceLegend } from "../components/AceLegend";
import { gameLogo } from "../lib/assets";
import { availableYears, CURRENT_YEAR } from "../lib/constants";
import { computePercentiles } from "../lib/epa";
import type { EventData, EventInsightRow } from "../types/api";
import {
  eventTypeLabel,
  eventWeekLabel,
  formatDateRange,
  locationString,
  normalizeDistrictKey,
} from "../lib/format";

const ALL = "all";

/** An event-insights stat row joined with its event metadata for display. */
type InsightRow = EventInsightRow & { event: EventData };

function EventCard({ event }: { event: EventData }) {
  return (
    <Card withBorder radius="md" padding="md" className="hover-lift" component={Link} to={`/event/${event.event_key}`}>
      <Stack gap={6} h="100%">
        <Text fw={600} lineClamp={2}>
          {event.event_data.name}
        </Text>
        <Text size="xs" c="dimmed">
          {event.event_key}
        </Text>
        <Text size="sm">
          {locationString(
            event.location_info.city,
            event.location_info.state_prov,
            event.location_info.country,
          )}
        </Text>
        <Text size="sm" c="dimmed">
          {formatDateRange(event.event_data.start_date, event.event_data.end_date)}
        </Text>
        <Group gap={6} mt="auto">
          {eventWeekLabel(event.week) ? (
            <Badge variant="light" size="sm">
              {eventWeekLabel(event.week)}
            </Badge>
          ) : null}
          <Badge variant="light" color="gray" size="sm">
            {eventTypeLabel(event.event_data.event_type)}
          </Badge>
        </Group>
      </Stack>
    </Card>
  );
}

const EVENT_LIST_COLUMNS: Column<EventData>[] = [
  {
    key: "week",
    header: "Week",
    width: 90,
    sortValue: (e) => (e.week ?? null),
    render: (e) =>
      eventWeekLabel(e.week) ? (
        <Badge variant="light" size="sm">
          {eventWeekLabel(e.week)}
        </Badge>
      ) : (
        <Text size="sm" c="dimmed">
          -
        </Text>
      ),
  },
  {
    key: "name",
    header: "Event",
    sortValue: (e) => e.event_data.name,
    render: (e) => (
      <>
        <Anchor component={Link} to={`/event/${e.event_key}`} fw={500}>
          {e.event_data.name}
        </Anchor>
        <Text size="xs" c="dimmed">
          {e.event_key}
        </Text>
      </>
    ),
  },
  {
    key: "location",
    header: "Location",
    sortValue: (e) =>
      locationString(e.location_info.city, e.location_info.state_prov, e.location_info.country),
    render: (e) =>
      locationString(e.location_info.city, e.location_info.state_prov, e.location_info.country),
  },
  {
    key: "type",
    header: "Type",
    sortValue: (e) => eventTypeLabel(e.event_data.event_type),
    render: (e) => eventTypeLabel(e.event_data.event_type),
  },
  {
    key: "dates",
    header: "Dates",
    sortValue: (e) => e.event_data.start_date ?? "",
    render: (e) => formatDateRange(e.event_data.start_date, e.event_data.end_date),
  },
];

export function Events() {
  const [searchParams, setSearchParams] = useSearchParams();
  const year = Number(searchParams.get("year")) || CURRENT_YEAR;
  const [filter, setFilter] = useState("");
  // Week/type/district filters live in the URL so a filtered view is shareable
  // (e.g. /events?year=2025&district=FIM&week=1).
  const weekFilter = searchParams.get("week") || ALL;
  const typeFilter = searchParams.get("type") || ALL;
  const districtFilter = searchParams.get("district") || ALL;
  const [view, setView] = useState<string>("cards");
  const [sortMode, setSortMode] = useState<"time" | "alpha">("time");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const setParam = (updates: Record<string, string | null>) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(updates)) {
          if (v === null || v === "" || v === ALL) next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace: false },
    );
  };

  const eventsQuery = useEvents(year);

  useEffect(() => {
    document.title = `${year} Events - Peekorobo`;
  }, [year]);

  const allEvents = eventsQuery.data?.events ?? [];

  const weekOptions = useMemo(() => {
    const weeks = new Set<number>();
    for (const e of allEvents) {
      if (e.week !== null && e.week !== undefined) weeks.add(e.week);
    }
    return [...weeks].sort((a, b) => a - b).map((w) => ({
      value: String(w),
      label: eventWeekLabel(w) ?? `Week ${w}`,
    }));
  }, [allEvents]);

  const typeOptions = useMemo(() => {
    const types = new Set<string>();
    for (const e of allEvents) {
      if (e.event_data.event_type) types.add(String(e.event_data.event_type));
    }
    return [...types]
      .map((t) => ({ value: t, label: eventTypeLabel(t) }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [allEvents]);

  const districtOptions = useMemo(() => {
    const districts = new Set<string>();
    for (const e of allEvents) {
      const d = normalizeDistrictKey(e.district_key ?? null);
      if (d) districts.add(d);
    }
    return [...districts].sort().map((d) => ({ value: d, label: d }));
  }, [allEvents]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const list = allEvents.filter((e) => {
      if (weekFilter !== ALL && String(e.week ?? "") !== weekFilter) return false;
      if (typeFilter !== ALL && String(e.event_data.event_type ?? "") !== typeFilter) return false;
      if (districtFilter !== ALL && normalizeDistrictKey(e.district_key ?? null) !== districtFilter) {
        return false;
      }
      if (!q) return true;
      const loc = locationString(
        e.location_info.city,
        e.location_info.state_prov,
        e.location_info.country,
      ).toLowerCase();
      return (
        e.event_key.toLowerCase().includes(q) ||
        e.event_data.name.toLowerCase().includes(q) ||
        loc.includes(q)
      );
    });
    list.sort((a, b) => {
      let cmp: number;
      if (sortMode === "alpha") {
        cmp = a.event_data.name.localeCompare(b.event_data.name);
      } else {
        cmp = (a.event_data.start_date || "").localeCompare(b.event_data.start_date || "");
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [allEvents, filter, weekFilter, typeFilter, districtFilter, sortMode, sortDir]);

  const { upcoming, ongoing } = useMemo(() => {
    const now = Date.now();
    const up: EventData[] = [];
    const on: EventData[] = [];
    for (const e of filtered) {
      const start = Date.parse(e.event_data.start_date);
      const end = Date.parse(e.event_data.end_date);
      if (!Number.isNaN(start) && start > now) up.push(e);
      else if (!Number.isNaN(start) && !Number.isNaN(end) && start <= now && now <= end + 864e5) {
        on.push(e);
      }
    }
    return { upcoming: up.slice(0, 8), ongoing: on };
  }, [filtered]);

  // ---- Event Insights: season-wide per-event ACE stats (deferred until tab open) ----
  const insightsQuery = useEventInsights(year, { enabled: view === "insights" });
  const insightsByKey = useMemo(() => {
    const m = new Map<string, EventInsightRow>();
    for (const r of insightsQuery.data?.events ?? []) m.set(r.event_key, r);
    return m;
  }, [insightsQuery.data]);

  const insightRows = useMemo<InsightRow[]>(() => {
    const out: InsightRow[] = [];
    for (const e of filtered) {
      const ins = insightsByKey.get(e.event_key);
      if (ins) out.push({ ...ins, event: e });
    }
    return out;
  }, [filtered, insightsByKey]);

  const insightThresholds = useMemo(
    () => ({
      max: computePercentiles(insightRows.map((r) => r.max_ace)),
      top8: computePercentiles(insightRows.map((r) => r.top8_ace)),
      top24: computePercentiles(insightRows.map((r) => r.top24_ace)),
      mean: computePercentiles(insightRows.map((r) => r.mean_ace)),
      median: computePercentiles(insightRows.map((r) => r.median_ace)),
    }),
    [insightRows],
  );

  const insightColumns = useMemo<Column<InsightRow>[]>(
    () => [
      {
        key: "name",
        header: "Event",
        sortValue: (r) => r.event.event_data.name,
        exportValue: (r) => r.event.event_data.name,
        render: (r) => (
          <>
            <Anchor component={Link} to={`/event/${r.event_key}`} fw={500}>
              {r.event.event_data.name}
            </Anchor>
            <Text size="xs" c="dimmed">
              {r.event_key}
            </Text>
          </>
        ),
      },
      {
        key: "week",
        header: "Week",
        width: 90,
        sortValue: (r) => r.event.week ?? null,
        exportValue: (r) => eventWeekLabel(r.event.week) ?? "",
        render: (r) => (
          <Text size="sm" c={eventWeekLabel(r.event.week) ? undefined : "dimmed"} style={{ whiteSpace: "nowrap" }}>
            {eventWeekLabel(r.event.week) ?? "-"}
          </Text>
        ),
      },
      {
        key: "district",
        header: "District",
        width: 100,
        sortValue: (r) => normalizeDistrictKey(r.event.district_key ?? null) ?? "",
        render: (r) => normalizeDistrictKey(r.event.district_key ?? null) || "-",
      },
      {
        key: "location",
        header: "Location",
        sortValue: (r) =>
          [r.event.location_info.state_prov, r.event.location_info.country]
            .filter(Boolean)
            .join(", "),
        render: (r) =>
          [r.event.location_info.state_prov, r.event.location_info.country]
            .filter(Boolean)
            .join(", ") || "-",
      },
      {
        key: "type",
        header: "Type",
        width: 110,
        sortValue: (r) => eventTypeLabel(r.event.event_data.event_type),
        render: (r) => eventTypeLabel(r.event.event_data.event_type),
      },
      {
        key: "teams",
        header: "Teams",
        width: 80,
        align: "center",
        sortValue: (r) => r.team_count,
        render: (r) => r.team_count,
      },
      {
        key: "max",
        header: "Max ACE",
        width: 100,
        sortValue: (r) => r.max_ace,
        render: (r) => <MetricCell value={r.max_ace} thresholds={insightThresholds.max} />,
      },
      {
        key: "top8",
        header: "Top 8 ACE",
        width: 100,
        sortValue: (r) => r.top8_ace,
        render: (r) => <MetricCell value={r.top8_ace} thresholds={insightThresholds.top8} />,
      },
      {
        key: "top24",
        header: "Top 24 ACE",
        width: 105,
        sortValue: (r) => r.top24_ace,
        render: (r) => <MetricCell value={r.top24_ace} thresholds={insightThresholds.top24} />,
      },
      {
        key: "mean",
        header: "Mean ACE",
        width: 100,
        sortValue: (r) => r.mean_ace,
        render: (r) => <MetricCell value={r.mean_ace} thresholds={insightThresholds.mean} />,
      },
      {
        key: "median",
        header: "Median ACE",
        width: 105,
        sortValue: (r) => r.median_ace,
        render: (r) => <MetricCell value={r.median_ace} thresholds={insightThresholds.median} />,
      },
    ],
    [insightThresholds],
  );

  return (
    <Stack gap="md" py="md">
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group gap="md" align="stretch" wrap="nowrap">
          <Box style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
            <img
              src={gameLogo(year)}
              alt={`${year} game`}
              style={{
                height: "100%",
                width: "auto",
                maxHeight: 64,
                objectFit: "contain",
                display: "block",
              }}
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
          </Box>
          <Title order={1} style={{ fontSize: 56, lineHeight: 1, fontWeight: 800 }}>
            Events
          </Title>
        </Group>
        <Select
          label="Season"
          value={String(year)}
          data={availableYears().map((y) => ({ value: String(y), label: String(y) }))}
          onChange={(val) => val && setParam({ year: val, week: null, type: null, district: null })}
          allowDeselect={false}
          w={120}
        />
      </Group>

      <Card withBorder padding="sm" radius="md">
        <Group gap="sm" wrap="wrap" align="flex-end">
          <TextInput
            label="Search"
            placeholder="Name, key, or location"
            leftSection={<IconSearch size={16} />}
            value={filter}
            onChange={(e) => setFilter(e.currentTarget.value)}
            w={220}
          />
          {weekOptions.length > 0 ? (
            <Select
              label="Week"
              data={[{ value: ALL, label: "All weeks" }, ...weekOptions]}
              value={weekFilter}
              onChange={(v) => setParam({ week: v ?? ALL })}
              allowDeselect={false}
              w={150}
            />
          ) : null}
          {typeOptions.length > 0 ? (
            <Select
              label="Type"
              data={[{ value: ALL, label: "All types" }, ...typeOptions]}
              value={typeFilter}
              onChange={(v) => setParam({ type: v ?? ALL })}
              allowDeselect={false}
              w={200}
            />
          ) : null}
          {districtOptions.length > 0 ? (
            <Select
              label="District"
              data={[{ value: ALL, label: "All districts" }, ...districtOptions]}
              value={districtFilter}
              onChange={(v) => setParam({ district: v ?? ALL })}
              allowDeselect={false}
              searchable
              w={180}
            />
          ) : null}
          <Select
            label="Sort"
            data={[
              { value: "time", label: "By Date" },
              { value: "alpha", label: "A\u2013Z" },
            ]}
            value={sortMode}
            onChange={(v) => setSortMode((v as "time" | "alpha") ?? "time")}
            allowDeselect={false}
            w={130}
          />
          <Button
            variant="default"
            mb={1}
            leftSection={<IconArrowsSort size={16} />}
            onClick={() => setSortDir((d) => (d === "asc" ? "desc" : "asc"))}
          >
            {sortDir === "asc" ? "Asc" : "Desc"}
          </Button>
          {filter || weekFilter !== ALL || typeFilter !== ALL || districtFilter !== ALL ? (
            <Button
              variant="subtle"
              mb={1}
              onClick={() => {
                setFilter("");
                setParam({ week: null, type: null, district: null });
              }}
            >
              Clear
            </Button>
          ) : null}
        </Group>
      </Card>

      {eventsQuery.isLoading ? (
        <LoadingState label={`Loading ${year} events...`} />
      ) : eventsQuery.error ? (
        <ErrorState error={eventsQuery.error} />
      ) : (
        <Tabs value={view} onChange={(v) => setView(v ?? "cards")} keepMounted={false}>
          <Tabs.List>
            <Tabs.Tab value="cards">Cards</Tabs.Tab>
            <Tabs.Tab value="list">List</Tabs.Tab>
            <Tabs.Tab value="insights">Event Insights</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="cards" pt="md">
            {filtered.length === 0 ? (
              <EmptyState>No events match your filters.</EmptyState>
            ) : (
              <Stack gap="lg">
                {ongoing.length > 0 ? (
                  <Stack gap="sm">
                    <Title order={3}>Ongoing Events</Title>
                    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="md">
                      {ongoing.map((e) => (
                        <EventCard key={e.event_key} event={e} />
                      ))}
                    </SimpleGrid>
                  </Stack>
                ) : null}
                {upcoming.length > 0 ? (
                  <Stack gap="sm">
                    <Title order={3}>Upcoming Events</Title>
                    <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="md">
                      {upcoming.map((e) => (
                        <EventCard key={e.event_key} event={e} />
                      ))}
                    </SimpleGrid>
                  </Stack>
                ) : null}
                <Stack gap="sm">
                  <Title order={3}>All Events</Title>
                  <Text size="sm" c="dimmed">
                    {filtered.length.toLocaleString()} events
                  </Text>
                  <SimpleGrid cols={{ base: 1, sm: 2, md: 3, lg: 4 }} spacing="md">
                    {filtered.map((e) => (
                      <EventCard key={e.event_key} event={e} />
                    ))}
                  </SimpleGrid>
                </Stack>
              </Stack>
            )}
          </Tabs.Panel>

          <Tabs.Panel value="list" pt="md">
            <DataTable
              data={filtered}
              columns={EVENT_LIST_COLUMNS}
              getRowKey={(e) => e.event_key}
              initialSort={{ key: "dates", dir: "asc" }}
              minWidth={720}
              defaultPageSize={50}
              exportFileName={`peekorobo-events-${year}`}
            />
          </Tabs.Panel>

          <Tabs.Panel value="insights" pt="md">
            {insightsQuery.isLoading ? (
              <LoadingState label={`Computing ${year} event insights...`} />
            ) : insightsQuery.error ? (
              <ErrorState error={insightsQuery.error} />
            ) : insightRows.length === 0 ? (
              <EmptyState>No event insights available for these filters.</EmptyState>
            ) : (
              <Stack gap="sm">
                <Text size="sm" c="dimmed">
                  Season-wide ACE statistics across each event's participating teams. Sorted by Top 8
                  ACE.
                </Text>
                <AceLegend />
                <DataTable
                  data={insightRows}
                  columns={insightColumns}
                  getRowKey={(r) => r.event_key}
                  initialSort={{ key: "top8", dir: "desc" }}
                  minWidth={920}
                  stickyHeader
                  defaultPageSize={25}
                  exportFileName={`peekorobo-event-insights-${year}`}
                />
              </Stack>
            )}
          </Tabs.Panel>
        </Tabs>
      )}
    </Stack>
  );
}
