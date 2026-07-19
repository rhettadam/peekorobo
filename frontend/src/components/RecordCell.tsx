import { Text } from "@mantine/core";

interface RecordCellProps {
  wins?: number | null;
  losses?: number | null;
  ties?: number | null;
}

/** Win-loss(-tie) record with wins green, losses red, ties grey. */
export function RecordCell({ wins, losses, ties }: RecordCellProps) {
  const w = wins ?? 0;
  const l = losses ?? 0;
  const t = ties ?? 0;
  return (
    <Text span fw={600} style={{ fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
      <Text span c="green.5" inherit>
        {w}
      </Text>
      <Text span c="dimmed" inherit>
        -
      </Text>
      <Text span c="red.5" inherit>
        {l}
      </Text>
      {t > 0 ? (
        <>
          <Text span c="dimmed" inherit>
            -
          </Text>
          <Text span c="gray.5" inherit>
            {t}
          </Text>
        </>
      ) : null}
    </Text>
  );
}
