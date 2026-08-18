import type { ReactNode } from "react";
import { Stack, Text, Tooltip } from "@mantine/core";
import { aceColor, type PercentileThresholds } from "../lib/epa";
import { formatNumber } from "../lib/format";
import type { TeamTrajectory, TrajectoryPoint } from "../lib/eventTrajectory";
import { METRIC_STYLES, type MetricKey } from "../lib/metrics";

export type TrajectoryView = "sparkline" | "heat" | "both";

/** Default chart width for the by-match metrics table. */
export const TRAJECTORY_CHART_WIDTH = 440;
const SPARK_H = 44;
const HEAT_H = 12;
const PAD = 3;

interface MetricTrajectoryCellProps {
  trajectory: TeamTrajectory;
  metric: MetricKey;
  thresholds: PercentileThresholds;
  view: TrajectoryView;
  width?: number;
  /** Unique id for SVG gradient defs (e.g. team number). */
  cellId: string | number;
}

function chartX(index: number, count: number, width: number): number {
  return ((index + 0.5) / count) * width;
}

function chartY(value: number, min: number, max: number): number {
  const range = max - min || 1;
  return PAD + (1 - (value - min) / range) * (SPARK_H - PAD * 2);
}

function lineSegments(
  points: TrajectoryPoint[],
  width: number,
  min: number,
  max: number,
  played: boolean,
): string[] {
  const segments: string[] = [];
  let current: string[] = [];

  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    if (p.value === null || p.played !== played) {
      if (current.length >= 2) segments.push(current.join(" "));
      current = [];
      continue;
    }
    current.push(`${chartX(i, points.length, width)},${chartY(p.value, min, max)}`);
  }
  if (current.length >= 2) segments.push(current.join(" "));

  return segments;
}

function areaPath(points: TrajectoryPoint[], width: number, min: number, max: number): string | null {
  const coords: Array<[number, number]> = [];
  for (let i = 0; i < points.length; i++) {
    const v = points[i].value;
    if (v === null) continue;
    coords.push([chartX(i, points.length, width), chartY(v, min, max)]);
  }
  if (coords.length < 2) return null;

  const baseline = SPARK_H - PAD;
  let d = `M ${coords[0][0]},${baseline} L ${coords[0][0]},${coords[0][1]}`;
  for (let i = 1; i < coords.length; i++) {
    d += ` L ${coords[i][0]},${coords[i][1]}`;
  }
  d += ` L ${coords[coords.length - 1][0]},${baseline} Z`;
  return d;
}

function gradientStops(
  points: TrajectoryPoint[],
  thresholds: PercentileThresholds,
): Array<{ offset: string; color: string }> {
  const withValues = points
    .map((p, i) => ({ p, i }))
    .filter(({ p }) => p.value !== null);
  if (withValues.length === 0) {
    return [{ offset: "0%", color: "#ccc" }, { offset: "100%", color: "#ccc" }];
  }
  if (withValues.length === 1) {
    const c = aceColor(withValues[0].p.value, thresholds) ?? "#888";
    return [{ offset: "0%", color: c }, { offset: "100%", color: c }];
  }
  const last = points.length - 1;
  return withValues.map(({ p, i }) => ({
    offset: `${(i / last) * 100}%`,
    color: aceColor(p.value, thresholds) ?? "#88888855",
  }));
}

function Sparkline({
  points,
  thresholds,
  metricColor,
  gradientId,
  width,
}: {
  points: TrajectoryPoint[];
  thresholds: PercentileThresholds;
  metricColor: string;
  gradientId: string;
  width: number;
}) {
  const values = points.map((p) => p.value).filter((v): v is number => v !== null);
  if (values.length === 0) {
    return (
      <svg width={width} height={SPARK_H} aria-hidden style={{ display: "block" }}>
        <line
          x1={0}
          y1={SPARK_H / 2}
          x2={width}
          y2={SPARK_H / 2}
          stroke="#ccc"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
      </svg>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const playedLine = lineSegments(points, width, min, max, true);
  const predLine = lineSegments(points, width, min, max, false);
  const area = areaPath(points, width, min, max);
  const stops = gradientStops(points, thresholds);

  return (
    <svg width={width} height={SPARK_H} aria-hidden style={{ display: "block" }}>
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
          {stops.map((s) => (
            <stop key={s.offset} offset={s.offset} stopColor={s.color} stopOpacity={0.55} />
          ))}
        </linearGradient>
      </defs>
      {area && <path d={area} fill={`url(#${gradientId})`} stroke="none" />}
      {predLine.map((seg, i) => (
        <polyline
          key={`pred-${i}`}
          points={seg}
          fill="none"
          stroke={metricColor}
          strokeWidth={2}
          strokeDasharray="5 4"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.65}
        />
      ))}
      {playedLine.map((seg, i) => (
        <polyline
          key={`act-${i}`}
          points={seg}
          fill="none"
          stroke={metricColor}
          strokeWidth={2.25}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
    </svg>
  );
}

function HeatStrip({
  points,
  thresholds,
  width,
  metric,
}: {
  points: TrajectoryPoint[];
  thresholds: PercentileThresholds;
  width: number;
  metric: MetricKey;
}) {
  const n = points.length;
  const cellW = width / n;
  const gap = n > 1 ? 1 : 0;

  return (
    <svg width={width} height={HEAT_H} aria-hidden style={{ display: "block" }}>
      {points.map((p, i) => {
        const bg =
          p.value !== null
            ? aceColor(p.value, thresholds) ?? "var(--mantine-color-gray-4)"
            : "var(--mantine-color-gray-3)";
        const x = i * cellW;
        const w = Math.max(1, cellW - (i < n - 1 ? gap : 0));
        return (
          <g key={p.matchKey}>
            <title>
              {p.value !== null
                ? `${p.label}: ${formatNumber(p.value, metricDecimals(metric))}${p.played ? "" : " (pred)"}`
                : `${p.label}: —`}
            </title>
            <rect
              x={x}
              y={0}
              width={w}
              height={HEAT_H}
              fill={bg}
              opacity={p.played ? 1 : 0.45}
              stroke={p.played ? "none" : "var(--mantine-color-gray-5)"}
              strokeWidth={p.played ? 0 : 1}
              strokeDasharray={p.played ? undefined : "2 2"}
              rx={2}
              style={{ cursor: "default" }}
            />
          </g>
        );
      })}
    </svg>
  );
}

function metricDecimals(metric: MetricKey): number {
  return metric === "confidence" ? 2 : 1;
}

function tooltipBody(trajectory: TeamTrajectory, metric: MetricKey): ReactNode {
  const label = METRIC_STYLES[metric].label;
  const dec = metricDecimals(metric);
  const lines = trajectory.points.filter((p) => p.value !== null);
  if (lines.length === 0) return "No match data";

  return (
    <Stack gap={2}>
      <Text size="xs" fw={600}>
        {label} by match
      </Text>
      {lines.map((p) => (
        <Text key={p.matchKey} size="xs">
          {p.label}: {formatNumber(p.value, dec)}
          {!p.played ? " (pred)" : ""}
        </Text>
      ))}
      {trajectory.delta !== null && (
        <Text size="xs" c="dimmed">
          Δ {formatNumber(trajectory.delta, dec)} · mom{" "}
          {trajectory.momentum !== null ? formatNumber(trajectory.momentum, dec) : "—"}
        </Text>
      )}
    </Stack>
  );
}

/** Inline sparkline + heat strip for per-match metric trajectories at an event. */
export function MetricTrajectoryCell({
  trajectory,
  metric,
  thresholds,
  view,
  width = TRAJECTORY_CHART_WIDTH,
  cellId,
}: MetricTrajectoryCellProps) {
  const { points } = trajectory;
  if (points.length === 0) {
    return (
      <Text size="xs" c="dimmed">
        —
      </Text>
    );
  }

  const metricColor = METRIC_STYLES[metric].color;
  const gradientId = `traj-grad-${cellId}`;

  const content = (
    <Stack gap={4} style={{ width, minWidth: width }}>
      {(view === "sparkline" || view === "both") && (
        <Sparkline
          points={points}
          thresholds={thresholds}
          metricColor={metricColor}
          gradientId={gradientId}
          width={width}
        />
      )}
      {(view === "heat" || view === "both") && (
        <HeatStrip points={points} thresholds={thresholds} width={width} metric={metric} />
      )}
    </Stack>
  );

  return (
    <Tooltip label={tooltipBody(trajectory, metric)} multiline w={220} withArrow position="left">
      {content}
    </Tooltip>
  );
}
