import { useMemo } from "react";
import { Anchor, Badge, Card, Group, Stack, Table, Text } from "@mantine/core";
import { Link } from "react-router-dom";
import { useEventMatches, useEventRankings } from "../api/queries";
import { TeamName } from "../components/TeamName";
import { StatPill } from "../components/StatPill";
import { RecordCell } from "../components/RecordCell";
import { predictionColor, isPlayed } from "../lib/prediction";
import type { EventPerfEntry, MatchResponse } from "../types/api";

const COMP_LEVEL_ORDER: Record<string, number> = { qm: 0, ef: 1, qf: 2, sf: 3, f: 4 };

function matchSort(a: MatchResponse, b: MatchResponse): number {
  const lvl = (COMP_LEVEL_ORDER[a.comp_level] ?? 9) - (COMP_LEVEL_ORDER[b.comp_level] ?? 9);
  if (lvl !== 0) return lvl;
  if (a.set_number !== b.set_number) return a.set_number - b.set_number;
  return a.match_number - b.match_number;
}

function rankColor(rank: number, total: number): string {
  if (total <= 0) return "inherit";
  const pct = rank / total;
  if (pct <= 0.25) return "var(--mantine-color-green-6)";
  if (pct <= 0.5) return "var(--mantine-color-orange-6)";
  return "var(--mantine-color-red-6)";
}

interface TeamEventBlockProps {
  eventKey: string;
  teamNumber: number;
  year: number;
  eventName?: string;
  weekLabel?: string | null;
  location?: string;
  perf?: EventPerfEntry;
  awards?: string[];
}

/**
 * One event block for the team page "Recent Events" section: a header (rank,
 * record, awards, event ACE pills) plus the team's matches with prediction and
 * outcome — mirroring build_recent_events_section in the Dash app.
 */
export function TeamEventBlock({
  eventKey,
  teamNumber,
  year,
  eventName,
  weekLabel,
  location,
  perf,
  awards,
}: TeamEventBlockProps) {
  const matchesQuery = useEventMatches(eventKey);
  const rankingsQuery = useEventRankings(eventKey);

  const teamMatches = useMemo(
    () =>
      [...(matchesQuery.data?.matches ?? [])]
        .filter((m) => m.red_teams.includes(teamNumber) || m.blue_teams.includes(teamNumber))
        .sort(matchSort),
    [matchesQuery.data, teamNumber],
  );

  const ranking = useMemo(
    () => rankingsQuery.data?.event_rankings.find((r) => r.team_number === teamNumber),
    [rankingsQuery.data, teamNumber],
  );
  const rankTotal = rankingsQuery.data?.event_rankings.length ?? 0;

  // Record: prefer official ranking; else derive from played matches.
  const record = useMemo(() => {
    if (ranking) return { w: ranking.wins, l: ranking.losses, t: ranking.ties };
    let w = 0;
    let l = 0;
    let t = 0;
    for (const m of teamMatches) {
      if (!isPlayed(m)) continue;
      const isRed = m.red_teams.includes(teamNumber);
      const won = (isRed && m.winning_alliance === "red") || (!isRed && m.winning_alliance === "blue");
      const tie = m.winning_alliance !== "red" && m.winning_alliance !== "blue";
      if (tie) t += 1;
      else if (won) w += 1;
      else l += 1;
    }
    return { w, l, t };
  }, [ranking, teamMatches, teamNumber]);

  const accuracy = useMemo(() => {
    let correct = 0;
    let total = 0;
    for (const m of teamMatches) {
      if (!isPlayed(m)) continue;
      const isRed = m.red_teams.includes(teamNumber);
      const prob = isRed ? m.red_win_prob : m.blue_win_prob;
      if (prob === null || prob === undefined) continue;
      const tie = m.winning_alliance !== "red" && m.winning_alliance !== "blue";
      if (tie) continue;
      total += 1;
      const won = (isRed && m.winning_alliance === "red") || (!isRed && m.winning_alliance === "blue");
      if (prob > 0.5 === won) correct += 1;
    }
    return total ? { correct, total, pct: (correct / total) * 100 } : null;
  }, [teamMatches, teamNumber]);

  const hasPills =
    year >= 2015 &&
    perf &&
    [perf.auto_raw, perf.teleop_raw, perf.endgame_raw, perf.raw, perf.ace].some(
      (v) => typeof v === "number",
    );

  return (
    <Card withBorder padding="md" radius="md">
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Stack gap={4} style={{ minWidth: 0 }}>
            <Anchor component={Link} to={`/event/${eventKey}`} fw={700} fz="lg">
              {year} {eventName ?? eventKey}
              {weekLabel ? (
                <Text span c="dimmed" fw={400} fz="md">
                  {" "}
                  ({weekLabel})
                </Text>
              ) : null}
            </Anchor>
            {location ? (
              <Text size="sm" c="dimmed">
                {location}
              </Text>
            ) : null}
            <Group gap="lg">
              {rankTotal > 0 && ranking ? (
                <Text size="sm">
                  Rank:{" "}
                  <Text span fw={700} c={rankColor(ranking.rank, rankTotal)}>
                    {ranking.rank}
                  </Text>
                  <Text span c="dimmed">
                    {" "}
                    / {rankTotal}
                  </Text>
                </Text>
              ) : null}
              <Text size="sm">
                Record: <RecordCell wins={record.w} losses={record.l} ties={record.t} />
              </Text>
            </Group>
            {awards && awards.length > 0 ? (
              <Text size="sm">
                Awards: <Text span fw={500}>{awards.join(", ")}</Text>
              </Text>
            ) : null}
          </Stack>
          {accuracy ? (
            <Badge variant="light" color="grape">
              Prediction Accuracy: {accuracy.correct}/{accuracy.total} ({accuracy.pct.toFixed(0)}%)
            </Badge>
          ) : null}
        </Group>

        {hasPills && perf ? (
          <Group gap={6}>
            <StatPill metric="auto" value={perf.auto_raw as number} size="sm" />
            <StatPill metric="teleop" value={perf.teleop_raw as number} size="sm" />
            <StatPill metric="endgame" value={perf.endgame_raw as number} size="sm" />
            <StatPill metric="raw" value={perf.raw as number} size="sm" />
            <StatPill metric="confidence" value={perf.confidence as number} size="sm" />
            <StatPill metric="ace" value={perf.ace as number} size="sm" />
          </Group>
        ) : null}

        {matchesQuery.isLoading ? (
          <Text size="sm" c="dimmed">
            Loading matches...
          </Text>
        ) : teamMatches.length === 0 ? (
          <Text size="sm" c="dimmed">
            No matches for this team at this event.
          </Text>
        ) : (
          <Table.ScrollContainer minWidth={720}>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={44}>Video</Table.Th>
                  <Table.Th w={80}>Match</Table.Th>
                  <Table.Th>Red</Table.Th>
                  <Table.Th>Blue</Table.Th>
                  <Table.Th w={90}>Score</Table.Th>
                  <Table.Th w={90}>Prediction</Table.Th>
                  <Table.Th w={80}>Outcome</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {teamMatches.map((m) => {
                  const isRed = m.red_teams.includes(teamNumber);
                  const played = isPlayed(m);
                  const prob = isRed ? m.red_win_prob : m.blue_win_prob;
                  const predColor = predictionColor(prob);
                  const won =
                    (isRed && m.winning_alliance === "red") ||
                    (!isRed && m.winning_alliance === "blue");
                  const tie = m.winning_alliance !== "red" && m.winning_alliance !== "blue";
                  const redWin = m.winning_alliance === "red";
                  const blueWin = m.winning_alliance === "blue";
                  return (
                    <Table.Tr key={m.match_key}>
                      <Table.Td>
                        {m.youtube_key ? (
                          <Anchor
                            href={`https://www.youtube.com/watch?v=${m.youtube_key}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            ▶
                          </Anchor>
                        ) : (
                          <Text c="dimmed" span>
                            –
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td>
                        <Anchor component={Link} to={`/match/${eventKey}/${m.match_key}`} size="sm">
                          {m.comp_level.toUpperCase()}
                          {m.comp_level !== "qm" ? `${m.set_number}-` : " "}
                          {m.match_number}
                        </Anchor>
                      </Table.Td>
                      <Table.Td style={isRed ? { backgroundColor: "rgba(220,53,69,0.12)" } : undefined}>
                        <Group gap={8}>
                          {m.red_teams.map((t) => (
                            <TeamName
                              key={t}
                              teamNumber={t}
                              year={year}
                              numberOnly
                              fw={t === teamNumber ? 800 : 500}
                            />
                          ))}
                        </Group>
                      </Table.Td>
                      <Table.Td style={!isRed ? { backgroundColor: "rgba(13,110,253,0.12)" } : undefined}>
                        <Group gap={8}>
                          {m.blue_teams.map((t) => (
                            <TeamName
                              key={t}
                              teamNumber={t}
                              year={year}
                              numberOnly
                              fw={t === teamNumber ? 800 : 500}
                            />
                          ))}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        {played ? (
                          <>
                            <Text span fw={redWin ? 700 : 400} c={redWin ? "red" : undefined}>
                              {m.red_score}
                            </Text>
                            {" - "}
                            <Text span fw={blueWin ? 700 : 400} c={blueWin ? "blue" : undefined}>
                              {m.blue_score}
                            </Text>
                          </>
                        ) : (
                          <Text span c="dimmed">
                            TBD
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td style={predColor ? { backgroundColor: predColor, fontWeight: 600 } : undefined}>
                        {prob !== null && prob !== undefined ? `${Math.round(prob * 100)}%` : "–"}
                      </Table.Td>
                      <Table.Td>
                        {played ? (
                          <Text span fw={600} c={tie ? "dimmed" : won ? "green.6" : "red.6"}>
                            {tie ? "Tie" : won ? "Win" : "Loss"}
                          </Text>
                        ) : (
                          <Text span c="dimmed">
                            –
                          </Text>
                        )}
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
      </Stack>
    </Card>
  );
}
