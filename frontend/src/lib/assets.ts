// Central helpers for referencing Peekorobo's static image assets.
//
// In dev, VITE_ASSETS_BASE_URL defaults to "/assets" and Vite serves the
// repo-root assets/ folder (see vite.config.ts). Brand icons also live under
// frontend/public/assets/ so Cloudflare Pages always ships logo/tba/etc. even
// when the post-build copy of ../assets is skipped. Avatars/game logos still
// come from the repo-root assets/ copy in CI.

export const ASSETS_BASE = (import.meta.env.VITE_ASSETS_BASE_URL ?? "/assets").replace(/\/$/, "");

/** Generic asset path builder, e.g. asset("logo.png"). */
export function asset(path: string): string {
  return `${ASSETS_BASE}/${path.replace(/^\//, "")}`;
}

/** Team avatar image URL. Falls back to a stock avatar on error (see STOCK_AVATAR). */
export function teamAvatar(teamNumber: number | string): string {
  return `${ASSETS_BASE}/avatars/${teamNumber}.png`;
}

export const STOCK_AVATAR = `${ASSETS_BASE}/avatars/stock.png`;

/**
 * User profile avatar URL. Avatar keys are stored like "1234.png" (a team
 * avatar) or "stock". Appends .png when the key has no extension.
 */
export function userAvatar(avatarKey?: string | null): string {
  if (!avatarKey) return STOCK_AVATAR;
  const key = avatarKey.includes(".") ? avatarKey : `${avatarKey}.png`;
  return `${ASSETS_BASE}/avatars/${key}`;
}

/** Per-season game logo (1992-present). `field` returns the field render variant. */
export function gameLogo(year: number, field = false): string {
  return `${ASSETS_BASE}/logos/${year}${field ? "field" : ""}.png`;
}

// Brand + section icons that live at the assets root.
export const BRAND = {
  logo: asset("logo.png"),
  banner: asset("banner.png"),
  home: asset("home.png"),
  mobileHome: asset("mobilehome.png"),
  favicon: asset("favicon.ico"),
  frc: asset("frc.png"),
  tba: asset("tba.png"),
  github: asset("github.png"),
  trophy: asset("trophy.png"),
  pin: asset("pin.png"),
} as const;
