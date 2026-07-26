import { Text } from "@mantine/core";
import type { MatchResponse } from "../types/api";
import { formatPredictedTime } from "../lib/format";
import { isPlayed, predictedMatchScores } from "../lib/prediction";

type AceMap = Map<number, number | null | undefined>;

/** Actual match score (or scheduled time / TBD if unplayed). */
export function MatchActualScoreCell({ match }: { match: MatchResponse }) {
  const played = isPlayed(match);
  if (played) {
    const redWin = match.winning_alliance === "red";
    const blueWin = match.winning_alliance === "blue";
    return (
      <Text span size="sm" style={{ whiteSpace: "nowrap" }}>
        <Text fw={redWin ? 700 : 400} c={redWin ? "red" : undefined} span>
          {match.red_score}
        </Text>
        {" - "}
        <Text fw={blueWin ? 700 : 400} c={blueWin ? "blue" : undefined} span>
          {match.blue_score}
        </Text>
      </Text>
    );
  }
  const when = formatPredictedTime(match.predicted_time);
  return (
    <Text
      c="dimmed"
      span
      size="sm"
      title={when ? "Predicted start (local time)" : undefined}
    >
      {when ?? "TBD"}
    </Text>
  );
}

/** Predicted alliance scores = sum of event ACE. */
export function MatchPredScoreCell({
  match,
  aceByTeam,
}: {
  match: MatchResponse;
  aceByTeam?: AceMap;
}) {
  const pred = predictedMatchScores(match, aceByTeam);
  if (!pred) {
    return (
      <Text c="dimmed" span>
        –
      </Text>
    );
  }
  const redWin = pred.red > pred.blue;
  const blueWin = pred.blue > pred.red;
  return (
    <Text span size="sm" title="Predicted score (sum of event ACE)" style={{ whiteSpace: "nowrap" }}>
      <Text fw={redWin ? 700 : 400} c={redWin ? "red" : undefined} span>
        {Math.round(pred.red)}
      </Text>
      {" - "}
      <Text fw={blueWin ? 700 : 400} c={blueWin ? "blue" : undefined} span>
        {Math.round(pred.blue)}
      </Text>
    </Text>
  );
}
