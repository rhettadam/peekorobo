import { useMutation, useQueryClient } from "@tanstack/react-query";
import { followUser, unfollowUser } from "./auth";
import type { PublicProfileResponse } from "../types/api";

/**
 * Follow/unfollow a user, optimistically updating the cached public profile
 * (is_following + followers_count), rolling back on error. Mirrors the
 * favorites toggle pattern.
 */
export function useToggleFollow(username: string) {
  const queryClient = useQueryClient();
  const key = ["public-profile", username];
  return useMutation({
    mutationFn: ({ isFollowing }: { isFollowing: boolean }) =>
      isFollowing ? unfollowUser(username) : followUser(username),
    onMutate: async ({ isFollowing }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<PublicProfileResponse>(key);
      if (previous) {
        queryClient.setQueryData<PublicProfileResponse>(key, {
          ...previous,
          is_following: !isFollowing,
          user: {
            ...previous.user,
            followers_count: Math.max(0, previous.user.followers_count + (isFollowing ? -1 : 1)),
          },
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSuccess: (status) => {
      const current = queryClient.getQueryData<PublicProfileResponse>(key);
      if (current) {
        queryClient.setQueryData<PublicProfileResponse>(key, {
          ...current,
          is_following: status.is_following,
          user: { ...current.user, followers_count: status.followers_count },
        });
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: key });
      // Also refresh the followers/following lists if open.
      queryClient.invalidateQueries({ queryKey: ["followers", username] });
      queryClient.invalidateQueries({ queryKey: ["following", username] });
    },
  });
}
