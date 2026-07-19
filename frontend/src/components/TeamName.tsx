import { Anchor } from "@mantine/core";
import { Link } from "react-router-dom";
import { useSearchIndex } from "../api/queries";
import { CURRENT_YEAR } from "../lib/constants";

interface TeamNameProps {
  teamNumber: number;
  year?: number;
  nickname?: string;
  withNumber?: boolean;
  /** Show only the team number (used in match tables, which never show names). */
  numberOnly?: boolean;
  fw?: number;
}

/**
 * Link to a team page. Falls back to the static search index for the nickname
 * and the team's last active year when not provided.
 */
export function TeamName({
  teamNumber,
  year,
  nickname,
  withNumber = true,
  numberOnly = false,
  fw = 500,
}: TeamNameProps) {
  const { data: index } = useSearchIndex();
  const entry = index?.teams[String(teamNumber)];
  const resolvedNickname = nickname ?? entry?.nickname ?? "";
  const linkYear = year ?? entry?.last_year ?? CURRENT_YEAR;
  const label = numberOnly
    ? String(teamNumber)
    : withNumber
      ? resolvedNickname
        ? `${teamNumber} | ${resolvedNickname}`
        : String(teamNumber)
      : resolvedNickname || String(teamNumber);

  return (
    <Anchor component={Link} to={`/team/${teamNumber}/${linkYear}`} fw={fw}>
      {label}
    </Anchor>
  );
}
