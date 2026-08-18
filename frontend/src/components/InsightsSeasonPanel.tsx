import type { ReactNode } from "react";
import { useMemo } from "react";
import {
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { BarChart, ScatterChart } from "@mantine/charts";
import { IconBook, IconBrandYoutube, IconPlayerPlay } from "@tabler/icons-react";
import { useLeaderboard, useSearchIndex } from "../api/queries";
import { ErrorState, LoadingState } from "./StateWrappers";
import { AceLegend } from "./AceLegend";
import { MetricCell, ConfidenceCell } from "./MetricCell";
import { TeamName } from "./TeamName";
import { TeamAvatar } from "./TeamAvatar";
import { DataTable, type Column } from "./DataTable";
import { gameLogo } from "../lib/assets";
import { isDemoTeam } from "../lib/constants";
import { computePercentiles, median } from "../lib/epa";
import { formatNumber } from "../lib/format";
import { gameLogoBannerStyle, useGameLogoColors } from "../lib/gameLogoColors";
import type { FrcGameInfo } from "../types/api";

function youtubeId(url: string | null | undefined): string | null {
  if (!url || url === "#") return null;
  const byParam = url.match(/[?&]v=([^&]+)/);
  if (byParam) return byParam[1];
  const short = url.match(/youtu\.be\/([^?&]+)/);
  if (short) return short[1];
  const embed = url.match(/embed\/([^?&]+)/);
  if (embed) return embed[1];
  return url.includes("/") || url.includes("=") ? null : url;
}

function quantile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  const rank = (p / 100) * (sorted.length - 1);
  const low = Math.floor(rank);
  const high = Math.ceil(rank);
  if (low === high) return sorted[low];
  const frac = rank - low;
  return sorted[low] * (1 - frac) + sorted[high] * frac;
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card withBorder padding="md" radius="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
        {label}
      </Text>
      <Text fz={26} fw={700} mt={4}>
        {value}
      </Text>
    </Card>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <Card withBorder padding="md" radius="md" h="100%">
      <Text fw={700}>{title}</Text>
      {subtitle ? (
        <Text size="xs" c="dimmed" mb="sm" mt={2}>
          {subtitle}
        </Text>
      ) : (
        <Text mb="sm" mt={2} style={{ height: 0 }} />
      )}
      {children}
    </Card>
  );
}

function buildHistogram(values: number[]): Array<{ bucket: string; Teams: number }> {
  if (values.length === 0) return [];
  const sorted = [...values].sort((a, b) => a - b);
  const max = sorted[sorted.length - 1];
  const bucketSize = Math.max(3, Math.ceil(max / 12 / 5) * 5);
  const buckets = new Map<number, number>();
  for (const v of values) {
    const b = Math.floor(v / bucketSize) * bucketSize;
    buckets.set(b, (buckets.get(b) ?? 0) + 1);
  }
  return [...buckets.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([start, count]) => ({ bucket: `${start}-${start + bucketSize}`, Teams: count }));
}

interface SeasonTeamRow {
  teamNumber: number;
  raw: number | null;
  ace: number | null;
  confidence: number | null;
  auto: number | null;
  teleop: number | null;
  endgame: number | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
  rankGlobal: number | null;
}

function metricStats(values: number[]) {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const sum = sorted.reduce((a, b) => a + b, 0);
  return {
    count: sorted.length,
    mean: sum / sorted.length,
    median: quantile(sorted, 50),
    p90: quantile(sorted, 90),
    max: sorted[sorted.length - 1],
  };
}

interface SeasonGameHeroProps {
  year: number;
  game: FrcGameInfo | null;
  videoId: string | null;
}

/** Game logo banner + summary + field / reveal media (matches event-page polish). */
function SeasonGameHero({ year, game, videoId }: SeasonGameHeroProps) {
  const logoColors = useGameLogoColors(year);
  const bannerStyle = gameLogoBannerStyle(logoColors);
  const manualUrl = game?.manual && game.manual !== "#" ? game.manual : null;
  const revealUrl = game?.video && game.video !== "#" ? game.video : null;

  return (
    <Stack gap="md">
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
        <Group align="flex-start" wrap="wrap" gap="md">
          <Box style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
            <img
              src={gameLogo(year)}
              alt=""
              className="event-banner-logo"
              style={{ width: "auto", objectFit: "contain", display: "block" }}
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
          </Box>
          <Stack gap="sm" style={{ minWidth: 0, flex: 1 }}>
            <Stack gap={6}>
              <Title order={2} fz={{ base: 26, sm: 34 }} lh={1.15}>
                {game?.name ?? `${year} FRC Season`}
              </Title>
              <Group gap="xs">
                <Badge variant="light" color="gray" radius="sm">
                  {year} Season
                </Badge>
              </Group>
            </Stack>
            {game?.summary ? (
              <Text c="dimmed" size="sm" maw={720} lh={1.65}>
                {game.summary}
              </Text>
            ) : null}
            {(manualUrl || revealUrl) && (
              <Group gap="xs" wrap="wrap">
                {manualUrl ? (
                  <Button
                    component="a"
                    href={manualUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    size="compact-sm"
                    variant="default"
                    leftSection={<IconBook size={14} />}
                  >
                    Game Manual
                  </Button>
                ) : null}
                {revealUrl ? (
                  <Button
                    component="a"
                    href={revealUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    size="compact-sm"
                    variant="light"
                    color="red"
                    leftSection={<IconBrandYoutube size={14} />}
                  >
                    Game Reveal
                  </Button>
                ) : null}
              </Group>
            )}
          </Stack>
        </Group>
      </Card>

      <SimpleGrid cols={{ base: 1, md: videoId ? 2 : 1 }} spacing="md">
        <Card withBorder padding="md" radius="md">
          <Box
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              minHeight: 160,
              maxHeight: 320,
            }}
          >
            <img
              src={gameLogo(year, true)}
              alt={`${year} field diagram`}
              style={{
                width: "100%",
                maxHeight: 300,
                objectFit: "contain",
                borderRadius: 6,
              }}
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
          </Box>
        </Card>

        {videoId && revealUrl ? (
          <Card withBorder padding={0} radius="md" style={{ overflow: "hidden" }}>
            <Anchor
              href={revealUrl}
              target="_blank"
              rel="noopener noreferrer"
              underline="never"
              style={{ display: "block", position: "relative" }}
            >
              <img
                src={`https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`}
                alt="Game reveal video"
                style={{
                  width: "100%",
                  aspectRatio: "16 / 9",
                  objectFit: "cover",
                  display: "block",
                }}
                onError={(e) => {
                  e.currentTarget.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
                }}
              />
              <Box
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background:
                    "linear-gradient(to top, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.15) 50%, rgba(0,0,0,0.1) 100%)",
                }}
              >
                <Box
                  style={{
                    width: 56,
                    height: 56,
                    borderRadius: "50%",
                    background: "rgba(255,0,0,0.92)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 4px 20px rgba(0,0,0,0.35)",
                  }}
                >
                  <IconPlayerPlay size={28} color="#fff" fill="#fff" style={{ marginLeft: 3 }} />
                </Box>
              </Box>
              <Text
                size="xs"
                fw={600}
                c="white"
                style={{
                  position: "absolute",
                  left: 12,
                  bottom: 10,
                  textShadow: "0 1px 4px rgba(0,0,0,0.8)",
                }}
              >
                Official game reveal
              </Text>
            </Anchor>
          </Card>
        ) : null}
      </SimpleGrid>
    </Stack>
  );
}

interface InsightsSeasonPanelProps {
  year: number;
  game: FrcGameInfo | null;
}

/** Rich per-season insights: game info, distributions, scatters, full leaderboard. */
export function InsightsSeasonPanel({ year, game }: InsightsSeasonPanelProps) {
  const leaderboard = useLeaderboard(year);
  const { data: searchIdx } = useSearchIndex();
  const nicknameOf = (tn: number) => searchIdx?.teams[String(tn)]?.nickname ?? "";
  const videoId = youtubeId(game?.video);

  const rows = useMemo<SeasonTeamRow[]>(() => {
    const data = leaderboard.data ?? [];
    return data
      .filter((tp) => !isDemoTeam(tp.team_number))
      .map((tp) => {
        const p = tp.team_perfs[0];
        return {
          teamNumber: tp.team_number,
          raw: p?.raw ?? null,
          ace: p?.ace ?? null,
          confidence: p?.confidence ?? null,
          auto: p?.auto_raw ?? null,
          teleop: p?.teleop_raw ?? null,
          endgame: p?.endgame_raw ?? null,
          wins: p?.wins ?? null,
          losses: p?.losses ?? null,
          ties: p?.ties ?? null,
          rankGlobal: p?.rank_global ?? null,
        };
      })
      .filter((r) => r.ace !== null);
  }, [leaderboard.data]);

  const thresholds = useMemo(
    () => ({
      ace: computePercentiles(rows.map((r) => r.ace)),
      auto: computePercentiles(rows.map((r) => r.auto)),
      teleop: computePercentiles(rows.map((r) => r.teleop)),
      endgame: computePercentiles(rows.map((r) => r.endgame)),
    }),
    [rows],
  );

  const confMedian = useMemo(() => median(rows.map((r) => r.confidence)), [rows]);

  const aceStats = useMemo(() => metricStats(rows.map((r) => r.ace!)), [rows]);
  const rawStats = useMemo(
    () => metricStats(rows.map((r) => r.raw).filter((v): v is number => v != null)),
    [rows],
  );

  const aceHistogram = useMemo(() => buildHistogram(rows.map((r) => r.ace!)), [rows]);
  const autoHistogram = useMemo(
    () => buildHistogram(rows.map((r) => r.auto).filter((v): v is number => v != null)),
    [rows],
  );
  const teleopHistogram = useMemo(
    () => buildHistogram(rows.map((r) => r.teleop).filter((v): v is number => v != null)),
    [rows],
  );
  const endgameHistogram = useMemo(
    () => buildHistogram(rows.map((r) => r.endgame).filter((v): v is number => v != null)),
    [rows],
  );

  const phaseMeans = useMemo(() => {
    const avg = (key: keyof Pick<SeasonTeamRow, "auto" | "teleop" | "endgame">) => {
      const vals = rows.map((r) => r[key]).filter((v): v is number => v != null);
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
    };
    return [
      { phase: "Auto", Score: Number(avg("auto").toFixed(1)) },
      { phase: "Teleop", Score: Number(avg("teleop").toFixed(1)) },
      { phase: "Endgame", Score: Number(avg("endgame").toFixed(1)) },
    ];
  }, [rows]);

  const phaseScatter = useMemo(
    () =>
      rows
        .filter((r) => r.auto != null && r.teleop != null)
        .map((r) => ({
          auto: r.auto!,
          teleop: r.teleop!,
        })),
    [rows],
  );

  const aceConfScatter = useMemo(
    () =>
      rows
        .filter((r) => r.ace != null && r.confidence != null)
        .map((r) => ({
          confidence: r.confidence!,
          ace: r.ace!,
        })),
    [rows],
  );

  const teamColumns = useMemo<Column<SeasonTeamRow>[]>(
    () => [
      {
        key: "rank",
        header: "#",
        width: 50,
        render: (_r, i) => i + 1,
      },
      {
        key: "num",
        header: "Team",
        width: 80,
        sortValue: (r) => r.teamNumber,
        render: (r) => <TeamName teamNumber={r.teamNumber} numberOnly year={year} />,
      },
      {
        key: "team",
        header: "Name",
        sortValue: (r) => nicknameOf(r.teamNumber).toLowerCase(),
        exportValue: (r) => nicknameOf(r.teamNumber),
        render: (r) => (
          <Group gap="sm" wrap="nowrap">
            <TeamAvatar teamNumber={r.teamNumber} size={28} radius={6} bordered />
            <TeamName teamNumber={r.teamNumber} withNumber={false} year={year} />
          </Group>
        ),
      },
      {
        key: "globalRank",
        header: "Global",
        width: 80,
        align: "right",
        sortValue: (r) => r.rankGlobal,
        render: (r) => (r.rankGlobal != null ? r.rankGlobal.toLocaleString() : "—"),
      },
      {
        key: "record",
        header: "W-L-T",
        width: 90,
        sortValue: (r) => r.wins,
        render: (r) =>
          r.wins != null ? `${r.wins}-${r.losses ?? 0}-${r.ties ?? 0}` : "—",
      },
      {
        key: "raw",
        header: "RAW",
        width: 72,
        sortValue: (r) => r.raw,
        render: (r) => formatNumber(r.raw),
      },
      {
        key: "confidence",
        header: "Conf",
        width: 90,
        sortValue: (r) => r.confidence,
        render: (r) => <ConfidenceCell value={r.confidence} median={confMedian} />,
      },
      {
        key: "ace",
        header: "ACE",
        width: 80,
        sortValue: (r) => r.ace,
        render: (r) => <MetricCell value={r.ace} thresholds={thresholds.ace} />,
      },
      {
        key: "auto",
        header: "Auto",
        width: 72,
        sortValue: (r) => r.auto,
        render: (r) => <MetricCell value={r.auto} thresholds={thresholds.auto} />,
      },
      {
        key: "teleop",
        header: "Teleop",
        width: 72,
        sortValue: (r) => r.teleop,
        render: (r) => <MetricCell value={r.teleop} thresholds={thresholds.teleop} />,
      },
      {
        key: "endgame",
        header: "End",
        width: 72,
        sortValue: (r) => r.endgame,
        render: (r) => <MetricCell value={r.endgame} thresholds={thresholds.endgame} />,
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [thresholds, confMedian, year, searchIdx],
  );

  if (leaderboard.isLoading) return <LoadingState label={`Loading ${year} insights...`} />;
  if (leaderboard.error) return <ErrorState error={leaderboard.error} />;
  if (!aceStats) {
    return <Text c="dimmed">No ACE data available for {year}.</Text>;
  }

  return (
    <Stack gap="lg">
      <SeasonGameHero year={year} game={game} videoId={videoId} />

      <Stack gap="xs">
        <Title order={3}>{year} Season at a Glance</Title>
        <Text size="sm" c="dimmed">
          {aceStats.count.toLocaleString()} teams with ACE ratings this season.
        </Text>
      </Stack>

      <SimpleGrid cols={{ base: 2, sm: 3, md: 6 }} spacing="sm">
        <StatCard label="Teams" value={aceStats.count.toLocaleString()} />
        <StatCard label="Mean ACE" value={formatNumber(aceStats.mean)} />
        <StatCard label="Median ACE" value={formatNumber(aceStats.median)} />
        <StatCard label="90th pct ACE" value={formatNumber(aceStats.p90)} />
        <StatCard label="Max ACE" value={formatNumber(aceStats.max)} />
        <StatCard label="Mean RAW" value={rawStats ? formatNumber(rawStats.mean) : "—"} />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2, lg: 4 }} spacing="md">
        <ChartCard title="ACE distribution">
          <BarChart
            h={220}
            data={aceHistogram}
            dataKey="bucket"
            series={[{ name: "Teams", color: "peeko.6" }]}
            gridAxis="y"
          />
        </ChartCard>
        <ChartCard title="Auto distribution">
          <BarChart
            h={220}
            data={autoHistogram}
            dataKey="bucket"
            series={[{ name: "Teams", color: "blue.5" }]}
            gridAxis="y"
          />
        </ChartCard>
        <ChartCard title="Teleop distribution">
          <BarChart
            h={220}
            data={teleopHistogram}
            dataKey="bucket"
            series={[{ name: "Teams", color: "orange.5" }]}
            gridAxis="y"
          />
        </ChartCard>
        <ChartCard title="Endgame distribution">
          <BarChart
            h={220}
            data={endgameHistogram}
            dataKey="bucket"
            series={[{ name: "Teams", color: "green.5" }]}
            gridAxis="y"
          />
        </ChartCard>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
        <ChartCard title="Phase averages" subtitle="Season mean score by period">
          <BarChart
            h={260}
            data={phaseMeans}
            dataKey="phase"
            series={[{ name: "Score", color: "violet.5" }]}
            gridAxis="y"
          />
        </ChartCard>
        <ChartCard title="Auto vs Teleop" subtitle="Every rated team — spot scoring profiles">
          {phaseScatter.length > 0 ? (
            <ScatterChart
              h={260}
              data={[{ name: "Teams", color: "peeko.5", data: phaseScatter }]}
              dataKey={{ x: "auto", y: "teleop" }}
              xAxisLabel="Auto"
              yAxisLabel="Teleop"
              gridAxis="xy"
              withTooltip
            />
          ) : (
            <Text size="sm" c="dimmed">
              Not enough phase data.
            </Text>
          )}
        </ChartCard>
      </SimpleGrid>

      <ChartCard title="ACE vs Confidence" subtitle="High ACE with low confidence = volatile rating">
        {aceConfScatter.length > 0 ? (
          <ScatterChart
            h={280}
            data={[{ name: "Teams", color: "violet.5", data: aceConfScatter }]}
            dataKey={{ x: "confidence", y: "ace" }}
            xAxisLabel="Confidence"
            yAxisLabel="ACE"
            gridAxis="xy"
            withTooltip
          />
        ) : (
          <Text size="sm" c="dimmed">
            Not enough data.
          </Text>
        )}
      </ChartCard>

      <Stack gap="sm">
        <Title order={3}>Season Leaderboard</Title>
        <AceLegend />
        <DataTable
          data={rows}
          columns={teamColumns}
          getRowKey={(r) => r.teamNumber}
          initialSort={{ key: "ace", dir: "desc" }}
          minWidth={980}
          stickyHeader
          defaultPageSize={25}
          pageSizeOptions={[10, 25, 50, 100]}
          exportFileName={`peekorobo-insights-${year}`}
        />
      </Stack>
    </Stack>
  );
}
