// Small typed fetch wrapper around the Peekorobo FastAPI backend.

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type QueryParams = Record<
  string,
  string | number | boolean | null | undefined
>;

// ---- Auth token persistence (SPA stores the JWT in localStorage) ----
const TOKEN_KEY = "peekorobo_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore storage errors (e.g. private mode)
  }
}

function buildQuery(params?: QueryParams): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseError(res: Response): Promise<never> {
  let detail = res.statusText;
  try {
    const body = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      const d = (body as { detail: unknown }).detail;
      detail = Array.isArray(d) ? d.map((x) => (x as { msg?: string })?.msg ?? String(x)).join(", ") : String(d);
    }
  } catch {
    // ignore body parse errors
  }
  throw new ApiError(res.status, detail || `Request failed (${res.status})`);
}

export async function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  const url = `${API_BASE}${path}${buildQuery(params)}`;
  let res: Response;
  try {
    res = await fetch(url, { headers: { Accept: "application/json", ...authHeaders() } });
  } catch (err) {
    throw new ApiError(0, `Network error contacting the API: ${(err as Error).message}`);
  }
  if (!res.ok) await parseError(res);
  return (await res.json()) as T;
}

async function apiSend<T>(
  method: "POST" | "PUT" | "DELETE",
  path: string,
  options: { body?: unknown; params?: QueryParams } = {},
): Promise<T> {
  const url = `${API_BASE}${path}${buildQuery(options.params)}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: {
        Accept: "application/json",
        ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(),
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch (err) {
    throw new ApiError(0, `Network error contacting the API: ${(err as Error).message}`);
  }
  if (!res.ok) await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiSend<T>("POST", path, { body });
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return apiSend<T>("PUT", path, { body });
}

export function apiDelete<T>(path: string, params?: QueryParams): Promise<T> {
  return apiSend<T>("DELETE", path, { params });
}
