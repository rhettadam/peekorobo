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
  Tabs,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { IconExternalLink, IconTrophy } from "@tabler/icons-react";
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
import { TeamName } from "../components/TeamName";
import { TeamAvatar } from "../components/TeamAvatar";
import { FavoriteWithCount } from "../components/FavoriteWithCount";
import { EventExternalLinks, WebcastButton } from "../components/WebcastControl";
import { MetricCell, ConfidenceCell } from "../components/MetricCell";
import { AceLegend } from "../components/AceLegend";
import {
  MetricTrajectoryCell,
  TRAJECTORY_CHART_WIDTH,
  type TrajectoryView,
} from "../components/MetricTrajectoryCell";
import { DataTable, type Column } from "../components/DataTable";
import { TeamBubbleChart } from "../components/TeamBubbleChart";
import type {
  EventPerfInfo,
  MatchResponse,
  TeamRankingInfo,
} from "../types/api";
import { gameLogo } from "../lib/assets";
import { gameLogoBannerStyle, useGameLogoColors } from "../lib/gameLogoColors";
import { computePercentiles, median, type PercentileThresholds } from "../lib/epa";
import {
  buildAllTeamTrajectories,
  preMatchFieldForMetric,
  type MatchExtremum,
  type TeamTrajectory,
} from "../lib/eventTrajectory";
import { collectEventPreMatchValues } from "../lib/predictionSource";
import { METRIC_STYLES, type MetricKey } from "../lib/metrics";
import {
  isPlayed,
  matchInsights,
  predictionAccuracy,
  predictionColor,
  predictionScoreMae,
  predictedMatchScores,
} from "../lib/prediction";
import { MatchActualScoreCell, MatchPredScoreCell } from "../components/MatchScoreCell";
import {
  eventTypeLabel,
  eventWeekLabel,
  formatDateRange,
  formatNumber,
  formatPredictedTime,
  locationString,
  yearFromEventKey,
} from "../lib/format";
import { CURRENT_YEAR } from "../lib/constants";

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
  aceByTeam,
}: {
  eventKey: string;
  title: string;
  matches: MatchResponse[];
  aceByTeam?: Map<number, number | null>;
}) {
  const acc = predictionAccuracy(matches);
  const scoreMae = predictionScoreMae(matches, aceByTeam);
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
        sortValue: (m) =>
          isPlayed(m) ? Math.max(m.red_score, m.blue_score) : (m.predicted_time ?? -1),
        exportValue: (m) => {
          if (isPlayed(m)) return `${m.red_score}-${m.blue_score}`;
          return formatPredictedTime(m.predicted_time) ?? "";
        },
        render: (m) => <MatchActualScoreCell match={m} />,
      },
      {
        key: "pred",
        header: "Pred",
        width: 100,
        sortValue: (m) => {
          const p = predictedMatchScores(m, aceByTeam);
          return p ? Math.max(p.red, p.blue) : null;
        },
        exportValue: (m) => {
          const p = predictedMatchScores(m, aceByTeam);
          return p ? `${Math.round(p.red)}-${Math.round(p.blue)}` : "";
        },
        render: (m) => <MatchPredScoreCell match={m} aceByTeam={aceByTeam} />,
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
    [eventKey, matchYear, aceByTeam],
  );

  return (
    <Stack gap="xs">
      <Group justify="space-between" align="center">
        <Text fw={700}>{title}</Text>
        <Group gap="xs">
          {acc.pct !== null ? (
            <Badge variant="light" color="grape">
              Prediction Accuracy: {acc.correct}/{acc.total} ({acc.pct.toFixed(0)}%)
            </Badge>
          ) : null}
          {scoreMae.mae !== null ? (
            <Badge variant="light" color="blue">
              Score MAE: {scoreMae.mae.toFixed(1)}
            </Badge>
          ) : null}
        </Group>
      </Group>
      <DataTable
        data={matches}
        columns={columns}
        getRowKey={(m) => m.match_key}
        initialSort={{ key: "match", dir: "asc" }}
        minWidth={860}
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
  predScore,
  win,
  predWin,
  played,
  color,
  year,
}: {
  teams: number[];
  score: number;
  predScore: number | null;
  win: boolean;
  predWin: boolean;
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
      <Group gap={6} wrap="nowrap">
        <Text size="sm" fw={win ? 800 : 500} c={played ? (win ? color : "dimmed") : "dimmed"}>
          {played ? score : "–"}
        </Text>
        <Text
          size="xs"
          fw={predWin ? 700 : 400}
          c={predWin ? color : "dimmed"}
          title="Predicted (event ACE sum)"
        >
          {predScore !== null ? Math.round(predScore) : "–"}
        </Text>
      </Group>
    </Group>
  );
}

function BracketMatch({
  eventKey,
  m,
  year,
  aceByTeam,
}: {
  eventKey: string;
  m: MatchResponse;
  year?: number;
  aceByTeam?: Map<number, number | null>;
}) {
  const played = isPlayed(m);
  const pred = predictedMatchScores(m, aceByTeam);
  return (
    <Card
      withBorder
      radius="md"
      padding="xs"
      w={230}
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
        predScore={pred?.red ?? null}
        win={m.winning_alliance === "red"}
        predWin={Boolean(pred && pred.red > pred.blue)}
        played={played}
        color="red"
        year={year}
      />
      <BracketAlliance
        teams={m.blue_teams}
        score={m.blue_score}
        predScore={pred?.blue ?? null}
        win={m.winning_alliance === "blue"}
        predWin={Boolean(pred && pred.blue > pred.red)}
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
  aceByTeam,
}: {
  eventKey: string;
  matches: MatchResponse[];
  year?: number;
  aceByTeam?: Map<number, number | null>;
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
              <BracketMatch
                key={m.match_key}
                eventKey={eventKey}
                m={m}
                year={year}
                aceByTeam={aceByTeam}
              />
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

function MatchExtremumCell({
  extremum,
  eventKey,
  thresholds,
  decimals = 1,
}: {
  extremum: MatchExtremum | null | undefined;
  eventKey: string;
  thresholds: PercentileThresholds;
  decimals?: number;
}) {
  if (!extremum) {
    return (
      <Text size="xs" c="dimmed">
        —
      </Text>
    );
  }
  return (
    <Stack gap={2} align="flex-start">
      <Anchor component={Link} to={`/match/${eventKey}/${extremum.matchKey}`} size="xs" fw={600}>
        {extremum.label}
        {!extremum.played ? " *" : ""}
      </Anchor>
      <MetricCell value={extremum.value} thresholds={thresholds} decimals={decimals} />
    </Stack>
  );
}

export function Event() {
  const { eventKey = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") ?? "teams";

  const year = yearFromEventKey(eventKey);
  const [metricsMode, setMetricsMode] = useState<"event" | "match" | "season">("event");
  const [bubbleMode, setBubbleMode] = useState<"event" | "season">("event");
  const [trajectoryMetric, setTrajectoryMetric] = useState<MetricKey>("ace");
  const [trajectoryView, setTrajectoryView] = useState<TrajectoryView>("both");
  const logoColors = useGameLogoColors(year);
  const bannerStyle = gameLogoBannerStyle(logoColors);

  const eventQuery = useEvent(eventKey);
  const teamsQuery = useEventTeams(eventKey);
  const perfsQuery = useEventPerfs(eventKey);
  const matchesQuery = useEventMatches(eventKey);
  const rankingsQuery = useEventRankings(eventKey);
  const awardsQuery = useEventAwards(eventKey);
  const { data: searchIdx } = useSearchIndex();
  const nicknameOf = (tn: number) => searchIdx?.teams[String(tn)]?.nickname ?? "";
  // Season EPAs for the whole year (teams tab, metrics by-season/event-delta, etc.).
  const seasonQuery = useLeaderboard(year ?? 0, {}, {
    enabled:
      Boolean(year) &&
      (tab === "teams" ||
        tab === "bubble" ||
        (tab === "metrics" && (metricsMode === "season" || metricsMode === "event"))),
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

  const seasonRankByTeam = useMemo(() => {
    const map = new Map<number, { rank: number | null; count: number | null }>();
    for (const r of seasonQuery.data ?? []) {
      const p = r.team_perfs[0];
      if (!p) continue;
      map.set(r.team_number, {
        rank: p.rank_global ?? null,
        count: p.count_global ?? null,
      });
    }
    return map;
  }, [seasonQuery.data]);

  useEffect(() => {
    document.title = event ? `${event.event_data.name} - Peekorobo` : `${eventKey} - Peekorobo`;
  }, [event, eventKey]);

  const perfFullByTeam = useMemo(() => {
    const map = new Map<number, EventPerfInfo>();
    for (const p of perfsQuery.data?.perfs ?? []) map.set(p.team_number, p);
    return map;
  }, [perfsQuery.data]);

  const perfByTeam = useMemo(() => {
    const map = new Map<number, number | null>();
    for (const [tn, p] of perfFullByTeam) map.set(tn, p.ace);
    return map;
  }, [perfFullByTeam]);

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
      const perf = perfFullByTeam.get(tn);
      const sos = winProbs.length ? winProbs.reduce((a, b) => a + b, 0) / winProbs.length : null;
      return {
        teamNumber: tn,
        sos,
        avgOpp: avg(oppAces),
        avgPartner: avg(partnerAces),
        hardest,
        easiest,
        count: tms.length,
        raw: perf?.raw ?? null,
        confidence: perf?.confidence ?? null,
        ace: perf?.ace ?? null,
        auto_raw: perf?.auto_raw ?? null,
        teleop_raw: perf?.teleop_raw ?? null,
        endgame_raw: perf?.endgame_raw ?? null,
      };
    });
    return rows.filter((r) => r.sos !== null).sort((a, b) => (b.sos ?? 0) - (a.sos ?? 0));
  }, [matchesQuery.data, teamsQuery.data, perfsQuery.data, perfByTeam, perfFullByTeam]);

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

  interface EventTeamRow {
    team_number: number;
    nickname: string;
    city: string;
    state_prov: string;
    country: string;
    event: EventPerfInfo | null;
    season: EventPerfInfo | null;
  }

  const eventTeamRows = useMemo<EventTeamRow[]>(() => {
    const perfMap = new Map<number, EventPerfInfo>();
    for (const p of perfsQuery.data?.perfs ?? []) perfMap.set(p.team_number, p);
    const teams = teamsQuery.data?.teams ?? [];
    const source =
      teams.length > 0
        ? teams
        : [...perfMap.values()].map((p) => ({
            team_number: p.team_number,
            nickname: nicknameOf(p.team_number),
            city: "",
            state_prov: "",
            country: "",
          }));
    return source.map((t) => ({
        team_number: t.team_number,
        nickname: t.nickname || nicknameOf(t.team_number),
        city: t.city,
        state_prov: t.state_prov,
        country: t.country,
        event: perfMap.get(t.team_number) ?? null,
        season: seasonPerfByTeam.get(t.team_number) ?? null,
      }));
  }, [teamsQuery.data, perfsQuery.data, seasonPerfByTeam, searchIdx]);

  const bubbleTeams = useMemo(
    () =>
      eventTeamRows.map((r) => {
        const src = bubbleMode === "season" ? r.season : r.event;
        return {
          teamNumber: r.team_number,
          nickname: r.nickname || nicknameOf(r.team_number),
          ace: src?.ace ?? null,
          raw: src?.raw ?? null,
          auto: src?.auto_raw ?? null,
          teleop: src?.teleop_raw ?? null,
          endgame: src?.endgame_raw ?? null,
          confidence: src?.confidence ?? null,
          rank:
            bubbleMode === "season"
              ? seasonRankByTeam.get(r.team_number)?.rank ?? null
              : aceRankByTeam.get(r.team_number) ?? null,
          seasonAce: r.season?.ace ?? null,
        };
      }),
    [eventTeamRows, bubbleMode, aceRankByTeam, seasonRankByTeam, searchIdx],
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
    if (metricsMode === "event" || metricsMode === "match") return sortedPerfs;
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

  const trajectoryThresholds = useMemo(() => {
    const matches = matchesQuery.data?.matches ?? [];
    const field = preMatchFieldForMetric(trajectoryMetric);
    return computePercentiles(collectEventPreMatchValues(matches, field));
  }, [matchesQuery.data, trajectoryMetric]);

  const trajectoryByTeam = useMemo(() => {
    if (metricsMode !== "match") return new Map<number, TeamTrajectory>();
    const matches = matchesQuery.data?.matches ?? [];
    const teamNums = metricRows.map((r) => r.team_number);
    return buildAllTeamTrajectories(teamNums, matches, trajectoryMetric);
  }, [matchesQuery.data, metricRows, trajectoryMetric, metricsMode]);

  const metricColumns = useMemo<Column<EventPerfInfo>[]>(
    () => {
      const globalRankCol: Column<EventPerfInfo> = {
        key: "globalRank",
        header: "Global Rank",
        width: 110,
        align: "right",
        sortValue: (r) => seasonRankByTeam.get(r.team_number)?.rank ?? null,
        render: (r) => {
          const meta = seasonRankByTeam.get(r.team_number);
          if (meta?.rank == null) return "—";
          return meta.count
            ? `${meta.rank.toLocaleString()} / ${meta.count.toLocaleString()}`
            : meta.rank.toLocaleString();
        },
      };

      const aceDeltaCol: Column<EventPerfInfo> = {
        key: "aceDelta",
        header: "ACE Δ",
        width: 80,
        align: "right",
        sortValue: (r) => {
          const seasonAce = seasonPerfByTeam.get(r.team_number)?.ace;
          if (r.ace == null || seasonAce == null) return null;
          return r.ace - seasonAce;
        },
        render: (r) => {
          const seasonAce = seasonPerfByTeam.get(r.team_number)?.ace;
          if (r.ace == null || seasonAce == null) return "—";
          const d = r.ace - seasonAce;
          const prefix = d > 0 ? "+" : "";
          return (
            <Text size="sm" fw={600} c={d > 0 ? "teal" : d < 0 ? "red" : undefined}>
              {prefix}
              {formatNumber(d, 1)}
            </Text>
          );
        },
      };

      return [
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
      ...(metricsMode === "season" ? [globalRankCol] : []),
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
        header: metricsMode === "season" ? "Season ACE" : "Event ACE",
        width: 90,
        sortValue: (r) => r.ace,
        render: (r) => <MetricCell value={r.ace} thresholds={activeThresholds.ace} />,
      },
      ...(metricsMode === "event" ? [aceDeltaCol] : []),
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
    ];
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [activeThresholds, activeConfMedian, year, searchIdx, metricsMode, seasonRankByTeam, seasonPerfByTeam],
  );

  const matchMetricColumns = useMemo<Column<EventPerfInfo>[]>(
    () => [
      {
        key: "rank",
        header: "#",
        width: 44,
        render: (_r, i) => i + 1,
      },
      {
        key: "team",
        header: "Team",
        width: 200,
        sortValue: (r) => nicknameOf(r.team_number).toLowerCase(),
        exportValue: (r) => `${r.team_number} ${nicknameOf(r.team_number)}`,
        render: (r) => (
          <Group gap="xs" wrap="nowrap">
            <TeamAvatar teamNumber={r.team_number} size={24} radius={6} bordered />
            <Stack gap={0}>
              <TeamName teamNumber={r.team_number} numberOnly year={year ?? undefined} />
              <TeamName teamNumber={r.team_number} withNumber={false} year={year ?? undefined} />
            </Stack>
          </Group>
        ),
      },
      {
        key: "trajectory",
        header: "Trajectory",
        sortValue: (r) => trajectoryByTeam.get(r.team_number)?.delta ?? null,
        exportValue: null,
        render: (r) => {
          const traj = trajectoryByTeam.get(r.team_number);
          if (!traj || traj.points.length === 0) {
            return (
              <Text size="xs" c="dimmed">
                —
              </Text>
            );
          }
          return (
            <MetricTrajectoryCell
              trajectory={traj}
              metric={trajectoryMetric}
              thresholds={trajectoryThresholds}
              view={trajectoryView}
              cellId={r.team_number}
              width={TRAJECTORY_CHART_WIDTH}
            />
          );
        },
      },
      {
        key: "best",
        header: "Best match",
        width: 118,
        sortValue: (r) => trajectoryByTeam.get(r.team_number)?.best?.value ?? null,
        exportValue: (r) => {
          const b = trajectoryByTeam.get(r.team_number)?.best;
          return b ? `${b.label} ${b.value}` : null;
        },
        render: (r) => (
          <MatchExtremumCell
            extremum={trajectoryByTeam.get(r.team_number)?.best}
            eventKey={eventKey}
            thresholds={trajectoryThresholds}
            decimals={trajectoryMetric === "confidence" ? 2 : 1}
          />
        ),
      },
      {
        key: "worst",
        header: "Worst match",
        width: 118,
        sortValue: (r) => trajectoryByTeam.get(r.team_number)?.worst?.value ?? null,
        exportValue: (r) => {
          const w = trajectoryByTeam.get(r.team_number)?.worst;
          return w ? `${w.label} ${w.value}` : null;
        },
        render: (r) => (
          <MatchExtremumCell
            extremum={trajectoryByTeam.get(r.team_number)?.worst}
            eventKey={eventKey}
            thresholds={trajectoryThresholds}
            decimals={trajectoryMetric === "confidence" ? 2 : 1}
          />
        ),
      },
      {
        key: "range",
        header: "Range",
        width: 72,
        align: "right",
        sortValue: (r) => {
          const t = trajectoryByTeam.get(r.team_number);
          if (!t?.best || !t?.worst) return null;
          return t.best.value - t.worst.value;
        },
        render: (r) => {
          const t = trajectoryByTeam.get(r.team_number);
          if (!t?.best || !t?.worst) return "—";
          return formatNumber(t.best.value - t.worst.value, trajectoryMetric === "confidence" ? 2 : 1);
        },
      },
      {
        key: "delta",
        header: "Δ",
        width: 64,
        align: "right",
        sortValue: (r) => trajectoryByTeam.get(r.team_number)?.delta ?? null,
        render: (r) => {
          const d = trajectoryByTeam.get(r.team_number)?.delta;
          if (d === null || d === undefined) return "—";
          const prefix = d > 0 ? "+" : "";
          return (
            <Text size="sm" fw={600} c={d > 0 ? "teal" : d < 0 ? "red" : undefined}>
              {prefix}
              {formatNumber(d, trajectoryMetric === "confidence" ? 2 : 1)}
            </Text>
          );
        },
      },
      {
        key: "momentum",
        header: "Mom",
        width: 64,
        align: "right",
        sortValue: (r) => trajectoryByTeam.get(r.team_number)?.momentum ?? null,
        render: (r) => {
          const m = trajectoryByTeam.get(r.team_number)?.momentum;
          if (m === null || m === undefined) return "—";
          const prefix = m > 0 ? "+" : "";
          return (
            <Text size="sm" c={m > 0 ? "teal" : m < 0 ? "red" : "dimmed"}>
              {prefix}
              {formatNumber(m, trajectoryMetric === "confidence" ? 2 : 1)}
            </Text>
          );
        },
      },
      {
        key: "ace",
        header: "Event ACE",
        width: 90,
        sortValue: (r) => r.ace,
        render: (r) => <MetricCell value={r.ace} thresholds={metricThresholds.ace} />,
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      trajectoryByTeam,
      trajectoryMetric,
      trajectoryThresholds,
      trajectoryView,
      metricThresholds.ace,
      year,
      searchIdx,
      eventKey,
    ],
  );

  const eventTeamColumns = useMemo<Column<EventTeamRow>[]>(
    () => [
      {
        key: "rank",
        header: "#",
        width: 50,
        sortValue: (r) => aceRankByTeam.get(r.team_number) ?? null,
        render: (r) => aceRankByTeam.get(r.team_number) ?? "–",
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
        sortValue: (r) => (r.nickname || nicknameOf(r.team_number)).toLowerCase(),
        exportValue: (r) => r.nickname || nicknameOf(r.team_number),
        render: (r) => (
          <Group gap="sm" wrap="nowrap">
            <TeamAvatar teamNumber={r.team_number} size={28} radius={6} bordered />
            <TeamName
              teamNumber={r.team_number}
              nickname={r.nickname || undefined}
              withNumber={false}
              year={year ?? undefined}
            />
          </Group>
        ),
      },
      {
        key: "location",
        header: "Location",
        sortValue: (r) => locationString(r.city, r.state_prov, r.country),
        render: (r) => locationString(r.city, r.state_prov, r.country),
      },
      {
        key: "raw",
        header: "RAW",
        width: 80,
        sortValue: (r) => r.event?.raw ?? null,
        render: (r) => formatNumber(r.event?.raw),
      },
      {
        key: "confidence",
        header: "Confidence",
        width: 110,
        sortValue: (r) => r.event?.confidence ?? null,
        render: (r) => <ConfidenceCell value={r.event?.confidence ?? null} median={confMedian} />,
      },
      {
        key: "seasonAce",
        header: "Season ACE",
        width: 110,
        sortValue: (r) => r.season?.ace ?? null,
        render: (r) => (
          <MetricCell value={r.season?.ace ?? null} thresholds={seasonThresholds.ace} />
        ),
      },
      {
        key: "auto",
        header: "Auto",
        width: 80,
        sortValue: (r) => r.event?.auto_raw ?? null,
        render: (r) => (
          <MetricCell value={r.event?.auto_raw ?? null} thresholds={metricThresholds.auto} />
        ),
      },
      {
        key: "teleop",
        header: "Teleop",
        width: 80,
        sortValue: (r) => r.event?.teleop_raw ?? null,
        render: (r) => (
          <MetricCell value={r.event?.teleop_raw ?? null} thresholds={metricThresholds.teleop} />
        ),
      },
      {
        key: "endgame",
        header: "Endgame",
        width: 90,
        sortValue: (r) => r.event?.endgame_raw ?? null,
        render: (r) => (
          <MetricCell value={r.event?.endgame_raw ?? null} thresholds={metricThresholds.endgame} />
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      aceRankByTeam,
      metricThresholds,
      seasonThresholds,
      confMedian,
      year,
      searchIdx,
    ],
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
        key: "raw",
        header: "RAW",
        width: 80,
        sortValue: (r) => perfFullByTeam.get(r.team_number)?.raw ?? null,
        render: (r) => formatNumber(perfFullByTeam.get(r.team_number)?.raw),
      },
      {
        key: "confidence",
        header: "Confidence",
        width: 110,
        sortValue: (r) => perfFullByTeam.get(r.team_number)?.confidence ?? null,
        render: (r) => (
          <ConfidenceCell
            value={perfFullByTeam.get(r.team_number)?.confidence}
            median={confMedian}
          />
        ),
      },
      {
        key: "ace",
        header: "Event ACE",
        width: 90,
        sortValue: (r) => perfFullByTeam.get(r.team_number)?.ace ?? null,
        render: (r) => (
          <MetricCell
            value={perfFullByTeam.get(r.team_number)?.ace ?? null}
            thresholds={metricThresholds.ace}
          />
        ),
      },
      {
        key: "auto",
        header: "Auto",
        width: 80,
        sortValue: (r) => perfFullByTeam.get(r.team_number)?.auto_raw ?? null,
        render: (r) => (
          <MetricCell
            value={perfFullByTeam.get(r.team_number)?.auto_raw ?? null}
            thresholds={metricThresholds.auto}
          />
        ),
      },
      {
        key: "teleop",
        header: "Teleop",
        width: 80,
        sortValue: (r) => perfFullByTeam.get(r.team_number)?.teleop_raw ?? null,
        render: (r) => (
          <MetricCell
            value={perfFullByTeam.get(r.team_number)?.teleop_raw ?? null}
            thresholds={metricThresholds.teleop}
          />
        ),
      },
      {
        key: "endgame",
        header: "Endgame",
        width: 90,
        sortValue: (r) => perfFullByTeam.get(r.team_number)?.endgame_raw ?? null,
        render: (r) => (
          <MetricCell
            value={perfFullByTeam.get(r.team_number)?.endgame_raw ?? null}
            thresholds={metricThresholds.endgame}
          />
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
    [perfFullByTeam, metricThresholds, confMedian, aceRankByTeam, year, searchIdx],
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
        render: (r) => <ConfidenceCell value={r.confidence} median={confMedian} />,
      },
      {
        key: "ace",
        header: "Event ACE",
        width: 90,
        sortValue: (r) => r.ace,
        render: (r) => <MetricCell value={r.ace} thresholds={metricThresholds.ace} />,
      },
      {
        key: "auto",
        header: "Auto",
        width: 80,
        sortValue: (r) => r.auto_raw,
        render: (r) => <MetricCell value={r.auto_raw} thresholds={metricThresholds.auto} />,
      },
      {
        key: "teleop",
        header: "Teleop",
        width: 80,
        sortValue: (r) => r.teleop_raw,
        render: (r) => <MetricCell value={r.teleop_raw} thresholds={metricThresholds.teleop} />,
      },
      {
        key: "endgame",
        header: "Endgame",
        width: 90,
        sortValue: (r) => r.endgame_raw,
        render: (r) => <MetricCell value={r.endgame_raw} thresholds={metricThresholds.endgame} />,
      },
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
    [eventKey, year, searchIdx, metricThresholds, confMedian],
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

  const website =
    event?.website && /^https?:\/\//i.test(event.website.trim()) ? event.website.trim() : null;

  return (
    <Stack gap="lg" py="md">
      <Card
        padding="md"
        radius="lg"
        withBorder
        style={{
          background: bannerStyle.background,
          borderColor: bannerStyle.borderColor,
          overflow: "hidden",
        }}
      >
        <Stack gap="md">
          <Group align="flex-start" wrap="wrap" gap="md">
            {year ? (
              <Box style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
                <img
                  src={gameLogo(year)}
                  alt=""
                  style={{
                    width: "auto",
                    maxHeight: 64,
                    objectFit: "contain",
                    display: "block",
                  }}
                  className="event-banner-logo"
                  onError={(e) => (e.currentTarget.style.display = "none")}
                />
              </Box>
            ) : null}
            <Stack gap={6} style={{ minWidth: 0, flex: 1 }}>
              <Group justify="space-between" align="flex-start" wrap="wrap" gap="sm">
                <Title order={1} fz={{ base: "h2", sm: "h1" }} style={{ lineHeight: 1.15, flex: 1, minWidth: 0 }}>
                  {event?.event_data.name ?? eventKey}
                </Title>
                <Box style={{ flexShrink: 0 }}>
                  <FavoriteWithCount itemType="event" itemKey={eventKey} size={22} />
                </Box>
              </Group>
              <Group gap="xs" wrap="wrap">
                <Text c="dimmed" size="sm">
                  {eventKey}
                </Text>
                {event ? (
                  <>
                    <Text c="dimmed" size="sm">
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
          <Group gap="xs" wrap="wrap" align="center">
            <WebcastButton
              webcastType={event?.webcast_type}
              webcastChannel={event?.webcast_channel}
            />
            {website ? (
              <Button
                component="a"
                href={website}
                target="_blank"
                rel="noopener noreferrer"
                size="compact-sm"
                variant="default"
                leftSection={<IconExternalLink size={14} />}
              >
                Website
              </Button>
            ) : null}
            <EventExternalLinks eventKey={eventKey} year={year} />
          </Group>
        </Stack>
      </Card>

      <Tabs value={tab} onChange={(val) => setSearchParams(val ? { tab: val } : {})} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="teams">Teams</Tabs.Tab>
          <Tabs.Tab value="metrics">Metrics</Tabs.Tab>
          <Tabs.Tab value="bubble">Bubble</Tabs.Tab>
          <Tabs.Tab value="matches">Matches</Tabs.Tab>
          <Tabs.Tab value="sos">SoS</Tabs.Tab>
          <Tabs.Tab value="rankings">Rankings</Tabs.Tab>
          <Tabs.Tab value="awards">Awards</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="teams" pt="md">
          {teamsQuery.isLoading || perfsQuery.isLoading || seasonQuery.isLoading ? (
            <LoadingState />
          ) : eventTeamRows.length === 0 ? (
            <EmptyState>No teams listed for this event yet.</EmptyState>
          ) : (
            <Stack gap="sm">
              <Text size="sm" c="dimmed">
                Event component metrics and season ACE. Sorted by season ACE by default.
              </Text>
              <AceLegend />
              <DataTable
                data={eventTeamRows}
                columns={eventTeamColumns}
                getRowKey={(t) => t.team_number}
                initialSort={{ key: "seasonAce", dir: "desc" }}
                minWidth={1080}
                stickyHeader
                defaultPageSize={50}
                exportFileName={`${eventKey}-teams`}
              />
            </Stack>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="metrics" pt="md">
          <Stack gap="sm">
            <Group justify="space-between" align="center" wrap="wrap">
              <Group gap="sm" wrap="wrap">
                <SegmentedControl
                  value={metricsMode}
                  onChange={(v) => setMetricsMode(v as "event" | "match" | "season")}
                  data={[
                    { label: "By Event", value: "event" },
                    { label: "By Match", value: "match" },
                    { label: "By Season", value: "season" },
                  ]}
                />
                {metricsMode === "match" && (
                  <>
                    <SegmentedControl
                      value={trajectoryMetric}
                      onChange={(v) => setTrajectoryMetric(v as MetricKey)}
                      data={(
                        ["ace", "auto", "teleop", "endgame", "raw", "confidence"] as MetricKey[]
                      ).map((k) => ({ label: METRIC_STYLES[k].label, value: k }))}
                    />
                    <SegmentedControl
                      value={trajectoryView}
                      onChange={(v) => setTrajectoryView(v as TrajectoryView)}
                      data={[
                        { label: "Both", value: "both" },
                        { label: "Sparkline", value: "sparkline" },
                        { label: "Heat strip", value: "heat" },
                      ]}
                    />
                  </>
                )}
              </Group>
              <Text size="xs" c="dimmed">
                {metricsMode === "event"
                  ? "Event ACE and ACE Δ vs full-season ACE (positive = outperformed season average)."
                  : metricsMode === "match"
                    ? "Walk-forward rating at each match. Sort Trajectory or Δ to find momentum."
                    : `Full ${year ?? ""} season ACE for these teams.`}
              </Text>
            </Group>
            {(metricsMode === "season"
              ? seasonQuery.isLoading
              : perfsQuery.isLoading ||
                (metricsMode === "event" && seasonQuery.isLoading) ||
                (metricsMode === "match" && matchesQuery.isLoading)) ? (
              <LoadingState />
            ) : metricRows.length === 0 ? (
              <EmptyState>No ACE metrics available for this event yet.</EmptyState>
            ) : (
              <>
                <AceLegend />
                <DataTable
                  data={metricRows}
                  columns={metricsMode === "match" ? matchMetricColumns : metricColumns}
                  getRowKey={(r) => r.team_number}
                  initialSort={{
                    key: metricsMode === "match" ? "trajectory" : "ace",
                    dir: "desc",
                  }}
                  minWidth={
                    metricsMode === "match" ? 1200 : metricsMode === "season" ? 820 : 800
                  }
                  stickyHeader
                  defaultPageSize={25}
                  exportFileName={`${eventKey}-metrics-${metricsMode}`}
                />
              </>
            )}
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="bubble" pt="md">
          {teamsQuery.isLoading ||
          perfsQuery.isLoading ||
          (bubbleMode === "season" && seasonQuery.isLoading) ? (
            <LoadingState />
          ) : bubbleTeams.filter((t) => t.ace != null).length === 0 ? (
            <EmptyState>
              {bubbleMode === "season"
                ? "No season ACE yet to plot for these teams."
                : "No event ACE yet to plot."}
            </EmptyState>
          ) : (
            <Stack gap="sm">
              <Group justify="space-between" align="center" wrap="wrap">
                <SegmentedControl
                  value={bubbleMode}
                  onChange={(v) => setBubbleMode(v as "event" | "season")}
                  data={[
                    { label: "By Event", value: "event" },
                    { label: "By Season", value: "season" },
                  ]}
                />
                <Text size="xs" c="dimmed">
                  {bubbleMode === "event"
                    ? "Metrics earned at this event. Rank is event ACE rank."
                    : `Full ${year ?? ""} season metrics. Rank is global rank.`}
                </Text>
              </Group>
              <TeamBubbleChart
                teams={bubbleTeams}
                year={year ?? CURRENT_YEAR}
                nicknameOf={nicknameOf}
                aceThresholds={
                  bubbleMode === "season" ? seasonThresholds.ace : metricThresholds.ace
                }
                defaultX="auto"
                defaultY="teleop"
                metrics={["ace", "raw", "auto", "teleop", "endgame", "confidence", "rank"]}
                rankLabel={bubbleMode === "season" ? "Global rank" : "ACE rank"}
              />
            </Stack>
          )}
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
                <AceLegend />
                <DataTable
                  data={sosRows}
                  columns={sosColumns}
                  getRowKey={(r) => r.teamNumber}
                  initialSort={{ key: "sos", dir: "desc" }}
                  minWidth={1180}
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
                  aceByTeam={perfByTeam}
                />
              ) : null}
              {playoffMatches.length > 0 ? (
                <MatchesTable
                  eventKey={eventKey}
                  title="Playoff Matches"
                  matches={playoffMatches}
                  aceByTeam={perfByTeam}
                />
              ) : null}
            </Stack>
          )}
        </Tabs.Panel>

        <Tabs.Panel value="rankings" pt="md">
          <Stack gap="lg">
            {rankingsQuery.isLoading || perfsQuery.isLoading ? (
              <LoadingState />
            ) : sortedRankings.length === 0 ? (
              playoffMatches.length > 0 ? null : (
                <EmptyState>No rankings available.</EmptyState>
              )
            ) : (
              <Stack gap="xs">
                <Text fw={700}>Qualification Rankings</Text>
                <AceLegend />
                <DataTable
                  data={sortedRankings}
                  columns={rankingColumns}
                  getRowKey={(r) => r.team_number}
                  initialSort={{ key: "rank", dir: "asc" }}
                  minWidth={1080}
                  stickyHeader
                  defaultPageSize={50}
                  exportFileName={`${eventKey}-rankings`}
                />
              </Stack>
            )}
            {playoffMatches.length > 0 ? (
              <PlayoffBracket
                eventKey={eventKey}
                matches={playoffMatches}
                year={year ?? undefined}
                aceByTeam={perfByTeam}
              />
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
