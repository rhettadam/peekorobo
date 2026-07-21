import { Anchor, Badge, Box, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { Link } from "react-router-dom";
import { BRAND } from "../lib/assets";
import { blueBannerKind } from "../lib/banners";
import { yearFromEventKey } from "../lib/format";
import type { TeamAwardData } from "../types/api";

/** Prefer full event name; fall back to key without the year prefix. */
function eventLabel(eventKey: string, eventName?: string | null): string {
  const name = (eventName || "").trim();
  if (name) return name;
  return eventKey.replace(/^\d{4}/, "").toUpperCase() || eventKey;
}

export type BlueBannerItem = TeamAwardData & {
  kind: NonNullable<ReturnType<typeof blueBannerKind>>;
  year: number | null;
};

/** Banner-worthy awards only, newest year first. */
export function toBlueBannerItems(awards: TeamAwardData[]): BlueBannerItem[] {
  return awards
    .map((a) => ({
      ...a,
      kind: blueBannerKind(a.award_name),
      year: yearFromEventKey(a.event_key),
    }))
    .filter((a): a is BlueBannerItem => a.kind !== null)
    .sort((a, b) => (b.year ?? 0) - (a.year ?? 0));
}

interface BannerTileProps {
  banner: BlueBannerItem;
  /** Narrow rail tiles use smaller type. */
  compact?: boolean;
}

export function BlueBannerTile({ banner: b, compact }: BannerTileProps) {
  const eventText = eventLabel(b.event_key, b.event_name);
  return (
    <Anchor
      component={Link}
      to={`/event/${b.event_key}`}
      underline="never"
      className="hover-lift"
      title={`${b.award_name} — ${eventText}`}
      style={{ display: "block", width: "100%" }}
    >
      <Box
        style={{
          position: "relative",
          width: "100%",
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
            top: compact ? "28%" : "32%",
            left: 0,
            right: 0,
            bottom: "12%",
            padding: compact ? "0 6px" : "0 8px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "flex-start",
            overflow: "hidden",
          }}
        >
          <Text
            fw={800}
            lh={1.15}
            c="#ffffff"
            style={{
              fontSize: compact
                ? "clamp(0.55rem, 1.05vw, 0.72rem)"
                : "clamp(0.6rem, 1.4vw, 0.82rem)",
              textShadow: "0 1px 3px rgba(0,0,0,0.6)",
              flexShrink: 0,
            }}
            lineClamp={compact ? 4 : 3}
          >
            {b.award_name}
          </Text>
          <Text
            mt={compact ? 4 : 6}
            c="#ffdd00"
            fw={700}
            style={{
              fontSize: compact
                ? "clamp(0.65rem, 1.15vw, 0.85rem)"
                : "clamp(0.7rem, 1.5vw, 0.95rem)",
              textShadow: "0 1px 3px rgba(0,0,0,0.6)",
              flexShrink: 0,
            }}
          >
            {b.year ?? ""}
          </Text>
          <Text
            mt={compact ? 4 : 6}
            c="rgba(255,255,255,0.9)"
            fw={600}
            lh={1.2}
            style={{
              fontSize: compact
                ? "clamp(0.48rem, 0.9vw, 0.64rem)"
                : "clamp(0.55rem, 1.05vw, 0.7rem)",
              textShadow: "0 1px 3px rgba(0,0,0,0.6)",
              whiteSpace: "normal",
              wordBreak: "break-word",
              overflowWrap: "anywhere",
              maxWidth: "100%",
            }}
            lineClamp={compact ? 5 : 4}
          >
            {eventText}
          </Text>
        </Box>
      </Box>
    </Anchor>
  );
}

interface BlueBannersProps {
  awards: TeamAwardData[];
  title?: string;
  /** grid = wall; column = vertical stack (history rails). */
  layout?: "grid" | "column";
  showTitle?: boolean;
}

/**
 * A wall of FRC blue banners for a team's banner-worthy awards. Each banner uses
 * the shared banner.png artwork with the award name / event / year overlaid, and
 * links to the event page. Renders nothing when there are no qualifying awards.
 */
export function BlueBanners({
  awards,
  title = "Blue Banners",
  layout = "grid",
  showTitle = true,
}: BlueBannersProps) {
  const banners = toBlueBannerItems(awards);

  if (banners.length === 0) return null;

  if (layout === "column") {
    return (
      <Stack gap="sm">
        {showTitle ? (
          <Group gap="xs" align="center" justify="center">
            <Badge color="blue" variant="filled" size="sm" radius="sm">
              {banners.length}
            </Badge>
          </Group>
        ) : null}
        {banners.map((b, i) => (
          <BlueBannerTile key={`${b.event_key}-${b.award_name}-${i}`} banner={b} compact />
        ))}
      </Stack>
    );
  }

  return (
    <Stack gap="sm">
      {showTitle ? (
        <Group gap="xs" align="center">
          <Title order={3}>{title}</Title>
          <Badge color="blue" variant="filled" size="lg" radius="sm">
            {banners.length}
          </Badge>
        </Group>
      ) : null}
      <SimpleGrid cols={{ base: 3, xs: 4, sm: 5, md: 6, lg: 8 }} spacing="md">
        {banners.map((b, i) => (
          <BlueBannerTile key={`${b.event_key}-${b.award_name}-${i}`} banner={b} />
        ))}
      </SimpleGrid>
    </Stack>
  );
}
