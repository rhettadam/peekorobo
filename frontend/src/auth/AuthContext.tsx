import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getToken, setToken } from "../api/client";
import { fetchMe, loginRequest, registerRequest } from "../api/auth";
import type { AuthUser, LoginPayload, RegisterPayload } from "../types/api";

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<AuthUser>;
  register: (payload: RegisterPayload) => Promise<AuthUser>;
  logout: () => void;
  setUser: (user: AuthUser | null) => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  // Start in loading state only if we have a token to validate.
  const [isLoading, setIsLoading] = useState<boolean>(() => Boolean(getToken()));

  // On mount, if a token is persisted, resolve the current user.
  useEffect(() => {
    let cancelled = false;
    if (!getToken()) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    fetchMe()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        // Token invalid/expired: clear it.
        if (!cancelled) {
          setToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const res = await loginRequest(payload);
      setToken(res.access_token);
      setUser(res.user);
      await queryClient.invalidateQueries({ queryKey: ["favorites"] });
      return res.user;
    },
    [queryClient],
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const res = await registerRequest(payload);
      setToken(res.access_token);
      setUser(res.user);
      await queryClient.invalidateQueries({ queryKey: ["favorites"] });
      return res.user;
    },
    [queryClient],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    // Drop any per-user cached data (favorites, etc.).
    queryClient.removeQueries({ queryKey: ["favorites"] });
    queryClient.removeQueries({ queryKey: ["favorite-status"] });
  }, [queryClient]);

  const refresh = useCallback(async () => {
    if (!getToken()) return;
    try {
      setUser(await fetchMe());
    } catch {
      setToken(null);
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      setUser,
      refresh,
    }),
    [user, isLoading, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
