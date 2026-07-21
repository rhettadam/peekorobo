import { useEffect, useMemo, useState } from "react";
import {
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Group,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Select,
  Tabs,
  Text,
  Title,
} from "@mantine/core";
import { AreaChart } from "@mantine/charts";
import {
  IconHistory,
} from "@tabler/icons-react";
import { useNavigate, useParams, Link } from "react-router-dom";
import {
  useEvents,
  useFilterOptions,
  useTeamAwards,
  useTeamEvents,
  useTeamInfo,
  useTeamNotables,
  useTeamPerfs,
} from "../api/queries";
import { ErrorState, LoadingState } from "../components/StateWrappers";
import { TeamAvatar } from "../components/TeamAvatar";
import { FavoriteButton } from "../components/FavoriteButton";
import { StatPill } from "../components/StatPill";
import { TeamEventBlock } from "../components/TeamEventBlock";
import { BlueBanners } from "../components/BlueBanners";
import { TeamProfileMeta } from "../components/TeamProfileMeta";
import type { EventData, EventPerfEntry, TeamPerfInfo } from "../types/api";
import { CURRENT_YEAR } from "../lib/constants";
import { BRAND } from "../lib/assets";
import { isBlueBanner } from "../lib/banners";
import { contrastText } from "../lib/epa";
import {
  eventWeekLabel,
  formatNumber,
  locationString,
  normalizeDistrictKey,
  yearFromEventKey,
} from "../lib/format";

function RankCard({
  label,
  rank,
  count,
  to,
  compact,
}: {
  label: string;
  rank?: number | null;
  count?: number | null;
  to?: string;
  /** Tighter layout for fitting 3 cards in one mobile row. */
  compact?: boolean;
}) {
  if (rank === null || rank === undefined) return null;
  const inner = (
    <>
      <Text
        size={compact ? "10px" : "xs"}
        c="dimmed"
        tt="uppercase"
        fw={700}
        ta="center"
        lh={1.15}
        lineClamp={2}
      >
        {label}
      </Text>
      <Text
        fz={compact ? { base: 26, sm: 40 } : 40}
        fw={800}
        mt={compact ? { base: 4, sm: 6 } : 6}
        ta="center"
        c="blue"
        lh={1.1}
      >
        {rank.toLocaleString()}
      </Text>
      {count ? (
        <Text size={compact ? "xs" : "sm"} c="dimmed" ta="center" mt={compact ? 2 : 0}>
          out of {count.toLocaleString()}
        </Text>
      ) : null}
    </>
  );
  if (to) {
    return (
      <Card
        withBorder
        padding={compact ? "sm" : "lg"}
        radius="md"
        component={Link}
        to={to}
        className="hover-lift"
        style={{ textDecoration: "none", color: "inherit", cursor: "pointer" }}
      >
        {inner}
      </Card>
    );
  }
  return (
    <Card withBorder padding={compact ? "sm" : "lg"} radius="md">
      {inner}
    </Card>
  );
}

function shortEventLabel(eventKey: string): string {
  return eventKey.replace(/^\d{4}/, "").toUpperCase();
}

interface EventTrendRow {
  event: string;
  eventKey?: string;
  name?: string;
  week?: string | null;
  Actual: number | null;
  Pred: number | null;
  Auto?: number | null;
  Teleop?: number | null;
  Endgame?: number | null;
  raw?: number | null;
  conf?: number | null;
  isPred?: boolean;
}

/** Rich hover card for the event-performance chart. */
function EventTrendTooltip({ payload }: { payload?: Array<{ payload?: EventTrendRow }> }) {
  const row = payload?.[0]?.payload;
  if (!row) return null;
  const rows: Array<[string, string, string?]> = [];
  if (row.isPred) {
    rows.push(["Projected ACE", formatNumber(row.Pred), "#2196F3"]);
  } else {
    rows.push(["ACE", formatNumber(row.Actual), "var(--mantine-color-peeko-6)"]);
    if (row.raw != null) rows.push(["RAW", formatNumber(row.raw)]);
    if (row.conf != null) rows.push(["Confidence", `${Math.round((row.conf ?? 0) * 100)}%`]);
    if (row.Auto != null) rows.push(["Auto", formatNumber(row.Auto), "#f59e0b"]);
    if (row.Teleop != null) rows.push(["Teleop", formatNumber(row.Teleop), "#3b82f6"]);
    if (row.Endgame != null) rows.push(["Endgame", formatNumber(row.Endgame), "#10b981"]);
  }
  return (
    <Card withBorder radius="md" padding="sm" shadow="md" style={{ minWidth: 180 }}>
      <Text fw={700} size="sm" lineClamp={2}>
        {row.isPred ? "Projection" : row.name || row.event}
      </Text>
      {!row.isPred && row.week ? (
        <Text size="xs" c="dimmed" mb={4}>
          {row.week}
        </Text>
      ) : null}
      <Stack gap={2} mt={4}>
        {rows.map(([label, value, color]) => (
          <Group key={label} justify="space-between" gap="lg" wrap="nowrap">
            <Group gap={6} wrap="nowrap">
              {color ? (
                <Box
                  style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }}
                />
              ) : null}
              <Text size="xs" c="dimmed">
                {label}
              </Text>
            </Group>
            <Text size="xs" fw={600}>
              {value}
            </Text>
          </Group>
        ))}
      </Stack>
      {!row.isPred && row.eventKey ? (
        <Text size="xs" c="peeko.5" mt={6}>
          Click point to open event
        </Text>
      ) : null}
    </Card>
  );
}

export function Team() {
  const params = useParams();
  const navigate = useNavigate();
  const teamNumber = Number(params.teamNumber);
  const paramYear = params.year ? Number(params.year) : undefined;
  const [chartMode, setChartMode] = useState<"trend" | "breakdown">("trend");

  const infoQuery = useTeamInfo(teamNumber);
  const perfsQuery = useTeamPerfs(teamNumber);
  const { data: filterOptions } = useFilterOptions();

  const perfs = perfsQuery.data?.team_perfs ?? [];
  const perfsByYear = useMemo(() => {
    const map = new Map<number, TeamPerfInfo>();
    for (const p of perfs) map.set(p.year, p);
    return map;
  }, [perfs]);

  const years = useMemo(() => [...perfsByYear.keys()].sort((a, b) => b - a), [perfsByYear]);
  const selectedYear = paramYear ?? years[0] ?? CURRENT_YEAR;
  const perf = perfsByYear.get(selectedYear);

  const eventsQuery = useTeamEvents(teamNumber, selectedYear);
  const awardsQuery = useTeamAwards(teamNumber, selectedYear);
  const allAwardsQuery = useTeamAwards(teamNumber);
  const notablesQuery = useTeamNotables(teamNumber);
  const yearEventsQuery = useEvents(selectedYear);

  const notables = notablesQuery.data?.notables ?? [];
  const hasWorldChampsNotable = notables.some((n) => n.category === "notables_world_champions");

  const eventMetaByKey = useMemo(() => {
    const map = new Map<string, EventData>();
    for (const e of yearEventsQuery.data?.events ?? []) map.set(e.event_key, e);
    return map;
  }, [yearEventsQuery.data]);

  const eventPerfByKey = useMemo(() => {
    const map = new Map<string, EventPerfEntry>();
    for (const ep of (perf?.event_perf ?? []) as EventPerfEntry[]) {
      if (ep.event_key) map.set(ep.event_key, ep);
    }
    return map;
  }, [perf]);

  const seasonAwards = awardsQuery.data?.awards ?? [];

  const awardsByEvent = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const a of seasonAwards) {
      const arr = map.get(a.event_key) ?? [];
      arr.push(a.award_name);
      map.set(a.event_key, arr);
    }
    return map;
  }, [seasonAwards]);

  const teamEventKeys = useMemo(() => {
    const keys = [...(eventsQuery.data?.events ?? [])];
    return keys.sort((a, b) => {
      const sa = eventMetaByKey.get(a)?.event_data.start_date ?? a;
      const sb = eventMetaByKey.get(b)?.event_data.start_date ?? b;
      return sb.localeCompare(sa); // most recent first
    });
  }, [eventsQuery.data, eventMetaByKey]);

  const honors = useMemo(() => {
    const awards = allAwardsQuery.data?.awards ?? [];
    const champYears = new Set<number>();
    for (const a of awards) {
      const name = (a.award_name || "").toLowerCase();
      const yr = yearFromEventKey(a.event_key ?? "");
      const isDivision = name.includes("division") || name.includes("subdivision");
      if (!isDivision && (name === "championship winner" || name === "championship winners")) {
        if (yr) champYears.add(yr);
      }
    }
    return {
      champYears: [...champYears].sort((a, b) => a - b),
    };
  }, [allAwardsQuery.data]);

  useEffect(() => {
    const nickname = infoQuery.data?.nickname;
    document.title = nickname
      ? `${teamNumber} | ${nickname} - Peekorobo`
      : `Team ${teamNumber} - Peekorobo`;
  }, [teamNumber, infoQuery.data?.nickname]);

  // Per-event Actual + damped-linear Pred projection (mirrors build_trends_chart).
  const eventTrend = useMemo(() => {
    const entries = (perf?.event_perf ?? []) as EventPerfEntry[];
    const events = entries
      .filter((e) => typeof e.ace === "number" && e.event_key)
      .map((e) => {
        const meta = eventMetaByKey.get(e.event_key as string);
        return {
          key: e.event_key as string,
          name: meta?.event_data.name ?? (e.event_key as string),
          week: eventWeekLabel(meta?.week),
          ace: e.ace as number,
          raw: typeof e.raw === "number" ? e.raw : null,
          conf: typeof e.confidence === "number" ? e.confidence : null,
          auto: typeof e.auto_raw === "number" ? e.auto_raw : null,
          teleop: typeof e.teleop_raw === "number" ? e.teleop_raw : null,
          endgame: typeof e.endgame_raw === "number" ? e.endgame_raw : null,
          start: meta?.event_data.start_date ?? e.event_key,
        };
      })
      .sort((a, b) => (a.start ?? "").localeCompare(b.start ?? ""));

    const rows: EventTrendRow[] = events.map((e) => ({
      event: shortEventLabel(e.key),
      eventKey: e.key,
      name: e.name,
      week: e.week,
      Actual: e.ace,
      Pred: null,
      Auto: e.auto,
      Teleop: e.teleop,
      Endgame: e.endgame,
      raw: e.raw,
      conf: e.conf,
    }));

    const n = events.length;
    const nPred = n >= 3 ? 2 : n >= 2 ? 1 : 0;
    let hasPred = false;
    if (nPred > 0) {
      // Least-squares linear fit over event index; damp positive slopes.
      const fit = (vals: Array<number | null>) => {
        const pts = vals
          .map((v, i) => ({ x: i, y: v }))
          .filter((p): p is { x: number; y: number } => p.y !== null);
        if (pts.length < 2) return null;
        const mx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
        const my = pts.reduce((s, p) => s + p.y, 0) / pts.length;
        let num = 0;
        let den = 0;
        for (const p of pts) {
          num += (p.x - mx) * (p.y - my);
          den += (p.x - mx) ** 2;
        }
        if (den === 0) return null;
        let slope = num / den;
        if (slope > 0) slope *= 0.6; // conservative damping of upward trends
        const intercept = my - slope * mx;
        return { slope, intercept };
      };
      const rawFit = fit(events.map((e) => e.raw));
      const confFit = fit(events.map((e) => e.conf));
      if (rawFit && confFit) {
        rows[rows.length - 1].Pred = events[n - 1].ace; // connect from last actual
        for (let k = 1; k <= nPred; k++) {
          const idx = n - 1 + k;
          const predRaw = Math.max(0, rawFit.intercept + rawFit.slope * idx);
          const predConf = Math.min(1, Math.max(0, confFit.intercept + confFit.slope * idx));
          rows.push({
            event: `Pred ${k}`,
            Actual: null,
            Pred: predRaw * predConf,
            isPred: true,
          });
        }
        hasPred = true;
      }
    }
    const breakdownRows = rows.filter((r) => !r.isPred);
    const hasBreakdown = breakdownRows.some(
      (r) => r.Auto != null || r.Teleop != null || r.Endgame != null,
    );
    return { rows, hasPred, breakdownRows, hasBreakdown };
  }, [perf, eventMetaByKey]);

  if (perfsQuery.isLoading) return <LoadingState label={`Loading team ${teamNumber}...`} />;
  if (perfsQuery.error) return <ErrorState error={perfsQuery.error} />;

  const info = infoQuery.data;
  const district = normalizeDistrictKey(info?.district_key ?? null);
  const districtName = district
    ? filterOptions?.districts.find((d) => d.value.toUpperCase() === district)?.label ?? district
    : null;

  const teamCountry = info?.country;
  const teamState = info?.state_prov;
  const districtOpt = district
    ? filterOptions?.districts.find((d) => d.value.toUpperCase() === district)
    : undefined;
  const rankCards = perf
    ? [
        {
          label: "Global",
          rank: perf.rank_global,
          count: perf.count_global,
          to: `/teams?year=${selectedYear}`,
        },
        {
          label: info?.country || "Country",
          rank: perf.rank_country,
          count: perf.count_country,
          to: teamCountry
            ? `/teams?year=${selectedYear}&country=${encodeURIComponent(teamCountry)}`
            : undefined,
        },
        {
          label: info?.state_prov || "State/Prov",
          rank: perf.rank_state,
          count: perf.count_state,
          to:
            teamCountry && teamState
              ? `/teams?year=${selectedYear}&country=${encodeURIComponent(teamCountry)}&state=${encodeURIComponent(teamState)}`
              : undefined,
        },
        {
          label: districtName || "District",
          rank: perf.rank_district,
          count: perf.count_district,
          to: districtOpt
            ? `/teams?year=${selectedYear}&district=${encodeURIComponent(districtOpt.value)}`
            : undefined,
        },
      ].filter((c) => c.rank !== null && c.rank !== undefined)
    : [];

  const colors = info?.team_colors as { primary?: string; secondary?: string } | null | undefined;
  const primary = typeof colors?.primary === "string" ? colors.primary : null;
  const secondary = typeof colors?.secondary === "string" ? colors.secondary : null;
  const gradient =
    primary && secondary
      ? `linear-gradient(135deg, ${primary}, ${secondary})`
      : "linear-gradient(135deg, #3a3a3a, #1a1a1a)";
  const headerText = primary ? contrastText(primary) : "#ffffff";

  return (
    <Stack gap="lg" py="md">
      {/* Team header: team-color gradient layered with a diagonal sheen, corner
          glow, dot + line grid, and a large faint team-number watermark. */}
      <Card
        radius="lg"
        p="lg"
        style={{
          position: "relative",
          background: [
            "linear-gradient(115deg, transparent 38%, rgba(255,255,255,0.10) 47%, transparent 56%)",
            "radial-gradient(circle at 90% 8%, rgba(255,255,255,0.22), transparent 46%)",
            "radial-gradient(rgba(255,255,255,0.10) 1.5px, transparent 1.6px)",
            "linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px)",
            "linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)",
            gradient,
          ].join(", "),
          backgroundSize: "100% 100%, 100% 100%, 52px 52px, 26px 26px, 26px 26px, 100% 100%",
          color: headerText,
          border: "none",
          overflow: "hidden",
        }}
      >
        <Box
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            zIndex: 2,
            background: "rgba(0,0,0,0.45)",
            borderRadius: 999,
            backdropFilter: "blur(6px)",
          }}
        >
          <FavoriteButton itemType="team" itemKey={teamNumber} size={22} />
        </Box>
        <Text
          aria-hidden
          style={{
            position: "absolute",
            right: -8,
            top: "50%",
            transform: "translateY(-50%)",
            fontSize: 200,
            fontWeight: 900,
            lineHeight: 1,
            letterSpacing: -8,
            color: headerText,
            opacity: 0.08,
            pointerEvents: "none",
            userSelect: "none",
            zIndex: 0,
          }}
        >
          {teamNumber}
        </Text>
        <Group justify="space-between" align="center" wrap="nowrap" gap="md" style={{ position: "relative", zIndex: 1 }}>
          <Stack gap={8} style={{ minWidth: 0, flex: 1 }}>
            <Title order={1} c={headerText} style={{ wordBreak: "break-word" }}>
              Team {teamNumber}
              {info?.nickname ? `: ${info.nickname}` : ""}
            </Title>

            <TeamProfileMeta
              headerText={headerText}
              location={
                info
                  ? locationString(info.city, info.state_prov, info.country) || "Unknown location"
                  : undefined
              }
              district={district}
              website={info?.website}
              teamNumber={teamNumber}
              notables={notables}
              champYears={honors.champYears}
              showWorldChampHonor={!hasWorldChampsNotable && honors.champYears.length > 0}
            />

            <Group gap="xs" mt={4} align="flex-end">
              {years.length > 0 ? (
                <Select
                  aria-label="Season"
                  value={String(selectedYear)}
                  data={years.map((y) => ({ value: String(y), label: String(y) }))}
                  onChange={(val) => val && navigate(`/team/${teamNumber}/${val}`)}
                  allowDeselect={false}
                  w={120}
                />
              ) : null}
              <Button
                component={Link}
                to={`/team/${teamNumber}/history`}
                variant="white"
                color="dark"
                size="sm"
                leftSection={<IconHistory size={16} />}
              >
                Full History
              </Button>
            </Group>

            <Group gap="xs" mt={4}>
              <Anchor
                href={`https://www.thebluealliance.com/team/${teamNumber}`}
                target="_blank"
                rel="noopener noreferrer"
                title="View on The Blue Alliance"
              >
                <img src={BRAND.tba} alt="The Blue Alliance" height={22} style={{ display: "block", borderRadius: 4 }} />
              </Anchor>
              <Anchor
                href={`https://www.statbotics.io/team/${teamNumber}`}
                target="_blank"
                rel="noopener noreferrer"
                title="View on Statbotics"
              >
                <img src={BRAND.statbotics} alt="Statbotics" height={22} style={{ display: "block", borderRadius: 4 }} />
              </Anchor>
              <Anchor
                href={`https://frc-events.firstinspires.org/team/${teamNumber}`}
                target="_blank"
                rel="noopener noreferrer"
                title="View on FRC Events"
              >
                <img src={BRAND.frc} alt="FRC Events" height={22} style={{ display: "block", borderRadius: 4 }} />
              </Anchor>
            </Group>
          </Stack>

          <Box
            visibleFrom="sm"
            mr={40}
            style={{
              flexShrink: 0,
              alignSelf: "center",
              background: "rgba(0,0,0,0.55)",
              backdropFilter: "blur(14px) saturate(140%)",
              WebkitBackdropFilter: "blur(14px) saturate(140%)",
              border: "1px solid rgba(255,255,255,0.14)",
              borderRadius: 22,
              padding: 20,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 8px 28px rgba(0,0,0,0.3), inset 0 1px 1px rgba(255,255,255,0.2)",
            }}
          >
            <TeamAvatar teamNumber={teamNumber} size={150} radius={14} upscale />
          </Box>
        </Group>
      </Card>

      <Tabs defaultValue="overview" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="overview">Overview</Tabs.Tab>
          <Tabs.Tab value="events">Events</Tabs.Tab>
          <Tabs.Tab value="awards">Awards</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="overview" pt="md">
          {perf ? (
            <Stack gap="lg">
              <SimpleGrid
                cols={{
                  // 3 non-district ranks → one snug mobile row; 4 stays 2×2.
                  base: rankCards.length === 3 ? 3 : 2,
                  sm: rankCards.length || 1,
                }}
                spacing={rankCards.length === 3 ? "xs" : "md"}
              >
                {rankCards.map((c) => (
                  <RankCard
                    key={c.label}
                    label={c.label}
                    rank={c.rank}
                    count={c.count}
                    to={c.to}
                    compact={rankCards.length === 3}
                  />
                ))}
              </SimpleGrid>

              <Text>
                Team {teamNumber}
                {info?.nickname ? ` (${info.nickname})` : ""} had a record of{" "}
                <Text span c="green.6" fw={700}>{perf.wins ?? 0}</Text>-
                <Text span c="red.6" fw={700}>{perf.losses ?? 0}</Text>-
                <Text span fw={700}>{perf.ties ?? 0}</Text> in {selectedYear}.
              </Text>

              <Group gap="xs">
                <StatPill metric="auto" value={perf.auto_raw} />
                <StatPill metric="teleop" value={perf.teleop_raw} />
                <StatPill metric="endgame" value={perf.endgame_raw} />
                <StatPill metric="raw" value={perf.raw} />
                <StatPill metric="confidence" value={perf.confidence} />
                <StatPill metric="ace" value={perf.ace} />
              </Group>

              {eventTrend.rows.length > 0 ? (
                <Card withBorder padding="md" radius="md">
                  <Group justify="space-between" align="center" mb="sm" wrap="wrap">
                    <Text fw={600}>
                      Team {teamNumber} Event Performance in {selectedYear}
                    </Text>
                    {eventTrend.hasBreakdown ? (
                      <SegmentedControl
                        size="xs"
                        value={chartMode}
                        onChange={(v) => setChartMode(v as "trend" | "breakdown")}
                        data={[
                          { label: "ACE Trend", value: "trend" },
                          { label: "Breakdown", value: "breakdown" },
                        ]}
                      />
                    ) : null}
                  </Group>
                  {chartMode === "breakdown" && eventTrend.hasBreakdown ? (
                    <AreaChart
                      h={280}
                      data={eventTrend.breakdownRows}
                      dataKey="event"
                      type="stacked"
                      series={[
                        { name: "Auto", color: "#f59e0b" },
                        { name: "Teleop", color: "#3b82f6" },
                        { name: "Endgame", color: "#10b981" },
                      ]}
                      curveType="monotone"
                      withDots
                      withGradient
                      gridAxis="xy"
                      yAxisLabel="Points"
                      withLegend
                      tooltipProps={{
                        content: ({ payload }) => (
                          <EventTrendTooltip
                            payload={payload as Array<{ payload?: EventTrendRow }>}
                          />
                        ),
                      }}
                      areaChartProps={{
                        onClick: (state: { activePayload?: Array<{ payload?: EventTrendRow }> }) => {
                          const ek = state?.activePayload?.[0]?.payload?.eventKey;
                          if (ek) navigate(`/event/${ek}`);
                        },
                        style: { cursor: "pointer" },
                      }}
                    />
                  ) : (
                    <AreaChart
                      h={280}
                      data={eventTrend.rows}
                      dataKey="event"
                      series={[
                        { name: "Actual", color: "peeko.6" },
                        ...(eventTrend.hasPred
                          ? [{ name: "Pred", color: "#2196F3", strokeDasharray: "6 6" }]
                          : []),
                      ]}
                      curveType="monotone"
                      withDots
                      withGradient
                      connectNulls={false}
                      gridAxis="xy"
                      yAxisLabel="ACE"
                      withLegend={eventTrend.hasPred}
                      tooltipProps={{
                        content: ({ payload }) => (
                          <EventTrendTooltip
                            payload={payload as Array<{ payload?: EventTrendRow }>}
                          />
                        ),
                      }}
                      areaChartProps={{
                        onClick: (state: { activePayload?: Array<{ payload?: EventTrendRow }> }) => {
                          const ek = state?.activePayload?.[0]?.payload?.eventKey;
                          if (ek) navigate(`/event/${ek}`);
                        },
                        style: { cursor: "pointer" },
                      }}
                    />
                  )}
                </Card>
              ) : null}

              {teamEventKeys.length > 0 ? (
                <Stack gap="md">
                  <Title order={3} mt="sm">
                    Recent Events
                  </Title>
                  {teamEventKeys.map((ek) => {
                    const meta = eventMetaByKey.get(ek);
                    return (
                      <TeamEventBlock
                        key={ek}
                        eventKey={ek}
                        teamNumber={teamNumber}
                        year={selectedYear}
                        eventName={meta?.event_data.name}
                        weekLabel={eventWeekLabel(meta?.week)}
                        location={
                          meta
                            ? locationString(
                                meta.location_info.city,
                                meta.location_info.state_prov,
                                meta.location_info.country,
                              )
                            : undefined
                        }
                        perf={eventPerfByKey.get(ek)}
                        awards={awardsByEvent.get(ek)}
                      />
                    );
                  })}
                </Stack>
              ) : null}
            </Stack>
          ) : (
            <Text c="dimmed">No performance data for {selectedYear}.</Text>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="events" pt="md">
          {eventsQuery.isLoading ? (
            <Text size="sm" c="dimmed">Loading events...</Text>
          ) : teamEventKeys.length > 0 ? (
            <Stack gap="md">
              <Group justify="space-between" align="baseline">
                <Title order={3}>{selectedYear} Events</Title>
                <Text size="sm" c="dimmed">
                  {teamEventKeys.length} event{teamEventKeys.length === 1 ? "" : "s"}
                </Text>
              </Group>
              {teamEventKeys.map((ek) => {
                const meta = eventMetaByKey.get(ek);
                return (
                  <TeamEventBlock
                    key={ek}
                    eventKey={ek}
                    teamNumber={teamNumber}
                    year={selectedYear}
                    eventName={meta?.event_data.name}
                    weekLabel={eventWeekLabel(meta?.week)}
                    location={
                      meta
                        ? locationString(
                            meta.location_info.city,
                            meta.location_info.state_prov,
                            meta.location_info.country,
                          )
                        : undefined
                    }
                    perf={eventPerfByKey.get(ek)}
                    awards={awardsByEvent.get(ek)}
                  />
                );
              })}
            </Stack>
          ) : (
            <Card withBorder padding="md" radius="md">
              <Text size="sm" c="dimmed">No events for this season.</Text>
            </Card>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="awards" pt="md">
          <Stack gap="lg">
            <Card withBorder padding="md" radius="md">
              <Group justify="space-between" mb="sm">
                <Text fw={600}>{selectedYear} Awards</Text>
                {seasonAwards.length > 0 ? (
                  <Badge variant="light" size="sm" radius="sm">
                    {seasonAwards.length}
                  </Badge>
                ) : null}
              </Group>
              {awardsQuery.isLoading ? (
                <Text size="sm" c="dimmed">Loading awards...</Text>
              ) : seasonAwards.length > 0 ? (
                <Stack gap={6}>
                  {seasonAwards.map((a) => (
                    <Group
                      key={`${a.event_key}-${a.award_name}`}
                      gap="xs"
                      wrap="nowrap"
                    >
                      <Anchor component={Link} to={`/event/${a.event_key}`} size="sm">
                        {a.event_key}
                      </Anchor>
                      <Text size="sm">{a.award_name}</Text>
                      {isBlueBanner(a.award_name) ? (
                        <Badge color="blue" variant="light" size="sm" radius="sm">
                          Banner
                        </Badge>
                      ) : null}
                    </Group>
                  ))}
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">No awards for this season.</Text>
              )}
            </Card>
            <BlueBanners awards={seasonAwards} title={`${selectedYear} Blue Banners`} />
          </Stack>
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
