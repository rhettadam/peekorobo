import { useMemo, useState } from "react";
import { Avatar, Box, Group, SimpleGrid, Stack, Text, TextInput, UnstyledButton } from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import { useSearchIndex } from "../api/queries";
import { STOCK_AVATAR, userAvatar } from "../lib/assets";
import { TeamAvatar } from "./TeamAvatar";

interface AvatarPickerProps {
  value: string; // avatar_key, e.g. "254.png" or "stock"
  onChange: (avatarKey: string) => void;
  /** Optional team number to suggest first (e.g. the user's team affiliation). */
  suggestTeam?: string;
}

const MAX_RESULTS = 48;

/**
 * Avatar gallery picker mirroring the old Dash app: pick from team avatars or the
 * stock avatar. Uses the static search index for team numbers/nicknames and only
 * renders a capped number of tiles at once (search to narrow), so it stays fast
 * even though there are thousands of teams.
 */
export function AvatarPicker({ value, onChange, suggestTeam }: AvatarPickerProps) {
  const { data: index } = useSearchIndex();
  const [search, setSearch] = useState("");

  const teamNumbers = useMemo(() => {
    if (!index?.teams) return [] as string[];
    return Object.keys(index.teams);
  }, [index]);

  const results = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) {
      // Default view: the suggested team (if any) so there's something to click.
      return suggestTeam && teamNumbers.includes(suggestTeam) ? [suggestTeam] : [];
    }
    const matches: string[] = [];
    for (const num of teamNumbers) {
      const nickname = index?.teams[num]?.nickname ?? "";
      if (num.startsWith(q) || nickname.toLowerCase().includes(q)) {
        matches.push(num);
        if (matches.length >= MAX_RESULTS) break;
      }
    }
    // Prefer numeric-prefix matches ordered by number.
    return matches.sort((a, b) => {
      const aStarts = a.startsWith(q) ? 0 : 1;
      const bStarts = b.startsWith(q) ? 0 : 1;
      if (aStarts !== bStarts) return aStarts - bStarts;
      return Number(a) - Number(b);
    });
  }, [search, teamNumbers, index, suggestTeam]);

  const isStock = !value || value === "stock" || value === "stock.png";

  return (
    <Stack gap="xs">
      <Group gap="sm" align="center">
        <Text size="sm" fw={600}>
          Avatar
        </Text>
        <Avatar src={userAvatar(value)} size={40} radius="md" />
        <Text size="xs" c="dimmed">
          {isStock ? "Stock avatar" : value}
        </Text>
      </Group>

      <TextInput
        placeholder="Search a team number or name..."
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
        leftSection={<IconSearch size={16} />}
        size="sm"
      />

      <SimpleGrid cols={{ base: 5, sm: 8 }} spacing="xs">
        {/* Stock option always available. */}
        <UnstyledButton onClick={() => onChange("stock")} title="Stock avatar">
          <Box
            style={{
              border: isStock ? "2px solid #ffdd00" : "1px solid var(--mantine-color-default-border)",
              borderRadius: 8,
              padding: 4,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
            }}
          >
            <img src={STOCK_AVATAR} alt="Stock" width={40} height={40} style={{ objectFit: "contain" }} />
            <Text size="9px" c="dimmed">
              Stock
            </Text>
          </Box>
        </UnstyledButton>

        {results.map((num) => {
          const key = `${num}.png`;
          const selected = value === key;
          return (
            <UnstyledButton key={num} onClick={() => onChange(key)} title={`Team ${num}`}>
              <Box
                style={{
                  border: selected ? "2px solid #ffdd00" : "1px solid var(--mantine-color-default-border)",
                  borderRadius: 8,
                  padding: 4,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                }}
              >
                <TeamAvatar teamNumber={num} size={40} radius={6} />
                <Text size="9px" c="dimmed">
                  {num}
                </Text>
              </Box>
            </UnstyledButton>
          );
        })}
      </SimpleGrid>

      {search.trim() && results.length === 0 ? (
        <Text size="xs" c="dimmed">
          No teams match "{search}".
        </Text>
      ) : !search.trim() ? (
        <Text size="xs" c="dimmed">
          Search a team number to use that team's avatar, or keep the stock avatar.
        </Text>
      ) : results.length >= MAX_RESULTS ? (
        <Text size="xs" c="dimmed">
          Showing the first {MAX_RESULTS} matches — keep typing to narrow.
        </Text>
      ) : null}
    </Stack>
  );
}
