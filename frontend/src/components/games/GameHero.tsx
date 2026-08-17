import type { ReactNode } from "react";
import { Anchor, Box, Group, Stack, Text, Title } from "@mantine/core";
import { IconChevronLeft } from "@tabler/icons-react";
import { Link } from "react-router-dom";
import { gameLogo } from "../../lib/assets";

interface GameHeroProps {
  title: string;
  subtitle?: string;
  year?: number;
  children?: ReactNode;
}

/** Shared page header for Misc games: back link, season logo, title, trailing controls. */
export function GameHero({ title, subtitle, year, children }: GameHeroProps) {
  return (
    <Stack gap={8}>
      <Anchor component={Link} to="/games" size="sm" c="dimmed" underline="hover">
        <Group gap={4} wrap="nowrap">
          <IconChevronLeft size={14} />
          All games
        </Group>
      </Anchor>
      <Group justify="space-between" align="flex-end" wrap="wrap">
        <Group gap="md" wrap="nowrap" align="stretch">
          {year ? (
            <Box style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
              <img
                src={gameLogo(year)}
                alt={`${year} game`}
                style={{ height: "auto", width: "auto", maxHeight: 56, objectFit: "contain", display: "block" }}
                onError={(e) => (e.currentTarget.style.display = "none")}
              />
            </Box>
          ) : null}
          <div>
            <Title order={1} style={{ fontSize: 44, lineHeight: 1, fontWeight: 800 }}>
              {title}
            </Title>
            {subtitle ? (
              <Text c="dimmed" mt={6} maw={640}>
                {subtitle}
              </Text>
            ) : null}
          </div>
        </Group>
        {children}
      </Group>
    </Stack>
  );
}
