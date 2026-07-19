import { useQuery } from "@tanstack/react-query";
import { Anchor, Avatar, Group, Modal, Stack, Text } from "@mantine/core";
import { Link } from "react-router-dom";
import { fetchFollowers, fetchFollowing } from "../api/auth";
import { userAvatar } from "../lib/assets";
import { LoadingState, ErrorState, EmptyState } from "./StateWrappers";

interface UserListModalProps {
  username: string;
  mode: "followers" | "following";
  opened: boolean;
  onClose: () => void;
}

export function UserListModal({ username, mode, opened, onClose }: UserListModalProps) {
  const query = useQuery({
    queryKey: [mode, username],
    queryFn: () => (mode === "followers" ? fetchFollowers(username) : fetchFollowing(username)),
    enabled: opened && Boolean(username),
  });

  const title = mode === "followers" ? "Followers" : "Following";
  const users = query.data?.users ?? [];

  return (
    <Modal opened={opened} onClose={onClose} title={title} centered>
      {query.isLoading ? (
        <LoadingState label={`Loading ${title.toLowerCase()}...`} />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : users.length === 0 ? (
        <EmptyState>No {title.toLowerCase()} yet.</EmptyState>
      ) : (
        <Stack gap="xs">
          {users.map((u) => (
            <Group key={u.id} gap="sm" wrap="nowrap">
              <Avatar src={userAvatar(u.avatar_key)} size={32} radius="xl" alt={u.username}>
                {u.username.slice(0, 2).toUpperCase()}
              </Avatar>
              <Anchor component={Link} to={`/user/${u.username}`} size="sm" onClick={onClose}>
                {u.username}
              </Anchor>
            </Group>
          ))}
          <Text size="xs" c="dimmed" ta="right">
            {users.length} {title.toLowerCase()}
          </Text>
        </Stack>
      )}
    </Modal>
  );
}
