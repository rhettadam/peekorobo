import { ActionIcon, Button, Tooltip } from "@mantine/core";
import { IconStar, IconStarFilled } from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useFavorites, useToggleFavorite } from "../api/favorites";
import type { FavoriteItemType } from "../types/api";

interface FavoriteButtonProps {
  itemType: FavoriteItemType;
  itemKey: string | number;
  /** "icon" renders a compact star ActionIcon; "button" renders a labelled button. */
  variant?: "icon" | "button";
  size?: number;
}

/**
 * Star toggle for favoriting a team or event. Only functional when logged in;
 * otherwise it routes to /login. Mirrors the old Dash favorite_button.
 */
export function FavoriteButton({ itemType, itemKey, variant = "icon", size = 22 }: FavoriteButtonProps) {
  const key = String(itemKey);
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { data: favorites } = useFavorites();
  const toggle = useToggleFavorite();

  const list = itemType === "team" ? favorites?.teams : favorites?.events;
  const favorited = Boolean(list?.includes(key));

  const label = favorited ? "Remove from favorites" : "Add to favorites";

  const handleClick = () => {
    if (!isAuthenticated) {
      notifications.show({
        title: "Log in required",
        message: `Log in to favorite ${itemType === "team" ? "teams" : "events"}.`,
        color: "yellow",
      });
      navigate("/login");
      return;
    }
    toggle.mutate(
      { itemType, itemKey: key, favorited },
      {
        onError: (err) =>
          notifications.show({
            title: "Something went wrong",
            message: err instanceof Error ? err.message : "Could not update favorite.",
            color: "red",
          }),
      },
    );
  };

  const StarIcon = favorited ? IconStarFilled : IconStar;
  const gold = "#ffdd00";

  if (variant === "button") {
    return (
      <Button
        onClick={handleClick}
        loading={toggle.isPending}
        variant={favorited ? "filled" : "default"}
        color="peeko"
        leftSection={<StarIcon size={18} />}
        size="sm"
      >
        {favorited ? "Favorited" : "Favorite"}
      </Button>
    );
  }

  return (
    <Tooltip label={label} withArrow>
      <ActionIcon
        onClick={handleClick}
        loading={toggle.isPending}
        variant="subtle"
        color="gray"
        size="lg"
        aria-label={label}
        style={{ color: favorited ? gold : undefined }}
      >
        <StarIcon size={size} color={favorited ? gold : "currentColor"} />
      </ActionIcon>
    </Tooltip>
  );
}
