import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  Badge,
  Box,
  Button,
  Card,
  Group,
  Progress,
  Select,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconCaretDownFilled, IconCaretUpFilled, IconFlame, IconRefresh } from "@tabler/icons-react";
import { Link, useSearchParams } from "react-router-dom";
import { useFilterOptions, useLeaderboard, useSearchIndex, useTeamInfo } from "../api/queries";
import { GameHero } from "../components/games/GameHero";
import { ErrorState, LoadingState } from "../components/StateWrappers";
import { TeamAvatar } from "../components/TeamAvatar";
import { TeamName } from "../components/TeamName";
import { AceBadge } from "../components/AceBadge";
import { RecordCell } from "../components/RecordCell";
import { teamAvatar } from "../lib/assets";
import { availableYears, CURRENT_YEAR, isDemoTeam } from "../lib/constants";
import { aceColor, computePercentiles, contrastText } from "../lib/epa";
import { formatNumber, locationString } from "../lib/format";
import type { TeamPerfResponse } from "../types/api";

interface PoolTeam {
  teamNumber: number;
  nickname: string;
  ace: number;
  raw: number | null;
  wins: number | null;
  losses: number | null;
  ties: number | null;
}

interface RoundRec {
  left: PoolTeam;
  right: PoolTeam;
  guess: "higher" | "lower";
  correct: boolean;
}

const BEST_KEY = "peekorobo.higherLower.best";

function readBest(): number {
  try {
    const n = Number(localStorage.getItem(BEST_KEY));
    return Number.isFinite(n) ? n : 0;
  } catch {
    return 0;
  }
}

function writeBest(n: number) {
  try {
    localStorage.setItem(BEST_KEY, String(n));
  } catch {
    /* ignore */
  }
}

function pickFrom(pool: PoolTeam[], exclude: Set<number>): PoolTeam | null {
  const candidates = pool.filter((t) => !exclude.has(t.teamNumber));
  if (candidates.length === 0) return pool[Math.floor(Math.random() * pool.length)] ?? null;
  return candidates[Math.floor(Math.random() * candidates.length)] ?? null;
}

function mutedBannerStyle(primary: string | null, secondary: string | null): CSSProperties {
  const p = primary ?? "#3a3a3a";
  const s = secondary ?? "#1a1a1a";
  const fill = `linear-gradient(135deg, color-mix(in srgb, ${p} 48%, #161616), color-mix(in srgb, ${s} 38%, #101010))`;
  return {
    position: "relative",
    background: [
      "linear-gradient(115deg, transparent 38%, rgba(255,255,255,0.08) 47%, transparent 56%)",
      "radial-gradient(circle at 90% 8%, rgba(255,255,255,0.16), transparent 46%)",
      "radial-gradient(rgba(255,255,255,0.10) 1.5px, transparent 1.6px)",
      "linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px)",
      "linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)",
      fill,
    ].join(", "),
    backgroundSize: "100% 100%, 100% 100%, 52px 52px, 26px 26px, 26px 26px, 100% 100%",
    color: "#fff",
    border: "none",
    overflow: "hidden",
  };
}

function PrefetchTeam({ teamNumber }: { teamNumber: number }) {
  useTeamInfo(teamNumber);
  return (
    <img
      src={teamAvatar(teamNumber)}
      alt=""
      width={1}
      height={1}
      decoding="async"
      style={{ position: "absolute", width: 0, height: 0, opacity: 0, pointerEvents: "none" }}
    />
  );
}

function TeamPlayCard({
  team,
  year,
  hideAce,
}: {
  team: PoolTeam;
  year: number;
  hideAce: boolean;
}) {
  const info = useTeamInfo(team.teamNumber);
  const colors = info.data?.team_colors as { primary?: string; secondary?: string } | null | undefined;
  const primary = typeof colors?.primary === "string" ? colors.primary : null;
  const secondary = typeof colors?.secondary === "string" ? colors.secondary : null;
  const loc = locationString(info.data?.city, info.data?.state_prov, info.data?.country);

  return (
    <Card className="game-hl-card" radius="lg" p="lg" h="100%" withBorder={false} shadow="md" style={mutedBannerStyle(primary, secondary)}>
      <Text
        aria-hidden
        style={{
          position: "absolute",
          right: -6,
          top: "50%",
          transform: "translateY(-50%)",
          fontSize: 140,
          fontWeight: 900,
          lineHeight: 1,
          letterSpacing: -6,
          color: "#fff",
          opacity: 0.07,
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        {team.teamNumber}
      </Text>
      <Stack align="center" gap="sm" style={{ position: "relative" }}>
        <TeamAvatar teamNumber={team.teamNumber} size={120} radius={16} upscale />
        <Title order={2} ta="center" c="#fff" style={{ wordBreak: "break-word", textShadow: "0 1px 2px rgba(0,0,0,0.55)" }}>
          {team.teamNumber}
        </Title>
        <Text fw={700} ta="center" lineClamp={2} c="#fff" style={{ textShadow: "0 1px 2px rgba(0,0,0,0.55)" }}>
          {team.nickname || "Unknown"}
        </Text>
        {loc ? (
          <Text size="sm" ta="center" style={{ color: "rgba(255,255,255,0.75)" }}>
            {loc}
          </Text>
        ) : null}
        <RecordCell wins={team.wins} losses={team.losses} ties={team.ties} />
        <Stack gap={2} align="center" mt="xs">
          <Text size="xs" tt="uppercase" fw={800} style={{ letterSpacing: 1, color: "rgba(255,255,255,0.7)" }}>
            Season ACE
          </Text>
          <Text
            fw={900}
            lh={1}
            c="#fff"
            className={hideAce ? "game-ace-hidden" : undefined}
            style={{ fontSize: 56, fontVariantNumeric: "tabular-nums", textShadow: "0 1px 2px rgba(0,0,0,0.55)" }}
          >
            {hideAce ? "??.?" : formatNumber(team.ace, 1)}
          </Text>
        </Stack>
        <Button component={Link} to={`/team/${team.teamNumber}/${year}`} variant="white" size="xs" color="dark">
          Team page
        </Button>
      </Stack>
    </Card>
  );
}

export function HigherLower() {
  const [searchParams, setSearchParams] = useSearchParams();
  const year = Number(searchParams.get("year")) || CURRENT_YEAR;
  const country = searchParams.get("country") || "All";
  const stateProv = searchParams.get("state") || "All";
  const district = searchParams.get("district") || "All";

  const { data: index } = useSearchIndex();
  const { data: filterOptions } = useFilterOptions();
  const leaderboardFilters = useMemo(
    () => ({
      country: country !== "All" ? country : undefined,
      state_prov: stateProv !== "All" ? stateProv : undefined,
      district_key: district !== "All" ? district : undefined,
    }),
    [country, stateProv, district],
  );
  const leaderboard = useLeaderboard(year, leaderboardFilters);
  const [best, setBest] = useState(readBest);
  const [playing, setPlaying] = useState(false);
  const [left, setLeft] = useState<PoolTeam | null>(null);
  const [right, setRight] = useState<PoolTeam | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [locked, setLocked] = useState(false);
  const [streak, setStreak] = useState(0);
  const [over, setOver] = useState(false);
  const [history, setHistory] = useState<RoundRec[]>([]);
  const [recent, setRecent] = useState<number[]>([]);
  const [queued, setQueued] = useState<PoolTeam | null>(null);
  const advanceTimer = useRef<number | null>(null);

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

  const stateOptions = useMemo(() => {
    const list =
      country !== "All"
        ? filterOptions?.statesByCountry[country] ?? []
        : filterOptions?.statesByCountry["USA"] ?? [];
    return [{ label: "All States/Provinces", value: "All" }, ...list];
  }, [filterOptions, country]);

  const pool: PoolTeam[] = useMemo(() => {
    const rows = (leaderboard.data ?? []).filter((tp: TeamPerfResponse) => !isDemoTeam(tp.team_number));
    const out: PoolTeam[] = [];
    for (const tp of rows) {
      const p = tp.team_perfs[0];
      const ace = p?.ace;
      if (typeof ace !== "number" || !Number.isFinite(ace) || ace <= 0) continue;
      out.push({
        teamNumber: tp.team_number,
        nickname: index?.teams[String(tp.team_number)]?.nickname ?? "",
        ace,
        raw: p?.raw ?? null,
        wins: p?.wins ?? null,
        losses: p?.losses ?? null,
        ties: p?.ties ?? null,
      });
    }
    return out;
  }, [leaderboard.data, index]);

  const thresholds = useMemo(() => computePercentiles(pool.map((t) => t.ace)), [pool]);

  const resetBoard = useCallback(() => {
    if (advanceTimer.current != null) {
      window.clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
    setPlaying(false);
    setLeft(null);
    setRight(null);
    setRevealed(false);
    setLocked(false);
    setStreak(0);
    setOver(false);
    setHistory([]);
    setRecent([]);
    setQueued(null);
  }, []);

  useEffect(() => {
    resetBoard();
  }, [year, country, stateProv, district, resetBoard]);

  useEffect(() => {
    document.title = `Higher or Lower - Peekorobo`;
  }, []);

  const startGame = () => {
    if (pool.length < 8) return;
    const a = pickFrom(pool, new Set());
    const b = a ? pickFrom(pool, new Set([a.teamNumber])) : null;
    if (!a || !b) return;
    // Avoid identical ACE on the opening pair.
    let rightTeam = b;
    if (rightTeam.ace === a.ace) {
      rightTeam = pickFrom(pool, new Set([a.teamNumber, b.teamNumber])) ?? b;
    }
    setLeft(a);
    setRight(rightTeam);
    setPlaying(true);
    setOver(false);
    setStreak(0);
    setHistory([]);
    setRevealed(false);
    setQueued(null);
    setRecent([a.teamNumber, rightTeam.teamNumber]);
  };

  const guess = (dir: "higher" | "lower") => {
    if (!left || !right || revealed || locked || over) return;
    setLocked(true);
    const higher = right.ace > left.ace;
    const lower = right.ace < left.ace;
    const correct =
      (dir === "higher" && (higher || right.ace === left.ace)) ||
      (dir === "lower" && (lower || right.ace === left.ace));
    setRevealed(true);
    setHistory((h) => [...h, { left, right, guess: dir, correct }]);
    const nextStreak = correct ? streak + 1 : streak;
    if (correct) {
      setStreak(nextStreak);
      if (nextStreak > best) {
        setBest(nextStreak);
        writeBest(nextStreak);
      }
    }

    let nxt: PoolTeam | null = null;
    if (correct) {
      const exclude = new Set([...recent.slice(-10), right.teamNumber]);
      nxt = pickFrom(pool, exclude);
      if (nxt && nxt.ace === right.ace) {
        nxt = pickFrom(pool, new Set([...exclude, nxt.teamNumber])) ?? nxt;
      }
      setQueued(nxt);
    }

    if (advanceTimer.current != null) window.clearTimeout(advanceTimer.current);
    const moving = right;
    advanceTimer.current = window.setTimeout(() => {
      advanceTimer.current = null;
      if (!correct || !nxt) {
        setOver(true);
        setLocked(false);
        setQueued(null);
        return;
      }
      setLeft(moving);
      setRight(nxt);
      setRecent((r) => [...r, nxt.teamNumber].slice(-16));
      setQueued(null);
      setRevealed(false);
      setLocked(false);
    }, 1150);
  };

  useEffect(() => {
    return () => {
      if (advanceTimer.current != null) window.clearTimeout(advanceTimer.current);
    };
  }, []);

  useEffect(() => {
    if (!playing || over || locked) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowUp" || e.key === "h" || e.key === "H") {
        e.preventDefault();
        guess("higher");
      }
      if (e.key === "ArrowDown" || e.key === "l" || e.key === "L") {
        e.preventDefault();
        guess("lower");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, over, locked, left, right, revealed]);

  if (leaderboard.isLoading) return <LoadingState label={`Loading ${year} teams...`} />;
  if (leaderboard.error) return <ErrorState error={leaderboard.error} />;

  return (
    <Stack gap="md" py="md">
      <GameHero
        title="Higher or Lower"
        subtitle="Guess whether the team on the right has a higher or lower ACE. Filters work like the Teams page."
        year={year}
      >
        <Group gap="sm">
          <Badge size="lg" variant="filled" color="orange" leftSection={<IconFlame size={14} />} style={{ textTransform: "none" }}>
            Streak {streak}
          </Badge>
          <Badge size="lg" variant="light" color="yellow" style={{ textTransform: "none" }}>
            Best {best}
          </Badge>
        </Group>
      </GameHero>

      <Card withBorder padding="sm" radius="md">
        <Group gap="sm" align="flex-end" wrap="wrap">
          <Select
            label="Season"
            value={String(year)}
            data={availableYears().map((y) => ({ value: String(y), label: String(y) }))}
            onChange={(val) => val && setParam({ year: val })}
            allowDeselect={false}
            w={120}
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
          {(country !== "All" || stateProv !== "All" || district !== "All") && (
            <Button variant="default" size="sm" mb={2} onClick={() => setParam({ country: null, state: null, district: null })}>
              Clear
            </Button>
          )}
        </Group>
      </Card>

      {!playing ? (
        <Card withBorder radius="lg" p="xl" ta="center">
          <Stack align="center" gap="md">
            <Text size="lg" fw={700}>
              {pool.length} teams in the pool
            </Text>
            <Text c="dimmed" maw={480}>
              Left card shows ACE. Guess whether the mystery team on the right is higher or lower. One miss ends the run.
              Arrow keys work too.
            </Text>
            <Button size="lg" onClick={startGame} disabled={pool.length < 8} leftSection={<IconCaretUpFilled size={18} />}>
              {pool.length < 8 ? "Need more teams" : "Start"}
            </Button>
          </Stack>
        </Card>
      ) : left && right ? (
        <>
          <Progress
            value={Math.min(100, (streak / Math.max(best, 10)) * 100)}
            color="peeko"
            size="sm"
            radius="xl"
          />
          <Group align="stretch" wrap="wrap" gap="md" justify="center">
            <Box style={{ flex: "1 1 280px", minWidth: 0 }}>
              <TeamPlayCard team={left} year={year} hideAce={false} />
            </Box>
            <Box
              className="game-vs-badge"
              style={{
                width: 72,
                height: 72,
                borderRadius: 999,
                background: "#ffdd00",
                color: "#111",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 900,
                fontSize: 22,
                alignSelf: "center",
                flexShrink: 0,
              }}
            >
              VS
            </Box>
            <Box style={{ flex: "1 1 280px", minWidth: 0 }}>
              <TeamPlayCard team={right} year={year} hideAce={!revealed} />
            </Box>
          </Group>
          {queued ? <PrefetchTeam teamNumber={queued.teamNumber} /> : null}

          {over ? (
            <Card withBorder radius="lg" p="lg">
              <Stack align="center" gap="sm">
                <Title order={3}>Streak over: {streak}</Title>
                <Text c="dimmed">
                  {right.nickname || right.teamNumber} had {formatNumber(right.ace, 1)} ACE vs{" "}
                  {formatNumber(left.ace, 1)} for {left.nickname || left.teamNumber}.
                </Text>
                <Group>
                  <AceBadge value={left.ace} thresholds={thresholds} />
                  <Text c="dimmed">vs</Text>
                  <AceBadge value={right.ace} thresholds={thresholds} />
                </Group>
                <Button leftSection={<IconRefresh size={16} />} onClick={startGame}>
                  Play again
                </Button>
              </Stack>
              {history.length > 0 ? (
                <Stack gap={6} mt="md">
                  {history.map((r, i) => {
                    const color = aceColor(r.right.ace, thresholds);
                    return (
                      <Group
                        key={`${r.right.teamNumber}-${i}`}
                        justify="space-between"
                        wrap="nowrap"
                        p="xs"
                        style={{
                          borderRadius: 8,
                          background: r.correct ? "rgba(76,175,80,0.12)" : "rgba(244,67,54,0.12)",
                        }}
                      >
                        <Group gap="sm" wrap="nowrap">
                          <Text fw={700} w={24} ta="center">
                            {i + 1}
                          </Text>
                          <TeamAvatar teamNumber={r.left.teamNumber} size={22} radius={4} />
                          <Text size="sm">{formatNumber(r.left.ace, 1)}</Text>
                          <Text c="dimmed" size="sm">
                            →
                          </Text>
                          <TeamAvatar teamNumber={r.right.teamNumber} size={22} radius={4} />
                          <TeamName teamNumber={r.right.teamNumber} year={year} withNumber />
                        </Group>
                        <Badge
                          variant="filled"
                          style={{
                            textTransform: "none",
                            backgroundColor: color,
                            color: color ? contrastText(color) : undefined,
                          }}
                        >
                          {formatNumber(r.right.ace, 1)} · {r.guess}
                        </Badge>
                      </Group>
                    );
                  })}
                </Stack>
              ) : null}
            </Card>
          ) : (
            <Group justify="center" gap="md" wrap="wrap">
              <Button
                size="xl"
                color="green"
                disabled={locked}
                leftSection={<IconCaretUpFilled size={22} />}
                onClick={() => guess("higher")}
                w={{ base: "100%", sm: 220 }}
              >
                Higher
              </Button>
              <Button
                size="xl"
                color="red"
                disabled={locked}
                leftSection={<IconCaretDownFilled size={22} />}
                onClick={() => guess("lower")}
                w={{ base: "100%", sm: 220 }}
              >
                Lower
              </Button>
            </Group>
          )}
        </>
      ) : null}
    </Stack>
  );
}
