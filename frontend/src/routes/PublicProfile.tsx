import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, SimpleGrid, Stack } from "@mantine/core";
import { IconUserMinus, IconUserPlus } from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { useNavigate, useParams } from "react-router-dom";
import { fetchPublicProfile } from "../api/auth";
import { useToggleFollow } from "../api/follows";
import { useAuth } from "../auth/AuthContext";
import { UserListModal } from "../components/UserListModal";
import {
  CommunityCard,
  FavoriteEventCard,
  FavoriteTeamCard,
  FavoritesSectionHeader,
  ProfileHero,
} from "../components/ProfileSections";
import { EmptyState, ErrorState, LoadingState } from "../components/StateWrappers";

export function PublicProfile() {
  const { username = "" } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [listMode, setListMode] = useState<"followers" | "following" | null>(null);
  const query = useQuery({
    queryKey: ["public-profile", username],
    queryFn: () => fetchPublicProfile(username),
    enabled: Boolean(username),
  });
  const toggleFollow = useToggleFollow(username);

  useEffect(() => {
    document.title = `${username} - Peekorobo`;
  }, [username]);

  if (query.isLoading) return <LoadingState label={`Loading ${username}...`} />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) return null;

  const { user, favorite_teams, favorite_events, is_following, is_self } = query.data;
  const teams = favorite_teams.slice().sort((a, b) => Number(a) - Number(b));
  const events = favorite_events.slice().sort();

  const handleFollow = () => {
    if (!isAuthenticated) {
      notifications.show({ title: "Log in required", message: "Log in to follow users.", color: "yellow" });
      navigate("/login");
      return;
    }
    toggleFollow.mutate(
      { isFollowing: is_following },
      {
        onError: (err) =>
          notifications.show({
            title: "Something went wrong",
            message: err instanceof Error ? err.message : "Could not update follow.",
            color: "red",
          }),
      },
    );
  };

  return (
    <Stack gap="lg" py="md">
      <ProfileHero
        user={user}
        favoritesCount={favorite_teams.length + favorite_events.length}
        onShowFollowers={() => setListMode("followers")}
        onShowFollowing={() => setListMode("following")}
        actions={
          !is_self ? (
            <Button
              onClick={handleFollow}
              loading={toggleFollow.isPending}
              variant={is_following ? "white" : "filled"}
              color={is_following ? "dark" : undefined}
              leftSection={is_following ? <IconUserMinus size={16} /> : <IconUserPlus size={16} />}
              size="sm"
            >
              {is_following ? "Unfollow" : "Follow"}
            </Button>
          ) : null
        }
      />

      {listMode ? (
        <UserListModal
          username={username}
          mode={listMode}
          opened={listMode !== null}
          onClose={() => setListMode(null)}
        />
      ) : null}

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
        <Card withBorder radius="md" p="md">
          <FavoritesSectionHeader label="Favorite Teams" count={teams.length} />
          {teams.length === 0 ? (
            <EmptyState>No favorite teams.</EmptyState>
          ) : (
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
              {teams.map((t) => (
                <FavoriteTeamCard key={t} teamNumber={t} />
              ))}
            </SimpleGrid>
          )}
        </Card>

        <Card withBorder radius="md" p="md">
          <FavoritesSectionHeader label="Favorite Events" count={events.length} />
          {events.length === 0 ? (
            <EmptyState>No favorite events.</EmptyState>
          ) : (
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
              {events.map((e) => (
                <FavoriteEventCard key={e} eventKey={e} />
              ))}
            </SimpleGrid>
          )}
        </Card>
      </SimpleGrid>

      <CommunityCard username={username} onOpen={(mode) => setListMode(mode)} />
    </Stack>
  );
}
