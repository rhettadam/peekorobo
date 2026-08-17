import { useMemo, useState } from "react";
import {
  Card,
  Group,
  SegmentedControl,
  Select,
  Stack,
  Text,
  useComputedColorScheme,
} from "@mantine/core";
import { useNavigate } from "react-router-dom";
import {
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { AceLegend } from "./AceLegend";
import { MetricCell } from "./MetricCell";
import { RecordCell } from "./RecordCell";
import { TeamAvatar } from "./TeamAvatar";
import { aceColor, computePercentiles, median, type PercentileThresholds } from "../lib/epa";
import { formatNumber } from "../lib/format";

export type BubbleMetricKey =
  | "ace"
  | "raw"
  | "auto"
  | "teleop"
  | "endgame"
  | "confidence"
  | "wins"
  | "losses"
  | "winRate"
  | "rank";

export interface BubbleTeam {
  teamNumber: number;
  nickname?: string;
  ace: number | null;
  raw?: number | null;
  auto?: number | null;
  teleop?: number | null;
  endgame?: number | null;
  confidence?: number | null;
  wins?: number | null;
  losses?: number | null;
  ties?: number | null;
  rank?: number | null;
  /** Optional extra ACE (e.g. season ACE on an event chart). */
  seasonAce?: number | null;
}

const METRIC_LABEL: Record<BubbleMetricKey, string> = {
  ace: "ACE",
  raw: "RAW",
  auto: "Auto",
  teleop: "Teleop",
  endgame: "Endgame",
  confidence: "Confidence",
  wins: "Wins",
  losses: "Losses",
  winRate: "Win rate",
  rank: "ACE rank",
};

const ALL_METRICS: BubbleMetricKey[] = [
  "ace",
  "raw",
  "auto",
  "teleop",
  "endgame",
  "confidence",
  "wins",
  "losses",
  "winRate",
  "rank",
];

const PRESETS: Array<{ id: string; label: string; x: BubbleMetricKey; y: BubbleMetricKey }> = [
  { id: "phases", label: "Auto vs Teleop", x: "auto", y: "teleop" },
  { id: "end", label: "Teleop vs Endgame", x: "teleop", y: "endgame" },
  { id: "ace-conf", label: "ACE vs Confidence", x: "confidence", y: "ace" },
  { id: "ace-rank", label: "ACE vs Rank", x: "ace", y: "rank" },
  { id: "wins", label: "ACE vs Wins", x: "wins", y: "ace" },
];

interface Point {
  x: number;
  y: number;
  z: number;
  teamNumber: number;
  color: string;
  highlighted: boolean;
}

function metricValue(t: BubbleTeam, key: BubbleMetricKey): number | null {
  switch (key) {
    case "ace":
      return t.ace;
    case "raw":
      return t.raw ?? null;
    case "auto":
      return t.auto ?? null;
    case "teleop":
      return t.teleop ?? null;
    case "endgame":
      return t.endgame ?? null;
    case "confidence":
      return t.confidence ?? null;
    case "wins":
      return t.wins ?? null;
    case "losses":
      return t.losses ?? null;
    case "rank":
      return t.rank ?? null;
    case "winRate": {
      const w = t.wins ?? 0;
      const l = t.losses ?? 0;
      const ti = t.ties ?? 0;
      const total = w + l + ti;
      return total > 0 ? (w / total) * 100 : null;
    }
    default:
      return null;
  }
}

function decimalsFor(key: BubbleMetricKey): number {
  if (key === "wins" || key === "losses" || key === "rank") return 0;
  if (key === "confidence") return 2;
  if (key === "winRate") return 1;
  return 1;
}

interface TeamBubbleChartProps {
  teams: BubbleTeam[];
  year: number;
  nicknameOf?: (teamNumber: number) => string;
  highlighted?: Iterable<number>;
  defaultX?: BubbleMetricKey;
  defaultY?: BubbleMetricKey;
  metrics?: BubbleMetricKey[];
  height?: number;
  aceThresholds?: PercentileThresholds;
}

export function TeamBubbleChart({
  teams,
  year,
  nicknameOf,
  highlighted,
  defaultX = "auto",
  defaultY = "teleop",
  metrics,
  height = 560,
  aceThresholds,
}: TeamBubbleChartProps) {
  const navigate = useNavigate();
  const scheme = useComputedColorScheme("dark", { getInitialValueInEffect: true });
  const isDark = scheme === "dark";
  const available = metrics ?? ALL_METRICS;
  const [xAxis, setXAxis] = useState<BubbleMetricKey>(
    available.includes(defaultX) ? defaultX : available[0],
  );
  const [yAxis, setYAxis] = useState<BubbleMetricKey>(
    available.includes(defaultY) ? defaultY : available[1] ?? available[0],
  );
  const [sizeMode, setSizeMode] = useState<"uniform" | "confidence">("uniform");

  const highlightSet = useMemo(() => new Set(highlighted ?? []), [highlighted]);
  const nick = (n: number) => nicknameOf?.(n) ?? teams.find((t) => t.teamNumber === n)?.nickname ?? "";

  const teamByNumber = useMemo(() => {
    const m = new Map<number, BubbleTeam>();
    for (const t of teams) m.set(t.teamNumber, t);
    return m;
  }, [teams]);

  const thresholds = useMemo(
    () => aceThresholds ?? computePercentiles(teams.map((t) => t.ace)),
    [aceThresholds, teams],
  );

  const axisOptions = useMemo(
    () => available.map((k) => ({ value: k, label: METRIC_LABEL[k] })),
    [available],
  );

  const presets = useMemo(
    () => PRESETS.filter((p) => available.includes(p.x) && available.includes(p.y)),
    [available],
  );

  const { points, highlightPoints, medX, medY } = useMemo(() => {
    const raw: Point[] = [];
    for (const t of teams) {
      const x = metricValue(t, xAxis);
      const y = metricValue(t, yAxis);
      if (x === null || y === null) continue;
      const color = aceColor(t.ace, thresholds) ?? "#616161";
      const z =
        sizeMode === "confidence" && typeof t.confidence === "number"
          ? Math.max(0.15, Math.min(1, t.confidence))
          : 0.55;
      raw.push({
        x,
        y,
        z,
        teamNumber: t.teamNumber,
        color,
        highlighted: highlightSet.has(t.teamNumber),
      });
    }
    // Low ACE first so the high-ACE (purple) dots paint on top.
    raw.sort((a, b) => {
      const aa = teamByNumber.get(a.teamNumber)?.ace ?? -Infinity;
      const bb = teamByNumber.get(b.teamNumber)?.ace ?? -Infinity;
      return aa - bb;
    });
    const xs = raw.map((p) => p.x);
    const ys = raw.map((p) => p.y);
    return {
      points: raw,
      highlightPoints: raw.filter((p) => p.highlighted),
      medX: median(xs),
      medY: median(ys),
    };
  }, [teams, xAxis, yAxis, sizeMode, thresholds, highlightSet, teamByNumber]);

  const zRange: [number, number] =
    sizeMode === "confidence"
      ? teams.length > 400
        ? [28, 120]
        : [50, 180]
      : teams.length > 400
        ? [36, 36]
        : teams.length > 80
          ? [64, 64]
          : [90, 90];

  const grid = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";
  const tick = isDark ? "#c1c2c5" : "#495057";
  const refStroke = isDark ? "rgba(255,255,255,0.28)" : "rgba(0,0,0,0.28)";

  const activePreset = presets.find((p) => p.x === xAxis && p.y === yAxis)?.id ?? "";

  return (
    <Stack gap="md">
      <Group gap="sm" align="flex-end" wrap="wrap">
        <Select
          label="X axis"
          data={axisOptions}
          value={xAxis}
          onChange={(v) => v && setXAxis(v as BubbleMetricKey)}
          allowDeselect={false}
          w={150}
        />
        <Select
          label="Y axis"
          data={axisOptions}
          value={yAxis}
          onChange={(v) => v && setYAxis(v as BubbleMetricKey)}
          allowDeselect={false}
          w={150}
        />
        <Stack gap={4}>
          <Text size="sm" fw={500}>
            Dot size
          </Text>
          <SegmentedControl
            size="xs"
            value={sizeMode}
            onChange={(v) => setSizeMode(v as "uniform" | "confidence")}
            data={[
              { value: "uniform", label: "Uniform" },
              { value: "confidence", label: "By confidence" },
            ]}
          />
        </Stack>
        <Text size="xs" c="dimmed" pb={8}>
          {points.length.toLocaleString()} teams · color is ACE percentile
        </Text>
      </Group>

      {presets.length > 0 ? (
        <Group gap={6} wrap="wrap">
          {presets.map((p) => (
            <Text
              key={p.id}
              component="button"
              size="xs"
              fw={activePreset === p.id ? 700 : 500}
              onClick={() => {
                setXAxis(p.x);
                setYAxis(p.y);
              }}
              style={{
                cursor: "pointer",
                border: "1px solid var(--mantine-color-default-border)",
                background:
                  activePreset === p.id ? "var(--mantine-color-peeko-6)" : "var(--mantine-color-body)",
                color: activePreset === p.id ? "#111" : undefined,
                borderRadius: 6,
                padding: "4px 10px",
              }}
            >
              {p.label}
            </Text>
          ))}
        </Group>
      ) : null}

      <AceLegend />

      <Card withBorder padding="md" radius="md">
        {points.length === 0 ? (
          <Text size="sm" c="dimmed" ta="center" py="xl">
            No teams with both {METRIC_LABEL[xAxis]} and {METRIC_LABEL[yAxis]}.
          </Text>
        ) : (
          <ResponsiveContainer width="100%" height={height}>
            <ScatterChart
              margin={{ top: 12, right: 16, bottom: 28, left: 8 }}
              style={{ cursor: "pointer" }}
              onClick={(state) => {
                const tn = (state as { activePayload?: Array<{ payload?: Point }> })?.activePayload?.[0]
                  ?.payload?.teamNumber;
                if (tn) navigate(`/team/${tn}/${year}`);
              }}
            >
              <CartesianGrid stroke={grid} strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="x"
                name={METRIC_LABEL[xAxis]}
                reversed={xAxis === "rank"}
                tick={{ fill: tick, fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: grid }}
                label={{
                  value: METRIC_LABEL[xAxis],
                  position: "insideBottom",
                  offset: -16,
                  fill: tick,
                  fontSize: 12,
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name={METRIC_LABEL[yAxis]}
                reversed={yAxis === "rank"}
                tick={{ fill: tick, fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: grid }}
                width={58}
                label={{
                  value: METRIC_LABEL[yAxis],
                  angle: -90,
                  position: "insideLeft",
                  fill: tick,
                  fontSize: 12,
                }}
              />
              <ZAxis type="number" dataKey="z" range={zRange} />
              {medX !== null ? (
                <ReferenceLine
                  x={medX}
                  stroke={refStroke}
                  strokeDasharray="4 4"
                  label={{ value: "median", fill: tick, fontSize: 10, position: "insideTop" }}
                />
              ) : null}
              {medY !== null ? (
                <ReferenceLine
                  y={medY}
                  stroke={refStroke}
                  strokeDasharray="4 4"
                  label={{ value: "median", fill: tick, fontSize: 10, position: "insideRight" }}
                />
              ) : null}
              <Tooltip
                cursor={{ strokeDasharray: "3 3", stroke: isDark ? "#ffdd00" : "#7a5a00" }}
                content={({ payload }) => {
                  const p = payload?.[0]?.payload as Point | undefined;
                  if (!p) return null;
                  const t = teamByNumber.get(p.teamNumber);
                  if (!t) return null;
                  return (
                    <Card withBorder padding="sm" radius="md" shadow="md" style={{ minWidth: 220 }}>
                      <Group gap={8} wrap="nowrap" mb={8}>
                        <TeamAvatar teamNumber={t.teamNumber} size={28} radius={6} bordered />
                        <div style={{ minWidth: 0 }}>
                          <Text fw={800} size="sm" lh={1.15}>
                            {t.teamNumber}
                          </Text>
                          <Text size="xs" c="dimmed" lineClamp={1}>
                            {nick(t.teamNumber)}
                          </Text>
                        </div>
                      </Group>
                      <Group gap={6} mb={6}>
                        <Text size="xs" c="dimmed">
                          ACE
                        </Text>
                        <MetricCell value={t.ace} thresholds={thresholds} />
                        {t.rank ? (
                          <Text size="xs" c="dimmed">
                            #{t.rank}
                          </Text>
                        ) : null}
                      </Group>
                      <Text size="xs">
                        {METRIC_LABEL[xAxis]} {formatNumber(p.x, decimalsFor(xAxis))}
                        {" · "}
                        {METRIC_LABEL[yAxis]} {formatNumber(p.y, decimalsFor(yAxis))}
                      </Text>
                      <Text size="xs" c="dimmed">
                        Auto {formatNumber(t.auto)} · Teleop {formatNumber(t.teleop)} · Endgame{" "}
                        {formatNumber(t.endgame)}
                      </Text>
                      {t.wins != null || t.losses != null ? (
                        <Group gap={6} mt={4}>
                          <Text size="xs" c="dimmed">
                            Record
                          </Text>
                          <RecordCell wins={t.wins} losses={t.losses} ties={t.ties} />
                        </Group>
                      ) : null}
                      {t.confidence != null ? (
                        <Text size="xs" c="dimmed">
                          Confidence {formatNumber(t.confidence, 2)}
                        </Text>
                      ) : null}
                      {t.seasonAce != null ? (
                        <Text size="xs" c="dimmed">
                          Season ACE {formatNumber(t.seasonAce)}
                        </Text>
                      ) : null}
                      <Text size="xs" c="dimmed" mt={6}>
                        Click to open team
                      </Text>
                    </Card>
                  );
                }}
              />
              <Scatter
                data={points}
                isAnimationActive={false}
                cursor="pointer"
                onClick={(state) => {
                  const tn = (state as { payload?: Point })?.payload?.teamNumber;
                  if (tn) navigate(`/team/${tn}/${year}`);
                }}
              >
                {points.map((p) => (
                  <Cell
                    key={p.teamNumber}
                    fill={p.color}
                    fillOpacity={1}
                    stroke="rgba(0,0,0,0.55)"
                    strokeWidth={0.7}
                  />
                ))}
              </Scatter>
              {highlightPoints.length > 0 ? (
                <Scatter
                  data={highlightPoints}
                  isAnimationActive={false}
                  cursor="pointer"
                  legendType="none"
                  onClick={(state) => {
                    const tn = (state as { payload?: Point })?.payload?.teamNumber;
                    if (tn) navigate(`/team/${tn}/${year}`);
                  }}
                >
                  {highlightPoints.map((p) => (
                    <Cell
                      key={`hl-${p.teamNumber}`}
                      fill={p.color}
                      fillOpacity={1}
                      stroke="#ffdd00"
                      strokeWidth={2.4}
                    />
                  ))}
                </Scatter>
              ) : null}
            </ScatterChart>
          </ResponsiveContainer>
        )}
      </Card>
    </Stack>
  );
}
