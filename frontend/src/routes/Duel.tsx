import { useEffect, useMemo } from "react";
import {
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Progress,
  RingProgress,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { BarChart } from "@mantine/charts";
import { IconArrowsExchange, IconUsers, IconSwords } from "@tabler/icons-react";
import { Link, useSearchParams } from "react-router-dom";
import { useH2H, useSearchIndex } from "../api/queries";
import { GameHero } from "../components/games/GameHero";
import { TeamPicker } from "../components/games/TeamPicker";
import { DataTable, type Column } from "../components/DataTable";
import { ErrorState, LoadingState, EmptyState } from "../components/StateWrappers";
import { TeamAvatar } from "../components/TeamAvatar";
import { RecordCell } from "../components/RecordCell";
import { availableYears, CURRENT_YEAR } from "../lib/constants";
import { eventWeekLabel, formatNumber, locationString, shortMatchLabel } from "../lib/format";
import type { H2HMatch, H2HTeamInfo } from "../types/api";

const CLASSICS: Array<[number, number, string]> = [
  [254, 1678, "Cheesy Poofs vs Citrus"],
  [1114, 2056, "Simbotics vs OP"],
  [118, 148, "Robonauts vs Robowranglers"],
  [33, 67, "Killer Bees vs HOT"],
  [359, 4414, "Hawaiian Kids vs HighTide"],
  [1678, 4414, "Citrus vs HighTide"],
];

function teamGradient(team: H2HTeamInfo, fallback: string) {
  const colors = team.team_colors as { primary?: string; secondary?: string } | null | undefined;
  const p = typeof colors?.primary === "string" ? colors.primary : null;
  const s = typeof colors?.secondary === "string" ? colors.secondary : null;
  if (p && s) return `linear-gradient(160deg, ${p}, ${s})`;
  return fallback;
}

function pctLabel(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

function DuelTeamCard({ team, year, side }: { team: H2HTeamInfo; year?: number | null; side: "a" | "b" }) {
  const fallback = side === "a" ? "linear-gradient(160deg, #7a0000, #1a1a1a)" : "linear-gradient(160deg, #003366, #1a1a1a)";
  const bg = teamGradient(team, fallback);
  const loc = locationString(team.city, team.state_prov, team.country);
  return (
    <Card radius="lg" p="lg" style={{ background: bg, color: "#fff", border: "none", height: "100%" }}>
      <Group wrap="nowrap" align="flex-start" justify="space-between">
        <Stack gap={4} style={{ minWidth: 0 }}>
          <Text fw={800} fz={28} lh={1} c="#fff">
            {team.team_number}
          </Text>
          <Text fw={700} lineClamp={2} c="#fff">
            {team.nickname}
          </Text>
          {loc ? (
            <Text size="sm" style={{ color: "rgba(255,255,255,0.78)" }}>
              {loc}
            </Text>
          ) : null}
          <Group gap={6} mt={6}>
            {typeof team.ace === "number" ? (
              <Badge variant="filled" color="violet" style={{ textTransform: "none" }}>
                ACE {formatNumber(team.ace, 1)}
              </Badge>
            ) : null}
            {team.rank_global ? (
              <Badge variant="filled" color="dark" style={{ textTransform: "none" }}>
                #{team.rank_global}
              </Badge>
            ) : null}
            {team.wins != null ? <RecordCell wins={team.wins} losses={team.losses} ties={team.ties} /> : null}
          </Group>
          <Button
            component={Link}
            to={`/team/${team.team_number}${year ? `/${year}` : ""}`}
            size="xs"
            variant="white"
            color="dark"
            mt={8}
            w="fit-content"
          >
            Team page
          </Button>
        </Stack>
        <TeamAvatar teamNumber={team.team_number} size={88} radius={12} bordered upscale />
      </Group>
    </Card>
  );
}

function StatRing({
  label,
  value,
  color,
  caption,
}: {
  label: string;
  value: number | null | undefined;
  color: string;
  caption: string;
}) {
  const pct = value != null ? Math.round(value * 100) : 0;
  return (
    <Card withBorder radius="md" p="md" ta="center">
      <RingProgress
        size={128}
        thickness={12}
        roundCaps
        mx="auto"
        sections={value != null ? [{ value: pct, color }] : []}
        label={
          <Text fw={800} ta="center" fz="lg">
            {pctLabel(value)}
          </Text>
        }
      />
      <Text fw={700} mt="xs">
        {label}
      </Text>
      <Text size="sm" c="dimmed">
        {caption}
      </Text>
    </Card>
  );
}

export function Duel() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: index } = useSearchIndex();
  const teamA = Number(searchParams.get("a")) || 0;
  const teamB = Number(searchParams.get("b")) || 0;
  const yearParam = searchParams.get("year");
  const year = yearParam === "all" || !yearParam ? null : Number(yearParam) || CURRENT_YEAR;
  const tab = searchParams.get("tab") === "against" ? "against" : "together";

  const setParam = (updates: Record<string, string | null>) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(updates)) {
          if (v === null || v === "") next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace: true },
    );
  };

  const h2h = useH2H(teamA, teamB, year, { enabled: teamA > 0 && teamB > 0 && teamA !== teamB });

  useEffect(() => {
    document.title = teamA && teamB ? `${teamA} vs ${teamB} Duel - Peekorobo` : "Duel - Peekorobo";
  }, [teamA, teamB]);

  const matches = useMemo(() => {
    const all = h2h.data?.matches ?? [];
    return all.filter((m) => m.relation === tab);
  }, [h2h.data, tab]);

  const columns = useMemo<Column<H2HMatch>[]>(
    () => [
      {
        key: "year",
        header: "Year",
        width: 70,
        sortValue: (m) => m.year,
        render: (m) => m.year,
      },
      {
        key: "event",
        header: "Event",
        sortValue: (m) => m.event_name || m.event_key,
        render: (m) => (
          <Stack gap={0}>
            <Anchor size="sm" component={Link} to={`/event/${m.event_key}`} fw={600}>
              {m.event_name || m.event_key}
            </Anchor>
            <Text size="xs" c="dimmed">
              {eventWeekLabel(m.week) ?? ""}
            </Text>
          </Stack>
        ),
      },
      {
        key: "match",
        header: "Match",
        width: 90,
        sortValue: (m) => `${m.comp_level}-${m.set_number}-${m.match_number}`,
        render: (m) => (
          <Anchor
            size="sm"
            fw={600}
            component={Link}
            to={`/match/${m.event_key}/${m.match_key}`}
          >
            {shortMatchLabel(m.comp_level, m.set_number, m.match_number)}
          </Anchor>
        ),
      },
      {
        key: "red",
        header: "Red",
        render: (m) => (
          <Group gap={4} wrap="wrap">
            {m.red_teams.map((t) => (
              <Badge
                key={t}
                variant={t === teamA || t === teamB ? "filled" : "light"}
                color="red"
                style={{ textTransform: "none" }}
                leftSection={<TeamAvatar teamNumber={t} size={14} radius={3} />}
              >
                {t}
              </Badge>
            ))}
          </Group>
        ),
        exportValue: (m) => m.red_teams.join(" "),
      },
      {
        key: "blue",
        header: "Blue",
        render: (m) => (
          <Group gap={4} wrap="wrap">
            {m.blue_teams.map((t) => (
              <Badge
                key={t}
                variant={t === teamA || t === teamB ? "filled" : "light"}
                color="blue"
                style={{ textTransform: "none" }}
                leftSection={<TeamAvatar teamNumber={t} size={14} radius={3} />}
              >
                {t}
              </Badge>
            ))}
          </Group>
        ),
        exportValue: (m) => m.blue_teams.join(" "),
      },
      {
        key: "score",
        header: "Score",
        width: 100,
        sortValue: (m) => m.red_score + m.blue_score,
        render: (m) => (
          <Text size="sm" fw={700} style={{ fontVariantNumeric: "tabular-nums" }}>
            <Text span c={m.winning_alliance === "red" ? "red" : undefined} fw={m.winning_alliance === "red" ? 800 : 500}>
              {m.red_score}
            </Text>
            {" – "}
            <Text span c={m.winning_alliance === "blue" ? "blue" : undefined} fw={m.winning_alliance === "blue" ? 800 : 500}>
              {m.blue_score}
            </Text>
          </Text>
        ),
      },
      {
        key: "result",
        header: tab === "together" ? "Alliance" : "Winner",
        width: 110,
        sortValue: (m) => (tab === "together" ? m.a_alliance : m.winning_alliance),
        render: (m) =>
          tab === "together" ? (
            <Badge color={m.a_alliance === "red" ? "red" : "blue"} variant="filled" style={{ textTransform: "none" }}>
              {m.a_alliance === "red" ? "Red" : "Blue"}
              {m.winning_alliance === m.a_alliance ? " W" : m.winning_alliance ? " L" : ""}
            </Badge>
          ) : (
            <Badge
              color={m.winning_alliance === m.a_alliance ? "green" : m.winning_alliance === m.b_alliance ? "red" : "gray"}
              variant="filled"
              style={{ textTransform: "none" }}
            >
              {m.winning_alliance === m.a_alliance
                ? `${teamA} win`
                : m.winning_alliance === m.b_alliance
                  ? `${teamB} win`
                  : "Tie"}
            </Badge>
          ),
      },
    ],
    [tab, teamA, teamB],
  );

  const yearChart = (h2h.data?.by_year ?? [])
    .slice()
    .reverse()
    .map((s) => ({
      year: String(s.year),
      Together: s.together,
      Against: s.against,
    }));

  const againstDecided = (h2h.data?.against.a_wins ?? 0) + (h2h.data?.against.b_wins ?? 0) + (h2h.data?.against.ties ?? 0);
  const aShare = againstDecided ? ((h2h.data?.against.a_wins ?? 0) / againstDecided) * 100 : 0;
  const bShare = againstDecided ? ((h2h.data?.against.b_wins ?? 0) / againstDecided) * 100 : 0;
  const tShare = againstDecided ? ((h2h.data?.against.ties ?? 0) / againstDecided) * 100 : 0;

  return (
    <Stack gap="md" py="md">
      <GameHero
        title="Duel"
        subtitle="How two teams play with each other — and against each other — across every shared event."
        year={year ?? undefined}
      />

      <Card withBorder padding="sm" radius="md">
        <Group gap="sm" align="flex-end" wrap="wrap">
          <TeamPicker
            label="Team A"
            value={teamA || null}
            onChange={(n) => setParam({ a: n ? String(n) : null })}
            exclude={teamB ? [teamB] : []}
          />
          <Button
            variant="default"
            mb={2}
            leftSection={<IconArrowsExchange size={16} />}
            onClick={() => {
              if (teamA && teamB) setParam({ a: String(teamB), b: String(teamA) });
            }}
            disabled={!teamA || !teamB}
          >
            Swap
          </Button>
          <TeamPicker
            label="Team B"
            value={teamB || null}
            onChange={(n) => setParam({ b: n ? String(n) : null })}
            exclude={teamA ? [teamA] : []}
          />
          <Select
            label="Season"
            value={year == null ? "all" : String(year)}
            data={[{ value: "all", label: "All seasons" }, ...availableYears().map((y) => ({ value: String(y), label: String(y) }))]}
            onChange={(val) => setParam({ year: val === "all" || !val ? "all" : val })}
            allowDeselect={false}
            w={150}
          />
        </Group>
        <Group gap="xs" mt="sm" wrap="wrap">
          <Text size="xs" c="dimmed">
            Classics:
          </Text>
          {CLASSICS.map(([a, b, label]) => (
            <Badge
              key={`${a}-${b}`}
              variant="light"
              style={{ cursor: "pointer", textTransform: "none" }}
              onClick={() => setParam({ a: String(a), b: String(b) })}
            >
              {label}
            </Badge>
          ))}
        </Group>
      </Card>

      {!teamA || !teamB || teamA === teamB ? (
        <EmptyState>Pick two different teams to open the duel.</EmptyState>
      ) : h2h.isLoading ? (
        <LoadingState label="Loading head-to-head..." />
      ) : h2h.error ? (
        <ErrorState error={h2h.error} />
      ) : h2h.data ? (
        <>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            <DuelTeamCard team={h2h.data.team_a} year={year} side="a" />
            <DuelTeamCard team={h2h.data.team_b} year={year} side="b" />
          </SimpleGrid>

          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
            <StatRing
              label="Together"
              value={h2h.data.together.win_pct}
              color="green"
              caption={`${h2h.data.together.wins}-${h2h.data.together.losses}${h2h.data.together.ties ? `-${h2h.data.together.ties}` : ""} in ${h2h.data.together.matches} matches as partners`}
            />
            <StatRing
              label={`${h2h.data.team_a.team_number} vs ${h2h.data.team_b.team_number}`}
              value={h2h.data.against.a_win_pct}
              color="red"
              caption={`${h2h.data.against.a_wins}–${h2h.data.against.b_wins} in ${h2h.data.against.matches} matches as opponents`}
            />
            <Card withBorder radius="md" p="md" ta="center">
              <Title order={2} mt={18}>
                {h2h.data.events_shared}
              </Title>
              <Text fw={700} mt="sm">
                Shared events
              </Text>
              <Text size="sm" c="dimmed">
                {h2h.data.together.matches + h2h.data.against.matches} matches on the same field
              </Text>
              {h2h.data.together.avg_margin != null ? (
                <Text size="sm" mt="xs">
                  Partner margin {formatNumber(h2h.data.together.avg_margin, 1)}
                </Text>
              ) : null}
              {h2h.data.against.avg_margin != null ? (
                <Text size="sm">
                  H2H margin {formatNumber(h2h.data.against.avg_margin, 1)} for {teamA}
                </Text>
              ) : null}
            </Card>
          </SimpleGrid>

          {againstDecided > 0 ? (
            <Card withBorder radius="md" p="md">
              <Text fw={700} mb="xs">
                Head-to-head split
              </Text>
              <Progress.Root size={22} radius="xl">
                <Progress.Section value={aShare} color="red">
                  <Progress.Label>
                    {teamA} {h2h.data.against.a_wins}
                  </Progress.Label>
                </Progress.Section>
                {tShare > 0 ? (
                  <Progress.Section value={tShare} color="gray">
                    <Progress.Label>Ties</Progress.Label>
                  </Progress.Section>
                ) : null}
                <Progress.Section value={bShare} color="blue">
                  <Progress.Label>
                    {teamB} {h2h.data.against.b_wins}
                  </Progress.Label>
                </Progress.Section>
              </Progress.Root>
              <Group justify="space-between" mt="xs">
                <Text size="sm">
                  Avg score {formatNumber(h2h.data.against.avg_a_score, 0)} – {formatNumber(h2h.data.against.avg_b_score, 0)}
                </Text>
                <Text size="sm" c="dimmed">
                  {index?.teams[String(teamA)]?.nickname} vs {index?.teams[String(teamB)]?.nickname}
                </Text>
              </Group>
            </Card>
          ) : null}

          {yearChart.length > 1 ? (
            <Card withBorder radius="md" p="md">
              <Text fw={700} mb="sm">
                Matches by season
              </Text>
              <BarChart
                h={220}
                data={yearChart}
                dataKey="year"
                series={[
                  { name: "Together", color: "green.6" },
                  { name: "Against", color: "red.6" },
                ]}
                withLegend
              />
            </Card>
          ) : null}

          <SegmentedControl
            value={tab}
            onChange={(v) => setParam({ tab: v })}
            data={[
              {
                value: "together",
                label: (
                  <Group gap={6} wrap="nowrap">
                    <IconUsers size={14} />
                    Together ({h2h.data.together.matches})
                  </Group>
                ),
              },
              {
                value: "against",
                label: (
                  <Group gap={6} wrap="nowrap">
                    <IconSwords size={14} />
                    Against ({h2h.data.against.matches})
                  </Group>
                ),
              },
            ]}
          />

          {matches.length === 0 ? (
            <EmptyState>
              {h2h.data.events_shared === 0
                ? "These teams have never been at the same event in this range."
                : tab === "together"
                  ? "No matches as alliance partners."
                  : "No matches as opponents."}
            </EmptyState>
          ) : (
            <DataTable
              data={matches}
              columns={columns}
              getRowKey={(m) => m.match_key}
              exportFileName={`duel-${teamA}-${teamB}-${tab}`}
              rowStyle={(m) => {
                if (tab === "together") {
                  return m.winning_alliance === m.a_alliance
                    ? { background: "rgba(76,175,80,0.08)" }
                    : m.winning_alliance
                      ? { background: "rgba(244,67,54,0.06)" }
                      : undefined;
                }
                const aWon = m.winning_alliance === m.a_alliance;
                const bWon = m.winning_alliance === m.b_alliance;
                if (aWon) return { background: "rgba(237,28,36,0.08)" };
                if (bWon) return { background: "rgba(0,102,179,0.08)" };
                return undefined;
              }}
            />
          )}
        </>
      ) : null}
    </Stack>
  );
}
