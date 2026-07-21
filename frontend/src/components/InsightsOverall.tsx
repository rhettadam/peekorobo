import type { ReactNode } from "react";
import { Badge, Card, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { AreaChart, BarChart, LineChart } from "@mantine/charts";
import { useInsightsOverview } from "../api/queries";
import { ErrorState, LoadingState } from "./StateWrappers";
import { TeamAvatar } from "./TeamAvatar";
import { TeamName } from "./TeamName";
import type { InsightsLeaderRow, InsightsTeamupRow } from "../types/api";

function formatCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toLocaleString();
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

function LeaderBoard({
  title,
  rows,
  unit,
}: {
  title: string;
  rows: InsightsLeaderRow[];
  unit: string;
}) {
  const list = rows ?? [];
  return (
    <Card withBorder padding="md" radius="md" h="100%">
      <Group justify="space-between" mb="sm" wrap="nowrap">
        <Text fw={700}>{title}</Text>
        {list.length > 0 ? (
          <Badge variant="light" color="gray" radius="sm">
            Top {list.length}
          </Badge>
        ) : null}
      </Group>
      {!list.length ? (
        <Text size="sm" c="dimmed">
          No data yet.
        </Text>
      ) : (
        <Stack gap={8}>
          {list.map((r, i) => (
            <Group key={r.team_number} gap="sm" wrap="nowrap" justify="space-between">
              <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                <Text fw={700} w={22} ta="right" c={i < 3 ? undefined : "dimmed"}>
                  {i + 1}
                </Text>
                <TeamAvatar teamNumber={r.team_number} size={28} radius={8} />
                <TeamName teamNumber={r.team_number} fw={600} />
              </Group>
              <Stack gap={0} align="flex-end" style={{ flexShrink: 0 }}>
                <Text fw={700}>{r.count.toLocaleString()}</Text>
                <Text size="xs" c="dimmed">
                  {r.detail || unit}
                </Text>
              </Stack>
            </Group>
          ))}
        </Stack>
      )}
    </Card>
  );
}

function TeamupBoard({
  title,
  subtitle,
  rows,
  unit,
}: {
  title: string;
  subtitle?: string;
  rows: InsightsTeamupRow[];
  unit: string;
}) {
  const list = rows ?? [];
  return (
    <Card withBorder padding="md" radius="md" h="100%">
      <Group justify="space-between" mb={subtitle ? 2 : "sm"} wrap="nowrap">
        <Text fw={700}>{title}</Text>
        {list.length > 0 ? (
          <Badge variant="light" color="gray" radius="sm">
            Top {list.length}
          </Badge>
        ) : null}
      </Group>
      {subtitle ? (
        <Text size="xs" c="dimmed" mb="sm">
          {subtitle}
        </Text>
      ) : null}
      {!list.length ? (
        <Text size="sm" c="dimmed">
          No data yet.
        </Text>
      ) : (
        <Stack gap={10}>
          {list.map((r, i) => (
            <Group
              key={`${r.team_a}-${r.team_b}`}
              gap="sm"
              wrap="nowrap"
              justify="space-between"
            >
              <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
                <Text fw={700} w={22} ta="right" c={i < 3 ? undefined : "dimmed"}>
                  {i + 1}
                </Text>
                <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
                  <TeamAvatar teamNumber={r.team_a} size={26} radius={8} />
                  <TeamName teamNumber={r.team_a} fw={600} />
                  <Text c="dimmed" size="sm">
                    +
                  </Text>
                  <TeamAvatar teamNumber={r.team_b} size={26} radius={8} />
                  <TeamName teamNumber={r.team_b} fw={600} />
                </Group>
              </Group>
              <Stack gap={0} align="flex-end" style={{ flexShrink: 0 }}>
                <Text fw={700}>{r.count.toLocaleString()}</Text>
                <Text size="xs" c="dimmed">
                  {unit}
                </Text>
              </Stack>
            </Group>
          ))}
        </Stack>
      )}
    </Card>
  );
}

/** All-time Insights: growth series + career leaderboards. */
export function InsightsOverall() {
  const overview = useInsightsOverview();

  if (overview.isLoading) return <LoadingState label="Crunching all-time insights..." />;
  if (overview.error) return <ErrorState error={overview.error} />;
  const data = overview.data;
  if (!data) return null;

  const years = data.years ?? [];
  const blueBanners = data.blue_banners ?? [];
  const championshipWins = data.championship_wins ?? [];
  const preds = data.predictions;
  const predictionAccuracy = preds?.by_year ?? data.prediction_accuracy ?? [];
  const predSummary = preds?.summary;

  const series = years.map((y) => ({
    year: String(y.year),
    Teams: y.team_count,
    Events: y.event_count,
    Matches: y.match_count,
  }));

  const accuracy = predictionAccuracy
    .filter((p) => p.total > 50)
    .map((p) => ({
      year: String(p.year),
      Accuracy: p.pct ?? 0,
      Brier: p.brier != null ? Number((p.brier * 100).toFixed(2)) : null,
    }));

  const confBars = (preds?.by_confidence ?? []).map((b) => ({
    band: b.label,
    Accuracy: b.pct ?? 0,
  }));

  const compBars = (preds?.by_comp_level ?? []).map((b) => ({
    level: b.label,
    Accuracy: b.pct ?? 0,
  }));

  const typeBars = (preds?.by_event_type ?? []).map((b) => ({
    type: b.label,
    Accuracy: b.pct ?? 0,
  }));

  const bannerBars = blueBanners.slice(0, 10).map((r) => ({
    team: String(r.team_number),
    Banners: r.count,
  }));

  const champBars = championshipWins.slice(0, 10).map((r) => ({
    team: String(r.team_number),
    Titles: r.count,
  }));

  const t = data.totals ?? {
    seasons: 0,
    events: 0,
    matches: 0,
    blue_banners: 0,
    predicted_matches: 0,
    teams_latest: 0,
  };

  return (
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 2, sm: 3, md: 6 }} spacing="sm">
        <StatCard label="Seasons tracked" value={String(t.seasons)} />
        <StatCard label="Events all-time" value={formatCompact(t.events)} />
        <StatCard label="Matches all-time" value={formatCompact(t.matches)} />
        <StatCard label="Teams (latest)" value={formatCompact(t.teams_latest)} />
        <StatCard label="Blue banners" value={formatCompact(t.blue_banners)} />
        <StatCard label="Predicted matches" value={formatCompact(t.predicted_matches)} />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
        <ChartCard title="Teams over time" subtitle="Distinct competing teams each season">
          <AreaChart
            h={240}
            data={series}
            dataKey="year"
            series={[{ name: "Teams", color: "peeko.6" }]}
            curveType="monotone"
            withDots={false}
            gridAxis="xy"
            connectNulls
          />
        </ChartCard>
        <ChartCard title="Events over time" subtitle="Events recorded each season">
          <AreaChart
            h={240}
            data={series}
            dataKey="year"
            series={[{ name: "Events", color: "violet.5" }]}
            curveType="monotone"
            withDots={false}
            gridAxis="xy"
            connectNulls
          />
        </ChartCard>
        <ChartCard title="Match volume" subtitle="Qual + playoff matches per season">
          <AreaChart
            h={240}
            data={series}
            dataKey="year"
            series={[{ name: "Matches", color: "pink.5" }]}
            curveType="monotone"
            withDots={false}
            gridAxis="xy"
            connectNulls
          />
        </ChartCard>
      </SimpleGrid>

      <Title order={3}>ACE Predictions</Title>
      <Text size="sm" c="dimmed" mt={-8}>
        How well ACE win probabilities call match winners. Score MAE isn&apos;t available yet — we
        only store win probs today, not predicted alliance scores.
      </Text>

      <SimpleGrid cols={{ base: 2, sm: 3, md: 5 }} spacing="sm">
        <StatCard
          label="Winner accuracy"
          value={predSummary?.pct != null ? `${predSummary.pct.toFixed(1)}%` : "—"}
        />
        <StatCard
          label="Matches scored"
          value={formatCompact(predSummary?.total ?? t.predicted_matches)}
        />
        <StatCard
          label="Brier score"
          value={predSummary?.brier != null ? predSummary.brier.toFixed(3) : "—"}
        />
        <StatCard
          label="Favorite hit rate"
          value={
            predSummary?.favorite_win_pct != null
              ? `${predSummary.favorite_win_pct.toFixed(1)}%`
              : "—"
          }
        />
        <StatCard
          label="Upset rate"
          value={predSummary?.upset_pct != null ? `${predSummary.upset_pct.toFixed(1)}%` : "—"}
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
        <ChartCard
          title="Winner accuracy over time"
          subtitle="Share of played matches where ACE correctly called the winner (50+ matches)"
        >
          <LineChart
            h={260}
            data={accuracy}
            dataKey="year"
            series={[{ name: "Accuracy", color: "teal.5" }]}
            curveType="monotone"
            withDots
            gridAxis="xy"
            yAxisProps={{ domain: [50, 100] }}
            valueFormatter={(v) => `${v}%`}
            connectNulls
          />
        </ChartCard>
        <ChartCard
          title="Brier score over time"
          subtitle="Lower is better (0 = perfect probabilities). Shown ×100 for readability."
        >
          <LineChart
            h={260}
            data={accuracy.filter((p) => p.Brier != null)}
            dataKey="year"
            series={[{ name: "Brier", color: "orange.5" }]}
            curveType="monotone"
            withDots
            gridAxis="xy"
            connectNulls
          />
        </ChartCard>
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
        <ChartCard title="By confidence" subtitle="Stronger favorites should (and do) hit more often">
          <BarChart
            h={240}
            data={confBars}
            dataKey="band"
            series={[{ name: "Accuracy", color: "teal.5" }]}
            tickLine="y"
            gridAxis="y"
            valueFormatter={(v) => `${v}%`}
          />
        </ChartCard>
        <ChartCard title="By match type" subtitle="Quals vs playoffs">
          <BarChart
            h={240}
            data={compBars}
            dataKey="level"
            series={[{ name: "Accuracy", color: "violet.5" }]}
            tickLine="y"
            gridAxis="y"
            valueFormatter={(v) => `${v}%`}
          />
        </ChartCard>
        <ChartCard title="By event type" subtitle="Where ACE calls are easiest / hardest">
          <BarChart
            h={240}
            data={typeBars}
            dataKey="type"
            series={[{ name: "Accuracy", color: "pink.5" }]}
            tickLine="y"
            gridAxis="y"
            valueFormatter={(v) => `${v}%`}
          />
        </ChartCard>
      </SimpleGrid>

      <Title order={3}>Career leaders</Title>
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <ChartCard title="Most blue banners" subtitle="Career banner-worthy awards">
          <BarChart
            h={280}
            data={bannerBars}
            dataKey="team"
            series={[{ name: "Banners", color: "blue.5" }]}
            tickLine="y"
            gridAxis="y"
          />
        </ChartCard>
        <ChartCard title="World Championship titles" subtitle="From Hall of Fame notables">
          <BarChart
            h={280}
            data={champBars}
            dataKey="team"
            series={[{ name: "Titles", color: "orange.5" }]}
            tickLine="y"
            gridAxis="y"
          />
        </ChartCard>
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
        <LeaderBoard title="Blue banners" rows={blueBanners} unit="banners" />
        <LeaderBoard title="Championship wins" rows={championshipWins} unit="titles" />
        <LeaderBoard title="Chairman's / Impact" rows={data.impact_chairmans ?? []} unit="awards" />
        <LeaderBoard
          title="Regional & DCMP Impact"
          rows={data.regional_dcmp_impact ?? []}
          unit="awards"
        />
        <LeaderBoard title="Regional wins" rows={data.regional_wins ?? []} unit="wins" />
        <LeaderBoard title="District / DCMP wins" rows={data.district_wins ?? []} unit="wins" />
        <LeaderBoard title="Division wins" rows={data.division_wins ?? []} unit="wins" />
        <LeaderBoard title="Woodie Flowers" rows={data.woodie_flowers ?? []} unit="awards" />
        <LeaderBoard
          title="Einstein appearances"
          rows={data.einstein_appearances ?? []}
          unit="years"
        />
        <LeaderBoard
          title="Longest Einstein streaks"
          rows={data.einstein_streaks ?? []}
          unit="years"
        />
      </SimpleGrid>

      <Title order={3}>Alliance teamups</Title>
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
        <TeamupBoard
          title="Most successful teamups"
          subtitle="Pairs that won the most official events together"
          rows={data.event_teamups ?? []}
          unit="wins"
        />
        <TeamupBoard
          title="Most successful Einstein teamups"
          subtitle="Pairs that won on Einstein together"
          rows={data.einstein_teamups ?? []}
          unit="wins"
        />
      </SimpleGrid>

      <Text size="xs" c="dimmed" ta="center">
        Banner classification matches Peekorobo blue-banner rules. Einstein stats use events whose
        name includes &ldquo;Einstein.&rdquo; ACE Predictions use stored win probabilities on played
        matches (Brier: mean squared error of those probs; lower is better).
      </Text>
    </Stack>
  );
}
