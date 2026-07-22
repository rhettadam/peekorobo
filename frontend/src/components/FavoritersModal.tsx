import { Anchor, Avatar, Group, Modal, Stack, Text } from "@mantine/core";
import { Link } from "react-router-dom";
import { useFavoriteItemDetail } from "../api/favorites";
import type { FavoriteItemType } from "../types/api";
import { userAvatar } from "../lib/assets";
import { LoadingState, ErrorState, EmptyState } from "./StateWrappers";

interface FavoritersModalProps {
  itemType: FavoriteItemType;
  itemKey: string | number;
  opened: boolean;
  onClose: () => void;
}

/** Modal listing users who favorited a team or event. */
export function FavoritersModal({ itemType, itemKey, opened, onClose }: FavoritersModalProps) {
  const query = useFavoriteItemDetail(itemType, itemKey);
  const users = query.data?.users ?? [];
  const count = query.data?.count ?? users.length;
  const label = itemType === "team" ? "team" : "event";

  return (
    <Modal opened={opened} onClose={onClose} title="Favorited by" centered>
      {query.isLoading ? (
        <LoadingState label="Loading favorites..." />
      ) : query.error ? (
        <ErrorState error={query.error} />
      ) : users.length === 0 ? (
        <EmptyState>No one has favorited this {label} yet.</EmptyState>
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
            {count} favorite{count === 1 ? "" : "s"}
          </Text>
        </Stack>
      )}
    </Modal>
  );
}
