import { useState } from "react";
import { Group, Text, UnstyledButton } from "@mantine/core";
import { FavoriteButton } from "./FavoriteButton";
import { FavoritersModal } from "./FavoritersModal";
import { useFavoriteItemDetail } from "../api/favorites";
import type { FavoriteItemType } from "../types/api";

interface FavoriteWithCountProps {
  itemType: FavoriteItemType;
  itemKey: string | number;
  size?: number;
}

/** Star toggle plus public favorite count on a dark pill (count always white). */
export function FavoriteWithCount({ itemType, itemKey, size = 22 }: FavoriteWithCountProps) {
  const [open, setOpen] = useState(false);
  const favoriters = useFavoriteItemDetail(itemType, itemKey);

  return (
    <>
      <Group
        gap={4}
        wrap="nowrap"
        style={{
          background: "rgba(0,0,0,0.45)",
          borderRadius: 999,
          backdropFilter: "blur(6px)",
          paddingRight: 10,
        }}
      >
        <FavoriteButton itemType={itemType} itemKey={itemKey} size={size} />
        <UnstyledButton
          onClick={() => setOpen(true)}
          aria-label={`View who favorited this ${itemType}`}
        >
          <Text fw={700} fz="sm" c="#ffffff" style={{ whiteSpace: "nowrap" }}>
            {favoriters.data?.count ?? 0}
          </Text>
        </UnstyledButton>
      </Group>
      <FavoritersModal
        itemType={itemType}
        itemKey={itemKey}
        opened={open}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
