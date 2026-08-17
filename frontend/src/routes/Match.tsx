import { useEffect, useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import {
  ActionIcon,
  Anchor,
  Badge,
  Card,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Tooltip,
  Title,
} from "@mantine/core";
import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";
import { Link, useParams } from "react-router-dom";
import { apiGet } from "../api/client";
import { useEvent, useEventMatches, useEvents } from "../api/queries";
import { ErrorState, LoadingState, EmptyState } from "../components/StateWrappers";
import { TeamName } from "../components/TeamName";
import { MetricCell, ConfidenceCell } from "../components/MetricCell";
import { AceLegend } from "../components/AceLegend";
import { computePercentiles, median, type PercentileThresholds } from "../lib/epa";
import { formatNumber, yearFromEventKey } from "../lib/format";
import { predictedMatchScores } from "../lib/prediction";
import type { TeamPerfInfo, TeamPerfResponse } from "../types/api";
import {
  collectEventPreMatchValues,
  compareMatchesChronologically,
  computePreMatchTeamSources,
  meanPreMatchField,
  mergePreMatchDisplays,
  PRE_MATCH_SOURCE_COLORS,
  PRE_MATCH_SOURCE_HINTS,
  PRE_MATCH_SOURCE_LABELS,
  sumPreMatchField,
  type PreMatchTeamDisplay,
  type PreMatchTeamDisplays,
} from "../lib/predictionSource";

function matchLabel(comp: string, set: number, num: number): string {
  const c = comp.toUpperCase();
  return comp === "qm" ? `Qualification ${num}` : `${c} ${set}-${num}`;
}

interface Thresholds {
  auto: PercentileThresholds;
  teleop: PercentileThresholds;
  endgame: PercentileThresholds;
  raw: PercentileThresholds;
  ace: PercentileThresholds;
}

type MetricKey = "auto" | "teleop" | "endgame" | "raw" | "confidence" | "ace";

const METRIC_ROWS: Array<{
  label: string;
  field: MetricKey;
  thr?: keyof Thresholds;
  decimals: number;
  bold?: boolean;
}> = [
  { label: "Auto", field: "auto", thr: "auto", decimals: 1 },
  { label: "Teleop", field: "teleop", thr: "teleop", decimals: 1 },
  { label: "Endgame", field: "endgame", thr: "endgame", decimals: 1 },
  { label: "RAW", field: "raw", thr: "raw", decimals: 1 },
  { label: "Confidence", field: "confidence", decimals: 2 },
  { label: "ACE", field: "ace", thr: "ace", decimals: 1, bold: true },
];

function ScoreStat({
  label,
  value,
  sub,
  subColor,
}: {
  label: string;
  value: string;
  sub?: string;
  subColor?: string;
}) {
  return (
    <Card withBorder padding="md" radius="md" ta="center">
      <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
        {label}
      </Text>
      <Text fz={34} fw={800} lh={1.1} mt={4}>
        {value}
      </Text>
      {sub ? (
        <Text size="sm" fw={600} c={subColor} mt={4}>
          {sub}
        </Text>
      ) : null}
    </Card>
  );
}

function AllianceAceBreakdown({
  teams,
  color,
  year,
  ratings,
  thresholds,
  confMedian,
  actualScore,
  played,
}: {
  teams: number[];
  color: "red" | "blue";
  year?: number;
  ratings: PreMatchTeamDisplays | null;
  thresholds: Thresholds;
  confMedian: number | null;
  actualScore: number;
  played: boolean;
}) {
  const accent = color === "red" ? "var(--mantine-color-red-6)" : "var(--mantine-color-blue-6)";
  const entries = teams.map((t) => ratings?.[String(t)] ?? null);

  return (
    <Card withBorder padding={0} radius="md">
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th style={{ color: accent, width: 110 }}>
              {color === "red" ? "Red" : "Blue"}
            </Table.Th>
            {teams.map((t) => {
              const entry = ratings?.[String(t)];
              return (
                <Table.Th key={t} ta="center">
                  <Stack gap={4} align="center">
                    <TeamName teamNumber={t} year={year} numberOnly />
                    {entry ? (
                      <Tooltip
                        label={PRE_MATCH_SOURCE_HINTS[entry.source]}
                        withArrow
                        multiline
                        w={260}
                      >
                        <Badge
                          size="xs"
                          variant="light"
                          color={PRE_MATCH_SOURCE_COLORS[entry.source]}
                          style={{ cursor: "help" }}
                        >
                          {PRE_MATCH_SOURCE_LABELS[entry.source]}
                        </Badge>
                      </Tooltip>
                    ) : null}
                  </Stack>
                </Table.Th>
              );
            })}
            <Table.Th ta="center">Alliance</Table.Th>
            <Table.Th ta="center">Match</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {METRIC_ROWS.map((row) => {
            const isAce = row.field === "ace";
            const allianceVal =
              row.field === "confidence"
                ? meanPreMatchField(ratings, teams, "confidence")
                : sumPreMatchField(ratings, teams, row.field);

            return (
              <Table.Tr
                key={row.label}
                style={isAce ? { borderTop: `2px solid ${accent}` } : undefined}
              >
                <Table.Td fw={isAce ? 800 : 600} style={isAce ? { color: accent } : undefined}>
                  {row.label}
                </Table.Td>
                {entries.map((entry, i) => (
                  <Table.Td key={teams[i]} ta="center">
                    <MetricValue
                      entry={entry}
                      field={row.field}
                      thresholds={thresholds}
                      thr={row.thr}
                      confMedian={confMedian}
                      decimals={row.decimals}
                    />
                  </Table.Td>
                ))}
                <Table.Td ta="center" fw={isAce ? 800 : 700}>
                  {row.field === "confidence" ? (
                    <ConfidenceCell value={allianceVal} median={confMedian} />
                  ) : row.thr ? (
                    <MetricCell value={allianceVal} thresholds={thresholds[row.thr]} decimals={row.decimals} />
                  ) : (
                    formatNumber(allianceVal, row.decimals)
                  )}
                </Table.Td>
                <Table.Td ta="center" fw={isAce ? 800 : undefined} style={isAce ? { color: accent } : undefined}>
                  {isAce ? (played ? actualScore : "—") : <Text c="dimmed">–</Text>}
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Card>
  );
}

function MetricValue({
  entry,
  field,
  thresholds,
  thr,
  confMedian,
  decimals,
}: {
  entry: PreMatchTeamDisplay | null;
  field: MetricKey;
  thresholds: Thresholds;
  thr?: keyof Thresholds;
  confMedian: number | null;
  decimals: number;
}) {
  const value = entry?.[field] ?? null;
  if (field === "confidence") {
    return <ConfidenceCell value={value} median={confMedian} />;
  }
  if (thr) {
    return <MetricCell value={value} thresholds={thresholds[thr]} decimals={decimals} />;
  }
  return <>{formatNumber(value, decimals)}</>;
}

export function Match() {
  const { eventKey = "", matchKey = "" } = useParams();
  const year = yearFromEventKey(eventKey) ?? undefined;
  const eventQuery = useEvent(eventKey);
  const matchesQuery = useEventMatches(eventKey);
  const yearEventsQuery = useEvents(year ?? 0);

  const sortedMatches = useMemo(
    () => [...(matchesQuery.data?.matches ?? [])].sort(compareMatchesChronologically),
    [matchesQuery.data],
  );
  const idx = sortedMatches.findIndex((m) => m.match_key === matchKey);
  const match = idx >= 0 ? sortedMatches[idx] : undefined;
  const prev = idx > 0 ? sortedMatches[idx - 1] : undefined;
  const next = idx >= 0 && idx < sortedMatches.length - 1 ? sortedMatches[idx + 1] : undefined;

  const matchTeams = useMemo(() => {
    if (!match) return [];
    return [...match.red_teams, ...match.blue_teams];
  }, [match]);

  const teamPerfQueries = useQueries({
    queries: matchTeams.map((tn) => ({
      queryKey: ["team-perfs", tn, "all"],
      queryFn: () => apiGet<TeamPerfResponse>(`/team_perfs/${tn}`),
      staleTime: 5 * 60 * 1000,
      enabled: tn > 0,
    })),
  });

  const eventsByKey = useMemo(() => {
    const map = new Map<string, { start_date: string }>();
    for (const e of yearEventsQuery.data?.events ?? []) {
      map.set(e.event_key, { start_date: e.event_data.start_date });
    }
    return map;
  }, [yearEventsQuery.data]);

  const teamSeasonPerf = useMemo(() => {
    const map = new Map<number, TeamPerfInfo>();
    if (!year) return map;
    matchTeams.forEach((tn, i) => {
      const perf = teamPerfQueries[i]?.data?.team_perfs.find((p) => p.year === year);
      if (perf) map.set(tn, perf);
    });
    return map;
  }, [matchTeams, teamPerfQueries, year]);

  const teamPriorSeasonPerf = useMemo(() => {
    const map = new Map<number, TeamPerfInfo>();
    const priorYear = year ? year - 1 : undefined;
    if (!priorYear) return map;
    matchTeams.forEach((tn, i) => {
      const perf = teamPerfQueries[i]?.data?.team_perfs.find((p) => p.year === priorYear);
      if (perf) map.set(tn, perf);
    });
    return map;
  }, [matchTeams, teamPerfQueries, year]);

  const preMatchSources = useMemo(() => {
    if (!match || !year) return null;
    return computePreMatchTeamSources({
      match,
      eventMatches: sortedMatches,
      eventKey,
      eventStartDate: eventQuery.data?.event_data.start_date ?? null,
      eventsByKey,
      teamSeasonPerf,
      teamPriorSeasonPerf,
    });
  }, [
    match,
    year,
    sortedMatches,
    eventKey,
    eventQuery.data,
    eventsByKey,
    teamSeasonPerf,
    teamPriorSeasonPerf,
  ]);

  const preMatchRatings = useMemo(() => {
    if (!match) return null;
    return mergePreMatchDisplays(
      match.pre_match_teams,
      preMatchSources,
      [...match.red_teams, ...match.blue_teams],
      {
        teamSeasonPerf,
        teamPriorSeasonPerf,
        eventKey,
        eventStartDate: eventQuery.data?.event_data.start_date ?? null,
        eventsByKey,
      },
    );
  }, [
    match,
    preMatchSources,
    teamSeasonPerf,
    teamPriorSeasonPerf,
    eventKey,
    eventQuery.data,
    eventsByKey,
  ]);

  const thresholds: Thresholds = useMemo(() => {
    const fromEvent = (field: "a" | "t" | "e" | "r" | "ace") =>
      collectEventPreMatchValues(sortedMatches, field);
    // Fall back to this match's six teams when the event hasn't been backfilled yet.
    const fromMatch = (field: MetricKey): Array<number | null> => {
      if (!preMatchRatings) return [];
      return matchTeams.map((t) => preMatchRatings[String(t)]?.[field] ?? null);
    };
    const auto = fromEvent("a");
    const teleop = fromEvent("t");
    const endgame = fromEvent("e");
    const raw = fromEvent("r");
    const ace = fromEvent("ace");
    return {
      auto: computePercentiles(auto.some((v) => v != null) ? auto : fromMatch("auto")),
      teleop: computePercentiles(teleop.some((v) => v != null) ? teleop : fromMatch("teleop")),
      endgame: computePercentiles(endgame.some((v) => v != null) ? endgame : fromMatch("endgame")),
      raw: computePercentiles(raw.some((v) => v != null) ? raw : fromMatch("raw")),
      ace: computePercentiles(ace.some((v) => v != null) ? ace : fromMatch("ace")),
    };
  }, [sortedMatches, preMatchRatings, matchTeams]);

  const confMedian = useMemo(() => {
    const fromEvent = collectEventPreMatchValues(sortedMatches, "c");
    if (fromEvent.some((v) => v != null)) return median(fromEvent);
    if (!preMatchRatings) return null;
    return median(matchTeams.map((t) => preMatchRatings[String(t)]?.confidence ?? null));
  }, [sortedMatches, preMatchRatings, matchTeams]);

  useEffect(() => {
    document.title = `${matchKey} - Peekorobo`;
  }, [matchKey]);

  if (matchesQuery.isLoading) return <LoadingState label="Loading match..." />;
  if (matchesQuery.error) return <ErrorState error={matchesQuery.error} />;
  if (!match) return <EmptyState>Match not found.</EmptyState>;

  const redWin = match.winning_alliance === "red";
  const blueWin = match.winning_alliance === "blue";
  const played = match.red_score > 0 || match.blue_score > 0 || redWin || blueWin;
  const redProb = match.red_win_prob ?? null;
  const blueProb = match.blue_win_prob ?? (redProb !== null ? 1 - redProb : null);
  const winProb =
    redProb !== null && blueProb !== null ? Math.round(Math.max(redProb, blueProb) * 100) : null;

  const breakdownRed = sumPreMatchField(preMatchRatings, match.red_teams, "ace");
  const breakdownBlue = sumPreMatchField(preMatchRatings, match.blue_teams, "ace");
  const storedPred = predictedMatchScores(match, undefined);
  const modelRed = breakdownRed ?? storedPred?.red ?? null;
  const modelBlue = breakdownBlue ?? storedPred?.blue ?? null;
  const modelWinner =
    modelRed !== null && modelBlue !== null
      ? modelRed === modelBlue
        ? "Tie"
        : modelRed > modelBlue
          ? "RED"
          : "BLUE"
      : null;

  const actualWinner = redWin ? "RED" : blueWin ? "BLUE" : played ? "TIE" : null;
  const modelCorrect =
    played &&
    modelWinner &&
    actualWinner &&
    actualWinner !== "TIE" &&
    modelWinner !== "Tie"
      ? modelWinner === actualWinner
      : null;

  return (
    <Stack gap="lg" py="md">
      <Group justify="space-between" align="center" wrap="nowrap">
        {prev ? (
          <ActionIcon
            variant="light"
            size="lg"
            component={Link}
            to={`/match/${eventKey}/${prev.match_key}`}
            aria-label="Previous match"
          >
            <IconChevronLeft size={20} />
          </ActionIcon>
        ) : (
          <ActionIcon variant="light" size="lg" disabled aria-label="Previous match">
            <IconChevronLeft size={20} />
          </ActionIcon>
        )}
        <Stack gap={2} align="center" style={{ minWidth: 0 }}>
          <Group gap="xs" justify="center">
            <Title order={1} ta="center">
              {matchLabel(match.comp_level, match.set_number, match.match_number)}
            </Title>
            {redWin ? <Badge color="red">Red win</Badge> : null}
            {blueWin ? <Badge color="blue">Blue win</Badge> : null}
            {modelCorrect === true ? (
              <Badge color="teal" variant="light">
                Model correct
              </Badge>
            ) : null}
            {modelCorrect === false ? (
              <Badge color="gray" variant="light">
                Model miss
              </Badge>
            ) : null}
          </Group>
          <Anchor component={Link} to={`/event/${eventKey}`} size="sm" ta="center">
            {year ? `${year} ` : ""}
            {eventQuery.data?.event_data.name ?? eventKey}
          </Anchor>
        </Stack>
        {next ? (
          <ActionIcon
            variant="light"
            size="lg"
            component={Link}
            to={`/match/${eventKey}/${next.match_key}`}
            aria-label="Next match"
          >
            <IconChevronRight size={20} />
          </ActionIcon>
        ) : (
          <ActionIcon variant="light" size="lg" disabled aria-label="Next match">
            <IconChevronRight size={20} />
          </ActionIcon>
        )}
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
        <ScoreStat
          label="Pre-match ACE"
          value={
            modelRed !== null && modelBlue !== null
              ? `${Math.round(modelRed)} – ${Math.round(modelBlue)}`
              : "—"
          }
          sub={modelWinner ? `Favors ${modelWinner}` : "No model data"}
          subColor={modelWinner === "RED" ? "red" : modelWinner === "BLUE" ? "blue" : "dimmed"}
        />
        <ScoreStat
          label="Actual score"
          value={played ? `${match.red_score} – ${match.blue_score}` : "— / —"}
          sub={actualWinner ? `Winner: ${actualWinner}` : "Not played"}
          subColor={actualWinner === "RED" ? "red" : actualWinner === "BLUE" ? "blue" : "dimmed"}
        />
        <ScoreStat
          label="Win probability"
          value={winProb !== null ? `${winProb}%` : "—"}
          sub={
            redProb !== null && blueProb !== null
              ? `Red ${(redProb * 100).toFixed(0)}% · Blue ${(blueProb * 100).toFixed(0)}%`
              : undefined
          }
          subColor={(redProb ?? 0) >= (blueProb ?? 0) ? "red" : "blue"}
        />
      </SimpleGrid>

      {redProb !== null && blueProb !== null ? (
        <Card withBorder padding="md" radius="md">
          <Group justify="space-between" mb={6}>
            <Text size="sm" fw={700} c="red">
              Red {(redProb * 100).toFixed(1)}%
            </Text>
            <Text size="sm" fw={700} c="blue">
              Blue {(blueProb * 100).toFixed(1)}%
            </Text>
          </Group>
          <Progress.Root size={14} radius="xl">
            <Progress.Section value={redProb * 100} color="red" />
            <Progress.Section value={blueProb * 100} color="blue" />
          </Progress.Root>
        </Card>
      ) : null}

      <Group justify="space-between" align="flex-end" wrap="wrap">
        <div>
          <Title order={3}>Pre-match ACE breakdown</Title>
          <Text size="sm" c="dimmed" maw={720}>
            Point-in-time ratings used for this prediction — auto / teleop / endgame → RAW ×
            confidence = ACE. Badges show where each team&apos;s rating came from.
          </Text>
        </div>
        <AceLegend />
      </Group>

      {preMatchRatings ? (
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          <AllianceAceBreakdown
            teams={match.red_teams}
            color="red"
            year={year}
            ratings={preMatchRatings}
            thresholds={thresholds}
            confMedian={confMedian}
            actualScore={match.red_score}
            played={played}
          />
          <AllianceAceBreakdown
            teams={match.blue_teams}
            color="blue"
            year={year}
            ratings={preMatchRatings}
            thresholds={thresholds}
            confMedian={confMedian}
            actualScore={match.blue_score}
            played={played}
          />
        </SimpleGrid>
      ) : (
        <EmptyState>
          Pre-match ACE components are not available for this match yet. Re-run the pipeline after
          deploying the pre_match_teams column.
        </EmptyState>
      )}

      <Card withBorder padding="md" radius="md">
        <Text fw={600} mb="xs">
          Match video
        </Text>
        {match.youtube_key ? (
          <div style={{ position: "relative", paddingTop: "56.25%" }}>
            <iframe
              title="Match video"
              src={`https://www.youtube.com/embed/${match.youtube_key}`}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", border: 0 }}
            />
          </div>
        ) : (
          <Text c="dimmed" size="sm">
            No video available.
          </Text>
        )}
      </Card>
    </Stack>
  );
}
