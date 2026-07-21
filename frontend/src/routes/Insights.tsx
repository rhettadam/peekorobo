import { useEffect, useMemo } from "react";
import {
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Select,
  Text,
  Title,
} from "@mantine/core";
import { BarChart } from "@mantine/charts";
import { IconArrowLeft, IconBook, IconBrandYoutube } from "@tabler/icons-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useFrcGames, useLeaderboard, useSearchIndex } from "../api/queries";
import { ErrorState, LoadingState } from "../components/StateWrappers";
import { InsightsOverall } from "../components/InsightsOverall";
import { AceBadge } from "../components/AceBadge";
import { TeamName } from "../components/TeamName";
import { TeamAvatar } from "../components/TeamAvatar";
import { DataTable, type Column } from "../components/DataTable";
import { gameLogo } from "../lib/assets";
import { availableYears, CURRENT_YEAR, isDemoTeam } from "../lib/constants";
import { computePercentiles } from "../lib/epa";
import { formatNumber } from "../lib/format";
import type { FrcGameInfo } from "../types/api";

/** Extract a YouTube video id from a full watch URL (or bare id). */
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

/** A single season tile on the Insights landing grid. */
function SeasonCard({ game }: { game: FrcGameInfo }) {
  return (
    <Card
      withBorder
      radius="md"
      padding="lg"
      className="hover-lift"
      component={Link}
      to={`/insights/${game.year}`}
    >
      <Stack gap="sm" align="center" h="100%">
        <Box
          h={96}
          w="100%"
          style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
        >
          <img
            src={gameLogo(game.year)}
            alt={game.name ?? `${game.year} game`}
            style={{ maxHeight: 96, maxWidth: "100%", objectFit: "contain", display: "block" }}
            onError={(e) => (e.currentTarget.style.display = "none")}
          />
        </Box>
        <Text fw={800} fz={30} lh={1}>
          {game.year}
        </Text>
        <Text c="dimmed" ta="center" size="sm" lineClamp={2}>
          {game.name ?? "Unknown Game"}
        </Text>
      </Stack>
    </Card>
  );
}

/** Insights landing: overall career charts + season picker grid. */
export function Insights() {
  const games = useFrcGames();

  useEffect(() => {
    document.title = "Insights - Peekorobo";
  }, []);

  const seasons = useMemo(() => {
    const list = games.data?.games ?? [];
    return [...list].sort((a, b) => b.year - a.year);
  }, [games.data]);

  return (
    <Stack gap="xl" py="md">
      <Group gap="md" align="flex-start" wrap="wrap">
        <Box style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
          <img
            src={gameLogo(CURRENT_YEAR)}
            alt={`${CURRENT_YEAR} game`}
            style={{
              height: 56,
              width: "auto",
              objectFit: "contain",
              display: "block",
            }}
            onError={(e) => (e.currentTarget.style.display = "none")}
          />
        </Box>
        <Stack gap={4} style={{ minWidth: 0 }}>
          <Title order={1}>Insights</Title>
          <Text c="dimmed" maw={640}>
            All-time FRC growth, ACE prediction accuracy, and career leaderboards — then dive into
            any season for game info and ACE distributions.
          </Text>
        </Stack>
      </Group>

      <Stack gap="sm">
        <Group gap="xs">
          <Title order={2}>Overall</Title>
          <Badge color="cyan" variant="light" radius="sm">
            All years
          </Badge>
        </Group>
        <InsightsOverall />
      </Stack>

      <Stack gap="sm">
        <Group gap="xs">
          <Title order={2}>By Season</Title>
          <Badge color="grape" variant="light" radius="sm">
            Pick a year
          </Badge>
        </Group>
        <Text c="dimmed" size="sm">
          Explore a season&apos;s game, reveal video, leaderboards, and ACE distribution.
        </Text>
        {games.isLoading ? (
          <LoadingState label="Loading seasons..." />
        ) : games.error ? (
          <ErrorState error={games.error} />
        ) : (
          <SimpleGrid cols={{ base: 2, xs: 3, sm: 4, md: 5, lg: 6 }} spacing="md">
            {seasons.map((game) => (
              <SeasonCard key={game.year} game={game} />
            ))}
          </SimpleGrid>
        )}
      </Stack>
    </Stack>
  );
}

/** Per-season detail: game info, reveal video, field diagram, ACE leaderboards. */
export function InsightsSeason() {
  const navigate = useNavigate();
  const params = useParams<{ year: string }>();
  const year = Number(params.year) || CURRENT_YEAR;
  const leaderboard = useLeaderboard(year);
  const games = useFrcGames();
  const { data: searchIdx } = useSearchIndex();
  const nicknameOf = (tn: number) => searchIdx?.teams[String(tn)]?.nickname ?? "";
  const game = useMemo(
    () => games.data?.games.find((g) => g.year === year) ?? null,
    [games.data, year],
  );
  const videoId = youtubeId(game?.video);

  useEffect(() => {
    document.title = game?.name
      ? `${game.name} (${year}) - Peekorobo`
      : `${year} Insights - Peekorobo`;
  }, [year, game?.name]);

  const rows = useMemo(() => {
    const data = leaderboard.data ?? [];
    return data
      .filter((tp) => !isDemoTeam(tp.team_number))
      .map((tp) => ({ teamNumber: tp.team_number, ace: tp.team_perfs[0]?.ace ?? null }))
      .filter((r) => r.ace !== null) as Array<{ teamNumber: number; ace: number }>;
  }, [leaderboard.data]);

  const aceValues = useMemo(() => rows.map((r) => r.ace).sort((a, b) => a - b), [rows]);
  const thresholds = useMemo(() => computePercentiles(aceValues), [aceValues]);

  const stats = useMemo(() => {
    if (aceValues.length === 0) return null;
    const sum = aceValues.reduce((a, b) => a + b, 0);
    return {
      count: aceValues.length,
      mean: sum / aceValues.length,
      median: quantile(aceValues, 50),
      p90: quantile(aceValues, 90),
      p99: quantile(aceValues, 99),
      max: aceValues[aceValues.length - 1],
    };
  }, [aceValues]);

  const histogram = useMemo(() => {
    if (aceValues.length === 0) return [];
    const max = aceValues[aceValues.length - 1];
    const bucketSize = Math.max(5, Math.ceil(max / 12 / 5) * 5);
    const buckets = new Map<number, number>();
    for (const v of aceValues) {
      const b = Math.floor(v / bucketSize) * bucketSize;
      buckets.set(b, (buckets.get(b) ?? 0) + 1);
    }
    return [...buckets.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([start, count]) => ({ bucket: `${start}-${start + bucketSize}`, Teams: count }));
  }, [aceValues]);

  const rankedTeams = useMemo(() => [...rows].sort((a, b) => b.ace - a.ace), [rows]);

  const topTeamColumns = useMemo<Column<{ teamNumber: number; ace: number }>[]>(
    () => [
      { key: "rank", header: "Rank", width: 70, render: (_r, i) => i + 1 },
      {
        key: "num",
        header: "#",
        width: 80,
        sortValue: (r) => r.teamNumber,
        render: (r) => <TeamName teamNumber={r.teamNumber} numberOnly year={year} />,
      },
      {
        key: "team",
        header: "Team",
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
        key: "ace",
        header: "ACE",
        width: 110,
        sortValue: (r) => r.ace,
        render: (r) => <AceBadge value={r.ace} thresholds={thresholds} />,
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [thresholds, year, searchIdx],
  );

  return (
    <Stack gap="md" py="md">
      <Anchor component={Link} to="/insights" size="sm" c="dimmed">
        <Group gap={4} align="center">
          <IconArrowLeft size={16} />
          All Seasons
        </Group>
      </Anchor>

      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group gap="md" align="stretch" wrap="nowrap">
          <Box style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
            <img
              src={gameLogo(year)}
              alt={`${year} game`}
              style={{
                height: "100%",
                width: "auto",
                maxHeight: 64,
                objectFit: "contain",
                display: "block",
              }}
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
          </Box>
          <Stack gap={2} justify="center">
            <Title order={1} style={{ fontSize: 56, lineHeight: 1, fontWeight: 800 }}>
              {year}
            </Title>
            <Text c="dimmed" fw={600}>
              {game?.name ?? "Unknown Game"}
            </Text>
          </Stack>
        </Group>
        <Select
          label="Season"
          value={String(year)}
          data={availableYears().map((y) => ({ value: String(y), label: String(y) }))}
          onChange={(val) => val && navigate(`/insights/${val}`)}
          allowDeselect={false}
          w={120}
        />
      </Group>

      {/* Season game info: logo, name, summary, manual, reveal video, field diagram */}
      <Card withBorder padding="lg" radius="md">
        <Group align="flex-start" wrap="wrap" gap="xl">
          <Stack gap="sm" align="center" style={{ flex: "0 0 220px" }}>
            <img
              src={gameLogo(year)}
              alt={game?.name ?? `${year} game`}
              style={{ width: "100%", maxWidth: 220, objectFit: "contain" }}
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
            {game?.manual && game.manual !== "#" ? (
              <Button
                component="a"
                href={game.manual}
                target="_blank"
                rel="noopener noreferrer"
                variant="outline"
                color="yellow"
                leftSection={<IconBook size={16} />}
                fullWidth
              >
                View Game Manual
              </Button>
            ) : null}
          </Stack>

          <Stack gap="xs" style={{ flex: "1 1 300px", minWidth: 260 }}>
            <Title order={2}>
              {game?.name ?? "Unknown Game"} ({year})
            </Title>
            {game?.summary ? (
              <Text c="dimmed" style={{ lineHeight: 1.6 }}>
                {game.summary}
              </Text>
            ) : (
              <Text c="dimmed">No summary available for this season.</Text>
            )}
          </Stack>
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md" mt="lg">
          <Stack gap={6}>
            <Text fw={600} size="sm">
              Field Diagram
            </Text>
            <img
              src={gameLogo(year, true)}
              alt={`${year} field`}
              style={{ width: "100%", borderRadius: 8, objectFit: "contain" }}
              onError={(e) => {
                const el = e.currentTarget.parentElement;
                if (el) el.style.display = "none";
              }}
            />
          </Stack>
          {videoId ? (
            <Stack gap={6}>
              <Text fw={600} size="sm">
                Watch the official game reveal
              </Text>
              <Anchor
                href={game?.video ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                style={{ position: "relative", display: "block", borderRadius: 8, overflow: "hidden" }}
              >
                <img
                  src={`https://img.youtube.com/vi/${videoId}/hqdefault.jpg`}
                  alt="Game reveal video"
                  style={{ width: "100%", display: "block", objectFit: "cover" }}
                />
                <span
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "rgba(0,0,0,0.25)",
                  }}
                >
                  <IconBrandYoutube size={64} color="#ff0000" fill="#ffffff" />
                </span>
              </Anchor>
            </Stack>
          ) : null}
        </SimpleGrid>
      </Card>

      <Title order={3} mt="sm">
        {year} Leaderboards
      </Title>

      {leaderboard.isLoading ? (
        <LoadingState label={`Loading ${year} insights...`} />
      ) : leaderboard.error ? (
        <ErrorState error={leaderboard.error} />
      ) : !stats ? (
        <Text c="dimmed">No ACE data available for {year}.</Text>
      ) : (
        <>
          <SimpleGrid cols={{ base: 2, sm: 3, md: 6 }} spacing="sm">
            <StatCard label="Teams" value={stats.count.toLocaleString()} />
            <StatCard label="Mean ACE" value={formatNumber(stats.mean)} />
            <StatCard label="Median" value={formatNumber(stats.median)} />
            <StatCard label="90th pct" value={formatNumber(stats.p90)} />
            <StatCard label="99th pct" value={formatNumber(stats.p99)} />
            <StatCard label="Max" value={formatNumber(stats.max)} />
          </SimpleGrid>

          <Card withBorder padding="md" radius="md">
            <Text fw={600} mb="sm">
              ACE distribution
            </Text>
            <BarChart
              h={280}
              data={histogram}
              dataKey="bucket"
              series={[{ name: "Teams", color: "peeko.6" }]}
              gridAxis="y"
            />
          </Card>

          <DataTable
            data={rankedTeams}
            columns={topTeamColumns}
            getRowKey={(r) => r.teamNumber}
            initialSort={{ key: "ace", dir: "desc" }}
            minWidth={420}
            defaultPageSize={10}
            pageSizeOptions={[10, 25, 50]}
            exportFileName={`peekorobo-insights-top-teams-${year}`}
          />
        </>
      )}
    </Stack>
  );
}
