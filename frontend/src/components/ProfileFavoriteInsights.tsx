import { useMemo, type ReactNode } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import {
  Anchor,
  Badge,
  Box,
  Card,
  Group,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconCalendarEvent, IconMapPin, IconTrophy } from "@tabler/icons-react";
import { Link } from "react-router-dom";
import { apiGet } from "../api/client";
import { useMapTeams, useSearchIndex } from "../api/queries";
import { FavoriteButton } from "./FavoriteButton";
import { RecordCell } from "./RecordCell";
import { StatPill } from "./StatPill";
import { TeamAvatar } from "./TeamAvatar";
import { EmptyState } from "./StateWrappers";
import { CURRENT_YEAR } from "../lib/constants";
import {
  eventTypeLabel,
  eventWeekLabel,
  formatDateRange,
  formatNumber,
  locationString,
  ordinal,
  yearFromEventKey,
} from "../lib/format";
import { isPlayed } from "../lib/prediction";
import type {
  EventData,
  EventMatchResponse,
  EventResponse,
  MatchResponse,
  TeamPerfInfo,
  TeamPerfResponse,
} from "../types/api";

const COMP_LEVEL_ORDER: Record<string, number> = { qm: 0, ef: 1, qf: 2, sf: 3, f: 4 };

function matchLabel(m: MatchResponse): string {
  const lvl = m.comp_level.toUpperCase();
  if (m.comp_level === "qm") return `QM ${m.match_number}`;
  return `${lvl} ${m.set_number}-${m.match_number}`;
}

function pickSeasonPerf(perfs: TeamPerfInfo[] | undefined): TeamPerfInfo | undefined {
  if (!perfs || perfs.length === 0) return undefined;
  return perfs.find((p) => p.year === CURRENT_YEAR) ?? [...perfs].sort((a, b) => b.year - a.year)[0];
}

interface ProfileFavoriteInsightsProps {
  teamKeys: string[];
  eventKeys: string[];
  canRemove?: boolean;
}

export function ProfileFavoriteInsights({
  teamKeys,
  eventKeys,
  canRemove = false,
}: ProfileFavoriteInsightsProps) {
  const teams = useMemo(
    () => [...teamKeys].sort((a, b) => Number(a) - Number(b)).slice(0, 24),
    [teamKeys],
  );
  const events = useMemo(() => [...eventKeys].sort().slice(0, 24), [eventKeys]);
  const eventYears = useMemo(() => {
    const years = new Set<number>([CURRENT_YEAR]);
    for (const key of events) {
      const y = yearFromEventKey(key);
      if (y) years.add(y);
    }
    return [...years];
  }, [events]);

  const { data: index } = useSearchIndex();
  const mapTeams = useMapTeams(CURRENT_YEAR);

  const teamPerfQueries = useQueries({
    queries: teams.map((team) => ({
      queryKey: ["team-perfs", Number(team), "all"] as const,
      queryFn: () => apiGet<TeamPerfResponse>(`/team_perfs/${team}`),
      staleTime: 5 * 60 * 1000,
      enabled: Number(team) > 0,
    })),
  });

  const eventYearQueries = useQueries({
    queries: eventYears.map((year) => ({
      queryKey: ["events", year, {}] as const,
      queryFn: () => apiGet<EventResponse>(`/events/${year}`),
      staleTime: 5 * 60 * 1000,
    })),
  });

  const eventMetaByKey = useMemo(() => {
    const map = new Map<string, EventData>();
    for (const q of eventYearQueries) {
      for (const e of q.data?.events ?? []) map.set(e.event_key, e);
    }
    return map;
  }, [eventYearQueries]);

  const perfsByTeam = useMemo(() => {
    const map = new Map<number, TeamPerfInfo>();
    teamPerfQueries.forEach((q, i) => {
      const num = Number(teams[i]);
      const season = pickSeasonPerf(q.data?.team_perfs);
      if (season) map.set(num, season);
    });
    return map;
  }, [teamPerfQueries, teams]);

  const teamsAtEvent = useMemo(() => {
    const map = new Map<string, Array<{ team: number; ace: number | null }>>();
    teamPerfQueries.forEach((q, i) => {
      const team = Number(teams[i]);
      for (const perf of q.data?.team_perfs ?? []) {
        for (const ep of perf.event_perf ?? []) {
          if (!ep.event_key) continue;
          const arr = map.get(ep.event_key) ?? [];
          if (arr.some((r) => r.team === team)) continue;
          arr.push({ team, ace: typeof ep.ace === "number" ? ep.ace : null });
          map.set(ep.event_key, arr);
        }
      }
    });
    return map;
  }, [teamPerfQueries, teams]);

  const snapshot = useMemo(() => {
    const seasonPerfs = [...perfsByTeam.values()];
    let wins = 0;
    let losses = 0;
    let ties = 0;
    let bestAce: { team: number; ace: number } | null = null;
    let bestRank: { team: number; rank: number } | null = null;
    for (const [team, perf] of perfsByTeam) {
      wins += perf.wins ?? 0;
      losses += perf.losses ?? 0;
      ties += perf.ties ?? 0;
      if (typeof perf.ace === "number" && (!bestAce || perf.ace > bestAce.ace)) {
        bestAce = { team, ace: perf.ace };
      }
      if (typeof perf.rank_global === "number" && (!bestRank || perf.rank_global < bestRank.rank)) {
        bestRank = { team, rank: perf.rank_global };
      }
    }
    return { wins, losses, ties, bestAce, bestRank, loaded: seasonPerfs.length };
  }, [perfsByTeam]);

  const locByTeam = useMemo(() => {
    const map = new Map<number, string>();
    for (const t of mapTeams.data?.teams ?? []) {
      map.set(t.team_number, locationString(t.city ?? "", t.state_prov ?? "", t.country ?? ""));
    }
    return map;
  }, [mapTeams.data]);

  const teamsLoading = teamPerfQueries.some((q) => q.isLoading);

  return (
    <Stack gap="xl" id="profile-favorites">
      {teams.length > 0 || events.length > 0 ? (
        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
          <SnapshotStat label="Teams" value={String(teamKeys.length)} />
          <SnapshotStat label="Events" value={String(eventKeys.length)} />
          <SnapshotStat
            label="Season record"
            value={
              snapshot.loaded ? (
                <RecordCell wins={snapshot.wins} losses={snapshot.losses} ties={snapshot.ties} />
              ) : (
                "—"
              )
            }
          />
          <SnapshotStat
            label="Best ACE"
            value={
              snapshot.bestAce
                ? `${formatNumber(snapshot.bestAce.ace)}  ·  #${snapshot.bestAce.team}`
                : "—"
            }
          />
        </SimpleGrid>
      ) : null}

      <Box>
        <Group gap="xs" mb="md">
          <Title order={3}>Your Teams</Title>
          <Badge variant="light" size="sm">
            {teamKeys.length}
          </Badge>
        </Group>
        {teams.length === 0 ? (
          <Card withBorder radius="md" p="lg">
            <EmptyState>
              Star teams from the search below or the{" "}
              <Anchor component={Link} to="/teams" size="sm">
                leaderboard
              </Anchor>
              . Their ACE, record, and recent matches will land here.
            </EmptyState>
          </Card>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            {teams.map((key, i) => (
              <FavoriteTeamInsightCard
                key={key}
                teamNumber={Number(key)}
                nickname={index?.teams[key]?.nickname ?? ""}
                location={locByTeam.get(Number(key))}
                perf={perfsByTeam.get(Number(key))}
                loading={teamPerfQueries[i]?.isLoading ?? teamsLoading}
                eventMetaByKey={eventMetaByKey}
                canRemove={canRemove}
                showMatches={i < 6}
              />
            ))}
          </SimpleGrid>
        )}
      </Box>

      <Box>
        <Group gap="xs" mb="md">
          <Title order={3}>Your Events</Title>
          <Badge variant="light" size="sm">
            {eventKeys.length}
          </Badge>
        </Group>
        {events.length === 0 ? (
          <Card withBorder radius="md" p="lg">
            <EmptyState>
              Favorite events from search or the{" "}
              <Anchor component={Link} to="/events" size="sm">
                events page
              </Anchor>
              . Dates, location, and which of your teams competed will show up here.
            </EmptyState>
          </Card>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            {events.map((key) => (
              <FavoriteEventInsightCard
                key={key}
                eventKey={key}
                event={eventMetaByKey.get(key)}
                name={index?.events[key]}
                yourTeams={teamsAtEvent.get(key) ?? []}
                canRemove={canRemove}
              />
            ))}
          </SimpleGrid>
        )}
      </Box>
    </Stack>
  );
}

function SnapshotStat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Card withBorder radius="md" p="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={700} style={{ letterSpacing: 0.4 }}>
        {label}
      </Text>
      <Text fw={800} fz={22} mt={4} style={{ fontVariantNumeric: "tabular-nums" }}>
        {value}
      </Text>
    </Card>
  );
}

function FavoriteTeamInsightCard({
  teamNumber,
  nickname,
  location,
  perf,
  loading,
  eventMetaByKey,
  canRemove,
  showMatches,
}: {
  teamNumber: number;
  nickname: string;
  location?: string;
  perf?: TeamPerfInfo;
  loading: boolean;
  eventMetaByKey: Map<string, EventData>;
  canRemove?: boolean;
  showMatches?: boolean;
}) {
  const year = perf?.year ?? CURRENT_YEAR;
  const recentEvents = useMemo(() => {
    const entries = [...(perf?.event_perf ?? [])].filter((e) => e.event_key);
    return entries
      .sort((a, b) => {
        const da =
          eventMetaByKey.get(String(a.event_key))?.event_data.start_date ?? String(a.event_key);
        const db =
          eventMetaByKey.get(String(b.event_key))?.event_data.start_date ?? String(b.event_key);
        return db.localeCompare(da);
      })
      .slice(0, 3);
  }, [perf, eventMetaByKey]);
  const latest = recentEvents[0];

  return (
    <Card withBorder radius="md" p="md" className="hover-lift profile-insight-card">
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb="sm">
        <Anchor
          component={Link}
          to={`/team/${teamNumber}/${year}`}
          underline="never"
          c="inherit"
          style={{ minWidth: 0, flex: 1 }}
        >
          <Group gap="sm" wrap="nowrap">
            <TeamAvatar teamNumber={teamNumber} size={52} radius={10} bordered />
            <Stack gap={2} style={{ minWidth: 0 }}>
              <Text fw={800} fz="lg" lh={1.15}>
                {teamNumber}
                {nickname ? (
                  <Text span fw={600} fz="md" c="dimmed">
                    {"  "}
                    {nickname}
                  </Text>
                ) : null}
              </Text>
              {location ? (
                <Group gap={4} wrap="nowrap">
                  <IconMapPin size={12} opacity={0.7} />
                  <Text size="xs" c="dimmed" lineClamp={1}>
                    {location}
                  </Text>
                </Group>
              ) : null}
            </Stack>
          </Group>
        </Anchor>
        {canRemove ? <FavoriteButton itemType="team" itemKey={teamNumber} /> : null}
      </Group>

      {loading ? (
        <Stack gap="xs">
          <Skeleton height={28} radius="sm" />
          <Skeleton height={22} radius="sm" />
        </Stack>
      ) : perf ? (
        <Stack gap="sm">
          <Group gap="lg" wrap="wrap">
            <Stack gap={0}>
              <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                ACE
              </Text>
              <Text fw={800} fz={24} lh={1.1} style={{ fontVariantNumeric: "tabular-nums" }}>
                {formatNumber(perf.ace)}
              </Text>
            </Stack>
            <Stack gap={0}>
              <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                {year} Record
              </Text>
              <Text fw={800} fz={24} lh={1.1}>
                <RecordCell wins={perf.wins} losses={perf.losses} ties={perf.ties} />
              </Text>
            </Stack>
            {perf.rank_global != null ? (
              <Stack gap={0}>
                <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                  Global
                </Text>
                <Text fw={800} fz={24} lh={1.1} c="blue.4">
                  {ordinal(perf.rank_global)}
                </Text>
              </Stack>
            ) : null}
          </Group>

          <Group gap={6}>
            <StatPill metric="auto" value={perf.auto_raw} size="sm" />
            <StatPill metric="teleop" value={perf.teleop_raw} size="sm" />
            <StatPill metric="endgame" value={perf.endgame_raw} size="sm" />
          </Group>

          {recentEvents.length > 0 ? (
            <Stack gap={6}>
              <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                Recent events
              </Text>
              {recentEvents.map((ep) => {
                const key = String(ep.event_key);
                const meta = eventMetaByKey.get(key);
                const name = meta?.event_data.name ?? key;
                return (
                  <Group key={key} justify="space-between" wrap="nowrap" gap="xs">
                    <Anchor component={Link} to={`/event/${key}`} size="sm" lineClamp={1} style={{ minWidth: 0 }}>
                      {name}
                    </Anchor>
                    <Text size="sm" fw={700} style={{ fontVariantNumeric: "tabular-nums" }}>
                      {formatNumber(typeof ep.ace === "number" ? ep.ace : null)}
                    </Text>
                  </Group>
                );
              })}
            </Stack>
          ) : null}

          {showMatches && latest?.event_key ? (
            <TeamRecentMatches eventKey={String(latest.event_key)} teamNumber={teamNumber} />
          ) : null}
        </Stack>
      ) : (
        <Text size="sm" c="dimmed">
          No {CURRENT_YEAR} performance yet.
        </Text>
      )}
    </Card>
  );
}

function TeamRecentMatches({ eventKey, teamNumber }: { eventKey: string; teamNumber: number }) {
  const query = useQuery({
    queryKey: ["event-matches", eventKey, {}],
    queryFn: () => apiGet<EventMatchResponse>(`/event/${eventKey}/matches`),
    staleTime: 5 * 60 * 1000,
    enabled: Boolean(eventKey),
  });

  const rows = useMemo(() => {
    const matches = [...(query.data?.matches ?? [])]
      .filter((m) => m.red_teams.includes(teamNumber) || m.blue_teams.includes(teamNumber))
      .filter(isPlayed)
      .sort((a, b) => {
        const lvl = (COMP_LEVEL_ORDER[a.comp_level] ?? 9) - (COMP_LEVEL_ORDER[b.comp_level] ?? 9);
        if (lvl !== 0) return lvl;
        if (a.set_number !== b.set_number) return a.set_number - b.set_number;
        return a.match_number - b.match_number;
      });
    return matches.slice(-4).reverse();
  }, [query.data, teamNumber]);

  if (query.isLoading || rows.length === 0) return null;

  return (
    <Stack gap={4}>
      <Text size="xs" c="dimmed" fw={700} tt="uppercase">
        Latest matches
      </Text>
      {rows.map((m) => {
        const isRed = m.red_teams.includes(teamNumber);
        const won =
          (isRed && m.winning_alliance === "red") || (!isRed && m.winning_alliance === "blue");
        const tie = m.winning_alliance !== "red" && m.winning_alliance !== "blue";
        const us = isRed ? m.red_score : m.blue_score;
        const them = isRed ? m.blue_score : m.red_score;
        return (
          <Group key={m.match_key} justify="space-between" wrap="nowrap" gap="xs">
            <Anchor component={Link} to={`/match/${eventKey}/${m.match_key}`} size="sm" c="dimmed">
              {matchLabel(m)}
            </Anchor>
            <Group gap={8} wrap="nowrap">
              <Text size="sm" fw={700} style={{ fontVariantNumeric: "tabular-nums" }}>
                {us}–{them}
              </Text>
              <Badge size="xs" color={tie ? "gray" : won ? "green" : "red"} variant="light">
                {tie ? "T" : won ? "W" : "L"}
              </Badge>
            </Group>
          </Group>
        );
      })}
    </Stack>
  );
}

function FavoriteEventInsightCard({
  eventKey,
  event,
  name,
  yourTeams,
  canRemove,
}: {
  eventKey: string;
  event?: EventData;
  name?: string;
  yourTeams: Array<{ team: number; ace: number | null }>;
  canRemove?: boolean;
}) {
  const year = yearFromEventKey(eventKey);
  const title = event?.event_data.name ?? name ?? eventKey;
  const loc = event
    ? locationString(
        event.location_info.city,
        event.location_info.state_prov,
        event.location_info.country,
      )
    : "";
  const dates = event ? formatDateRange(event.event_data.start_date, event.event_data.end_date) : "";
  const week = eventWeekLabel(event?.week);
  const type = eventTypeLabel(event?.event_data.event_type);
  const today = new Date().toISOString().slice(0, 10);
  const start = event?.event_data.start_date?.slice(0, 10) ?? "";
  const end = event?.event_data.end_date?.slice(0, 10) ?? "";
  const status =
    start && start > today ? "Upcoming" : end && end < today ? "Completed" : start ? "This week" : null;

  return (
    <Card withBorder radius="md" p="md" className="hover-lift profile-insight-card">
      <Group justify="space-between" align="flex-start" wrap="nowrap" mb="xs">
        <Anchor
          component={Link}
          to={`/event/${eventKey}`}
          underline="never"
          c="inherit"
          style={{ minWidth: 0, flex: 1 }}
        >
          <Group gap="sm" wrap="nowrap" align="flex-start">
            <Box
              style={{
                width: 44,
                height: 44,
                borderRadius: 10,
                background: "var(--mantine-color-yellow-light)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <IconCalendarEvent size={22} />
            </Box>
            <Stack gap={4} style={{ minWidth: 0 }}>
              <Text fw={800} lh={1.2} lineClamp={2}>
                {year ? `${year} ` : ""}
                {title}
              </Text>
              <Group gap={6}>
                {week ? (
                  <Badge size="xs" variant="light">
                    {week}
                  </Badge>
                ) : null}
                {type ? (
                  <Badge size="xs" variant="outline" color="gray">
                    {type}
                  </Badge>
                ) : null}
                {status ? (
                  <Badge size="xs" color={status === "Upcoming" ? "blue" : status === "This week" ? "green" : "gray"}>
                    {status}
                  </Badge>
                ) : null}
              </Group>
            </Stack>
          </Group>
        </Anchor>
        {canRemove ? <FavoriteButton itemType="event" itemKey={eventKey} /> : null}
      </Group>

      <Stack gap={6} mt="sm">
        {dates ? (
          <Text size="sm" c="dimmed">
            {dates}
          </Text>
        ) : (
          <Text size="sm" c="dimmed">
            {eventKey}
          </Text>
        )}
        {loc ? (
          <Group gap={4} wrap="nowrap">
            <IconMapPin size={12} opacity={0.7} />
            <Text size="sm" c="dimmed" lineClamp={1}>
              {loc}
            </Text>
          </Group>
        ) : null}

        {yourTeams.length > 0 ? (
          <Stack gap={4} mt={4}>
            <Group gap={4}>
              <IconTrophy size={12} opacity={0.7} />
              <Text size="xs" c="dimmed" fw={700} tt="uppercase">
                Your teams here
              </Text>
            </Group>
            {yourTeams.map((row) => (
              <Group key={row.team} justify="space-between" wrap="nowrap">
                <Anchor component={Link} to={`/team/${row.team}/${year ?? CURRENT_YEAR}`} size="sm">
                  Team {row.team}
                </Anchor>
                <Text size="sm" fw={700} style={{ fontVariantNumeric: "tabular-nums" }}>
                  ACE {formatNumber(row.ace)}
                </Text>
              </Group>
            ))}
          </Stack>
        ) : (
          <Text size="sm" c="dimmed">
            None of your favorite teams have results here yet.
          </Text>
        )}
      </Stack>
    </Card>
  );
}
