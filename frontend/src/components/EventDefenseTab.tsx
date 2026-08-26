import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  ActionIcon,
  Anchor,
  Badge,
  Box,
  Button,
  Group,
  SegmentedControl,
  SimpleGrid,
  Slider,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { IconLock, IconLockOpen, IconRefresh, IconX } from "@tabler/icons-react";
import { Link } from "react-router-dom";
import { AceLegend } from "./AceLegend";
import { DataTable, type Column } from "./DataTable";
import { MetricCell, ConfidenceCell } from "./MetricCell";
import { EmptyState } from "./StateWrappers";
import { TeamAvatar } from "./TeamAvatar";
import { TeamName } from "./TeamName";
import type { EventPerfInfo, MatchResponse } from "../types/api";
import {
  countHighDefenseTeams,
  defensePctTopQuartile,
  eventResidualStats,
  matchDefenseRows,
  teamDefenseRows,
  thresholdSliderMax,
  type MatchDefenseRow,
  type TeamDefenseRow,
  type TeamImpactPoint,
} from "../lib/defense";
import type { PercentileThresholds } from "../lib/epa";
import { formatNumber, shortMatchLabel } from "../lib/format";

const FLAG_TINT = "rgba(230, 126, 34, 0.35)";
const FLAG_STRONG = "rgba(211, 84, 0, 0.55)";
const TOP_QUARTILE_ROW = "rgba(230, 126, 34, 0.12)";
const HIGH_DEFENSE_ROW = "rgba(192, 57, 43, 0.16)";

type ViewMode = "teams" | "matches";
type MatchFilter = "all" | "flagged" | "team";

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

/** Warm tint intensity for Defense % pills (scout-focus signal, not ACE green). */
function defensePctStyle(pct: number | null): CSSProperties {
  if (pct === null || pct === undefined) return {};
  let bg = "transparent";
  let fw = 600;
  let color: string | undefined;
  if (pct >= 50) {
    bg = FLAG_STRONG;
    fw = 800;
    color = "#fff";
  } else if (pct >= 35) {
    bg = FLAG_TINT;
    fw = 700;
  } else if (pct >= 20) {
    bg = "rgba(230, 126, 34, 0.18)";
    fw = 600;
  }
  return {
    display: "inline-block",
    minWidth: 56,
    textAlign: "center",
    backgroundColor: bg,
    color,
    borderRadius: 6,
    padding: "4px 8px",
    fontWeight: fw,
    fontSize: pct >= 50 ? 15 : 13,
  };
}

function ImpactSparkline({ series, threshold }: { series: TeamImpactPoint[]; threshold: number }) {
  const w = 120;
  const h = 36;
  const pad = 2;
  if (series.length === 0) {
    return (
      <svg width={w} height={h} aria-hidden style={{ display: "block" }}>
        <line x1={0} y1={h / 2} x2={w} y2={h / 2} stroke="#8884" strokeWidth={1} strokeDasharray="3 3" />
      </svg>
    );
  }
  const values = series.map((p) => p.impact);
  const absMax = Math.max(threshold, ...values.map(Math.abs), 1);
  const barW = Math.max(2, (w - pad * 2) / series.length - 1);
  const midY = h / 2;

  return (
    <Tooltip
      label={series
        .map((p) => `QM${p.matchNumber}: ${p.impact >= 0 ? "+" : ""}${p.impact.toFixed(0)}${p.flagged ? " ★" : ""}`)
        .join(" · ")}
      multiline
      maw={360}
      withArrow
    >
      <svg width={w} height={h} aria-hidden style={{ display: "block", cursor: "default" }}>
        <line x1={0} y1={midY} x2={w} y2={midY} stroke="#8885" strokeWidth={1} />
        {series.map((p, i) => {
          const x = pad + i * ((w - pad * 2) / series.length);
          const barH = (Math.abs(p.impact) / absMax) * (midY - pad);
          const y = p.impact >= 0 ? midY - barH : midY;
          const fill = p.flagged ? "#d35400" : p.impact > 0 ? "#e67e22aa" : "#7f8c8daa";
          return <rect key={p.matchKey} x={x} y={y} width={barW} height={Math.max(1, barH)} fill={fill} rx={1} />;
        })}
      </svg>
    </Tooltip>
  );
}

function ImpactCell({ value, flagged }: { value: number; flagged: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        minWidth: 48,
        textAlign: "center",
        backgroundColor: flagged ? FLAG_STRONG : value > 0 ? "rgba(230,126,34,0.15)" : undefined,
        color: flagged ? "#fff" : undefined,
        borderRadius: 6,
        padding: "4px 6px",
        fontWeight: flagged ? 700 : 500,
      }}
    >
      {value >= 0 ? "+" : ""}
      {formatNumber(value, 1)}
    </span>
  );
}

function AllianceTeams({
  teams,
  year,
  highlight,
  onTeamClick,
}: {
  teams: number[];
  year: number | null;
  highlight?: number | null;
  onTeamClick?: (tn: number) => void;
}) {
  return (
    <Group gap={4} wrap="wrap">
      {teams.map((tn) => (
        <Anchor
          key={tn}
          component="button"
          type="button"
          size="sm"
          fw={highlight === tn ? 800 : 500}
          c={highlight === tn ? "orange" : undefined}
          onClick={() => onTeamClick?.(tn)}
          style={{ background: "none", border: "none", padding: 0, cursor: "pointer" }}
        >
          <TeamName teamNumber={tn} numberOnly year={year ?? undefined} />
        </Anchor>
      ))}
    </Group>
  );
}

export interface EventDefenseTabProps {
  eventKey: string;
  year: number | null;
  matches: MatchResponse[];
  perfs: EventPerfInfo[];
  teamNumbers: number[];
  nicknameOf: (tn: number) => string;
  metricThresholds: {
    ace: PercentileThresholds;
    auto: PercentileThresholds;
    teleop: PercentileThresholds;
    endgame: PercentileThresholds;
  };
  confMedian: number | null;
}

export function EventDefenseTab({
  eventKey,
  year,
  matches,
  perfs,
  teamNumbers,
  nicknameOf,
  metricThresholds,
  confMedian,
}: EventDefenseTabProps) {
  const aceByTeam = useMemo(() => {
    const map = new Map<number, number | null>();
    for (const p of perfs) map.set(p.team_number, p.ace);
    return map;
  }, [perfs]);

  const perfsByTeam = useMemo(() => {
    const map = new Map<number, EventPerfInfo>();
    for (const p of perfs) map.set(p.team_number, p);
    return map;
  }, [perfs]);

  const residualStats = useMemo(
    () => eventResidualStats(matches, aceByTeam),
    [matches, aceByTeam],
  );

  const [thresholdLocked, setThresholdLocked] = useState(true);
  const [threshold, setThreshold] = useState<number | null>(null);
  const [view, setView] = useState<ViewMode>("teams");
  const [selectedTeam, setSelectedTeam] = useState<number | null>(null);
  const [matchFilter, setMatchFilter] = useState<MatchFilter>("all");

  // Keep threshold on event σ while locked (and seed once when stats arrive).
  useEffect(() => {
    if (!residualStats) return;
    setThreshold((prev) => {
      if (thresholdLocked || prev === null) return residualStats.defaultThreshold;
      return prev;
    });
  }, [residualStats, thresholdLocked]);

  const effectiveThreshold = threshold ?? residualStats?.defaultThreshold ?? 15;

  const allMatchRows = useMemo(
    () => matchDefenseRows(matches, aceByTeam, effectiveThreshold),
    [matches, aceByTeam, effectiveThreshold],
  );

  const teamRows = useMemo(
    () => teamDefenseRows(matches, teamNumbers, perfsByTeam, aceByTeam, effectiveThreshold),
    [matches, teamNumbers, perfsByTeam, aceByTeam, effectiveThreshold],
  );

  const topQ = useMemo(() => defensePctTopQuartile(teamRows), [teamRows]);
  const highDefenseCount = useMemo(() => countHighDefenseTeams(teamRows, 50), [teamRows]);
  const sliderMax = useMemo(
    () => thresholdSliderMax(residualStats, allMatchRows),
    [residualStats, allMatchRows],
  );

  const filteredMatchRows = useMemo(() => {
    if (matchFilter === "team" && selectedTeam !== null) {
      return allMatchRows.filter(
        (r) =>
          r.match.red_teams.includes(selectedTeam) || r.match.blue_teams.includes(selectedTeam),
      );
    }
    if (matchFilter === "flagged") {
      return allMatchRows.filter((r) => r.redFlagged || r.blueFlagged);
    }
    return allMatchRows;
  }, [allMatchRows, matchFilter, selectedTeam]);

  const selectTeamForMatches = (tn: number) => {
    setSelectedTeam(tn);
    setMatchFilter("team");
    setView("matches");
  };

  const clearTeamFilter = () => {
    setSelectedTeam(null);
    setMatchFilter("all");
  };

  const resetThreshold = () => {
    if (residualStats) setThreshold(residualStats.defaultThreshold);
    setThresholdLocked(true);
  };

  const teamColumns = useMemo<Column<TeamDefenseRow>[]>(
    () => [
      {
        key: "num",
        header: "#",
        width: 72,
        sortValue: (r) => r.teamNumber,
        render: (r) => (
          <Anchor
            component="button"
            type="button"
            size="sm"
            onClick={() => selectTeamForMatches(r.teamNumber)}
            style={{ background: "none", border: "none", padding: 0, cursor: "pointer" }}
          >
            <TeamName teamNumber={r.teamNumber} numberOnly year={year ?? undefined} />
          </Anchor>
        ),
      },
      {
        key: "team",
        header: "Team",
        sortValue: (r) => nicknameOf(r.teamNumber).toLowerCase(),
        exportValue: (r) => nicknameOf(r.teamNumber),
        render: (r) => (
          <Group gap="sm" wrap="nowrap">
            <TeamAvatar teamNumber={r.teamNumber} size={28} radius={6} bordered />
            <Anchor
              component="button"
              type="button"
              size="sm"
              onClick={() => selectTeamForMatches(r.teamNumber)}
              style={{ background: "none", border: "none", padding: 0, cursor: "pointer", textAlign: "left" }}
            >
              <TeamName teamNumber={r.teamNumber} withNumber={false} year={year ?? undefined} />
            </Anchor>
          </Group>
        ),
      },
      {
        key: "defensePct",
        header: "Defense %",
        width: 100,
        sortValue: (r) => r.defensePct,
        exportValue: (r) => (r.defensePct !== null ? Math.round(r.defensePct * 10) / 10 : null),
        render: (r) => (
          <span style={defensePctStyle(r.defensePct)}>
            {r.defensePct !== null ? `${formatNumber(r.defensePct, 0)}%` : "-"}
          </span>
        ),
      },
      {
        key: "flagged",
        header: "Flagged",
        width: 90,
        sortValue: (r) => r.flaggedCount,
        exportValue: (r) => `${r.flaggedCount}/${r.matchCount}`,
        render: (r) => (
          <Badge
            size="sm"
            variant={r.flaggedCount > 0 ? "filled" : "light"}
            color={r.flaggedCount / Math.max(1, r.matchCount) >= 0.5 ? "orange" : "gray"}
          >
            {r.flaggedCount}/{r.matchCount}
          </Badge>
        ),
      },
      {
        key: "meanImpact",
        header: "Mean Imp",
        width: 90,
        sortValue: (r) => r.meanImpact,
        render: (r) => formatNumber(r.meanImpact, 1),
      },
      {
        key: "medianImpact",
        header: "Med Imp",
        width: 85,
        sortValue: (r) => r.medianImpact,
        render: (r) => formatNumber(r.medianImpact, 1),
      },
      {
        key: "maxImpact",
        header: "Max Imp",
        width: 90,
        sortValue: (r) => r.maxImpact,
        render: (r) =>
          r.maxImpact !== null ? (
            <ImpactCell value={r.maxImpact} flagged={r.maxImpact > effectiveThreshold} />
          ) : (
            "-"
          ),
      },
      {
        key: "sumImpact",
        header: "Sum Imp",
        width: 85,
        sortValue: (r) => r.sumImpact,
        render: (r) => formatNumber(r.sumImpact, 0),
      },
      {
        key: "stdImpact",
        header: "σ Imp",
        width: 75,
        sortValue: (r) => r.stdImpact,
        render: (r) => formatNumber(r.stdImpact, 1),
      },
      {
        key: "spark",
        header: "Impact by match",
        width: 130,
        exportValue: null,
        sortValue: (r) => r.meanImpact,
        render: (r) => <ImpactSparkline series={r.impactSeries} threshold={effectiveThreshold} />,
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
    ],
    // selectTeamForMatches is stable enough via closures; recompute when threshold/ACE change
    [year, nicknameOf, effectiveThreshold, confMedian, metricThresholds],
  );

  const matchColumns = useMemo<Column<MatchDefenseRow>[]>(
    () => [
      {
        key: "match",
        header: "Match",
        width: 80,
        sortValue: (r) => r.match.match_number,
        exportValue: (r) =>
          shortMatchLabel(r.match.comp_level, r.match.set_number, r.match.match_number),
        render: (r) => (
          <Anchor component={Link} to={`/match/${eventKey}/${r.match.match_key}`} size="sm" fw={600}>
            {shortMatchLabel(r.match.comp_level, r.match.set_number, r.match.match_number)}
          </Anchor>
        ),
      },
      {
        key: "red",
        header: "Red",
        exportValue: (r) => r.match.red_teams.join(" "),
        cellStyle: () => ({ backgroundColor: "rgba(220,53,69,0.08)" }),
        render: (r) => (
          <AllianceTeams
            teams={r.match.red_teams}
            year={year}
            highlight={selectedTeam}
            onTeamClick={selectTeamForMatches}
          />
        ),
      },
      {
        key: "blue",
        header: "Blue",
        exportValue: (r) => r.match.blue_teams.join(" "),
        cellStyle: () => ({ backgroundColor: "rgba(13,110,253,0.08)" }),
        render: (r) => (
          <AllianceTeams
            teams={r.match.blue_teams}
            year={year}
            highlight={selectedTeam}
            onTeamClick={selectTeamForMatches}
          />
        ),
      },
      {
        key: "redScore",
        header: "Red Scr",
        width: 80,
        sortValue: (r) => r.match.red_score,
        render: (r) => formatNumber(r.match.red_score, 0),
      },
      {
        key: "blueScore",
        header: "Blue Scr",
        width: 85,
        sortValue: (r) => r.match.blue_score,
        render: (r) => formatNumber(r.match.blue_score, 0),
      },
      {
        key: "redPred",
        header: "Red Pred",
        width: 85,
        sortValue: (r) => r.redPred,
        render: (r) => formatNumber(r.redPred, 0),
      },
      {
        key: "bluePred",
        header: "Blue Pred",
        width: 90,
        sortValue: (r) => r.bluePred,
        render: (r) => formatNumber(r.bluePred, 0),
      },
      {
        key: "redImpact",
        header: "Red Impact",
        width: 100,
        sortValue: (r) => r.redImpact,
        cellStyle: (r) => {
          if (selectedTeam !== null && !r.match.red_teams.includes(selectedTeam)) {
            return { opacity: 0.35 };
          }
          return undefined;
        },
        render: (r) => <ImpactCell value={r.redImpact} flagged={r.redFlagged} />,
      },
      {
        key: "blueImpact",
        header: "Blue Impact",
        width: 105,
        sortValue: (r) => r.blueImpact,
        cellStyle: (r) => {
          if (selectedTeam !== null && !r.match.blue_teams.includes(selectedTeam)) {
            return { opacity: 0.35 };
          }
          return undefined;
        },
        render: (r) => <ImpactCell value={r.blueImpact} flagged={r.blueFlagged} />,
      },
      {
        key: "teamImpact",
        header: "Team Impact",
        width: 105,
        sortValue: (r) => {
          if (selectedTeam === null) return null;
          if (r.match.red_teams.includes(selectedTeam)) return r.redImpact;
          if (r.match.blue_teams.includes(selectedTeam)) return r.blueImpact;
          return null;
        },
        exportValue: (r) => {
          if (selectedTeam === null) return null;
          if (r.match.red_teams.includes(selectedTeam)) return r.redImpact;
          if (r.match.blue_teams.includes(selectedTeam)) return r.blueImpact;
          return null;
        },
        render: (r) => {
          if (selectedTeam === null) return <Text size="sm" c="dimmed">—</Text>;
          const onRed = r.match.red_teams.includes(selectedTeam);
          const onBlue = r.match.blue_teams.includes(selectedTeam);
          if (!onRed && !onBlue) return "-";
          const impact = onRed ? r.redImpact : r.blueImpact;
          const flagged = onRed ? r.redFlagged : r.blueFlagged;
          return <ImpactCell value={impact} flagged={flagged} />;
        },
      },
    ],
    [eventKey, year, selectedTeam],
  );

  if (!residualStats || teamRows.length === 0) {
    return (
      <EmptyState>
        No defense indicator data yet (needs played qualification matches with score predictions).
      </EmptyState>
    );
  }

  return (
    <Stack gap="md">
      <Stack gap={4}>
        <Text size="sm" c="dimmed">
          Defensive Impact = opposing alliance predicted score − actual score. Defense Indicator
          (Defense %) = share of a team&apos;s quals where Impact &gt; X. This is a{" "}
          <Text span fw={600} c="dimmed">
            scout-focusing flag
          </Text>
          , not proof a team played defense — scoring failures and intermittent defense add noise.
        </Text>
      </Stack>

      <SimpleGrid cols={{ base: 2, sm: 3, md: 6 }} spacing="md">
        <InsightStat label="Event σ (X default)" value={formatNumber(residualStats.std, 1)} />
        <InsightStat label="Threshold X" value={`${formatNumber(effectiveThreshold, 1)} pts`} />
        <InsightStat label="Mean |residual|" value={formatNumber(residualStats.meanAbs, 1)} />
        <InsightStat
          label="Large-Δ matches"
          value={`${residualStats.largeImpactMatchCount}/${allMatchRows.length}`}
        />
        <InsightStat label="Teams Defense % ≥ 50" value={String(highDefenseCount)} />
        <InsightStat label="Alliance residuals" value={String(residualStats.count)} />
      </SimpleGrid>

      <Box
        p="sm"
        style={{
          border: "1px solid var(--mantine-color-default-border)",
          borderRadius: 8,
        }}
      >
        <Group justify="space-between" align="flex-start" mb="xs" wrap="wrap">
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              Defense threshold X = {formatNumber(effectiveThreshold, 1)} pts
              {thresholdLocked ? " (locked to event σ)" : " (custom)"}
            </Text>
            <Text size="xs" c="dimmed">
              Unlock to tune how large an opponent underperformance must be to flag a match.
            </Text>
          </Stack>
          <Group gap="xs">
            <Tooltip label={thresholdLocked ? "Unlock slider" : "Lock slider"}>
              <ActionIcon
                variant={thresholdLocked ? "filled" : "light"}
                color="orange"
                aria-label={thresholdLocked ? "Unlock threshold" : "Lock threshold"}
                onClick={() => setThresholdLocked((v) => !v)}
              >
                {thresholdLocked ? <IconLock size={16} /> : <IconLockOpen size={16} />}
              </ActionIcon>
            </Tooltip>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconRefresh size={14} />}
              onClick={resetThreshold}
            >
              Reset to event σ
            </Button>
          </Group>
        </Group>
        <Slider
          min={0}
          max={sliderMax}
          step={0.5}
          value={effectiveThreshold}
          onChange={(v) => {
            if (thresholdLocked) return;
            setThreshold(v);
          }}
          disabled={thresholdLocked}
          color="orange"
          marks={[
            { value: 0, label: "0" },
            {
              value: residualStats.defaultThreshold,
              label: `σ ${formatNumber(residualStats.defaultThreshold, 0)}`,
            },
            { value: sliderMax, label: String(sliderMax) },
          ]}
          mb="lg"
        />
      </Box>

      <Group justify="space-between" wrap="wrap">
        <SegmentedControl
          value={view}
          onChange={(v) => setView(v as ViewMode)}
          data={[
            { label: "Teams", value: "teams" },
            { label: "Matches", value: "matches" },
          ]}
        />
        {view === "matches" ? (
          <Group gap="xs">
            <SegmentedControl
              size="xs"
              value={matchFilter}
              onChange={(v) => setMatchFilter(v as MatchFilter)}
              data={[
                { label: "All", value: "all" },
                { label: "Flagged", value: "flagged" },
                {
                  label: selectedTeam !== null ? `Team ${selectedTeam}` : "Team",
                  value: "team",
                  disabled: selectedTeam === null,
                },
              ]}
            />
          </Group>
        ) : null}
      </Group>

      {selectedTeam !== null ? (
        <Badge
          size="lg"
          variant="outline"
          color="orange"
          rightSection={
            <ActionIcon
              size="xs"
              color="orange"
              radius="xl"
              variant="transparent"
              aria-label="Clear team filter"
              onClick={clearTeamFilter}
            >
              <IconX size={12} />
            </ActionIcon>
          }
        >
          Filtering team {selectedTeam}
        </Badge>
      ) : null}

      {view === "teams" ? (
        <Stack gap="sm">
          <AceLegend />
          <DataTable
            data={teamRows}
            columns={teamColumns}
            getRowKey={(r) => r.teamNumber}
            initialSort={{ key: "defensePct", dir: "desc" }}
            minWidth={1400}
            stickyHeader
            defaultPageSize={50}
            exportFileName={`${eventKey}-defense`}
            rowStyle={(r) => {
              if ((r.defensePct ?? 0) >= 50) return { backgroundColor: HIGH_DEFENSE_ROW };
              if (topQ !== null && (r.defensePct ?? 0) >= topQ) {
                return { backgroundColor: TOP_QUARTILE_ROW };
              }
              return undefined;
            }}
          />
        </Stack>
      ) : (
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            Red Impact = blue predicted − blue actual (opponents underperformed while facing red).
            Blue Impact is the mirror. Flagged cells exceed X = {formatNumber(effectiveThreshold, 1)}.
          </Text>
          <DataTable
            data={filteredMatchRows}
            columns={matchColumns}
            getRowKey={(r) => r.match.match_key}
            initialSort={{ key: "match", dir: "asc" }}
            minWidth={1200}
            stickyHeader
            defaultPageSize={50}
            exportFileName={`${eventKey}-defense-matches`}
            rowStyle={(r) => {
              if (r.redFlagged || r.blueFlagged) return { backgroundColor: TOP_QUARTILE_ROW };
              return undefined;
            }}
          />
        </Stack>
      )}
    </Stack>
  );
}
