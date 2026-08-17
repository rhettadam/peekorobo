import { useEffect, useMemo, useRef, useState } from "react";
import {
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Progress,
  RingProgress,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Text,
  Title,
} from "@mantine/core";
import {
  IconCheck,
  IconPlayerPlay,
  IconRefresh,
  IconTrophy,
  IconX,
} from "@tabler/icons-react";
import { Link, useSearchParams } from "react-router-dom";
import { useEvents, usePredictorMatches } from "../api/queries";
import { GameHero } from "../components/games/GameHero";
import { DataTable, type Column } from "../components/DataTable";
import { ErrorState, LoadingState, EmptyState } from "../components/StateWrappers";
import { TeamAvatar } from "../components/TeamAvatar";
import { availableYears, CURRENT_YEAR } from "../lib/constants";
import { eventTypeLabel, eventWeekLabel, formatNumber, shortMatchLabel } from "../lib/format";
import { predictionColor } from "../lib/prediction";
import type { PredictorMatch } from "../types/api";

type PickSide = "red" | "blue";
type Phase = "setup" | "play" | "results";

interface RoundResult {
  match: PredictorMatch;
  you: PickSide;
  model: PickSide;
  actual: PickSide;
}

function modelPick(m: PredictorMatch): PickSide {
  const rp = m.red_win_prob ?? 0.5;
  return rp >= 0.5 ? "red" : "blue";
}

function AlliancePanel({
  color,
  teams,
  nicknames,
  picked,
  revealed,
  won,
  score,
  winProb,
  predScore,
  onPick,
}: {
  color: PickSide;
  teams: number[];
  nicknames: Record<string, string>;
  picked: boolean;
  revealed: boolean;
  won: boolean;
  score: number;
  winProb?: number | null;
  predScore?: number | null;
  onPick: () => void;
}) {
  const accent = color === "red" ? "#ED1C24" : "#0066B3";
  const bg = color === "red"
    ? "linear-gradient(165deg, #5a0000 0%, #1a0a0a 70%)"
    : "linear-gradient(165deg, #002a4a 0%, #0a121a 70%)";
  return (
    <Card
      className={`game-alliance-card${picked ? " is-picked" : ""}`}
      radius="lg"
      p="lg"
      onClick={revealed ? undefined : onPick}
      style={{
        background: bg,
        color: "#fff",
        border: picked ? `2px solid ${accent}` : "1px solid rgba(255,255,255,0.1)",
        boxShadow: won && revealed ? `0 0 0 3px ${accent}` : undefined,
        cursor: revealed ? "default" : "pointer",
        height: "100%",
      }}
    >
      <Stack gap="md">
        <Group justify="space-between">
          <Badge size="lg" variant="filled" color={color} style={{ textTransform: "none" }}>
            {color === "red" ? "Red Alliance" : "Blue Alliance"}
          </Badge>
          {revealed ? (
            <Badge variant="filled" color={won ? "green" : "gray"} style={{ textTransform: "none" }}>
              {won ? "Winner" : "Lost"}
            </Badge>
          ) : null}
        </Group>
        <Stack gap="sm">
          {teams.map((t) => (
            <Group key={t} gap="sm" wrap="nowrap">
              <TeamAvatar teamNumber={t} size={44} radius={8} bordered />
              <div style={{ minWidth: 0 }}>
                <Text fw={800} c="#fff" lh={1.1}>
                  {t}
                </Text>
                <Text size="sm" lineClamp={1} style={{ color: "rgba(255,255,255,0.82)" }}>
                  {nicknames[String(t)] || ""}
                </Text>
              </div>
            </Group>
          ))}
        </Stack>
        {revealed ? (
          <Stack gap={4}>
            <Text fw={900} fz={42} lh={1} c="#fff">
              {score}
            </Text>
            {typeof winProb === "number" ? (
              <Text size="sm" style={{ color: "rgba(255,255,255,0.85)" }}>
                Model {Math.round(winProb * 100)}% · pred {formatNumber(predScore, 0)}
              </Text>
            ) : null}
          </Stack>
        ) : (
          <Button color={color} variant="white" fullWidth style={{ pointerEvents: "none" }}>
            Pick {color === "red" ? "Red" : "Blue"}
          </Button>
        )}
      </Stack>
    </Card>
  );
}

export function MatchPredictor() {
  const [searchParams, setSearchParams] = useSearchParams();
  const year = Number(searchParams.get("year")) || CURRENT_YEAR;
  const eventKey = searchParams.get("event") || "";
  const mode = searchParams.get("mode") === "event" ? "event" : "mix";
  const playoffsOnly = searchParams.get("elims") === "1";
  const roundLen = Math.min(40, Math.max(5, Number(searchParams.get("n")) || 12));

  const [phase, setPhase] = useState<Phase>("setup");
  const [idx, setIdx] = useState(0);
  const [pick, setPick] = useState<PickSide | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [results, setResults] = useState<RoundResult[]>([]);
  const [seed, setSeed] = useState(() => Math.floor(Math.random() * 1_000_000));
  const [fetching, setFetching] = useState(false);
  const pickLock = useRef(false);

  const events = useEvents(year);
  const predictor = usePredictorMatches(
    year,
    {
      event_key: mode === "event" && eventKey ? eventKey : undefined,
      limit: roundLen,
      seed,
      playoffs_only: playoffsOnly,
    },
    { enabled: fetching },
  );

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
      { replace: true },
    );
  };

  useEffect(() => {
    document.title = "Match Predictor - Peekorobo";
  }, []);

  const eventOptions = useMemo(() => {
    const list = events.data?.events ?? [];
    return list.map((e) => ({
      value: e.event_key,
      label: `${e.event_data.name}${eventWeekLabel(e.week) ? ` · ${eventWeekLabel(e.week)}` : ""}`,
    }));
  }, [events.data]);

  const deck = useMemo(() => {
    const all = predictor.data?.matches ?? [];
    if (mode !== "event" || all.length <= 24) return all;
    const elims = all.filter((m) => m.comp_level !== "qm");
    const quals = all.filter((m) => m.comp_level === "qm");
    const takeQuals = Math.max(0, 24 - elims.length);
    return [...quals.slice(-takeQuals), ...elims];
  }, [predictor.data, mode]);
  const nicknames = predictor.data?.nicknames ?? {};
  const current = deck[idx];
  const total = deck.length;

  const start = () => {
    pickLock.current = false;
    setSeed(Math.floor(Math.random() * 1_000_000));
    setResults([]);
    setIdx(0);
    setPick(null);
    setRevealed(false);
    setPhase("play");
    setFetching(true);
  };

  const commitPick = (side: PickSide) => {
    if (!current || revealed || pickLock.current) return;
    pickLock.current = true;
    setPick(side);
    setRevealed(true);
    const actual = current.winning_alliance === "blue" ? "blue" : "red";
    setResults((r) => [
      ...r,
      { match: current, you: side, model: modelPick(current), actual },
    ]);
  };

  const next = () => {
    pickLock.current = false;
    if (idx + 1 >= total) {
      setPhase("results");
      return;
    }
    setIdx((i) => i + 1);
    setPick(null);
    setRevealed(false);
  };

  useEffect(() => {
    if (phase !== "play" || !current) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft" || e.key === "r" || e.key === "R") {
        e.preventDefault();
        commitPick("red");
      }
      if (e.key === "ArrowRight" || e.key === "b" || e.key === "B") {
        e.preventDefault();
        commitPick("blue");
      }
      if (revealed && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        next();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, current, revealed, idx, total]);

  const youCorrect = results.filter((r) => r.you === r.actual).length;
  const modelCorrect = results.filter((r) => r.model === r.actual).length;
  const agree = results.filter((r) => r.you === r.model).length;
  const youPct = results.length ? youCorrect / results.length : 0;
  const modelPct = results.length ? modelCorrect / results.length : 0;
  const agreePct = results.length ? agree / results.length : 0;
  const youWins = youCorrect > modelCorrect;
  const tie = youCorrect === modelCorrect;

  const resultCols = useMemo<Column<RoundResult>[]>(
    () => [
      {
        key: "match",
        header: "Match",
        render: (r) => (
          <Stack gap={0}>
            <Anchor
              size="sm"
              fw={700}
              component={Link}
              to={`/match/${r.match.event_key}/${r.match.match_key}`}
            >
              {shortMatchLabel(r.match.comp_level, r.match.set_number, r.match.match_number)}
            </Anchor>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {r.match.event_name || r.match.event_key}
            </Text>
          </Stack>
        ),
        sortValue: (r) => r.match.match_key,
      },
      {
        key: "alliances",
        header: "Alliances",
        render: (r) => (
          <Text size="xs">
            <Text span c="red" fw={700}>
              {r.match.red_teams.join("-")}
            </Text>
            {" vs "}
            <Text span c="blue" fw={700}>
              {r.match.blue_teams.join("-")}
            </Text>
          </Text>
        ),
        exportValue: (r) => `${r.match.red_teams.join(" ")} vs ${r.match.blue_teams.join(" ")}`,
      },
      {
        key: "you",
        header: "You",
        width: 80,
        render: (r) => (
          <Badge color={r.you === r.actual ? "green" : "red"} variant="filled" style={{ textTransform: "none" }}>
            {r.you}
          </Badge>
        ),
        sortValue: (r) => (r.you === r.actual ? 1 : 0),
      },
      {
        key: "model",
        header: "Model",
        width: 90,
        render: (r) => (
          <Badge color={r.model === r.actual ? "green" : "red"} variant="filled" style={{ textTransform: "none" }}>
            {r.model} {Math.round((r.model === "red" ? r.match.red_win_prob ?? 0.5 : r.match.blue_win_prob ?? 0.5) * 100)}%
          </Badge>
        ),
        cellStyle: (r) => {
          const p = r.model === "red" ? r.match.red_win_prob : r.match.blue_win_prob;
          const bg = predictionColor(p);
          return bg ? { backgroundColor: bg } : undefined;
        },
        sortValue: (r) => r.match.red_win_prob ?? 0,
      },
      {
        key: "actual",
        header: "Actual",
        width: 110,
        render: (r) => (
          <Text size="sm" fw={800} style={{ fontVariantNumeric: "tabular-nums" }}>
            <Text span c="red">
              {r.match.red_score}
            </Text>
            {" – "}
            <Text span c="blue">
              {r.match.blue_score}
            </Text>
          </Text>
        ),
      },
      {
        key: "verdict",
        header: "",
        width: 70,
        render: (r) =>
          r.you === r.actual ? <IconCheck size={18} color="var(--mantine-color-green-5)" /> : <IconX size={18} color="var(--mantine-color-red-5)" />,
        exportValue: (r) => (r.you === r.actual ? "correct" : "wrong"),
      },
    ],
    [],
  );

  return (
    <Stack gap="md" py="md">
      <GameHero
        title="Match Predictor"
        subtitle="You're shown a match. Pick a winner. At the end we line your card up against the model."
        year={year}
      />

      {phase === "setup" ? (
        <Card withBorder radius="lg" p="lg">
          <Stack gap="md">
            <Group gap="sm" align="flex-end" wrap="wrap">
              <Select
                label="Season"
                value={String(year)}
                data={availableYears().map((y) => ({ value: String(y), label: String(y) }))}
                onChange={(val) => val && setParam({ year: val, event: null })}
                allowDeselect={false}
                w={120}
              />
              <Stack gap={4}>
                <Text size="sm" fw={500}>
                  Mode
                </Text>
                <SegmentedControl
                  value={mode}
                  onChange={(v) => setParam({ mode: v })}
                  data={[
                    { value: "mix", label: "Season mix" },
                    { value: "event", label: "One event" },
                  ]}
                />
              </Stack>
              {mode === "event" ? (
                <Select
                  label="Event"
                  placeholder="Pick an event"
                  searchable
                  data={eventOptions}
                  value={eventKey || null}
                  onChange={(v) => setParam({ event: v })}
                  w={320}
                />
              ) : (
                <Select
                  label="Matches"
                  value={String(roundLen)}
                  data={["8", "12", "16", "20"].map((n) => ({ value: n, label: `${n} matches` }))}
                  onChange={(v) => v && setParam({ n: v })}
                  allowDeselect={false}
                  w={140}
                />
              )}
              <Switch
                label="Playoffs only"
                checked={playoffsOnly}
                onChange={(e) => setParam({ elims: e.currentTarget.checked ? "1" : null })}
                mb={6}
              />
            </Group>
            <Text c="dimmed" size="sm" maw={640}>
              Alliances stay hidden from the model until you lock a pick — no ACE, no win probability, just robots on
              a field. Season mix spreads matches across events. One event plays that regional in order.
            </Text>
            <Button
              size="lg"
              w="fit-content"
              leftSection={<IconPlayerPlay size={18} />}
              onClick={start}
              disabled={mode === "event" && !eventKey}
            >
              Deal the matches
            </Button>
          </Stack>
        </Card>
      ) : null}

      {phase === "play" && fetching && predictor.isLoading ? (
        <LoadingState label="Dealing matches..." />
      ) : null}
      {phase === "play" && predictor.error ? <ErrorState error={predictor.error} /> : null}
      {phase === "play" && predictor.data && total === 0 ? (
        <Card withBorder radius="md" p="lg" ta="center">
          <EmptyState>
            No played matches with predictions in this slice. Try another event or turn off playoffs-only.
          </EmptyState>
          <Button mt="md" variant="default" onClick={() => { setPhase("setup"); setFetching(false); }}>
            Back to setup
          </Button>
        </Card>
      ) : null}

      {phase === "play" && current ? (
        <>
          <Group justify="space-between" wrap="wrap">
            <div>
              <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                {eventWeekLabel(current.week) ?? "Season"} · {eventTypeLabel(current.event_type)}
              </Text>
              <Title order={3}>
                {current.event_name || current.event_key} ·{" "}
                {shortMatchLabel(current.comp_level, current.set_number, current.match_number)}
              </Title>
            </div>
            <Badge size="lg" variant="light" style={{ textTransform: "none" }}>
              {idx + 1} / {total}
            </Badge>
          </Group>
          <Progress value={((idx + (revealed ? 1 : 0)) / total) * 100} color="peeko" radius="xl" />

          <Group align="stretch" wrap="wrap" gap="md" justify="center">
            <Box style={{ flex: "1 1 280px", minWidth: 0 }}>
              <AlliancePanel
                color="red"
                teams={current.red_teams}
                nicknames={nicknames}
                picked={pick === "red"}
                revealed={revealed}
                won={current.winning_alliance === "red"}
                score={current.red_score}
                winProb={current.red_win_prob}
                predScore={current.red_predicted_score}
                onPick={() => commitPick("red")}
              />
            </Box>
            <Box
              className="game-vs-badge"
              style={{
                width: 64,
                height: 64,
                borderRadius: 999,
                background: "#ffdd00",
                color: "#111",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 900,
                fontSize: 18,
                alignSelf: "center",
                flexShrink: 0,
              }}
            >
              VS
            </Box>
            <Box style={{ flex: "1 1 280px", minWidth: 0 }}>
              <AlliancePanel
                color="blue"
                teams={current.blue_teams}
                nicknames={nicknames}
                picked={pick === "blue"}
                revealed={revealed}
                won={current.winning_alliance === "blue"}
                score={current.blue_score}
                winProb={current.blue_win_prob}
                predScore={current.blue_predicted_score}
                onPick={() => commitPick("blue")}
              />
            </Box>
          </Group>

          {revealed && pick ? (
            <Card withBorder radius="md" p="md">
              <Group justify="space-between" wrap="wrap">
                <Stack gap={4}>
                  <Text fw={800} c={pick === (current.winning_alliance === "blue" ? "blue" : "red") ? "green" : "red"}>
                    {pick === (current.winning_alliance === "blue" ? "blue" : "red") ? "You got it" : "Miss"}
                  </Text>
                  <Text size="sm" c="dimmed">
                    Model liked {modelPick(current)} at{" "}
                    {Math.round((modelPick(current) === "red" ? current.red_win_prob ?? 0.5 : current.blue_win_prob ?? 0.5) * 100)}
                    %. Actual {current.red_score}–{current.blue_score}.
                  </Text>
                </Stack>
                <Group>
                  <Button
                    variant="default"
                    component={Link}
                    to={`/match/${current.event_key}/${current.match_key}`}
                  >
                    Match page
                  </Button>
                  <Button onClick={next}>{idx + 1 >= total ? "See results" : "Next match"}</Button>
                </Group>
              </Group>
            </Card>
          ) : (
            <Text ta="center" c="dimmed" size="sm">
              Tap an alliance. ← Red · Blue → · Enter for next.
            </Text>
          )}
        </>
      ) : null}

      {phase === "results" ? (
        <Stack gap="md">
          <Card
            radius="lg"
            p="lg"
            style={{
              background: tie
                ? "linear-gradient(135deg, #3a3a00, #1a1a1a)"
                : youWins
                  ? "linear-gradient(135deg, #1b5e20, #0d2a12)"
                  : "linear-gradient(135deg, #4a148c, #1a1a1a)",
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.12)",
            }}
          >
            <Group justify="space-between" wrap="wrap" align="center">
              <div>
                <Group gap="xs" mb={6}>
                  <IconTrophy color="#ffdd00" />
                  <Text fw={800} tt="uppercase" size="sm" c="#ffdd00">
                    Final card
                  </Text>
                </Group>
                <Title order={2} c="#fff">
                  {tie ? "Dead even with the model" : youWins ? "You beat the model" : "The model edged you"}
                </Title>
                <Text style={{ color: "rgba(255,255,255,0.85)" }} mt={4}>
                  {youCorrect}–{results.length - youCorrect} yours · {modelCorrect}–{results.length - modelCorrect}{" "}
                  Peekorobo · {agree} agreements
                </Text>
              </div>
              <Button leftSection={<IconRefresh size={16} />} onClick={() => { setPhase("setup"); setFetching(false); }}>
                Play again
              </Button>
            </Group>
          </Card>

          <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
            {[
              { label: "You", pct: youPct, color: "peeko", sub: `${youCorrect}/${results.length}` },
              { label: "Model", pct: modelPct, color: "violet", sub: `${modelCorrect}/${results.length}` },
              { label: "Agreement", pct: agreePct, color: "cyan", sub: `${agree}/${results.length} same pick` },
            ].map((s) => (
              <Card withBorder radius="md" p="md" ta="center" key={s.label}>
                <RingProgress
                  size={140}
                  thickness={14}
                  roundCaps
                  mx="auto"
                  sections={[{ value: Math.round(s.pct * 100), color: s.color }]}
                  label={
                    <Text fw={800} fz="xl" ta="center">
                      {Math.round(s.pct * 100)}%
                    </Text>
                  }
                />
                <Text fw={700} mt="sm">
                  {s.label}
                </Text>
                <Text size="sm" c="dimmed">
                  {s.sub}
                </Text>
              </Card>
            ))}
          </SimpleGrid>

          <Title order={4}>Bracket card</Title>
          <DataTable
            data={results}
            columns={resultCols}
            getRowKey={(r) => r.match.match_key}
            exportFileName={`predictor-${year}`}
            rowStyle={(r) =>
              r.you === r.actual
                ? { background: "rgba(76,175,80,0.08)" }
                : { background: "rgba(244,67,54,0.06)" }
            }
          />
        </Stack>
      ) : null}
    </Stack>
  );
}
