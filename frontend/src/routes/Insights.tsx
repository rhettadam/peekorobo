import { useEffect, useMemo } from "react";
import { Badge, Group, Select, Stack, Text, Title } from "@mantine/core";
import { useNavigate, useParams } from "react-router-dom";
import { useFrcGames } from "../api/queries";
import { ErrorState } from "../components/StateWrappers";
import { InsightsOverall } from "../components/InsightsOverall";
import { InsightsSeasonPanel } from "../components/InsightsSeasonPanel";

/** Insights hub: overall career stats or per-season deep dive via top dropdown. */
export function Insights() {
  const navigate = useNavigate();
  const { year: yearParam } = useParams();
  const games = useFrcGames();

  const seasons = useMemo(() => {
    const list = games.data?.games ?? [];
    return [...list].sort((a, b) => b.year - a.year);
  }, [games.data]);

  const year = yearParam ? Number(yearParam) : null;
  const game = useMemo(
    () => (year ? seasons.find((g) => g.year === year) ?? null : null),
    [seasons, year],
  );

  const selectValue = year ? String(year) : "overall";

  const selectData = useMemo(
    () => [
      { value: "overall", label: "Overall (all years)" },
      ...seasons.map((g) => ({
        value: String(g.year),
        label: g.name ? `${g.year} — ${g.name}` : String(g.year),
      })),
    ],
    [seasons],
  );

  useEffect(() => {
    if (year && game?.name) {
      document.title = `${game.name} (${year}) - Insights - Peekorobo`;
    } else if (year) {
      document.title = `${year} Insights - Peekorobo`;
    } else {
      document.title = "Insights - Peekorobo";
    }
  }, [year, game?.name]);

  const handleSelect = (val: string | null) => {
    if (!val || val === "overall") navigate("/insights");
    else navigate(`/insights/${val}`);
  };

  return (
    <Stack gap="lg" py="md">
      <Group justify="space-between" align="flex-end" wrap="wrap" gap="md">
        <Stack gap={4} style={{ flex: "1 1 280px" }}>
          <Group gap="xs">
            <Title order={1}>Insights</Title>
            <Badge color={year ? "grape" : "cyan"} variant="light" radius="sm">
              {year ?? "All years"}
            </Badge>
          </Group>
          <Text c="dimmed" maw={640}>
            {year
              ? `Season breakdown for ${game?.name ?? year}. Distributions, phase profiles, and the full ACE leaderboard.`
              : "All-time FRC growth, ACE prediction accuracy, and career leaderboards."}
          </Text>
        </Stack>
        {games.isLoading ? (
          <Select label="Season" placeholder="Loading…" data={[]} disabled w={280} />
        ) : games.error ? null : (
          <Select
            label="View"
            value={selectValue}
            data={selectData}
            onChange={handleSelect}
            allowDeselect={false}
            searchable
            w={280}
          />
        )}
      </Group>

      {games.error ? <ErrorState error={games.error} /> : null}

      {year ? (
        <InsightsSeasonPanel year={year} game={game} />
      ) : (
        <InsightsOverall />
      )}
    </Stack>
  );
}
