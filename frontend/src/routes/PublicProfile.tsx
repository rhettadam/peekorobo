import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button, Stack } from "@mantine/core";
import { IconUserMinus, IconUserPlus } from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchPublicProfile } from "../api/auth";
import { useToggleFollow } from "../api/follows";
import { useAuth } from "../auth/AuthContext";
import { UserListModal } from "../components/UserListModal";
import { ProfileFavoriteInsights } from "../components/ProfileFavoriteInsights";
import { CommunityCard, ProfileHero } from "../components/ProfileSections";
import { ErrorState, LoadingState } from "../components/StateWrappers";

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
        onShowFavorites={() =>
          document.getElementById("profile-favorites")?.scrollIntoView({ behavior: "smooth", block: "start" })
        }
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
          ) : (
            <Button component={Link} to="/user?edit=1" variant="white" color="dark" size="sm">
              Edit profile
            </Button>
          )
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

      <ProfileFavoriteInsights teamKeys={favorite_teams} eventKeys={favorite_events} />

      <CommunityCard username={username} onOpen={(mode) => setListMode(mode)} />
    </Stack>
  );
}
