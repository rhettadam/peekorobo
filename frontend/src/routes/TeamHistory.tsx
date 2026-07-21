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
  Text,
  Title,
} from "@mantine/core";
import { LineChart } from "@mantine/charts";
import {
  IconArrowLeft,
  IconAward,
} from "@tabler/icons-react";
import { Link, useParams } from "react-router-dom";
import {
  useTeamAwards,
  useTeamInfo,
  useTeamNotables,
  useTeamPerfs,
} from "../api/queries";
import { ErrorState, LoadingState } from "../components/StateWrappers";
import { TeamAvatar } from "../components/TeamAvatar";
import { BlueBanners, BlueBannerTile, toBlueBannerItems } from "../components/BlueBanners";
import { TeamProfileMeta } from "../components/TeamProfileMeta";
import { RecordCell } from "../components/RecordCell";
import { DataTable, type Column } from "../components/DataTable";
import { contrastText } from "../lib/epa";
import { formatNumber, locationString, yearFromEventKey } from "../lib/format";
import type { TeamPerfInfo } from "../types/api";

interface SeasonRankRow {
  year: string;
  rank: number;
  count: number | null;
  ace: number | null;
  raw: number | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
}

/** Rich hover card for the rank-by-season chart (rank on the axis, ACE in hover). */
function SeasonRankTooltip({ payload }: { payload?: Array<{ payload?: SeasonRankRow }> }) {
  const row = payload?.[0]?.payload;
  if (!row) return null;
  const stat = (label: string, value: string, color?: string) => (
    <Group justify="space-between" gap="lg" wrap="nowrap">
      <Group gap={6} wrap="nowrap">
        {color ? (
          <Box style={{ width: 8, height: 8, borderRadius: 2, background: color, flexShrink: 0 }} />
        ) : null}
        <Text size="xs" c="dimmed">
          {label}
        </Text>
      </Group>
      <Text size="xs" fw={600}>
        {value}
      </Text>
    </Group>
  );
  return (
    <Card withBorder radius="md" padding="sm" shadow="md" style={{ minWidth: 180 }}>
      <Text fw={700} size="sm" mb={4}>
        {row.year}
      </Text>
      <Stack gap={2}>
        {stat(
          "Global Rank",
          row.count ? `#${row.rank.toLocaleString()} / ${row.count.toLocaleString()}` : `#${row.rank.toLocaleString()}`,
          "var(--mantine-color-peeko-6)",
        )}
        {row.ace != null ? stat("ACE", formatNumber(row.ace)) : null}
        {row.raw != null ? stat("RAW", formatNumber(row.raw)) : null}
        {row.wins != null
          ? stat("Record", `${row.wins}-${row.losses ?? 0}-${row.ties ?? 0}`)
          : null}
      </Stack>
    </Card>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card withBorder radius="md" padding="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={700} lh={1.2}>
        {label}
      </Text>
      <Text fz={28} fw={800} lh={1.15} mt={4}>
        {value}
      </Text>
      {sub ? (
        <Text size="xs" c="dimmed">
          {sub}
        </Text>
      ) : null}
    </Card>
  );
}

export function TeamHistory() {
  const params = useParams();
  const teamNumber = Number(params.teamNumber);

  const infoQuery = useTeamInfo(teamNumber);
  const perfsQuery = useTeamPerfs(teamNumber);
  const awardsQuery = useTeamAwards(teamNumber);
  const notablesQuery = useTeamNotables(teamNumber);

  const info = infoQuery.data;
  const perfs = useMemo(() => perfsQuery.data?.team_perfs ?? [], [perfsQuery.data]);
  const awards = awardsQuery.data?.awards ?? [];
  const bannerItems = useMemo(() => toBlueBannerItems(awards), [awards]);
  const leftBanners = useMemo(() => bannerItems.filter((_, i) => i % 2 === 0), [bannerItems]);
  const rightBanners = useMemo(() => bannerItems.filter((_, i) => i % 2 === 1), [bannerItems]);
  const notables = notablesQuery.data?.notables ?? [];

  useEffect(() => {
    document.title = info?.nickname
      ? `${teamNumber} | ${info.nickname} — History - Peekorobo`
      : `Team ${teamNumber} History - Peekorobo`;
  }, [teamNumber, info?.nickname]);

  const seasonsDesc = useMemo(
    () => [...perfs].sort((a, b) => b.year - a.year),
    [perfs],
  );

  // Rank is comparable across seasons (ACE units drift year to year since the
  // game changes), so we plot global rank over time and surface ACE in the hover.
  const seasonTrend = useMemo(
    () =>
      [...perfs]
        .filter((p) => p.rank_global !== null && p.rank_global !== undefined)
        .sort((a, b) => a.year - b.year)
        .map((p) => ({
          year: String(p.year),
          rank: p.rank_global as number,
          count: p.count_global ?? null,
          ace: p.ace ?? null,
          raw: p.raw ?? null,
          wins: p.wins ?? null,
          losses: p.losses ?? null,
          ties: p.ties ?? null,
        })),
    [perfs],
  );

  const summary = useMemo(() => {
    if (perfs.length === 0) return null;
    const years = perfs.map((p) => p.year);
    let wins = 0;
    let losses = 0;
    let ties = 0;
    let bestAce: number | null = null;
    let bestRank: number | null = null;
    let bestRankYear: number | null = null;
    for (const p of perfs) {
      wins += p.wins ?? 0;
      losses += p.losses ?? 0;
      ties += p.ties ?? 0;
      if (p.ace !== null && p.ace !== undefined && (bestAce === null || p.ace > bestAce)) {
        bestAce = p.ace;
      }
      if (
        p.rank_global !== null &&
        p.rank_global !== undefined &&
        (bestRank === null || p.rank_global < bestRank)
      ) {
        bestRank = p.rank_global;
        bestRankYear = p.year;
      }
    }
    return {
      firstYear: Math.min(...years),
      lastYear: Math.max(...years),
      seasons: perfs.length,
      wins,
      losses,
      ties,
      bestAce,
      bestRank,
      bestRankYear,
    };
  }, [perfs]);

  const awardsByYear = useMemo(() => {
    const map = new Map<number, string[]>();
    for (const a of awards) {
      const y = yearFromEventKey(a.event_key) ?? 0;
      const list = map.get(y) ?? [];
      list.push(a.award_name);
      map.set(y, list);
    }
    return [...map.entries()].sort((a, b) => b[0] - a[0]);
  }, [awards]);

  const columns = useMemo<Column<TeamPerfInfo>[]>(
    () => [
      {
        key: "year",
        header: "Season",
        width: 90,
        sortValue: (p) => p.year,
        render: (p) => (
          <Anchor component={Link} to={`/team/${teamNumber}/${p.year}`} fw={600}>
            {p.year}
          </Anchor>
        ),
      },
      { key: "ace", header: "ACE", width: 80, sortValue: (p) => p.ace, render: (p) => formatNumber(p.ace) },
      { key: "raw", header: "RAW", width: 80, sortValue: (p) => p.raw, render: (p) => formatNumber(p.raw) },
      { key: "auto", header: "Auto", width: 80, sortValue: (p) => p.auto_raw, render: (p) => formatNumber(p.auto_raw) },
      { key: "teleop", header: "Teleop", width: 80, sortValue: (p) => p.teleop_raw, render: (p) => formatNumber(p.teleop_raw) },
      { key: "endgame", header: "Endgame", width: 90, sortValue: (p) => p.endgame_raw, render: (p) => formatNumber(p.endgame_raw) },
      {
        key: "record",
        header: "Record",
        width: 110,
        sortValue: (p) => p.wins,
        exportValue: (p) => `${p.wins ?? 0}-${p.losses ?? 0}-${p.ties ?? 0}`,
        render: (p) => <RecordCell wins={p.wins} losses={p.losses} ties={p.ties} />,
      },
      {
        key: "rank",
        header: "Global Rank",
        width: 110,
        sortValue: (p) => p.rank_global,
        render: (p) =>
          p.rank_global != null
            ? `${p.rank_global.toLocaleString()}${p.count_global ? ` / ${p.count_global.toLocaleString()}` : ""}`
            : "—",
      },
    ],
    [teamNumber],
  );

  if (perfsQuery.isLoading) return <LoadingState label={`Loading team ${teamNumber} history...`} />;
  if (perfsQuery.error) return <ErrorState error={perfsQuery.error} />;

  const colors = info?.team_colors as { primary?: string; secondary?: string } | null | undefined;
  const primary = typeof colors?.primary === "string" ? colors.primary : null;
  const secondary = typeof colors?.secondary === "string" ? colors.secondary : null;
  const gradient =
    primary && secondary
      ? `linear-gradient(135deg, ${primary}, ${secondary})`
      : "linear-gradient(135deg, #3a3a3a, #1a1a1a)";
  const headerText = primary ? contrastText(primary) : "#ffffff";

  return (
    <div className="peeko-history-layout">
      <aside className="peeko-history-rail" aria-label="Blue banners">
        {leftBanners.map((b, i) => (
          <BlueBannerTile key={`${b.event_key}-${b.award_name}-${i}`} banner={b} compact />
        ))}
      </aside>

      <Stack gap="lg" py="md" style={{ minWidth: 0 }}>
      <Card radius="lg" p="lg" style={{ background: gradient, color: headerText, border: "none" }}>
        <Group justify="space-between" align="center" wrap="nowrap">
          <Stack gap={6} style={{ minWidth: 0 }}>
            <Button
              component={Link}
              to={`/team/${teamNumber}`}
              variant="white"
              color="dark"
              size="xs"
              leftSection={<IconArrowLeft size={16} />}
              w="fit-content"
            >
              Back to Team {teamNumber}
            </Button>
            <Title order={1} c={headerText} style={{ wordBreak: "break-word" }}>
              Team {teamNumber}
              {info?.nickname ? `: ${info.nickname}` : ""} — History
            </Title>
            <TeamProfileMeta
              headerText={headerText}
              location={
                info
                  ? locationString(info.city, info.state_prov, info.country) || undefined
                  : undefined
              }
              teamNumber={teamNumber}
              notables={notables}
            />
          </Stack>
          <Box visibleFrom="sm" style={{ flexShrink: 0 }}>
            <TeamAvatar teamNumber={teamNumber} size={110} radius={14} upscale />
          </Box>
        </Group>
      </Card>

      {summary ? (
        <SimpleGrid cols={{ base: 2, sm: 3, md: 5 }} spacing="md">
          <StatCard
            label="Seasons"
            value={String(summary.seasons)}
            sub={`${summary.firstYear}\u2013${summary.lastYear}`}
          />
          <StatCard label="Career Record" value={`${summary.wins}-${summary.losses}-${summary.ties}`} />
          <StatCard label="Best ACE" value={formatNumber(summary.bestAce)} />
          <StatCard
            label="Best Global Rank"
            value={summary.bestRank != null ? `#${summary.bestRank.toLocaleString()}` : "—"}
            sub={summary.bestRankYear ? `in ${summary.bestRankYear}` : undefined}
          />
          <StatCard label="Awards" value={String(awards.length)} />
        </SimpleGrid>
      ) : (
        <Text c="dimmed">No historical performance data for team {teamNumber}.</Text>
      )}

      {seasonTrend.length > 1 ? (
        <Card withBorder padding="md" radius="md">
          <Text fw={600}>Global Rank by Season</Text>
          <Text size="xs" c="dimmed" mb="sm">
            Rank is comparable across years; hover a point for that season's ACE. Higher is better.
          </Text>
          <LineChart
            h={280}
            data={seasonTrend}
            dataKey="year"
            series={[{ name: "rank", label: "Global Rank", color: "peeko.6" }]}
            curveType="monotone"
            withDots
            connectNulls
            gridAxis="xy"
            yAxisLabel="Global Rank"
            yAxisProps={{ reversed: true, allowDecimals: false, domain: [1, "dataMax"] }}
            tooltipProps={{
              content: ({ payload }) => (
                <SeasonRankTooltip payload={payload as Array<{ payload?: SeasonRankRow }>} />
              ),
            }}
          />
        </Card>
      ) : null}

      {seasonsDesc.length > 0 ? (
        <Stack gap="sm">
          <Title order={3}>Season by Season</Title>
          <DataTable
            data={seasonsDesc}
            columns={columns}
            getRowKey={(p) => p.year}
            initialSort={{ key: "year", dir: "desc" }}
            minWidth={720}
            defaultPageSize={25}
            exportFileName={`peekorobo-team-${teamNumber}-history`}
          />
        </Stack>
      ) : null}

      {awardsByYear.length > 0 ? (
        <Stack gap="sm">
          <Title order={3}>Awards History</Title>
          <Card withBorder radius="md" padding="md">
            <Stack gap="md">
              {awardsByYear.map(([yr, names]) => (
                <Group key={yr} align="flex-start" wrap="nowrap" gap="md">
                  <Anchor
                    component={Link}
                    to={`/team/${teamNumber}/${yr}`}
                    fw={700}
                    style={{ minWidth: 56, flexShrink: 0 }}
                  >
                    {yr || "—"}
                  </Anchor>
                  <Group gap={8}>
                    {names.map((name, i) => (
                      <Badge
                        key={`${yr}-${i}`}
                        variant="light"
                        color={/impact|chairman/i.test(name) ? "grape" : /winner|champion/i.test(name) ? "yellow" : "gray"}
                        leftSection={<IconAward size={12} />}
                        radius="sm"
                        size="lg"
                        style={{ textTransform: "none" }}
                      >
                        {name}
                      </Badge>
                    ))}
                  </Group>
                </Group>
              ))}
            </Stack>
          </Card>
        </Stack>
      ) : null}

      <div className="peeko-history-banners-mobile">
        <BlueBanners awards={awards} title="Blue Banners" />
      </div>
      </Stack>

      <aside className="peeko-history-rail" aria-label="Blue banners">
        {rightBanners.map((b, i) => (
          <BlueBannerTile key={`${b.event_key}-${b.award_name}-${i}`} banner={b} compact />
        ))}
      </aside>
    </div>
  );
}
