// Raw API calls for accounts/auth. Higher-level state lives in auth/AuthContext.
import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import type {
  ApiKeyResponse,
  AuthUser,
  FollowStatusResponse,
  LoginPayload,
  PublicProfileResponse,
  RegisterPayload,
  TokenResponse,
  UpdateProfilePayload,
  UserListResponse,
} from "../types/api";

export function registerRequest(payload: RegisterPayload): Promise<TokenResponse> {
  return apiPost<TokenResponse>("/auth/register", payload);
}

export function loginRequest(payload: LoginPayload): Promise<TokenResponse> {
  return apiPost<TokenResponse>("/auth/login", payload);
}

export function fetchMe(): Promise<AuthUser> {
  return apiGet<AuthUser>("/auth/me");
}

export function updateProfile(payload: UpdateProfilePayload): Promise<AuthUser> {
  return apiPut<AuthUser>("/auth/me", payload);
}

export function fetchPublicProfile(username: string): Promise<PublicProfileResponse> {
  return apiGet<PublicProfileResponse>(`/users/${encodeURIComponent(username)}`);
}

// ---- Follows ----
export function followUser(username: string): Promise<FollowStatusResponse> {
  return apiPost<FollowStatusResponse>(`/users/${encodeURIComponent(username)}/follow`);
}

export function unfollowUser(username: string): Promise<FollowStatusResponse> {
  return apiDelete<FollowStatusResponse>(`/users/${encodeURIComponent(username)}/follow`);
}

export function fetchFollowers(username: string): Promise<UserListResponse> {
  return apiGet<UserListResponse>(`/users/${encodeURIComponent(username)}/followers`);
}

export function fetchFollowing(username: string): Promise<UserListResponse> {
  return apiGet<UserListResponse>(`/users/${encodeURIComponent(username)}/following`);
}

// ---- API key ----
export function fetchApiKey(): Promise<ApiKeyResponse> {
  return apiGet<ApiKeyResponse>("/auth/api-key");
}

export function generateApiKey(): Promise<ApiKeyResponse> {
  return apiPost<ApiKeyResponse>("/auth/api-key");
}

export function revokeApiKey(): Promise<ApiKeyResponse> {
  return apiDelete<ApiKeyResponse>("/auth/api-key");
}
