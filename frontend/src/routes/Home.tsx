import { useEffect } from "react";
import { Anchor, Box, Button, Grid, Group, Stack, Text, Title } from "@mantine/core";
import { IconCalendarEvent, IconUsers } from "@tabler/icons-react";
import { Link } from "react-router-dom";
import { SearchBar } from "../components/SearchBar";
import { CURRENT_YEAR } from "../lib/constants";
import { BRAND } from "../lib/assets";

export function Home() {
  useEffect(() => {
    document.title = "Peekorobo";
  }, []);

  return (
    <Stack gap={48} justify="center" style={{ flexGrow: 1 }}>
      <Grid gutter={{ base: "lg", md: 48 }} align="center">
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Box visibleFrom="md" style={{ display: "flex", justifyContent: "center" }}>
            <img
              src={BRAND.home}
              alt="Peekorobo"
              style={{ width: "100%", maxWidth: 460, height: "auto", display: "block" }}
            />
          </Box>
          <Box hiddenFrom="md" style={{ display: "flex", justifyContent: "center" }}>
            <img
              src={BRAND.mobileHome}
              alt="Peekorobo"
              style={{ width: "100%", maxWidth: 320, height: "auto", display: "block" }}
            />
          </Box>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 6 }}>
          <Stack gap="md">
            <Title order={1} fz={{ base: 34, sm: 44 }} lh={1.05}>
              Data-Driven FRC Insights
            </Title>
            <Text c="dimmed" size="lg">
              Explore teams, events, and matches from the{" "}
              <Anchor
                href="https://www.firstinspires.org/robotics/frc"
                target="_blank"
                rel="noopener noreferrer"
              >
                FIRST Robotics Competition
              </Anchor>
              .
            </Text>
            <div style={{ maxWidth: 520 }}>
              <SearchBar size="md" />
            </div>
            <Group gap="sm">
              <Button component={Link} to="/teams" leftSection={<IconUsers size={18} />}>
                Teams
              </Button>
              <Button
                component={Link}
                to="/events"
                variant="default"
                leftSection={<IconCalendarEvent size={18} />}
              >
                Events
              </Button>
            </Group>
            <Text size="sm" c="dimmed">
              Jump into the {CURRENT_YEAR} season.
            </Text>
          </Stack>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
