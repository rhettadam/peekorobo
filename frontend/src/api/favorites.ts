import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost } from "./client";
import type { FavoriteItemType, FavoriteStatusResponse, FavoritesResponse } from "../types/api";
import { useAuth } from "../auth/AuthContext";

export function fetchFavorites(): Promise<FavoritesResponse> {
  return apiGet<FavoritesResponse>("/favorites");
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
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["favorites"] });
    },
  });
}
