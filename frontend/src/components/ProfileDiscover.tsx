import { useMemo, useState, type ReactNode } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Avatar,
  Box,
  Button,
  Card,
  Group,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import {
  IconCalendarEvent,
  IconRobot,
  IconSearch,
  IconUserPlus,
  IconUsers,
} from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { Link } from "react-router-dom";
import { fetchFavoriteItemDetail, useFavorites } from "../api/favorites";
import { fetchFollowing, fetchUsersByTeam, followUser, searchUsers, unfollowUser } from "../api/auth";
import { useLeaderboardPreview, useMapEvents, useMapTeams, useSearchIndex } from "../api/queries";
import { apiGet } from "../api/client";
import { FavoriteButton } from "./FavoriteButton";
import { TeamAvatar } from "./TeamAvatar";
import { userAvatar } from "../lib/assets";
import { CURRENT_YEAR } from "../lib/constants";
import {
  suggestEvents,
  suggestTeams,
  suggestUsers,
  type SuggestedEvent,
  type SuggestedTeam,
  type SuggestedUser,
} from "../lib/profileDiscover";
import { searchIndex, type EventSuggestion, type TeamSuggestion } from "../api/search";
import type { AuthUser, TeamPerfResponse, UserSummary } from "../types/api";

type DiscoverMode = "teams" | "events" | "people";

interface ProfileDiscoverProps {
  user: AuthUser;
}

export function ProfileDiscover({ user }: ProfileDiscoverProps) {
  const [mode, setMode] = useState<DiscoverMode>("teams");
  const [query, setQuery] = useState("");
  const [debouncedQuery] = useDebouncedValue(query.trim(), 250);

  const { data: favorites } = useFavorites();
  const { data: index } = useSearchIndex();
  const mapTeams = useMapTeams(CURRENT_YEAR);
  const mapEvents = useMapEvents(CURRENT_YEAR);
  const leaderboard = useLeaderboardPreview(CURRENT_YEAR, 30);

  const followingQuery = useQuery({
    queryKey: ["following", user.username],
    queryFn: () => fetchFollowing(user.username),
  });

  const teamMembersQuery = useQuery({
    queryKey: ["users-by-team", user.team],
    queryFn: () => fetchUsersByTeam(user.team!),
    enabled: Boolean(user.team?.trim()),
  });

  const seedTeams = (favorites?.teams ?? []).slice(0, 4);
  const favoriterQueries = useQueries({
    queries: seedTeams.map((team) => ({
      queryKey: ["favorites", "item", "team", team] as const,
      queryFn: () => fetchFavoriteItemDetail("team", team),
      staleTime: 60_000,
    })),
  });

  const seedPerfQueries = useQueries({
    queries: seedTeams.map((team) => ({
      queryKey: ["team-perfs", Number(team), "all"] as const,
      queryFn: () => apiGet<TeamPerfResponse>(`/team_perfs/${team}`),
      staleTime: 5 * 60 * 1000,
      enabled: Number(team) > 0,
    })),
  });

  const followingSet = useMemo(
    () => new Set((followingQuery.data?.users ?? []).map((u) => u.username.toLowerCase())),
    [followingQuery.data],
  );

  const coFavoriters = useMemo(() => {
    const out: UserSummary[] = [];
    const seen = new Set<number>();
    for (const q of favoriterQueries) {
      for (const u of q.data?.users ?? []) {
        if (seen.has(u.id) || u.id === user.id) continue;
        seen.add(u.id);
        out.push({ id: u.id, username: u.username, avatar_key: u.avatar_key ?? null });
      }
    }
    return out;
  }, [favoriterQueries, user.id]);

  const attendedEventKeys = useMemo(() => {
    const keys: string[] = [];
    for (const q of seedPerfQueries) {
      for (const perf of q.data?.team_perfs ?? []) {
        for (const ep of perf.event_perf ?? []) {
          if (ep.event_key) keys.push(String(ep.event_key));
        }
      }
    }
    return keys;
  }, [seedPerfQueries]);

  const suggestions = useMemo(() => {
    const topTeamNumbers =
      leaderboard.data?.map((row) => row.team_number).filter((n): n is number => n != null) ?? [];
    return {
      teams: suggestTeams({
        favoriteTeams: favorites?.teams ?? [],
        mapTeams: mapTeams.data?.teams ?? [],
        topTeamNumbers,
        userTeam: user.team,
      }),
      events: suggestEvents({
        favoriteEvents: favorites?.events ?? [],
        favoriteTeams: favorites?.teams ?? [],
        mapEvents: mapEvents.data?.events ?? [],
        mapTeams: mapTeams.data?.teams ?? [],
        attendedEventKeys,
      }),
      users: suggestUsers({
        selfId: user.id,
        selfUsername: user.username,
        following: followingQuery.data?.users ?? [],
        teamMembers: teamMembersQuery.data?.users ?? [],
        coFavoriters,
      }),
    };
  }, [
    attendedEventKeys,
    coFavoriters,
    favorites?.events,
    favorites?.teams,
    followingQuery.data,
    leaderboard.data,
    mapEvents.data,
    mapTeams.data,
    teamMembersQuery.data,
    user.id,
    user.team,
    user.username,
  ]);

  const teamResults = useMemo(() => {
    if (!index || mode !== "teams" || !query.trim()) return [];
    return searchIndex(index, query, 24).filter((s): s is TeamSuggestion => s.type === "team");
  }, [index, mode, query]);

  const eventResults = useMemo(() => {
    if (!index || mode !== "events" || !query.trim()) return [];
    return searchIndex(index, query, 24).filter((s): s is EventSuggestion => s.type === "event");
  }, [index, mode, query]);

  const peopleResults = useQuery({
    queryKey: ["users-search", debouncedQuery],
    queryFn: () => searchUsers(debouncedQuery),
    enabled: mode === "people" && debouncedQuery.length >= 2,
  });

  const searchPlaceholder =
    mode === "teams"
      ? "Add a team — number or nickname"
      : mode === "events"
        ? "Add an event — name or key"
        : "Find people to follow";

  const showSearchResults =
    (mode === "teams" && teamResults.length > 0) ||
    (mode === "events" && eventResults.length > 0) ||
    (mode === "people" && debouncedQuery.length >= 2);

  return (
    <Stack gap="md">
      <Card withBorder radius="md" p="md">
        <Group justify="space-between" align="flex-end" mb="sm" wrap="wrap">
          <div>
            <Title order={4}>Find teams, events & people</Title>
            <Text size="sm" c="dimmed">
              Favorite from search, or follow someone new.
            </Text>
          </div>
          <SegmentedControl
            size="xs"
            value={mode}
            onChange={(v) => setMode(v as DiscoverMode)}
            data={[
              { label: "Teams", value: "teams" },
              { label: "Events", value: "events" },
              { label: "People", value: "people" },
            ]}
          />
        </Group>

        <TextInput
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          placeholder={searchPlaceholder}
          leftSection={<IconSearch size={16} />}
          radius="md"
        />

        {showSearchResults ? (
          <Box mt="sm" className="profile-discover-results">
            {mode === "teams"
              ? teamResults.map((row) => <DiscoverTeamRow key={row.teamNumber} team={row} />)
              : null}
            {mode === "events"
              ? eventResults.map((row) => <DiscoverEventRow key={row.eventKey} event={row} />)
              : null}
            {mode === "people" ? (
              peopleResults.isLoading ? (
                <Text size="sm" c="dimmed" p="sm">
                  Searching…
                </Text>
              ) : (peopleResults.data?.users.length ?? 0) === 0 ? (
                <Text size="sm" c="dimmed" p="sm">
                  No users match “{debouncedQuery}”.
                </Text>
              ) : (
                peopleResults.data!.users.map((u) => (
                  <DiscoverUserRow
                    key={u.id}
                    person={u}
                    isFollowing={followingSet.has(u.username.toLowerCase())}
                    selfUsername={user.username}
                  />
                ))
              )
            ) : null}
          </Box>
        ) : null}
      </Card>

      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
        <SuggestionList
          title="Teams nearby"
          icon={<IconRobot size={16} />}
          empty="Favorite a team to get nearby suggestions."
          loading={mapTeams.isLoading}
        >
          {suggestions.teams.map((t) => (
            <SuggestedTeamRow key={t.teamNumber} item={t} />
          ))}
        </SuggestionList>

        <SuggestionList
          title="Events for you"
          icon={<IconCalendarEvent size={16} />}
          empty="Favorite a team to see events in your area."
          loading={mapEvents.isLoading}
        >
          {suggestions.events.map((e) => (
            <SuggestedEventRow key={e.eventKey} item={e} />
          ))}
        </SuggestionList>

        <SuggestionList
          title="People to follow"
          icon={<IconUsers size={16} />}
          empty="Set your team or favorite teams to meet others."
          loading={followingQuery.isLoading || teamMembersQuery.isLoading}
        >
          {suggestions.users.map((u) => (
            <SuggestedUserRow
              key={u.id}
              person={u}
              isFollowing={followingSet.has(u.username.toLowerCase())}
              selfUsername={user.username}
            />
          ))}
        </SuggestionList>
      </SimpleGrid>
    </Stack>
  );
}

function SuggestionList({
  title,
  icon,
  empty,
  loading,
  children,
}: {
  title: string;
  icon: ReactNode;
  empty: string;
  loading: boolean;
  children: ReactNode;
}) {
  const count = Array.isArray(children) ? children.filter(Boolean).length : children ? 1 : 0;

  return (
    <Card withBorder radius="md" p="md">
      <Group gap={8} mb="sm">
        {icon}
        <Text fw={700} size="sm">
          {title}
        </Text>
      </Group>
      {loading ? (
        <Text size="sm" c="dimmed">
          Loading…
        </Text>
      ) : count === 0 ? (
        <Text size="sm" c="dimmed">
          {empty}
        </Text>
      ) : (
        <Stack gap={4}>{children}</Stack>
      )}
    </Card>
  );
}

function DiscoverTeamRow({ team }: { team: TeamSuggestion }) {
  return (
    <Group justify="space-between" wrap="nowrap" className="profile-discover-row">
      <UnstyledButton component={Link} to={`/team/${team.teamNumber}`} style={{ minWidth: 0, flex: 1 }}>
        <Group gap="sm" wrap="nowrap">
          <TeamAvatar teamNumber={team.teamNumber} size={32} radius={6} bordered />
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Text fw={600} size="sm">
              Team {team.teamNumber}
            </Text>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {team.nickname || "FRC team"}
            </Text>
          </Stack>
        </Group>
      </UnstyledButton>
      <FavoriteButton itemType="team" itemKey={team.teamNumber} size={18} />
    </Group>
  );
}

function DiscoverEventRow({ event }: { event: EventSuggestion }) {
  return (
    <Group justify="space-between" wrap="nowrap" className="profile-discover-row">
      <UnstyledButton component={Link} to={`/event/${event.eventKey}`} style={{ minWidth: 0, flex: 1 }}>
        <Group gap="sm" wrap="nowrap">
          <Avatar size={32} radius={6} color="yellow" variant="light">
            <IconCalendarEvent size={16} />
          </Avatar>
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Text fw={600} size="sm" lineClamp={1}>
              {event.name}
            </Text>
            <Text size="xs" c="dimmed">
              {event.eventKey}
            </Text>
          </Stack>
        </Group>
      </UnstyledButton>
      <FavoriteButton itemType="event" itemKey={event.eventKey} size={18} />
    </Group>
  );
}

function DiscoverUserRow({
  person,
  isFollowing,
  selfUsername,
}: {
  person: UserSummary;
  isFollowing: boolean;
  selfUsername: string;
}) {
  if (person.username.toLowerCase() === selfUsername.toLowerCase()) return null;
  return (
    <Group justify="space-between" wrap="nowrap" className="profile-discover-row">
      <UnstyledButton component={Link} to={`/user/${person.username}`} style={{ minWidth: 0, flex: 1 }}>
        <Group gap="sm" wrap="nowrap">
          <Avatar src={userAvatar(person.avatar_key)} size={32} radius={6} alt={person.username}>
            {person.username.slice(0, 2).toUpperCase()}
          </Avatar>
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Text fw={600} size="sm">
              {person.username}
            </Text>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {person.team ? `Team ${person.team}` : person.role || "Peekorobo member"}
            </Text>
          </Stack>
        </Group>
      </UnstyledButton>
      <FollowUserButton username={person.username} isFollowing={isFollowing} viewerUsername={selfUsername} />
    </Group>
  );
}

function SuggestedTeamRow({ item }: { item: SuggestedTeam }) {
  const loc = [item.city, item.state].filter(Boolean).join(", ");
  return (
    <Group justify="space-between" wrap="nowrap" py={4}>
      <UnstyledButton component={Link} to={`/team/${item.teamNumber}`} style={{ minWidth: 0, flex: 1 }}>
        <Group gap="sm" wrap="nowrap">
          <TeamAvatar teamNumber={item.teamNumber} size={32} radius={6} bordered />
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Text fw={600} size="sm">
              {item.teamNumber} {item.nickname}
            </Text>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {item.reason}
              {loc ? ` · ${loc}` : ""}
            </Text>
          </Stack>
        </Group>
      </UnstyledButton>
      <FavoriteButton itemType="team" itemKey={item.teamNumber} size={16} />
    </Group>
  );
}

function SuggestedEventRow({ item }: { item: SuggestedEvent }) {
  const loc = [item.city, item.state].filter(Boolean).join(", ");
  return (
    <Group justify="space-between" wrap="nowrap" py={4}>
      <UnstyledButton component={Link} to={`/event/${item.eventKey}`} style={{ minWidth: 0, flex: 1 }}>
        <Stack gap={0} style={{ minWidth: 0 }}>
          <Text fw={600} size="sm" lineClamp={1}>
            {item.name}
          </Text>
          <Text size="xs" c="dimmed" lineClamp={1}>
            {item.reason}
            {loc ? ` · ${loc}` : ""}
          </Text>
        </Stack>
      </UnstyledButton>
      <FavoriteButton itemType="event" itemKey={item.eventKey} size={16} />
    </Group>
  );
}

function SuggestedUserRow({
  person,
  isFollowing,
  selfUsername,
}: {
  person: SuggestedUser;
  isFollowing: boolean;
  selfUsername: string;
}) {
  return (
    <Group justify="space-between" wrap="nowrap" py={4}>
      <UnstyledButton component={Link} to={`/user/${person.username}`} style={{ minWidth: 0, flex: 1 }}>
        <Group gap="sm" wrap="nowrap">
          <Avatar src={userAvatar(person.avatar_key)} size={32} radius={6} alt={person.username}>
            {person.username.slice(0, 2).toUpperCase()}
          </Avatar>
          <Stack gap={0} style={{ minWidth: 0 }}>
            <Text fw={600} size="sm">
              {person.username}
            </Text>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {person.reason}
            </Text>
          </Stack>
        </Group>
      </UnstyledButton>
      <FollowUserButton username={person.username} isFollowing={isFollowing} viewerUsername={selfUsername} compact />
    </Group>
  );
}

function FollowUserButton({
  username,
  isFollowing,
  viewerUsername,
  compact,
}: {
  username: string;
  isFollowing: boolean;
  viewerUsername: string;
  compact?: boolean;
}) {
  const queryClient = useQueryClient();
  const toggle = useMutation({
    mutationFn: (following: boolean) => (following ? unfollowUser(username) : followUser(username)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["following", viewerUsername] });
      queryClient.invalidateQueries({ queryKey: ["followers"] });
      queryClient.invalidateQueries({ queryKey: ["public-profile", username] });
    },
    onError: (err) =>
      notifications.show({
        title: "Something went wrong",
        message: err instanceof Error ? err.message : "Could not update follow.",
        color: "red",
      }),
  });

  return (
    <Button
      size={compact ? "compact-xs" : "xs"}
      variant={isFollowing ? "light" : "default"}
      loading={toggle.isPending}
      onClick={() => toggle.mutate(isFollowing)}
      leftSection={!isFollowing ? <IconUserPlus size={14} /> : undefined}
    >
      {isFollowing ? "Following" : "Follow"}
    </Button>
  );
}
