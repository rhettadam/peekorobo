import type { ReactNode } from "react";
import { Anchor, Box, Group, Stack, Text, UnstyledButton } from "@mantine/core";
import { Link } from "react-router-dom";
import {
  IconAward,
  IconBrandYoutube,
  IconChevronRight,
  IconExternalLink,
  IconMapPin,
  IconTrophy,
  IconWorld,
} from "@tabler/icons-react";
import type { TeamNotable } from "../types/api";

type GlassTone = {
  panel: string;
  border: string;
  chip: string;
  chipBorder: string;
  muted: string;
};

function glassTone(headerText: string): GlassTone {
  const darkOnLight = headerText === "#000000";
  if (darkOnLight) {
    return {
      panel: "rgba(255,255,255,0.55)",
      border: "rgba(0,0,0,0.10)",
      chip: "rgba(0,0,0,0.08)",
      chipBorder: "rgba(0,0,0,0.08)",
      muted: "rgba(0,0,0,0.55)",
    };
  }
  return {
    panel: "rgba(0,0,0,0.38)",
    border: "rgba(255,255,255,0.16)",
    chip: "rgba(255,255,255,0.12)",
    chipBorder: "rgba(255,255,255,0.14)",
    muted: "rgba(255,255,255,0.72)",
  };
}

const glassPanel = (tone: GlassTone): React.CSSProperties => ({
  background: tone.panel,
  border: `1px solid ${tone.border}`,
  borderRadius: 14,
  backdropFilter: "blur(12px) saturate(140%)",
  WebkitBackdropFilter: "blur(12px) saturate(140%)",
  boxShadow: "0 6px 20px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.12)",
});

function YearChip({
  year,
  color,
  tone,
}: {
  year: number | string;
  color: string;
  tone: GlassTone;
}) {
  return (
    <Box
      component="span"
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        borderRadius: 999,
        background: tone.chip,
        border: `1px solid ${tone.chipBorder}`,
        color,
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: 0.2,
        lineHeight: 1.4,
      }}
    >
      {year}
    </Box>
  );
}

function MetaChip({
  icon,
  children,
  color,
  tone,
  href,
  to,
  title,
}: {
  icon?: ReactNode;
  children: ReactNode;
  color: string;
  tone: GlassTone;
  href?: string;
  /** In-app route (e.g. map deep link). */
  to?: string;
  title?: string;
}) {
  const body = (
    <Group gap={8} wrap="nowrap" style={{ ...glassPanel(tone), padding: "8px 12px" }}>
      {icon ? (
        <Box c={color} style={{ display: "flex", flexShrink: 0, opacity: 0.9 }}>
          {icon}
        </Box>
      ) : null}
      <Text size="sm" fw={600} c={color} style={{ lineHeight: 1.3 }}>
        {children}
      </Text>
      {to ? (
        <Box c={color} style={{ display: "flex", opacity: 0.75, flexShrink: 0 }}>
          <IconChevronRight size={14} />
        </Box>
      ) : href ? (
        <Box c={color} style={{ display: "flex", opacity: 0.7, flexShrink: 0 }}>
          <IconExternalLink size={14} />
        </Box>
      ) : null}
    </Group>
  );
  if (to) {
    return (
      <Anchor component={Link} to={to} underline="never" c="inherit" title={title}>
        {body}
      </Anchor>
    );
  }
  if (href) {
    return (
      <Anchor href={href} target="_blank" rel="noopener noreferrer" underline="never" c="inherit" title={title}>
        {body}
      </Anchor>
    );
  }
  return body;
}

function HallOfFameCard({
  year,
  color,
  tone,
  video,
}: {
  year?: number;
  color: string;
  tone: GlassTone;
  video?: string | null;
}) {
  // Same glass language as HonorCard, but compact: one year, one row.
  return (
    <Box
      style={{
        ...glassPanel(tone),
        padding: "8px 10px",
        width: "fit-content",
        maxWidth: "100%",
      }}
    >
      <Group gap={8} wrap="nowrap" align="center">
        <Box
          style={{
            width: 26,
            height: 26,
            borderRadius: 8,
            display: "grid",
            placeItems: "center",
            background: tone.chip,
            border: `1px solid ${tone.chipBorder}`,
            color,
            flexShrink: 0,
          }}
        >
          <IconAward size={14} />
        </Box>
        <Stack gap={2} style={{ minWidth: 0 }}>
          <Text size="xs" fw={800} c={color} lh={1.2} style={{ letterSpacing: 0.1 }}>
            Hall of Fame
          </Text>
          {year != null ? (
            <Text size="xs" fw={700} c={tone.muted} lh={1.2}>
              {year}
            </Text>
          ) : null}
        </Stack>
        {video ? (
          <UnstyledButton
            component="a"
            href={video}
            target="_blank"
            rel="noopener noreferrer"
            title="Impact Video"
            aria-label="Hall of Fame impact video"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              marginLeft: 4,
              padding: "4px 8px",
              borderRadius: 999,
              background: tone.chip,
              border: `1px solid ${tone.chipBorder}`,
              color,
              fontSize: 11,
              fontWeight: 700,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            <IconBrandYoutube size={13} />
            Video
          </UnstyledButton>
        ) : null}
      </Group>
    </Box>
  );
}

function HonorCard({
  icon,
  label,
  years,
  color,
  tone,
  video,
}: {
  icon: ReactNode;
  label: string;
  years: number[];
  color: string;
  tone: GlassTone;
  video?: string | null;
}) {
  const shown = years.slice(0, 6);
  const extra = years.length - shown.length;

  return (
    <Box style={{ ...glassPanel(tone), padding: "10px 12px", minWidth: 0, maxWidth: 420 }}>
      <Group gap={8} wrap="nowrap" mb={8} justify="space-between" align="flex-start">
        <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
          <Box
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              display: "grid",
              placeItems: "center",
              background: tone.chip,
              border: `1px solid ${tone.chipBorder}`,
              color,
              flexShrink: 0,
            }}
          >
            {icon}
          </Box>
          <Text size="sm" fw={800} c={color} lh={1.25} style={{ letterSpacing: 0.1 }}>
            {label}
          </Text>
        </Group>
        {video ? (
          <UnstyledButton
            component="a"
            href={video}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              padding: "4px 9px",
              borderRadius: 999,
              background: tone.chip,
              border: `1px solid ${tone.chipBorder}`,
              color,
              fontSize: 11,
              fontWeight: 700,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            <IconBrandYoutube size={14} />
            Video
          </UnstyledButton>
        ) : null}
      </Group>
      {years.length > 0 ? (
        <Group gap={5}>
          {shown.map((y) => (
            <YearChip key={y} year={y} color={color} tone={tone} />
          ))}
          {extra > 0 ? <YearChip year={`+${extra}`} color={color} tone={tone} /> : null}
        </Group>
      ) : (
        <Text size="xs" c={tone.muted} fw={600}>
          Career honor
        </Text>
      )}
    </Box>
  );
}

export interface TeamProfileMetaProps {
  headerText: string;
  location?: string;
  district?: string | null;
  website?: string | null;
  /** When set, location chip links to the map focused on this team. */
  teamNumber?: number;
  notables: TeamNotable[];
  /** Championship winner years when not already covered by a World Champions notable. */
  champYears?: number[];
  showWorldChampHonor?: boolean;
}

/**
 * Frosted meta chips + honor cards for the team profile / history gradient header.
 * Notable cards come from the notables API (Hall of Fame, World Champions) — not
 * inferred from every Chairman's / Impact win.
 */
export function TeamProfileMeta({
  headerText,
  location,
  district,
  website,
  teamNumber,
  notables,
  champYears = [],
  showWorldChampHonor = false,
}: TeamProfileMetaProps) {
  const tone = glassTone(headerText);
  const color = headerText;
  const mapTo =
    teamNumber && Number.isFinite(teamNumber) && teamNumber > 0
      ? `/map?team=${teamNumber}`
      : undefined;

  return (
    <Stack gap={10}>
      {(location || district) && (
        <Group gap={8} wrap="wrap">
          {location ? (
            <MetaChip
              icon={<IconMapPin size={15} />}
              color={color}
              tone={tone}
              to={mapTo}
              title={mapTo ? `Show team ${teamNumber} on the map` : undefined}
            >
              {location}
            </MetaChip>
          ) : null}
          {district ? (
            <MetaChip color={color} tone={tone}>
              {district}
            </MetaChip>
          ) : null}
        </Group>
      )}

      {(notables.length > 0 || showWorldChampHonor) && (
        <Group gap={8} align="stretch" wrap="wrap">
          {notables.map((n) =>
            n.category === "notables_hall_of_fame" ? (
              <HallOfFameCard
                key={n.category}
                year={n.years[0]}
                color={color}
                tone={tone}
                video={n.video}
              />
            ) : (
              <HonorCard
                key={n.category}
                icon={<IconTrophy size={15} />}
                label={n.label}
                years={n.years}
                color={color}
                tone={tone}
                video={n.video}
              />
            ),
          )}
          {showWorldChampHonor ? (
            <HonorCard
              icon={<IconTrophy size={15} />}
              label="World Champions"
              years={champYears}
              color={color}
              tone={tone}
            />
          ) : null}
        </Group>
      )}

      {website ? (
        <Group gap={8} wrap="wrap">
          <MetaChip
            icon={<IconWorld size={15} />}
            color={color}
            tone={tone}
            href={website}
          >
            {website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
          </MetaChip>
        </Group>
      ) : null}
    </Stack>
  );
}
