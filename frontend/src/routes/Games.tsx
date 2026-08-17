import { useEffect } from "react";
import {
  Badge,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import {
  IconCaretUpFilled,
  IconPlayerPlay,
  IconSwords,
  IconTrophy,
} from "@tabler/icons-react";
import { Link } from "react-router-dom";
import { gameLogo } from "../lib/assets";
import { CURRENT_YEAR } from "../lib/constants";

const GAMES = [
  {
    to: "/games/higher-lower",
    title: "Higher or Lower",
    tag: "ACE",
    blurb: "Two teams. One question. Who has the higher ACE? Streak it until you miss.",
    accent: "linear-gradient(135deg, #4a148c 0%, #7b1fa2 40%, #ffdd00 160%)",
    icon: IconCaretUpFilled,
  },
  {
    to: "/games/duel",
    title: "Duel",
    tag: "Head to head",
    blurb: "Partners, rivals, and every match two teams have ever shared. Win rates, margins, the full table.",
    accent: "linear-gradient(135deg, #8b0000 0%, #1a1a2e 50%, #003d7a 100%)",
    icon: IconSwords,
  },
  {
    to: "/games/predictor",
    title: "Match Predictor",
    tag: "Vs the model",
    blurb: "Pick winners match by match, then stack your card against Peekorobo’s predictions.",
    accent: "linear-gradient(135deg, #0b3d2e 0%, #1b5e20 45%, #ffdd00 140%)",
    icon: IconTrophy,
  },
] as const;

export function Games() {
  useEffect(() => {
    document.title = "Games - Peekorobo";
  }, []);

  return (
    <Stack gap="lg" py="md">
      <Group gap="md" wrap="nowrap" align="flex-end">
        <img
          src={gameLogo(CURRENT_YEAR)}
          alt=""
          style={{ height: 52, width: "auto", objectFit: "contain" }}
          onError={(e) => (e.currentTarget.style.display = "none")}
        />
        <div>
          <Title order={1} style={{ fontSize: 52, lineHeight: 1, fontWeight: 800 }}>
            Games
          </Title>
          <Text c="dimmed" mt={6}>
            Quick challenges tucked under Misc. No accounts, just play.
          </Text>
        </div>
      </Group>

      <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="md">
        {GAMES.map((g) => (
          <Card
            key={g.to}
            component={Link}
            to={g.to}
            className="hover-lift"
            radius="lg"
            p="lg"
            h="100%"
            style={{
              background: g.accent,
              color: "#fff",
              border: "1px solid rgba(255,255,255,0.12)",
              minHeight: 240,
              textDecoration: "none",
            }}
          >
            <Stack justify="space-between" h="100%" gap="md">
              <div>
                <Group justify="space-between" mb="sm">
                  <ThemeIcon size={42} radius="md" color="dark" variant="filled">
                    <g.icon size={22} color="#ffdd00" />
                  </ThemeIcon>
                  <Badge variant="filled" color="dark" style={{ textTransform: "none" }}>
                    {g.tag}
                  </Badge>
                </Group>
                <Title order={3} c="#fff">
                  {g.title}
                </Title>
                <Text size="sm" mt={8} style={{ color: "rgba(255,255,255,0.88)" }}>
                  {g.blurb}
                </Text>
              </div>
              <Group justify="space-between">
                <Text fw={700} size="sm" c="#ffdd00">
                  Play →
                </Text>
                <IconPlayerPlay size={18} color="#ffdd00" />
              </Group>
            </Stack>
          </Card>
        ))}
      </SimpleGrid>
    </Stack>
  );
}
