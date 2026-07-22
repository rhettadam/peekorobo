import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost } from "./client";
import type {
  FavoriteCountsResponse,
  FavoriteItemDetailResponse,
  FavoriteItemType,
  FavoriteStatusResponse,
  FavoritesResponse,
} from "../types/api";
import { useAuth } from "../auth/AuthContext";

export function fetchFavorites(): Promise<FavoritesResponse> {
  return apiGet<FavoritesResponse>("/favorites");
}

export function fetchFavoriteItemDetail(
  itemType: FavoriteItemType,
  itemKey: string,
): Promise<FavoriteItemDetailResponse> {
  return apiGet<FavoriteItemDetailResponse>(`/favorites/item/${itemType}/${encodeURIComponent(itemKey)}`);
}

export function fetchFavoriteCounts(itemType: FavoriteItemType = "team"): Promise<FavoriteCountsResponse> {
  return apiGet<FavoriteCountsResponse>("/favorites/counts", { item_type: itemType });
}

export function addFavorite(itemType: FavoriteItemType, itemKey: string): Promise<FavoriteStatusResponse> {
  return apiPost<FavoriteStatusResponse>("/favorites", { item_type: itemType, item_key: itemKey });
}

export function removeFavorite(itemType: FavoriteItemType, itemKey: string): Promise<FavoriteStatusResponse> {
  return apiDelete<FavoriteStatusResponse>("/favorites", { item_type: itemType, item_key: itemKey });
}

/** Current user's favorited teams and events. Empty when logged out. */
export function useFavorites(): UseQueryResult<FavoritesResponse> {
  const { isAuthenticated } = useAuth();
  return useQuery({
    queryKey: ["favorites"],
    queryFn: fetchFavorites,
    enabled: isAuthenticated,
    staleTime: 60 * 1000,
  });
}

/** Public: who favorited a team/event + total count. */
export function useFavoriteItemDetail(
  itemType: FavoriteItemType,
  itemKey: string | number | undefined,
): UseQueryResult<FavoriteItemDetailResponse> {
  const key = itemKey != null ? String(itemKey) : "";
  return useQuery({
    queryKey: ["favorites", "item", itemType, key],
    queryFn: () => fetchFavoriteItemDetail(itemType, key),
    enabled: Boolean(key),
    staleTime: 60 * 1000,
  });
}

/** Public map of item_key -> favorite count (leaderboards). */
export function useFavoriteCounts(itemType: FavoriteItemType = "team"): UseQueryResult<FavoriteCountsResponse> {
  return useQuery({
    queryKey: ["favorites", "counts", itemType],
    queryFn: () => fetchFavoriteCounts(itemType),
    staleTime: 60 * 1000,
  });
}

/**
 * Toggle a favorite. Reads current state from the cached favorites list and
 * optimistically flips it, rolling back on error.
 */
export function useToggleFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      itemType,
      itemKey,
      favorited,
    }: {
      itemType: FavoriteItemType;
      itemKey: string;
      favorited: boolean;
    }) => (favorited ? removeFavorite(itemType, itemKey) : addFavorite(itemType, itemKey)),
    onMutate: async ({ itemType, itemKey, favorited }) => {
      await queryClient.cancelQueries({ queryKey: ["favorites"] });
      const previous = queryClient.getQueryData<FavoritesResponse>(["favorites"]);
      if (previous) {
        const key = itemType === "team" ? "teams" : "events";
        const list = previous[key];
        const next = favorited ? list.filter((k) => k !== itemKey) : [...list, itemKey];
        queryClient.setQueryData<FavoritesResponse>(["favorites"], { ...previous, [key]: next });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(["favorites"], context.previous);
    },
    onSettled: (_data, _err, vars) => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
      if (vars) {
        queryClient.invalidateQueries({ queryKey: ["favorites", "item", vars.itemType, vars.itemKey] });
        queryClient.invalidateQueries({ queryKey: ["favorites", "counts", vars.itemType] });
      }
    },
  });
}
