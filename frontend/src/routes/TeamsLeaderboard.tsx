import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Card,
  Group,
  Select,
  SimpleGrid,
  Slider,
  Stack,
  Switch,
  Tabs,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import { Link, useSearchParams } from "react-router-dom";
import {
  useFilterOptions,
  useLeaderboard,
  useLeaderboardPreview,
  useSearchIndex,
  useTeamInfo,
} from "../api/queries";
import { ErrorState, LoadingState } from "../components/StateWrappers";
import { TeamName } from "../components/TeamName";
import { TeamAvatar } from "../components/TeamAvatar";
import { MetricCell, ConfidenceCell } from "../components/MetricCell";
import { AceLegend } from "../components/AceLegend";
import { RecordCell } from "../components/RecordCell";
import { DataTable, type Column } from "../components/DataTable";
import { TeamBubbleChart } from "../components/TeamBubbleChart";
import { gameLogo, teamAvatar, STOCK_AVATAR } from "../lib/assets";
import { availableYears, CURRENT_YEAR, isDemoTeam } from "../lib/constants";
import { computePercentiles, contrastText, median } from "../lib/epa";
import { formatNumber } from "../lib/format";
import { useFavoriteCounts } from "../api/favorites";
import { IconStarFilled } from "@tabler/icons-react";

interface Row {
  teamNumber: number;
  ace: number | null;
  raw: number | null;
  confidence: number | null;
  auto: number | null;
  teleop: number | null;
  endgame: number | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
  rankGlobal: number | null;
  favorites: number;
}

const TILE_BG = { blue: "#0066B3", red: "#ED1C24" } as const;

/** Top-3 spotlight card colored by the team's own color gradient. */
function SpotlightCard({
  teamNumber,
  nickname,
  ace,
  year,
}: {
  teamNumber: number;
  nickname: string;
  ace: number | null;
  year: number;
}) {
  const info = useTeamInfo(teamNumber);
  const colors = info.data?.team_colors as
    | { primary?: string; secondary?: string }
    | null
    | undefined;
  const primary = typeof colors?.primary === "string" ? colors.primary : null;
  const secondary = typeof colors?.secondary === "string" ? colors.secondary : null;
  const gradient =
    primary && secondary
      ? `linear-gradient(135deg, ${primary}, ${secondary})`
      : "linear-gradient(135deg, #3a3a3a, #1a1a1a)";
  const text = primary ? contrastText(primary) : "#ffffff";
  const dim = text === "#000000" ? "rgba(0,0,0,0.7)" : "rgba(255,255,255,0.9)";
  return (
    <Card radius="lg" p="md" style={{ background: gradient, color: text, border: "none" }}>
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <Stack gap={2} style={{ minWidth: 0 }}>
          <Text fw={800} fz="lg" c={text} style={{ wordBreak: "break-word" }}>
            #{teamNumber}
          </Text>
          <Text fw={600} lineClamp={1} c={text}>
            {nickname || "\u00a0"}
          </Text>
          <Text fz="sm" c={dim}>
            ACE {formatNumber(ace, 1)}
          </Text>
          <Button
            component={Link}
            to={`/team/${teamNumber}/${year}`}
            size="xs"
            variant="default"
            mt={6}
            w="fit-content"
          >
            Peek
          </Button>
        </Stack>
        <TeamAvatar teamNumber={teamNumber} size={72} radius={8} />
      </Group>
    </Card>
  );
}

export function TeamsLeaderboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const year = Number(searchParams.get("year")) || CURRENT_YEAR;
  const [filter, setFilter] = useState("");
  const [tab, setTab] = useState<string>("leaderboard");
  const [avatarSize, setAvatarSize] = useState(48);
  const [tileBg, setTileBg] = useState<keyof typeof TILE_BG>("blue");
  // Location filters live in the URL so a filtered leaderboard is shareable
  // (e.g. /teams?year=2025&country=USA&state=Louisiana or ?district=fim).
  const country = searchParams.get("country") || "All";
  const stateProv = searchParams.get("state") || "All";
  const district = searchParams.get("district") || "All";
  const [percentileFiltered, setPercentileFiltered] = useState(false);

  const setParam = (updates: Record<string, string | null>) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(updates)) {
          if (v === null || v === "" || v === "All") next.delete(k);
          else next.set(k, v);
        }
        return next;
      },
      { replace: false },
    );
  };
  // The full year is heavy to load, so we start with a fast top-100 preview and
  // only fetch the whole year once the user interacts (search / paginate / sort /
  // location filter / a data-heavy tab).
  const [fullRequested, setFullRequested] = useState(false);

  const { data: index } = useSearchIndex();
  const { data: filterOptions } = useFilterOptions();
  const { data: favoriteCounts } = useFavoriteCounts("team");

  const leaderboardFilters = useMemo(
    () => ({
      country: country !== "All" ? country : undefined,
      state_prov: stateProv !== "All" ? stateProv : undefined,
      district_key: district !== "All" ? district : undefined,
    }),
    [country, stateProv, district],
  );
  const hasLocationFilter = Boolean(
    leaderboardFilters.country || leaderboardFilters.state_prov || leaderboardFilters.district_key,
  );

  // A location filter always needs the full (filtered) year from the API.
  const needFull = fullRequested || hasLocationFilter;

  // Fast initial paint: top 100 by global ACE rank.
  const preview = useLeaderboardPreview(year);
  // Full year, deferred until the user actually needs it.
  const leaderboard = useLeaderboard(year, leaderboardFilters, { enabled: needFull });
  // Unfiltered year snapshot: only needed as the "global" percentile basis when a
  // location filter is active.
  const globalLeaderboard = useLeaderboard(year, {}, { enabled: hasLocationFilter });

  // A brand-new season resets us back to the fast preview.
  useEffect(() => {
    setFullRequested(false);
  }, [year]);

  // The data currently driving the table: full year once loaded, otherwise the
  // top-100 preview (but never the preview when a location filter is applied).
  const activeData = leaderboard.data ?? (hasLocationFilter ? undefined : preview.data);
  const showingPreview = !leaderboard.data && !hasLocationFilter;
  const loadingFull = needFull && leaderboard.isLoading;

  const stateOptions = useMemo(() => {
    const list =
      country !== "All"
        ? filterOptions?.statesByCountry[country] ?? []
        : filterOptions?.statesByCountry["USA"] ?? [];
    return [{ label: "All States/Provinces", value: "All" }, ...list];
  }, [filterOptions, country]);

  useEffect(() => {
    document.title = `${year} Teams - Peekorobo`;
  }, [year]);

  const nicknameOf = (tn: number) => index?.teams[String(tn)]?.nickname ?? "";

  const rows: Row[] = useMemo(() => {
    const data = activeData ?? [];
    const favByTeam = favoriteCounts?.counts ?? {};
    const flat: Row[] = data.map((tp) => {
      const p = tp.team_perfs[0];
      return {
        teamNumber: tp.team_number,
        ace: p?.ace ?? null,
        raw: p?.raw ?? null,
        confidence: p?.confidence ?? null,
        auto: p?.auto_raw ?? null,
        teleop: p?.teleop_raw ?? null,
        endgame: p?.endgame_raw ?? null,
        wins: p?.wins ?? null,
        losses: p?.losses ?? null,
        ties: p?.ties ?? null,
        rankGlobal: p?.rank_global ?? null,
        favorites: favByTeam[String(tp.team_number)] ?? 0,
      };
    });
    flat.sort((a, b) => (b.ace ?? -Infinity) - (a.ace ?? -Infinity));
    return flat;
  }, [activeData, favoriteCounts]);

  const realRows = useMemo(() => rows.filter((r) => !isDemoTeam(r.teamNumber)), [rows]);

  // Global (unfiltered) rows used as the default percentile-coloring basis.
  const globalRealRows = useMemo(() => {
    const data = globalLeaderboard.data ?? [];
    return data
      .filter((tp) => !isDemoTeam(tp.team_number))
      .map((tp) => tp.team_perfs[0])
      .filter((p): p is NonNullable<typeof p> => Boolean(p));
  }, [globalLeaderboard.data]);

  // When "Filter Percentiles" is on, color-scale thresholds come from the
  // currently displayed (filtered) rows; otherwise from the global year set.
  const basis = useMemo(() => {
    if (percentileFiltered || !hasLocationFilter) {
      return {
        ace: realRows.map((r) => r.ace),
        auto: realRows.map((r) => r.auto),
        teleop: realRows.map((r) => r.teleop),
        endgame: realRows.map((r) => r.endgame),
        confidence: realRows.map((r) => r.confidence),
      };
    }
    return {
      ace: globalRealRows.map((p) => p.ace),
      auto: globalRealRows.map((p) => p.auto_raw),
      teleop: globalRealRows.map((p) => p.teleop_raw),
      endgame: globalRealRows.map((p) => p.endgame_raw),
      confidence: globalRealRows.map((p) => p.confidence),
    };
  }, [percentileFiltered, hasLocationFilter, realRows, globalRealRows]);

  const thresholds = useMemo(
    () => ({
      ace: computePercentiles(basis.ace),
      auto: computePercentiles(basis.auto),
      teleop: computePercentiles(basis.teleop),
      endgame: computePercentiles(basis.endgame),
    }),
    [basis],
  );
  const confMedian = useMemo(() => median(basis.confidence), [basis]);

  const matchesFilter = (r: Row, q: string) => {
    if (!q) return true;
    return String(r.teamNumber).includes(q) || nicknameOf(r.teamNumber).toLowerCase().includes(q);
  };

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => matchesFilter(r, q));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, filter, index]);

  const spotlight = useMemo(() => realRows.slice(0, 3), [realRows]);

  const bubbleHighlight = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return [];
    return realRows.filter((r) => matchesFilter(r, q)).map((r) => r.teamNumber);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [realRows, filter, index]);

  const bubbleTeams = useMemo(
    () =>
      realRows.map((r) => ({
        teamNumber: r.teamNumber,
        nickname: nicknameOf(r.teamNumber),
        ace: r.ace,
        raw: r.raw,
        auto: r.auto,
        teleop: r.teleop,
        endgame: r.endgame,
        confidence: r.confidence,
        wins: r.wins,
        losses: r.losses,
        ties: r.ties,
        rank: r.rankGlobal,
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [realRows, index],
  );

  const leaderboardColumns = useMemo<Column<Row>[]>(
    () => [
      {
        key: "rank",
        header: "ACE Rank",
        width: 90,
        sortValue: (r) => r.rankGlobal,
        render: (r, i) => r.rankGlobal ?? i + 1,
      },
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
      { key: "raw", header: "RAW", width: 80, sortValue: (r) => r.raw, render: (r) => formatNumber(r.raw) },
      {
        key: "confidence",
        header: "Confidence",
        width: 110,
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
        width: 80,
        sortValue: (r) => r.auto,
        render: (r) => <MetricCell value={r.auto} thresholds={thresholds.auto} />,
      },
      {
        key: "teleop",
        header: "Teleop",
        width: 80,
        sortValue: (r) => r.teleop,
        render: (r) => <MetricCell value={r.teleop} thresholds={thresholds.teleop} />,
      },
      {
        key: "endgame",
        header: "Endgame",
        width: 90,
        sortValue: (r) => r.endgame,
        render: (r) => <MetricCell value={r.endgame} thresholds={thresholds.endgame} />,
      },
      {
        key: "record",
        header: "Record",
        width: 100,
        sortValue: (r) => r.wins,
        exportValue: (r) => `${r.wins ?? 0}-${r.losses ?? 0}-${r.ties ?? 0}`,
        render: (r) => <RecordCell wins={r.wins} losses={r.losses} ties={r.ties} />,
      },
      {
        key: "favorites",
        header: "Favorites",
        width: 100,
        sortValue: (r) => r.favorites,
        render: (r) => (
          <Group gap={4} wrap="nowrap" justify="flex-start">
            <IconStarFilled size={14} color="var(--peeko-link)" style={{ flexShrink: 0 }} />
            <Text span fz="sm" fw={r.favorites > 0 ? 600 : 400}>
              {r.favorites}
            </Text>
          </Group>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [thresholds, confMedian, year, index],
  );

  if (!activeData && (preview.isLoading || leaderboard.isLoading))
    return <LoadingState label={`Loading ${year} leaderboard...`} />;
  if (!activeData && (leaderboard.error || preview.error))
    return <ErrorState error={(leaderboard.error || preview.error)!} />;

  return (
    <Stack gap="md" py="md">
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
          <Title order={1} style={{ fontSize: 56, lineHeight: 1, fontWeight: 800 }}>
            Teams
          </Title>
        </Group>
        <Select
          label="Season"
          value={String(year)}
          data={availableYears().map((y) => ({ value: String(y), label: String(y) }))}
          onChange={(val) => val && setParam({ year: val })}
          allowDeselect={false}
          w={120}
        />
      </Group>

      <Card withBorder padding="sm" radius="md">
        <Group gap="sm" align="flex-end" wrap="wrap">
          <TextInput
            label="Search"
            placeholder="Team # or name"
            leftSection={<IconSearch size={16} />}
            value={filter}
            onChange={(e) => {
              const v = e.currentTarget.value;
              setFilter(v);
              if (v.trim()) setFullRequested(true);
            }}
            w={200}
          />
          <Select
            label="Country"
            data={filterOptions?.countries ?? [{ label: "All Countries", value: "All" }]}
            value={country}
            onChange={(val) => setParam({ country: val ?? "All", state: null })}
            allowDeselect={false}
            searchable
            w={180}
          />
          <Select
            label="State/Province"
            data={stateOptions}
            value={stateProv}
            onChange={(val) => setParam({ state: val ?? "All" })}
            allowDeselect={false}
            searchable
            w={180}
          />
          <Select
            label="District"
            data={filterOptions?.districts ?? [{ label: "All Districts", value: "All" }]}
            value={district}
            onChange={(val) => setParam({ district: val ?? "All" })}
            allowDeselect={false}
            searchable
            w={200}
          />
          <Switch
            label="Filter Percentiles"
            checked={percentileFiltered}
            onChange={(e) => setPercentileFiltered(e.currentTarget.checked)}
            mb={6}
          />
          {hasLocationFilter || filter ? (
            <Button
              variant="default"
              size="sm"
              mb={2}
              onClick={() => {
                setParam({ country: null, state: null, district: null });
                setFilter("");
              }}
            >
              Clear
            </Button>
          ) : null}
        </Group>
      </Card>

      {spotlight.length === 3 ? (
        <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
          {spotlight.map((r) => (
            <SpotlightCard
              key={r.teamNumber}
              teamNumber={r.teamNumber}
              nickname={nicknameOf(r.teamNumber)}
              ace={r.ace}
              year={year}
            />
          ))}
        </SimpleGrid>
      ) : null}

      <Tabs
        value={tab}
        onChange={(v) => {
          const next = v ?? "leaderboard";
          setTab(next);
          // Avatars + bubble chart both need the whole field.
          if (next === "avatars" || next === "bubble") setFullRequested(true);
        }}
        keepMounted={false}
      >
        <Tabs.List>
          <Tabs.Tab value="leaderboard">Leaderboard</Tabs.Tab>
          <Tabs.Tab value="avatars">Avatars</Tabs.Tab>
          <Tabs.Tab value="bubble">Bubble Chart</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="leaderboard" pt="md">
          <Stack gap="md">
            <AceLegend />
            {showingPreview ? (
              <Group justify="space-between" align="center" wrap="wrap">
                <Text size="sm" c="dimmed">
                  Showing the top {filtered.length} teams for a fast load.
                </Text>
                <Button
                  variant="default"
                  size="xs"
                  loading={loadingFull}
                  onClick={() => setFullRequested(true)}
                >
                  Load full season
                </Button>
              </Group>
            ) : loadingFull ? (
              <Text size="sm" c="dimmed">
                Loading the full season…
              </Text>
            ) : null}
            <DataTable
              data={filtered}
              columns={leaderboardColumns}
              getRowKey={(r) => r.teamNumber}
              initialSort={{ key: "ace", dir: "desc" }}
              minWidth={820}
              stickyHeader
              defaultPageSize={50}
              onInteract={() => setFullRequested(true)}
              exportFileName={`peekorobo-teams-${year}`}
            />
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="avatars" pt="md">
          <Stack gap="md">
            <Group justify="space-between" align="center" wrap="wrap">
              <Text size="sm" c="dimmed">
                {filtered.length.toLocaleString()} teams
              </Text>
              <Group gap="lg" align="center">
                <Group gap="xs" align="center">
                  <Text size="sm">Size</Text>
                  <Slider
                    w={160}
                    min={32}
                    max={80}
                    step={4}
                    value={avatarSize}
                    onChange={setAvatarSize}
                    marks={[
                      { value: 32 },
                      { value: 48 },
                      { value: 64 },
                      { value: 80 },
                    ]}
                  />
                </Group>
                <Button
                  variant="default"
                  size="xs"
                  onClick={() => setTileBg((b) => (b === "blue" ? "red" : "blue"))}
                >
                  Toggle Background
                </Button>
              </Group>
            </Group>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: `repeat(auto-fill, minmax(${avatarSize + 8}px, 1fr))`,
                gap: 8,
              }}
            >
              {filtered.map((r) => (
                <Link
                  key={r.teamNumber}
                  to={`/team/${r.teamNumber}/${year}`}
                  title={`${r.teamNumber} | ${nicknameOf(r.teamNumber)}`}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 2,
                    padding: 4,
                    borderRadius: 8,
                    background: TILE_BG[tileBg],
                    textDecoration: "none",
                  }}
                >
                  <img
                    src={teamAvatar(r.teamNumber)}
                    alt={`Team ${r.teamNumber}`}
                    width={avatarSize}
                    height={avatarSize}
                    loading="lazy"
                    onError={(e) => (e.currentTarget.src = STOCK_AVATAR)}
                    style={{ imageRendering: "pixelated", objectFit: "contain" }}
                  />
                  <span style={{ color: "#fff", fontSize: 11, fontWeight: 600 }}>
                    {r.teamNumber}
                  </span>
                </Link>
              ))}
            </div>
          </Stack>
        </Tabs.Panel>

        <Tabs.Panel value="bubble" pt="md">
          <TeamBubbleChart
            teams={bubbleTeams}
            year={year}
            nicknameOf={nicknameOf}
            highlighted={bubbleHighlight}
            aceThresholds={thresholds.ace}
            defaultX="auto"
            defaultY="teleop"
          />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
