import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ActionIcon,
  Anchor,
  Avatar,
  Badge,
  Box,
  Card,
  Group,
  Stack,
  Text,
  Title,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import {
  IconCalendarEvent,
  IconStarFilled,
  IconTrash,
  IconUsersGroup,
} from "@tabler/icons-react";
import { Link } from "react-router-dom";
import { fetchFollowers, fetchFollowing } from "../api/auth";
import { useSearchIndex } from "../api/queries";
import { userAvatar } from "../lib/assets";
import { contrastText } from "../lib/epa";
import { TeamAvatar } from "./TeamAvatar";
import type { AuthUser, UserSummary } from "../types/api";

// ---------------------------------------------------------------------------
// Hero banner: big avatar, name, role/team, stats, and an actions slot.
// ---------------------------------------------------------------------------

interface ProfileHeroProps {
  user: AuthUser;
  favoritesCount?: number;
  onShowFollowers?: () => void;
  onShowFollowing?: () => void;
  onShowFavorites?: () => void;
  actions?: ReactNode;
}

export function ProfileHero({
  user,
  favoritesCount,
  onShowFollowers,
  onShowFollowing,
  onShowFavorites,
  actions,
}: ProfileHeroProps) {
  const isMobile = useMediaQuery("(max-width: 48em)");
  const accent = user.color || null;
  const gradient = accent
    ? `linear-gradient(135deg, ${accent} 0%, #0d0d0d 135%)`
    : "linear-gradient(135deg, #303030 0%, #0d0d0d 130%)";
  const text = accent ? contrastText(accent) : "#ffffff";
  const onDark = text !== "#000000";
  const dim = onDark ? "rgba(255,255,255,0.78)" : "rgba(0,0,0,0.6)";
  const chipBg = onDark ? "rgba(255,255,255,0.16)" : "rgba(0,0,0,0.1)";
  const chipBorder = onDark ? "rgba(255,255,255,0.32)" : "rgba(0,0,0,0.22)";
  const initials = user.username.slice(0, 2).toUpperCase();
  const avatarSize = isMobile ? 72 : 104;
  const frameRadius = isMobile ? 16 : 22;

  return (
    <Card
      radius="lg"
      p={{ base: "md", sm: "xl" }}
      style={{
        position: "relative",
        background: [
          "radial-gradient(circle at 88% 6%, rgba(255,255,255,0.22), transparent 46%)",
          "radial-gradient(rgba(255,255,255,0.09) 1.4px, transparent 1.5px)",
          "linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px)",
          "linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)",
          gradient,
        ].join(", "),
        backgroundSize: "100% 100%, 48px 48px, 24px 24px, 24px 24px, 100% 100%",
        color: text,
        border: "none",
        overflow: "hidden",
      }}
    >
      <Stack gap={isMobile ? "md" : "lg"} style={{ position: "relative", zIndex: 1 }}>
        <Group justify="space-between" align="flex-start" wrap="nowrap" gap="sm">
          <Group align="center" wrap="nowrap" gap={isMobile ? "sm" : "lg"} style={{ minWidth: 0, flex: 1 }}>
            <Box
              style={{
                flexShrink: 0,
                padding: isMobile ? 4 : 6,
                borderRadius: frameRadius,
                background: "rgba(0,0,0,0.32)",
                border: "1px solid rgba(255,255,255,0.28)",
                backdropFilter: "blur(8px)",
                WebkitBackdropFilter: "blur(8px)",
                boxShadow: "0 8px 26px rgba(0,0,0,0.32)",
              }}
            >
              <Avatar
                src={userAvatar(user.avatar_key)}
                size={avatarSize}
                radius={isMobile ? 12 : 16}
                alt={user.username}
              >
                {initials}
              </Avatar>
            </Box>
            <Stack gap={6} style={{ minWidth: 0, flex: 1 }}>
              <Title
                order={1}
                c={text}
                fz={{ base: 26, sm: 34 }}
                style={{ wordBreak: "break-word", lineHeight: 1.1 }}
              >
                {user.username}
              </Title>
              <Group gap="xs">
                <Badge
                  radius="sm"
                  styles={{
                    root: {
                      background: chipBg,
                      color: text,
                      border: `1px solid ${chipBorder}`,
                      textTransform: "none",
                    },
                  }}
                >
                  {user.role || "Member"}
                </Badge>
                {user.team ? (
                  <Anchor
                    component={Link}
                    to={`/team/${user.team}`}
                    c={text}
                    fw={700}
                    style={{ textDecoration: "underline" }}
                  >
                    Team {user.team}
                  </Anchor>
                ) : null}
              </Group>
            </Stack>
          </Group>

          {actions ? (
            <Group gap="xs" wrap="nowrap" style={{ flexShrink: 0 }} visibleFrom="sm">
              {actions}
            </Group>
          ) : null}
        </Group>

        <Group gap={isMobile ? "lg" : 40} wrap="wrap">
          <HeroStat
            label="Followers"
            value={user.followers_count}
            onClick={onShowFollowers}
            color={text}
            dim={dim}
          />
          <HeroStat
            label="Following"
            value={user.following_count}
            onClick={onShowFollowing}
            color={text}
            dim={dim}
          />
          {favoritesCount !== undefined ? (
            <HeroStat
              label="Favorites"
              value={favoritesCount}
              onClick={onShowFavorites}
              color={text}
              dim={dim}
            />
          ) : null}
        </Group>

        {user.bio ? (
          <Text c={text} style={{ whiteSpace: "pre-wrap", maxWidth: 640, opacity: 0.95 }}>
            {user.bio}
          </Text>
        ) : null}

        {actions ? (
          <Stack gap="xs" hiddenFrom="sm">
            {actions}
          </Stack>
        ) : null}
      </Stack>
    </Card>
  );
}

function HeroStat({
  label,
  value,
  onClick,
  color,
  dim,
}: {
  label: string;
  value: number;
  onClick?: () => void;
  color: string;
  dim: string;
}) {
  const inner = (
    <Stack gap={0} align="center">
      <Text fw={800} fz={22} c={color} lh={1.1}>
        {value}
      </Text>
      <Text fz="xs" c={dim} tt="uppercase" fw={700} style={{ letterSpacing: 0.4 }}>
        {label}
      </Text>
    </Stack>
  );
  if (!onClick) return inner;
  return (
    <UnstyledButton onClick={onClick} style={{ borderRadius: 8 }}>
      {inner}
    </UnstyledButton>
  );
}

// ---------------------------------------------------------------------------
// Community card: follower + following avatar strips.
// ---------------------------------------------------------------------------

const STRIP_LIMIT = 16;

export function CommunityCard({
  username,
  onOpen,
}: {
  username: string;
  onOpen: (mode: "followers" | "following") => void;
}) {
  const followers = useQuery({
    queryKey: ["followers", username],
    queryFn: () => fetchFollowers(username),
    enabled: Boolean(username),
  });
  const following = useQuery({
    queryKey: ["following", username],
    queryFn: () => fetchFollowing(username),
    enabled: Boolean(username),
  });

  return (
    <Card withBorder radius="md" p="md">
      <Group gap={6} mb="md">
        <IconUsersGroup size={16} color="#ffdd00" />
        <Text fw={600}>Community</Text>
      </Group>
      <Stack gap="lg">
        <FriendStrip
          title="Followers"
          users={followers.data?.users ?? []}
          loading={followers.isLoading}
          onMore={() => onOpen("followers")}
        />
        <FriendStrip
          title="Following"
          users={following.data?.users ?? []}
          loading={following.isLoading}
          onMore={() => onOpen("following")}
        />
      </Stack>
    </Card>
  );
}

function FriendStrip({
  title,
  users,
  loading,
  onMore,
}: {
  title: string;
  users: UserSummary[];
  loading: boolean;
  onMore: () => void;
}) {
  const shown = users.slice(0, STRIP_LIMIT);
  const extra = users.length - shown.length;
  return (
    <Box>
      <Group justify="space-between" mb={8}>
        <Text size="sm" fw={600} c="dimmed">
          {title}
        </Text>
        {users.length > 0 ? (
          <Anchor size="xs" component="button" type="button" onClick={onMore}>
            See all {users.length}
          </Anchor>
        ) : null}
      </Group>
      {loading ? (
        <Text size="sm" c="dimmed">
          Loading...
        </Text>
      ) : users.length === 0 ? (
        <Text size="sm" c="dimmed">
          No {title.toLowerCase()} yet.
        </Text>
      ) : (
        <Group gap="xs">
          {shown.map((u) => (
            <Tooltip key={u.id} label={u.username} withArrow>
              <Anchor component={Link} to={`/user/${u.username}`}>
                <Avatar src={userAvatar(u.avatar_key)} size={40} radius={8} alt={u.username}>
                  {u.username.slice(0, 2).toUpperCase()}
                </Avatar>
              </Anchor>
            </Tooltip>
          ))}
          {extra > 0 ? (
            <UnstyledButton onClick={onMore}>
              <Avatar size={40} radius={8} color="gray">
                +{extra}
              </Avatar>
            </UnstyledButton>
          ) : null}
        </Group>
      )}
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Favorite team / event "profile" cards.
// ---------------------------------------------------------------------------

export function FavoriteTeamCard({
  teamNumber,
  onRemove,
}: {
  teamNumber: string;
  onRemove?: () => void;
}) {
  const { data: index } = useSearchIndex();
  const entry = index?.teams[teamNumber];
  const nickname = entry?.nickname ?? "";
  const year = entry?.last_year ?? undefined;
  return (
    <Card
      withBorder
      radius="md"
      p="sm"
      component={Link}
      to={`/team/${teamNumber}${year ? `/${year}` : ""}`}
      className="hover-lift"
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <Group gap="sm" wrap="nowrap">
        <TeamAvatar teamNumber={Number(teamNumber)} size={44} radius={8} bordered />
        <Stack gap={0} style={{ minWidth: 0, flex: 1 }}>
          <Text fw={700}>Team {teamNumber}</Text>
          <Text size="sm" c="dimmed" lineClamp={1}>
            {nickname || "\u00a0"}
          </Text>
        </Stack>
        {onRemove ? (
          <ActionIcon
            variant="subtle"
            color="red"
            aria-label={`Remove team ${teamNumber}`}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onRemove();
            }}
          >
            <IconTrash size={16} />
          </ActionIcon>
        ) : null}
      </Group>
    </Card>
  );
}

export function FavoriteEventCard({
  eventKey,
  onRemove,
}: {
  eventKey: string;
  onRemove?: () => void;
}) {
  const { data: index } = useSearchIndex();
  const name = index?.events[eventKey] ?? eventKey;
  const year = /^\d{4}/.test(eventKey) ? eventKey.slice(0, 4) : "";
  return (
    <Card
      withBorder
      radius="md"
      p="sm"
      component={Link}
      to={`/event/${eventKey}`}
      className="hover-lift"
      style={{ textDecoration: "none", color: "inherit" }}
    >
      <Group gap="sm" wrap="nowrap">
        <Avatar size={44} radius={8} color="yellow" variant="light">
          <IconCalendarEvent size={22} />
        </Avatar>
        <Stack gap={0} style={{ minWidth: 0, flex: 1 }}>
          <Text fw={700} lineClamp={1}>
            {year ? `${year} ${name}` : name}
          </Text>
          <Text size="xs" c="dimmed">
            {eventKey}
          </Text>
        </Stack>
        {onRemove ? (
          <ActionIcon
            variant="subtle"
            color="red"
            aria-label={`Remove event ${eventKey}`}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onRemove();
            }}
          >
            <IconTrash size={16} />
          </ActionIcon>
        ) : null}
      </Group>
    </Card>
  );
}

export function FavoritesSectionHeader({
  label,
  count,
}: {
  label: string;
  count: number;
}) {
  return (
    <Group gap={6} mb="sm">
      <IconStarFilled size={16} color="#ffdd00" />
      <Text fw={600}>{label}</Text>
      <Badge variant="light" size="sm">
        {count}
      </Badge>
    </Group>
  );
}
