import { useEffect, useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import {
  ActionIcon,
  Anchor,
  Badge,
  Card,
  Group,
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
import { useEvent, useEventMatches, useEventPerfs, useEvents } from "../api/queries";
import { ErrorState, LoadingState, EmptyState } from "../components/StateWrappers";
import { TeamName } from "../components/TeamName";
import { MetricCell, ConfidenceCell } from "../components/MetricCell";
import { AceLegend } from "../components/AceLegend";
import { computePercentiles, median, type PercentileThresholds } from "../lib/epa";
import { formatNumber, yearFromEventKey } from "../lib/format";
import { predictedMatchScores } from "../lib/prediction";
import type { EventPerfInfo, MatchResponse, TeamPerfInfo, TeamPerfResponse } from "../types/api";
import {
  computePreMatchTeamSources,
  PRE_MATCH_SOURCE_COLORS,
  PRE_MATCH_SOURCE_HINTS,
  PRE_MATCH_SOURCE_LABELS,
  teamPreMatchRating,
  type PreMatchTeamRatings,
} from "../lib/predictionSource";

const COMP_LEVEL_ORDER: Record<string, number> = { qm: 0, ef: 1, qf: 2, sf: 3, f: 4 };

function matchSort(a: MatchResponse, b: MatchResponse): number {
  const lvl = (COMP_LEVEL_ORDER[a.comp_level] ?? 9) - (COMP_LEVEL_ORDER[b.comp_level] ?? 9);
  if (lvl !== 0) return lvl;
  if (a.set_number !== b.set_number) return a.set_number - b.set_number;
  return a.match_number - b.match_number;
}

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

const PHASES: Array<{ label: string; field: keyof EventPerfInfo; thr: keyof Thresholds }> = [
  { label: "Auto", field: "auto_raw", thr: "auto" },
  { label: "Teleop", field: "teleop_raw", thr: "teleop" },
  { label: "Endgame", field: "endgame_raw", thr: "endgame" },
  { label: "RAW", field: "raw", thr: "raw" },
];

function sumField(perfs: (EventPerfInfo | undefined)[], field: keyof EventPerfInfo): number {
  return perfs.reduce((s, p) => s + (typeof p?.[field] === "number" ? (p[field] as number) : 0), 0);
}

function AllianceBreakdown({
  teams,
  color,
  year,
  perfByTeam,
  thresholds,
  confMedian,
  actualScore,
}: {
  teams: number[];
  color: "red" | "blue";
  year?: number;
  perfByTeam: Map<number, EventPerfInfo>;
  thresholds: Thresholds;
  confMedian: number | null;
  actualScore: number;
}) {
  const perfs = teams.map((t) => perfByTeam.get(t));
  const accent = color === "red" ? "var(--mantine-color-red-6)" : "var(--mantine-color-blue-6)";
  return (
    <Card withBorder padding={0} radius="md">
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th style={{ color: accent }}>Phase</Table.Th>
            {teams.map((t) => (
              <Table.Th key={t} ta="center">
                <TeamName teamNumber={t} year={year} numberOnly />
              </Table.Th>
            ))}
            <Table.Th ta="center">Alliance</Table.Th>
            <Table.Th ta="center">Match</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {PHASES.map((phase) => (
            <Table.Tr key={phase.label}>
              <Table.Td fw={600}>{phase.label}</Table.Td>
              {perfs.map((p, i) => (
                <Table.Td key={teams[i]} ta="center">
                  <MetricCell
                    value={(p?.[phase.field] as number | null | undefined) ?? null}
                    thresholds={thresholds[phase.thr]}
                  />
                </Table.Td>
              ))}
              <Table.Td ta="center" fw={700}>
                {formatNumber(sumField(perfs, phase.field), 1)}
              </Table.Td>
              <Table.Td ta="center" c="dimmed">
                –
              </Table.Td>
            </Table.Tr>
          ))}
          <Table.Tr>
            <Table.Td fw={600}>Confidence</Table.Td>
            {perfs.map((p, i) => (
              <Table.Td key={teams[i]} ta="center">
                <ConfidenceCell value={p?.confidence ?? null} median={confMedian} />
              </Table.Td>
            ))}
            <Table.Td ta="center" fw={700}>
              {(() => {
                const vals = perfs
                  .map((p) => p?.confidence)
                  .filter((v): v is number => typeof v === "number");
                return formatNumber(
                  vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null,
                  2,
                );
              })()}
            </Table.Td>
            <Table.Td ta="center" c="dimmed">
              –
            </Table.Td>
          </Table.Tr>
          <Table.Tr style={{ borderTop: `2px solid ${accent}` }}>
            <Table.Td fw={800} style={{ color: accent }}>
              ACE
            </Table.Td>
            {perfs.map((p, i) => (
              <Table.Td key={teams[i]} ta="center">
                <MetricCell value={p?.ace ?? null} thresholds={thresholds.ace} />
              </Table.Td>
            ))}
            <Table.Td ta="center" fw={800}>
              {formatNumber(sumField(perfs, "ace"), 1)}
            </Table.Td>
            <Table.Td ta="center" fw={800} style={{ color: accent }}>
              {actualScore}
            </Table.Td>
          </Table.Tr>
        </Table.Tbody>
      </Table>
    </Card>
  );
}

function AlliancePreMatchInputs({
  teams,
  color,
  year,
  ratings,
}: {
  teams: number[];
  color: "red" | "blue";
  year?: number;
  ratings: PreMatchTeamRatings | null;
}) {
  const accent = color === "red" ? "var(--mantine-color-red-6)" : "var(--mantine-color-blue-6)";
  return (
    <Card withBorder padding="md" radius="md">
      <Text fw={700} mb="sm" style={{ color: accent }}>
        {color === "red" ? "Red" : "Blue"} alliance
      </Text>
      <Stack gap="sm">
        {teams.map((team) => {
          const entry = teamPreMatchRating(ratings, team);
          return (
            <Group key={team} justify="space-between" wrap="nowrap" gap="xs">
              <TeamName teamNumber={team} year={year} />
              {entry ? (
                <Group gap="xs" wrap="nowrap">
                  {entry.rating != null ? (
                    <Text size="sm" fw={700}>
                      {formatNumber(entry.rating, 1)}
                    </Text>
                  ) : null}
                  <Tooltip label={PRE_MATCH_SOURCE_HINTS[entry.source]} withArrow multiline w={280}>
                    <Badge
                      size="sm"
                      variant="light"
                      color={PRE_MATCH_SOURCE_COLORS[entry.source]}
                      style={{ cursor: "help" }}
                    >
                      {PRE_MATCH_SOURCE_LABELS[entry.source]}
                    </Badge>
                  </Tooltip>
                </Group>
              ) : (
                <Text size="sm" c="dimmed">
                  —
                </Text>
              )}
            </Group>
          );
        })}
      </Stack>
    </Card>
  );
}

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

export function Match() {
  const { eventKey = "", matchKey = "" } = useParams();
  const year = yearFromEventKey(eventKey) ?? undefined;
  const eventQuery = useEvent(eventKey);
  const matchesQuery = useEventMatches(eventKey);
  const perfsQuery = useEventPerfs(eventKey);
  const yearEventsQuery = useEvents(year ?? 0);

  const sortedMatches = useMemo(
    () => [...(matchesQuery.data?.matches ?? [])].sort(matchSort),
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

  const preMatchRatings = useMemo(() => {
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

  const perfByTeam = useMemo(() => {
    const map = new Map<number, EventPerfInfo>();
    for (const p of perfsQuery.data?.perfs ?? []) map.set(p.team_number, p);
    return map;
  }, [perfsQuery.data]);

  const aceByTeam = useMemo(() => {
    const map = new Map<number, number | null | undefined>();
    for (const p of perfsQuery.data?.perfs ?? []) map.set(p.team_number, p.ace);
    return map;
  }, [perfsQuery.data]);

  const thresholds: Thresholds = useMemo(() => {
    const perfs = perfsQuery.data?.perfs ?? [];
    return {
      auto: computePercentiles(perfs.map((p) => p.auto_raw)),
      teleop: computePercentiles(perfs.map((p) => p.teleop_raw)),
      endgame: computePercentiles(perfs.map((p) => p.endgame_raw)),
      raw: computePercentiles(perfs.map((p) => p.raw)),
      ace: computePercentiles(perfs.map((p) => p.ace)),
    };
  }, [perfsQuery.data]);
  const confMedian = useMemo(
    () => median((perfsQuery.data?.perfs ?? []).map((p) => p.confidence)),
    [perfsQuery.data],
  );

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

  const modelStrength = predictedMatchScores(match, aceByTeam);
  const modelRed = modelStrength?.red ?? null;
  const modelBlue = modelStrength?.blue ?? null;
  const modelWinner =
    modelRed !== null && modelBlue !== null
      ? modelRed === modelBlue
        ? "Tie"
        : modelRed > modelBlue
          ? "RED"
          : "BLUE"
      : null;

  const actualWinner = redWin ? "RED" : blueWin ? "BLUE" : played ? "TIE" : null;

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
          label="Pre-match strength"
          value={
            modelRed !== null && modelBlue !== null
              ? `${Math.round(modelRed)} - ${Math.round(modelBlue)}`
              : "—"
          }
          sub={modelWinner ? `Model favors: ${modelWinner}` : "No model data"}
          subColor={modelWinner === "RED" ? "red" : modelWinner === "BLUE" ? "blue" : "dimmed"}
        />
        <ScoreStat
          label="Actual score"
          value={played ? `${match.red_score} - ${match.blue_score}` : "— / —"}
          sub={actualWinner ? `Winner: ${actualWinner}` : "Not played"}
          subColor={actualWinner === "RED" ? "red" : actualWinner === "BLUE" ? "blue" : "dimmed"}
        />
        <ScoreStat
          label="Win probability"
          value={winProb !== null ? `${winProb}%` : "—"}
          sub={
            winProb !== null
              ? `${(redProb ?? 0) >= (blueProb ?? 0) ? "RED" : "BLUE"} favored`
              : undefined
          }
          subColor={(redProb ?? 0) >= (blueProb ?? 0) ? "red" : "blue"}
        />
      </SimpleGrid>

      <Text size="sm" c="dimmed">
        Pre-match strength and win % use the walk-forward model stored on this match (sum of
        pre-match ACE ratings, not predicted game points). Phase tables below show each team&apos;s
        ACE at this event after all of their matches here — not a point-in-time pre-match forecast.
      </Text>

      {preMatchRatings ? (
        <>
          <Title order={3}>Pre-match model inputs</Title>
          <Text size="sm" c="dimmed" mb="xs">
            Inferred from this team&apos;s match history — no pipeline rerun needed. Hover a badge
            for details.
          </Text>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            <AlliancePreMatchInputs
              teams={match.red_teams}
              color="red"
              year={year}
              ratings={preMatchRatings}
            />
            <AlliancePreMatchInputs
              teams={match.blue_teams}
              color="blue"
              year={year}
              ratings={preMatchRatings}
            />
          </SimpleGrid>
        </>
      ) : null}

      <AceLegend />

      <Title order={3}>Event ACE breakdown</Title>
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <AllianceBreakdown
          teams={match.red_teams}
          color="red"
          year={year}
          perfByTeam={perfByTeam}
          thresholds={thresholds}
          confMedian={confMedian}
          actualScore={match.red_score}
        />
        <AllianceBreakdown
          teams={match.blue_teams}
          color="blue"
          year={year}
          perfByTeam={perfByTeam}
          thresholds={thresholds}
          confMedian={confMedian}
          actualScore={match.blue_score}
        />
      </SimpleGrid>

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
