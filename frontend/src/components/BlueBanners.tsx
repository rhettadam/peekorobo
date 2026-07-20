import { Anchor, Badge, Box, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { Link } from "react-router-dom";
import { BRAND } from "../lib/assets";
import { blueBannerKind } from "../lib/banners";
import { yearFromEventKey } from "../lib/format";
import type { TeamAwardData } from "../types/api";

/** Event code without the leading season year, e.g. "2024cmptx" -> "CMPTX". */
function shortEventLabel(eventKey: string): string {
  return eventKey.replace(/^\d{4}/, "").toUpperCase();
}

interface BlueBannersProps {
  awards: TeamAwardData[];
  title?: string;
}

/**
 * A wall of FRC blue banners for a team's banner-worthy awards. Each banner uses
 * the shared banner.png artwork with the award name / event / year overlaid, and
 * links to the event page. Renders nothing when there are no qualifying awards.
 */
export function BlueBanners({ awards, title = "Blue Banners" }: BlueBannersProps) {
  const banners = awards
    .map((a) => ({
      ...a,
      kind: blueBannerKind(a.award_name),
      year: yearFromEventKey(a.event_key),
    }))
    .filter((a) => a.kind !== null)
    .sort((a, b) => (b.year ?? 0) - (a.year ?? 0));

  if (banners.length === 0) return null;

  return (
    <Stack gap="sm">
      <Group gap="xs" align="center">
        <Title order={3}>{title}</Title>
        <Badge color="blue" variant="filled" size="lg" radius="sm">
          {banners.length}
        </Badge>
      </Group>
      <SimpleGrid cols={{ base: 3, xs: 4, sm: 5, md: 6, lg: 8 }} spacing="md">
        {banners.map((b, i) => (
          <Anchor
            key={`${b.event_key}-${b.award_name}-${i}`}
            component={Link}
            to={`/event/${b.event_key}`}
            underline="never"
            className="hover-lift"
            title={`${b.award_name} — ${b.event_key}`}
          >
            <Box
              style={{
                position: "relative",
                aspectRatio: "269 / 440",
                backgroundImage: `url(${BRAND.banner})`,
                backgroundSize: "contain",
                backgroundPosition: "center top",
                backgroundRepeat: "no-repeat",
                filter: "drop-shadow(0 4px 10px rgba(0,0,0,0.45))",
              }}
            >
              <Box
                style={{
                  position: "absolute",
                  top: "34%",
                  left: 0,
                  right: 0,
                  padding: "0 8px",
                  textAlign: "center",
                }}
              >
                <Text
                  fw={800}
                  lh={1.15}
                  c="#ffffff"
                  style={{ fontSize: "clamp(0.6rem, 1.4vw, 0.82rem)", textShadow: "0 1px 3px rgba(0,0,0,0.6)" }}
                  lineClamp={4}
                >
                  {b.award_name}
                </Text>
                <Text
                  mt={6}
                  c="#ffdd00"
                  fw={700}
                  style={{ fontSize: "clamp(0.7rem, 1.5vw, 0.95rem)", textShadow: "0 1px 3px rgba(0,0,0,0.6)" }}
                >
                  {b.year ?? ""}
                </Text>
                <Text
                  c="rgba(255,255,255,0.85)"
                  fw={600}
                  style={{ fontSize: "clamp(0.55rem, 1.1vw, 0.7rem)", textShadow: "0 1px 3px rgba(0,0,0,0.6)" }}
                  lineClamp={1}
                >
                  {shortEventLabel(b.event_key)}
                </Text>
              </Box>
            </Box>
          </Anchor>
        ))}
      </SimpleGrid>
    </Stack>
  );
}
