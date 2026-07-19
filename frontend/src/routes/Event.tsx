import { useEffect, useMemo, useState } from "react";
import {
  Anchor,
  Badge,
  Box,
  Card,
  Group,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { IconTrophy } from "@tabler/icons-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  useEvent,
  useEventAwards,
  useEventMatches,
  useEventPerfs,
  useEventRankings,
  useEventTeams,
  useLeaderboard,
  useSearchIndex,
} from "../api/queries";
import { ErrorState, LoadingState, EmptyState } from "../components/StateWrappers";
import { AceBadge } from "../components/AceBadge";
import { TeamName } from "../components/TeamName";
import { TeamAvatar } from "../components/TeamAvatar";
import { FavoriteButton } from "../components/FavoriteButton";
import { MetricCell, ConfidenceCell } from "../components/MetricCell";
import { AceLegend } from "../components/AceLegend";
import { DataTable, type Column } from "../components/DataTable";
import type {
  EventPerfInfo,
  EventTeamEntry,
  MatchResponse,
  TeamRankingInfo,
} from "../types/api";
import { gameLogo } from "../lib/assets";
import { computePercentiles, median } from "../lib/epa";
import {
  isPlayed,
  matchInsights,
  predictionAccuracy,
  predictionColor,
} from "../lib/prediction";
import {
  eventTypeLabel,
  eventWeekLabel,
  formatDateRange,
  formatNumber,
  locationString,
  yearFromEventKey,
} from "../lib/format";

const COMP_LEVEL_ORDER: Record<string, number> = { qm: 0, ef: 1, qf: 2, sf: 3, f: 4 };

const RED_TINT = "rgba(220,53,69,0.12)";
const BLUE_TINT = "rgba(13,110,253,0.12)";

function matchOrderKey(m: MatchResponse): number {
  return (COMP_LEVEL_ORDER[m.comp_level] ?? 9) * 1_000_000 + m.set_number * 1000 + m.match_number;
}

function MatchesTable({
  eventKey,
  title,
  matches,
}: {
  eventKey: string;
  title: string;
  matches: MatchResponse[];
}) {
  const acc = predictionAccuracy(matches);
  const matchYear = yearFromEventKey(eventKey) ?? undefined;

  const columns = useMemo<Column<MatchResponse>[]>(
    () => [
      {
        key: "video",
        header: "Video",
        width: 44,
        render: (m) =>
          m.youtube_key ? (
            <Anchor
              href={`https://www.youtube.com/watch?v=${m.youtube_key}`}
              target="_blank"
              rel="noopener noreferrer"
              title="Watch on YouTube"
            >
              ▶
            </Anchor>
          ) : (
            <Text c="dimmed" span>
              –
            </Text>
          ),
      },
      {
        key: "match",
        header: "Match",
        width: 90,
        sortValue: (m) => matchOrderKey(m),
        exportValue: (m) => matchLabel(m),
        render: (m) => (
          <Anchor component={Link} to={`/match/${eventKey}/${m.match_key}`} size="sm">
            {m.comp_level.toUpperCase()}
            {m.comp_level !== "qm" ? `${m.set_number}-` : " "}
            {m.match_number}
          </Anchor>
        ),
      },
      {
        key: "red",
        header: "Red Alliance",
        cellStyle: () => ({ backgroundColor: RED_TINT }),
        exportValue: (m) => m.red_teams.join(" "),
        render: (m) => (
          <Group gap={8}>
            {m.red_teams.map((t) => (
              <TeamName key={t} teamNumber={t} year={matchYear} numberOnly />
            ))}
          </Group>
        ),
      },
      {
        key: "blue",
        header: "Blue Alliance",
        cellStyle: () => ({ backgroundColor: BLUE_TINT }),
        exportValue: (m) => m.blue_teams.join(" "),
        render: (m) => (
          <Group gap={8}>
            {m.blue_teams.map((t) => (
              <TeamName key={t} teamNumber={t} year={matchYear} numberOnly />
            ))}
          </Group>
        ),
      },
      {
        key: "score",
        header: "Score",
        width: 100,
        sortValue: (m) => (isPlayed(m) ? Math.max(m.red_score, m.blue_score) : -1),
        render: (m) => {
          if (!isPlayed(m))
            return (
              <Text c="dimmed" span>
                TBD
              </Text>
            );
          const redWin = m.winning_alliance === "red";
          const blueWin = m.winning_alliance === "blue";
          return (
            <>
              <Text fw={redWin ? 700 : 400} c={redWin ? "red" : undefined} span>
                {m.red_score}
              </Text>
              {" - "}
              <Text fw={blueWin ? 700 : 400} c={blueWin ? "blue" : undefined} span>
                {m.blue_score}
              </Text>
            </>
          );
        },
      },
      {
        key: "winner",
        header: "Winner",
        width: 80,
        sortValue: (m) => m.winning_alliance || "",
        render: (m) => {
          if (!isPlayed(m))
            return (
              <Text c="dimmed" span>
                –
              </Text>
            );
          const redWin = m.winning_alliance === "red";
          const blueWin = m.winning_alliance === "blue";
          return (
            <Text fw={600} c={redWin ? "red" : blueWin ? "blue" : "dimmed"} span>
              {redWin ? "Red" : blueWin ? "Blue" : "Tie"}
            </Text>
          );
        },
      },
      {
        key: "redpct",
        header: "Red %",
        width: 70,
        sortValue: (m) => m.red_win_prob ?? null,
        cellStyle: (m) => {
          const c = predictionColor(m.red_win_prob);
          return c ? { backgroundColor: c, fontWeight: 600 } : undefined;
        },
        render: (m) =>
          m.red_win_prob !== null && m.red_win_prob !== undefined
            ? `${Math.round(m.red_win_prob * 100)}%`
            : "–",
      },
      {
        key: "bluepct",
        header: "Blue %",
        width: 70,
        sortValue: (m) => {
          const bp =
            m.blue_win_prob ??
            (m.red_win_prob !== null && m.red_win_prob !== undefined ? 1 - m.red_win_prob : null);
          return bp;
        },
        cellStyle: (m) => {
          const bp =
            m.blue_win_prob ??
            (m.red_win_prob !== null && m.red_win_prob !== undefined ? 1 - m.red_win_prob : null);
          const c = predictionColor(bp);
          return c ? { backgroundColor: c, fontWeight: 600 } : undefined;
        },
        render: (m) => {
          const bp =
            m.blue_win_prob ??
            (m.red_win_prob !== null && m.red_win_prob !== undefined ? 1 - m.red_win_prob : null);
          return bp !== null && bp !== undefined ? `${Math.round(bp * 100)}%` : "–";
        },
      },
    ],
    [eventKey, matchYear],
  );

  return (
    <Stack gap="xs">
      <Group justify="space-between" align="center">
        <Text fw={700}>{title}</Text>
        {acc.pct !== null ? (
          <Badge variant="light" color="grape">
            Prediction Accuracy: {acc.correct}/{acc.total} ({acc.pct.toFixed(0)}%)
          </Badge>
        ) : null}
      </Group>
      <DataTable
        data={matches}
        columns={columns}
        getRowKey={(m) => m.match_key}
        initialSort={{ key: "match", dir: "asc" }}
        minWidth={760}
        defaultPageSize={25}
        exportFileName={`${eventKey}-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
      />
    </Stack>
  );
}

function InsightStat({ label, value }: { label: string; value: string }) {
  return (
    <Stack gap={0}>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={700}>{value}</Text>
    </Stack>
  );
}

const PLAYOFF_LEVEL_LABEL: Record<string, string> = { ef: "EF", qf: "QF", sf: "SF", f: "F" };

function matchLabel(m: MatchResponse): string {
  if (m.comp_level === "f") return `Finals ${m.match_number}`;
  return `${PLAYOFF_LEVEL_LABEL[m.comp_level] ?? m.comp_level.toUpperCase()} ${m.set_number}`;
}

interface BracketColumn {
  label: string;
  matches: MatchResponse[];
}

/**
 * Groups playoff matches into bracket columns. Uses the 2023+ 8-alliance
 * double-elimination round layout when detected (13 sf sets), otherwise falls
 * back to grouping by competition level.
 */
function playoffColumns(playoff: MatchResponse[]): BracketColumn[] {
  const bySet = (a: MatchResponse, b: MatchResponse) =>
    a.set_number - b.set_number || a.match_number - b.match_number;
  const sf = playoff.filter((m) => m.comp_level === "sf").sort(bySet);
  const qf = playoff.filter((m) => m.comp_level === "qf").sort(bySet);
  const ef = playoff.filter((m) => m.comp_level === "ef").sort(bySet);
  const f = playoff
    .filter((m) => m.comp_level === "f")
    .sort((a, b) => a.match_number - b.match_number);
  const cols: BracketColumn[] = [];
  const maxSfSet = sf.reduce((mx, m) => Math.max(mx, m.set_number), 0);
  if (maxSfSet >= 11) {
    const range = (lo: number, hi: number, label: string) => {
      const ms = sf.filter((m) => m.set_number >= lo && m.set_number <= hi);
      if (ms.length) cols.push({ label, matches: ms });
    };
    range(1, 4, "Round 1");
    range(5, 8, "Round 2");
    range(9, 10, "Round 3");
    range(11, 12, "Round 4");
    range(13, 13, "Round 5");
  } else {
    if (ef.length) cols.push({ label: "Eighthfinals", matches: ef });
    if (qf.length) cols.push({ label: "Quarterfinals", matches: qf });
    if (sf.length) cols.push({ label: "Semifinals", matches: sf });
  }
  if (f.length) cols.push({ label: "Finals", matches: f });
  return cols;
}

function BracketAlliance({
  teams,
  score,
  win,
  played,
  color,
  year,
}: {
  teams: number[];
  score: number;
  win: boolean;
  played: boolean;
  color: "red" | "blue";
  year?: number;
}) {
  const tint = color === "red" ? RED_TINT : BLUE_TINT;
  return (
    <Group
      justify="space-between"
      wrap="nowrap"
      gap={6}
      px={6}
      py={4}
      style={{ borderRadius: 6, backgroundColor: win ? tint : undefined }}
    >
      <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
        {teams.map((t) => (
          <TeamName key={t} teamNumber={t} year={year} numberOnly fw={win ? 800 : 500} />
        ))}
      </Group>
      <Text size="sm" fw={win ? 800 : 500} c={win ? color : "dimmed"}>
        {played ? score : "-"}
      </Text>
    </Group>
  );
}

function BracketMatch({
  eventKey,
  m,
  year,
}: {
  eventKey: string;
  m: MatchResponse;
  year?: number;
}) {
  const played = isPlayed(m);
  return (
    <Card
      withBorder
      radius="md"
      padding="xs"
      w={210}
      component={Link}
      to={`/match/${eventKey}/${m.match_key}`}
      style={{ textDecoration: "none", flexShrink: 0 }}
    >
      <Text size="xs" c="dimmed" fw={600} mb={4}>
        {matchLabel(m)}
      </Text>
      <BracketAlliance
        teams={m.red_teams}
        score={m.red_score}
        win={m.winning_alliance === "red"}
        played={played}
        color="red"
        year={year}
      />
      <BracketAlliance
        teams={m.blue_teams}
        score={m.blue_score}
        win={m.winning_alliance === "blue"}
        played={played}
        color="blue"
        year={year}
      />
    </Card>
  );
}

function PlayoffBracket({
  eventKey,
  matches,
  year,
}: {
  eventKey: string;
  matches: MatchResponse[];
  year?: number;
}) {
  const cols = useMemo(() => playoffColumns(matches), [matches]);
  if (cols.length === 0) return null;
  return (
    <Card withBorder radius="md" padding="md">
      <Text fw={700} mb="sm">
        Playoff Bracket
      </Text>
      <Group align="flex-start" gap="lg" wrap="nowrap" style={{ overflowX: "auto" }}>
        {cols.map((col) => (
          <Stack key={col.label} gap="sm" style={{ flexShrink: 0 }}>
            <Text size="sm" fw={600} c="dimmed">
              {col.label}
            </Text>
            {col.matches.map((m) => (
              <BracketMatch key={m.match_key} eventKey={eventKey} m={m} year={year} />
            ))}
          </Stack>
        ))}
      </Group>
    </Card>
  );
}

function AwardCard({
  awardName,
  teams,
  year,
}: {
  awardName: string;
  teams: number[];
  year?: number;
}) {
  const realTeams = teams.filter((t) => t > 0);
  return (
    <Card
      withBorder
      radius="md"
      padding="md"
      style={{ borderLeft: "4px solid var(--mantine-color-yellow-6)" }}
    >
      <Group gap="sm" align="flex-start" wrap="nowrap">
        <ThemeIcon size={40} radius="md" variant="light" color="yellow">
          <IconTrophy size={22} />
        </ThemeIcon>
        <Stack gap={6} style={{ minWidth: 0 }}>
          <Text fw={700}>{awardName}</Text>
          {realTeams.length > 0 ? (
            <Group gap="md">
              {realTeams.map((t) => (
                <Group key={t} gap={6} wrap="nowrap">
                  <TeamAvatar teamNumber={t} size={22} radius={4} bordered />
                  <TeamName teamNumber={t} year={year} />
                </Group>
              ))}
            </Group>
          ) : (
            <Text size="sm" c="dimmed">
              &ndash;
            </Text>
          )}
        </Stack>
      </Group>
    </Card>
  );
}

export function Event() {
  const { eventKey = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") ?? "teams";

  const year = yearFromEventKey(eventKey);
  const [metricsMode, setMetricsMode] = useState<"event" | "season">("event");

  const eventQuery = useEvent(eventKey);
  const teamsQuery = useEventTeams(eventKey);
  const perfsQuery = useEventPerfs(eventKey);
  const matchesQuery = useEventMatches(eventKey);
  const rankingsQuery = useEventRankings(eventKey);
  const awardsQuery = useEventAwards(eventKey);
  const { data: searchIdx } = useSearchIndex();
  const nicknameOf = (tn: number) => searchIdx?.teams[String(tn)]?.nickname ?? "";
  // Season EPAs for the whole year (used only by the "By Season" metrics view).
  const seasonQuery = useLeaderboard(year ?? 0, {}, {
    enabled: Boolean(year) && tab === "metrics" && metricsMode === "season",
  });

  const event = eventQuery.data;

  const seasonPerfByTeam = useMemo(() => {
    const map = new Map<number, EventPerfInfo>();
    for (const r of seasonQuery.data ?? []) {
      const p = r.team_perfs[0];
      if (!p) continue;
      map.set(r.team_number, {
        team_number: r.team_number,
        event_key: eventKey,
        raw: p.raw,
        ace: p.ace,
        confidence: p.confidence,
        auto_raw: p.auto_raw,
        teleop_raw: p.teleop_raw,
        endgame_raw: p.endgame_raw,
      });
    }
    return map;
  }, [seasonQuery.data, eventKey]);

  // Percentile basis for by-season coloring: computed over the whole season.
  const seasonThresholds = useMemo(() => {
    const rows = (seasonQuery.data ?? []).map((r) => r.team_perfs[0]).filter(Boolean);
    return {
      ace: computePercentiles(rows.map((r) => r.ace)),
      auto: computePercentiles(rows.map((r) => r.auto_raw)),
      teleop: computePercentiles(rows.map((r) => r.teleop_raw)),
      endgame: computePercentiles(rows.map((r) => r.endgame_raw)),
    };
  }, [seasonQuery.data]);
  const seasonConfMedian = useMemo(
    () => median((seasonQuery.data ?? []).map((r) => r.team_perfs[0]?.confidence ?? null)),
    [seasonQuery.data],
  );

  useEffect(() => {
    document.title = event ? `${event.event_data.name} - Peekorobo` : `${eventKey} - Peekorobo`;
  }, [event, eventKey]);

  const perfByTeam = useMemo(() => {
    const map = new Map<number, number | null>();
    for (const p of perfsQuery.data?.perfs ?? []) map.set(p.team_number, p.ace);
    return map;
  }, [perfsQuery.data]);

  const aceThresholds = useMemo(
    () => computePercentiles((perfsQuery.data?.perfs ?? []).map((p) => p.ace)),
    [perfsQuery.data],
  );

  // Rank of each team within this event by event ACE (descending, nulls excluded).
  const aceRankByTeam = useMemo(() => {
    const ranked = (perfsQuery.data?.perfs ?? [])
      .filter((p) => p.ace !== null && p.ace !== undefined)
      .sort((a, b) => (b.ace ?? 0) - (a.ace ?? 0));
    const map = new Map<number, number>();
    ranked.forEach((p, i) => map.set(p.team_number, i + 1));
    return map;
  }, [perfsQuery.data]);

  const metricThresholds = useMemo(() => {
    const perfs = perfsQuery.data?.perfs ?? [];
    return {
      ace: computePercentiles(perfs.map((p) => p.ace)),
      auto: computePercentiles(perfs.map((p) => p.auto_raw)),
      teleop: computePercentiles(perfs.map((p) => p.teleop_raw)),
      endgame: computePercentiles(perfs.map((p) => p.endgame_raw)),
    };
  }, [perfsQuery.data]);
  const confMedian = useMemo(
    () => median((perfsQuery.data?.perfs ?? []).map((p) => p.confidence)),
    [perfsQuery.data],
  );

  // Strength of Schedule (client-side): mean of a team's own-alliance predicted
  // win probability across qualification matches (mirrors the Dash SoS tab).
  const sosRows = useMemo(() => {
    const quals = (matchesQuery.data?.matches ?? []).filter((m) => m.comp_level === "qm");
    const eventTeams = teamsQuery.data?.teams ?? [];
    const teamNums = eventTeams.length
      ? eventTeams.map((t) => t.team_number)
      : (perfsQuery.data?.perfs ?? []).map((p) => p.team_number);
    const aceOf = (tn: number) => perfByTeam.get(tn) ?? 0;
    const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

    const rows = teamNums.map((tn) => {
      const tms = quals.filter((m) => m.red_teams.includes(tn) || m.blue_teams.includes(tn));
      const winProbs: number[] = [];
      const oppAces: number[] = [];
      const partnerAces: number[] = [];
      let hardest: { prob: number; key: string } | null = null;
      let easiest: { prob: number; key: string } | null = null;
      for (const m of tms) {
        const isRed = m.red_teams.includes(tn);
        const allies = isRed ? m.red_teams : m.blue_teams;
        const opps = isRed ? m.blue_teams : m.red_teams;
        const partners = allies.filter((t) => t !== tn);
        if (opps.length) oppAces.push(opps.reduce((s, o) => s + aceOf(o), 0) / opps.length);
        if (partners.length)
          partnerAces.push(partners.reduce((s, p) => s + aceOf(p), 0) / partners.length);
        const prob = isRed ? m.red_win_prob : m.blue_win_prob;
        if (prob === null || prob === undefined) continue;
        winProbs.push(prob);
        if (!hardest || prob < hardest.prob) hardest = { prob, key: m.match_key };
        if (!easiest || prob > easiest.prob) easiest = { prob, key: m.match_key };
      }
      const sos = winProbs.length ? winProbs.reduce((a, b) => a + b, 0) / winProbs.length : null;
      return {
        teamNumber: tn,
        sos,
        avgOpp: avg(oppAces),
        avgPartner: avg(partnerAces),
        hardest,
        easiest,
        count: tms.length,
      };
    });
    return rows.filter((r) => r.sos !== null).sort((a, b) => (b.sos ?? 0) - (a.sos ?? 0));
  }, [matchesQuery.data, teamsQuery.data, perfsQuery.data, perfByTeam]);

  const sortedMatches = useMemo(() => {
    const matches = [...(matchesQuery.data?.matches ?? [])];
    matches.sort((a, b) => {
      const lvl = (COMP_LEVEL_ORDER[a.comp_level] ?? 9) - (COMP_LEVEL_ORDER[b.comp_level] ?? 9);
      if (lvl !== 0) return lvl;
      if (a.set_number !== b.set_number) return a.set_number - b.set_number;
      return a.match_number - b.match_number;
    });
    return matches;
  }, [matchesQuery.data]);

  const qualMatches = useMemo(
    () => sortedMatches.filter((m) => m.comp_level === "qm"),
    [sortedMatches],
  );
  const playoffMatches = useMemo(
    () => sortedMatches.filter((m) => m.comp_level !== "qm"),
    [sortedMatches],
  );
  const insights = useMemo(() => matchInsights(sortedMatches), [sortedMatches]);
  const hasPlayed = useMemo(() => sortedMatches.some(isPlayed), [sortedMatches]);

  const sortedRankings = useMemo(
    () => [...(rankingsQuery.data?.event_rankings ?? [])].sort((a, b) => a.rank - b.rank),
    [rankingsQuery.data],
  );

  const sortedTeams = useMemo(
    () => [...(teamsQuery.data?.teams ?? [])].sort((a, b) => a.team_number - b.team_number),
    [teamsQuery.data],
  );

  const sortedPerfs = useMemo(
    () =>
      [...(perfsQuery.data?.perfs ?? [])].sort(
        (a, b) => (b.ace ?? -Infinity) - (a.ace ?? -Infinity),
      ),
    [perfsQuery.data],
  );

  // Metric rows for the active mode. By-season maps each event team to its
  // full-season EPA; by-event uses the event-specific perfs.
  const metricRows = useMemo<EventPerfInfo[]>(() => {
    if (metricsMode === "event") return sortedPerfs;
    const teamNums =
      (teamsQuery.data?.teams ?? []).map((t) => t.team_number) ||
      sortedPerfs.map((p) => p.team_number);
    return teamNums
      .map((tn) => seasonPerfByTeam.get(tn))
      .filter((p): p is EventPerfInfo => Boolean(p))
      .sort((a, b) => (b.ace ?? -Infinity) - (a.ace ?? -Infinity));
  }, [metricsMode, sortedPerfs, teamsQuery.data, seasonPerfByTeam]);

  const activeThresholds = metricsMode === "season" ? seasonThresholds : metricThresholds;
  const activeConfMedian = metricsMode === "season" ? seasonConfMedian : confMedian;

  const metricColumns = useMemo<Column<EventPerfInfo>[]>(
    () => [
      {
        key: "rank",
        header: "#",
        width: 50,
        render: (_r, i) => i + 1,
      },
      {
        key: "num",
        header: "#",
        width: 80,
        sortValue: (r) => r.team_number,
        render: (r) => <TeamName teamNumber={r.team_number} numberOnly year={year ?? undefined} />,
      },
      {
        key: "team",
        header: "Team",
        sortValue: (r) => nicknameOf(r.team_number).toLowerCase(),
        exportValue: (r) => nicknameOf(r.team_number),
        render: (r) => (
          <Group gap="sm" wrap="nowrap">
            <TeamAvatar teamNumber={r.team_number} size={28} radius={6} bordered />
            <TeamName teamNumber={r.team_number} withNumber={false} year={year ?? undefined} />
          </Group>
        ),
      },
      {
        key: "raw",
        header: "RAW",
        width: 80,
        sortValue: (r) => r.raw,
        render: (r) => formatNumber(r.raw),
      },
      {
        key: "confidence",
        header: "Confidence",
        width: 110,
        sortValue: (r) => r.confidence,
        render: (r) => <ConfidenceCell value={r.confidence} median={activeConfMedian} />,
      },
      {
        key: "ace",
        header: "ACE",
        width: 80,
        sortValue: (r) => r.ace,
        render: (r) => <MetricCell value={r.ace} thresholds={activeThresholds.ace} />,
      },
      {
        key: "auto",
        header: "Auto",
        width: 80,
        sortValue: (r) => r.auto_raw,
        render: (r) => <MetricCell value={r.auto_raw} thresholds={activeThresholds.auto} />,
      },
      {
        key: "teleop",
        header: "Teleop",
        width: 80,
        sortValue: (r) => r.teleop_raw,
        render: (r) => <MetricCell value={r.teleop_raw} thresholds={activeThresholds.teleop} />,
      },
      {
        key: "endgame",
        header: "Endgame",
        width: 90,
        sortValue: (r) => r.endgame_raw,
        render: (r) => <MetricCell value={r.endgame_raw} thresholds={activeThresholds.endgame} />,
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeThresholds, activeConfMedian, year, searchIdx],
  );

  const teamColumns = useMemo<Column<EventTeamEntry>[]>(
    () => [
      {
        key: "num",
        header: "#",
        width: 80,
        sortValue: (t) => t.team_number,
        render: (t) => <TeamName teamNumber={t.team_number} numberOnly year={year ?? undefined} />,
      },
      {
        key: "team",
        header: "Team",
        sortValue: (t) => (t.nickname || "").toLowerCase(),
        exportValue: (t) => t.nickname || "",
        render: (t) => (
          <Group gap="sm" wrap="nowrap">
            <TeamAvatar teamNumber={t.team_number} size={28} radius={6} bordered />
            <TeamName
              teamNumber={t.team_number}
              nickname={t.nickname || undefined}
              withNumber={false}
              year={year ?? undefined}
            />
          </Group>
        ),
      },
      {
        key: "location",
        header: "Location",
        sortValue: (t) => locationString(t.city, t.state_prov, t.country),
        render: (t) => locationString(t.city, t.state_prov, t.country),
      },
      {
        key: "ace",
        header: "Event ACE",
        width: 120,
        sortValue: (t) => perfByTeam.get(t.team_number) ?? null,
        render: (t) => (
          <AceBadge value={perfByTeam.get(t.team_number) ?? null} thresholds={aceThresholds} />
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [perfByTeam, aceThresholds, year, searchIdx],
  );

  const rankingColumns = useMemo<Column<TeamRankingInfo>[]>(
    () => [
      { key: "rank", header: "Rank", width: 70, sortValue: (r) => r.rank, render: (r) => r.rank },
      {
        key: "num",
        header: "#",
        width: 80,
        sortValue: (r) => r.team_number,
        render: (r) => <TeamName teamNumber={r.team_number} numberOnly year={year ?? undefined} />,
      },
      {
        key: "team",
        header: "Team",
        sortValue: (r) => nicknameOf(r.team_number).toLowerCase(),
        exportValue: (r) => nicknameOf(r.team_number),
        render: (r) => (
          <Group gap="sm" wrap="nowrap">
            <TeamAvatar teamNumber={r.team_number} size={28} radius={6} bordered />
            <TeamName teamNumber={r.team_number} withNumber={false} year={year ?? undefined} />
          </Group>
        ),
      },
      { key: "wins", header: "W", width: 55, align: "center", sortValue: (r) => r.wins, render: (r) => r.wins },
      { key: "losses", header: "L", width: 55, align: "center", sortValue: (r) => r.losses, render: (r) => r.losses },
      { key: "ties", header: "T", width: 55, align: "center", sortValue: (r) => r.ties, render: (r) => r.ties },
      { key: "dq", header: "DQ", width: 55, align: "center", sortValue: (r) => r.dq, render: (r) => r.dq },
      {
        key: "ace",
        header: "ACE",
        width: 100,
        align: "center",
        sortValue: (r) => perfByTeam.get(r.team_number) ?? null,
        render: (r) => (
          <AceBadge value={perfByTeam.get(r.team_number) ?? null} thresholds={aceThresholds} />
        ),
      },
      {
        key: "acerank",
        header: "ACE Rank",
        width: 90,
        align: "center",
        sortValue: (r) => aceRankByTeam.get(r.team_number) ?? null,
        render: (r) => {
          const rk = aceRankByTeam.get(r.team_number);
          return rk ? `#${rk}` : "-";
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [perfByTeam, aceThresholds, aceRankByTeam, year, searchIdx],
  );

  type SosRow = (typeof sosRows)[number];
  const sosColumns = useMemo<Column<SosRow>[]>(
    () => [
      {
        key: "num",
        header: "#",
        width: 80,
        sortValue: (r) => r.teamNumber,
        render: (r) => <TeamName teamNumber={r.teamNumber} numberOnly year={year ?? undefined} />,
      },
      {
        key: "team",
        header: "Team",
        sortValue: (r) => nicknameOf(r.teamNumber).toLowerCase(),
        exportValue: (r) => nicknameOf(r.teamNumber),
        render: (r) => (
          <Group gap="sm" wrap="nowrap">
            <TeamAvatar teamNumber={r.teamNumber} size={28} radius={6} bordered />
            <TeamName teamNumber={r.teamNumber} withNumber={false} year={year ?? undefined} />
          </Group>
        ),
      },
      { key: "sos", header: "SoS", width: 80, sortValue: (r) => r.sos, render: (r) => formatNumber(r.sos, 2) },
      { key: "opp", header: "Avg Opp ACE", width: 120, sortValue: (r) => r.avgOpp, render: (r) => formatNumber(r.avgOpp, 1) },
      {
        key: "partner",
        header: "Avg Partner ACE",
        width: 130,
        sortValue: (r) => r.avgPartner,
        render: (r) => formatNumber(r.avgPartner, 1),
      },
      {
        key: "hardest",
        header: "Hardest",
        width: 100,
        sortValue: (r) => r.hardest?.prob ?? null,
        render: (r) =>
          r.hardest ? (
            <Anchor component={Link} to={`/match/${eventKey}/${r.hardest.key}`}>
              {(r.hardest.prob * 100).toFixed(0)}%
            </Anchor>
          ) : (
            "-"
          ),
      },
      {
        key: "easiest",
        header: "Easiest",
        width: 100,
        sortValue: (r) => r.easiest?.prob ?? null,
        render: (r) =>
          r.easiest ? (
            <Anchor component={Link} to={`/match/${eventKey}/${r.easiest.key}`}>
              {(r.easiest.prob * 100).toFixed(0)}%
            </Anchor>
          ) : (
            "-"
          ),
      },
      { key: "count", header: "Matches", width: 90, align: "center", sortValue: (r) => r.count, render: (r) => r.count },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [eventKey, year, searchIdx],
  );

  // Group awards by name, de-duplicating repeated (award, team) rows that the
  // source data sometimes contains.
  const awardGroups = useMemo(() => {
    const map = new Map<string, Set<number>>();
    for (const a of awardsQuery.data?.teams_and_awards ?? []) {
      const name = a.award_name.trim();
      if (!name) continue;
      const set = map.get(name) ?? new Set<number>();
      set.add(a.team_number);
      map.set(name, set);
    }
    return [...map.entries()].map(([award_name, teams]) => ({
      award_name,
      teams: [...teams].sort((a, b) => a - b),
    }));
  }, [awardsQuery.data]);

  if (eventQuery.isLoading) return <LoadingState label={`Loading ${eventKey}...`} />;
  if (eventQuery.error) return <ErrorState error={eventQuery.error} />;

  return (
    <Stack gap="lg" py="md">
      <Group gap="md" align="stretch" wrap="nowrap">
        {year ? (
          <Box style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
            <img
              src={gameLogo(year)}
              alt=""
              style={{
                height: "100%",
                width: "auto",
                maxHeight: 110,
                objectFit: "contain",
                display: "block",
              }}
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
          </Box>
        ) : null}
        <Stack gap={4} style={{ minWidth: 0, flex: 1 }}>
        <Group gap="xs" wrap="nowrap" justify="space-between" align="flex-start">
          <Title order={1}>{event?.event_data.name ?? eventKey}</Title>
          <FavoriteButton itemType="event" itemKey={eventKey} />
        </Group>
        <Group gap="xs">
          <Text c="dimmed">{eventKey}</Text>
          {event ? (
            <>
              <Text c="dimmed">
                {locationString(
                  event.location_info.city,
                  event.location_info.state_prov,
                  event.location_info.country,
                )}
              </Text>
              {eventWeekLabel(event.week) ? (
                <Badge variant="light">{eventWeekLabel(event.week)}</Badge>
              ) : null}
              <Badge variant="light" color="gray">
                {eventTypeLabel(event.event_data.event_type)}
              </Badge>
            </>
          ) : null}
        </Group>
        {event ? (
          <Text size="sm" c="dimmed">
            {formatDateRange(event.event_data.start_date, event.event_data.end_date)}
          </Text>
        ) : null}
        </Stack>
      </Group>

      <Tabs value={tab} onChange={(val) => setSearchParams(val ? { tab: val } : {})} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="teams">Teams</Tabs.Tab>
          <Tabs.Tab value="metrics">Metrics</Tabs.Tab>
          <Tabs.Tab value="matches">Matches</Tabs.Tab>
          <Tabs.Tab value="sos">SoS</Tabs.Tab>
          <Tabs.Tab value="rankings">Rankings</Tabs.Tab>
          <Tabs.Tab value="awards">Awards</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="teams" pt="md">
          {teamsQuery.isLoading ? (
            <LoadingState />
          ) : sortedTeams.length === 0 ? (
            <EmptyState>No teams listed for this event yet.</EmptyState>
          ) : (
            <DataTable
              data={sortedTeams}
              columns={teamColumns}
              getRowKey={(t) => t.team_number}
              initialSort={{ key: "team", dir: "asc" }}
              minWidth={560}
              defaultPageSize={50}
              exportFileName={`${eventKey}-teams`}
            />
          )}
        </Tabs.Panel>

        <Tabs.Panel value="metrics" pt="md">
          <Stack gap="sm">
            <Group justify="space-between" align="center" wrap="wrap">
              <SegmentedControl
                value={metricsMode}
                onChange={(v) => setMetricsMode(v as "event" | "season")}
                data={[
                  { label: "By Event", value: "event" },
                  { label: "By Season", value: "season" },
                ]}
              />
              <Text size="xs" c="dimmed">
                {metricsMode === "event"
                  ? "EPA earned at this event only."
                  : `Full ${year ?? ""} season EPA for these teams.`}
              </Text>
            </Group>
            {(metricsMode === "event" ? perfsQuery.isLoading : seasonQuery.isLoading) ? (
              <LoadingState />
            ) : metricRows.length === 0 ? (
              <EmptyState>No EPA metrics available for this event yet.</EmptyState>
            ) : (
              <>
                <AceLegend />
                <DataTable
                  data={metricRows}
                  columns={metricColumns}
                  getRowKey={(r) => r.team_number}
                  initialSort={{ key: "ace", dir: "desc" }}
                  minWidth={720}
                  stickyHeader
                  defaultPageSize={25}
                  exportFileName={`${eventKey}-metrics`}
                />
              </>
            )}
          </Stack>
        </Tabs.Panel>

          <Tabs.Panel value="sos" pt="md">
            {matchesQuery.isLoading || perfsQuery.isLoading ? (
              <LoadingState />
            ) : sosRows.length === 0 ? (
              <EmptyState>
                No strength-of-schedule data yet (needs qualification matches with win
                predictions).
              </EmptyState>
            ) : (
              <Stack gap="sm">
                <Text size="sm" c="dimmed">
                  SoS = mean predicted win probability for a team's alliance across its
                  qualification matches. Higher = an easier draw.
                </Text>
                <DataTable
                  data={sosRows}
                  columns={sosColumns}
                  getRowKey={(r) => r.teamNumber}
                  initialSort={{ key: "sos", dir: "desc" }}
                  minWidth={760}
                  stickyHeader
                  defaultPageSize={50}
                  exportFileName={`${eventKey}-strength-of-schedule`}
                />
              </Stack>
            )}
          </Tabs.Panel>

        <Tabs.Panel value="matches" pt="md">
          {matchesQuery.isLoading ? (
            <LoadingState />
          ) : sortedMatches.length === 0 ? (
            <EmptyState>No matches posted yet.</EmptyState>
          ) : (
            <Stack gap="lg">
              {hasPlayed ? (
                <Card withBorder padding="md" radius="md">
                  <Text fw={700} mb="sm">
                    Event Insights
                  </Text>
                  <SimpleGrid cols={{ base: 2, sm: 3, md: 6 }} spacing="md">
                    <InsightStat label="Matches" value={String(insights.numMatches)} />
                    <InsightStat label="Avg Score" value={formatNumber(insights.avgScore, 1)} />
                    <InsightStat
                      label="Avg Win Score"
                      value={formatNumber(insights.avgWinningScore, 1)}
                    />
                    <InsightStat
                      label="Avg Margin"
                      value={formatNumber(insights.avgMargin, 1)}
                    />
                    <InsightStat
                      label="High Score"
                      value={insights.highScore ? String(insights.highScore.value) : "–"}
                    />
                    <InsightStat
                      label="High Margin"
                      value={insights.highMargin ? String(insights.highMargin.value) : "–"}
                    />
                  </SimpleGrid>
                </Card>
              ) : null}
              {qualMatches.length > 0 ? (
                <MatchesTable
                  eventKey={eventKey}
                  title="Qualification Matches"
                  matches={qualMatches}
                />
              ) : null}
              {playoffMatches.length > 0 ? (
                <MatchesTable
                  eventKey={eventKey}
                  title="Playoff Matches"
                  matches={playoffMatches}
                />
              ) : null}
            </Stack>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="rankings" pt="md">
          <Stack gap="lg">
            {rankingsQuery.isLoading ? (
              <LoadingState />
            ) : sortedRankings.length === 0 ? (
              playoffMatches.length > 0 ? null : (
                <EmptyState>No rankings available.</EmptyState>
              )
            ) : (
              <Stack gap="xs">
                <Text fw={700}>Qualification Rankings</Text>
                <DataTable
                  data={sortedRankings}
                  columns={rankingColumns}
                  getRowKey={(r) => r.team_number}
                  initialSort={{ key: "rank", dir: "asc" }}
                  minWidth={560}
                  defaultPageSize={50}
                  exportFileName={`${eventKey}-rankings`}
                />
              </Stack>
            )}
            {playoffMatches.length > 0 ? (
              <PlayoffBracket eventKey={eventKey} matches={playoffMatches} year={year ?? undefined} />
            ) : null}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="awards" pt="md">
          {awardsQuery.isLoading ? (
            <LoadingState />
          ) : awardGroups.length === 0 ? (
            <EmptyState>No awards recorded for this event.</EmptyState>
          ) : (
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
              {awardGroups.map((g) => (
                <AwardCard
                  key={g.award_name}
                  awardName={g.award_name}
                  teams={g.teams}
                  year={year ?? undefined}
                />
              ))}
            </SimpleGrid>
          )}
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
