import type { FeatureCollection, Feature, Point } from "geojson";
import type { MapEvent, MapTeam } from "../types/api";
import { eventWeekLabel, formatDateRange, locationString } from "./format";

export const ACCENT = "#ffdd00";

// US-centered default view matching the legacy folium map.
export const DEFAULT_CENTER: [number, number] = [-98.5795, 39.8283];
export const DEFAULT_ZOOM = 4;

// Free, keyless dark vector basemaps. CARTO is primary; OpenFreeMap is the
// fallback if CARTO's style fails to load.
export const BASEMAP_PRIMARY =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
export const BASEMAP_FALLBACK = "https://tiles.openfreemap.org/styles/dark";

// Event marker colors by type (legacy folium map palette).
const EVENT_COLORS = {
  regional: "#3b82f6", // blue
  district: "#22c55e", // green
  championship: "#f59e0b", // gold/orange
  offseason: "#9ca3af", // gray
  other: "#ef4444", // red
} as const;

export function eventTypeColor(eventType?: string | null): string {
  const t = (eventType ?? "").toLowerCase();
  if (t.includes("regional")) return EVENT_COLORS.regional;
  if (t.includes("district")) return EVENT_COLORS.district;
  if (t.includes("championship")) return EVENT_COLORS.championship;
  if (t.includes("offseason") || t.includes("off-season")) return EVENT_COLORS.offseason;
  return EVENT_COLORS.other;
}

export const EVENT_LEGEND: Array<{ label: string; color: string }> = [
  { label: "Regional", color: EVENT_COLORS.regional },
  { label: "District", color: EVENT_COLORS.district },
  { label: "Championship", color: EVENT_COLORS.championship },
  { label: "Offseason", color: EVENT_COLORS.offseason },
  { label: "Other", color: EVENT_COLORS.other },
];

// FRC district colors (keyed by the `district` property injected into the
// filtered Natural Earth GeoJSON in public/data/districts.geojson).
export const DISTRICT_COLORS: Record<string, string> = {
  ONT: "#1f77b4",
  FMA: "#ff7f0e",
  ISR: "#2ca02c",
  FCH: "#d62728",
  FIT: "#9467bd",
  PCH: "#8c564b",
  PNW: "#e377c2",
  FIM: "#17becf",
  FSC: "#bcbd22",
  FNC: "#17becf",
  FIN: "#ff9896",
  NE: "#98df8a",
  CA: "#00bfff",
  WIN: "#ff7f0e",
};

export interface TeamFeatureProps {
  kind: "team";
  team_number: number;
  nickname: string;
  location: string;
}

export interface EventFeatureProps {
  kind: "event";
  event_key: string;
  name: string;
  location: string;
  event_type: string;
  week: string;
  dates: string;
  color: string;
  /** How many events share this venue (for stack popups). */
  stack_size?: number;
  true_lat?: number;
  true_lng?: number;
}

export function teamToPopupProps(t: MapTeam): TeamFeatureProps {
  return {
    kind: "team",
    team_number: t.team_number,
    nickname: t.nickname ?? "",
    location: locationString(t.city ?? "", t.state_prov ?? "", t.country ?? ""),
  };
}

/** Bucket near-identical coords so stacked venues/teams share one key. */
export function coordKey(lat: number, lng: number, decimals = 5): string {
  const a = Number(lat);
  const b = Number(lng);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return "invalid";
  return `${a.toFixed(decimals)},${b.toFixed(decimals)}`;
}

/** Deterministic 0..1 from an integer seed (stable across zooms / re-renders). */
function hash01(seed: number): number {
  const x = Math.sin(seed * 127.1 + 311.7) * 43758.5453123;
  return x - Math.floor(x);
}

function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// Golden angle (radians) — phyllotaxis / sunflower packing.
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/**
 * Organic offset (lngΔ, latΔ) for co-located markers.
 * Uses a golden-angle spiral with light jitter so piles look like a natural
 * scatter instead of a rigid circle. `radiusDeg` from `stackRadiusForZoom`.
 */
export function stackOffset(
  index: number,
  count: number,
  radiusDeg: number,
  seed = index,
): [number, number] {
  if (count <= 1 || radiusDeg <= 0) return [0, 0];
  const angle = index * GOLDEN_ANGLE + (hash01(seed) - 0.5) * 0.55;
  // Fill a soft disk (sqrt → even area density), with gentle radial noise.
  const t = (index + 0.35) / count;
  const radial = Math.sqrt(t) * (0.78 + hash01(seed + 17) * 0.5);
  const r = radiusDeg * radial * (0.95 + 0.12 * Math.sqrt(count));
  return [Math.cos(angle) * r, Math.sin(angle) * r];
}

/**
 * Geographic radius for stack spread.
 * Kept mostly constant so zooming in *opens* the pile on screen instead of
 * keeping markers in a forever-tight knot.
 */
export function stackRadiusForZoom(zoom: number, _lat = 39): number {
  const z = Number.isFinite(zoom) ? zoom : 4;
  // ~0.006° ≈ 650m — readable fan that grows larger on screen as you zoom in.
  // Tiny nudge past ~z10 so deep zooms feel even more opened up.
  const base = 0.006;
  const deep = Math.max(0, z - 10) * 0.0005;
  return Math.min(0.018, base + deep);
}

/** Display positions for items that share lat/lng (true coords unchanged on the object). */
export function spreadByCoords<T>(
  items: T[],
  getLatLng: (item: T) => { lat: number; lng: number } | null,
  radiusDeg = stackRadiusForZoom(6),
  getSeed?: (item: T) => number | string,
): Array<{ item: T; lat: number; lng: number; trueLat: number; trueLng: number; stackSize: number }> {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const ll = getLatLng(item);
    if (!ll) continue;
    const key = coordKey(ll.lat, ll.lng);
    const list = groups.get(key) ?? [];
    list.push(item);
    groups.set(key, list);
  }
  const out: Array<{
    item: T;
    lat: number;
    lng: number;
    trueLat: number;
    trueLng: number;
    stackSize: number;
  }> = [];
  for (const group of groups.values()) {
    // Stable order so seeds/indexes don't reshuffle when the viewport changes.
    const sorted = [...group].sort((a, b) => {
      const sa = getSeed?.(a);
      const sb = getSeed?.(b);
      const na = typeof sa === "number" ? sa : hashString(String(sa ?? ""));
      const nb = typeof sb === "number" ? sb : hashString(String(sb ?? ""));
      return na - nb;
    });
    const n = sorted.length;
    sorted.forEach((item, i) => {
      const ll = getLatLng(item)!;
      const raw = getSeed?.(item);
      const seed =
        typeof raw === "number" ? raw : raw != null ? hashString(String(raw)) : i;
      const [dlng, dlat] = stackOffset(i, n, radiusDeg, seed);
      out.push({
        item,
        lat: ll.lat + dlat,
        lng: ll.lng + dlng,
        trueLat: ll.lat,
        trueLng: ll.lng,
        stackSize: n,
      });
    });
  }
  return out;
}

export function teamsToGeoJSON(teams: MapTeam[]): FeatureCollection<Point, TeamFeatureProps> {
  const features: Feature<Point, TeamFeatureProps>[] = [];
  for (const t of teams) {
    if (typeof t.lat !== "number" || typeof t.lng !== "number") continue;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [t.lng, t.lat] },
      properties: {
        kind: "team",
        team_number: t.team_number,
        nickname: t.nickname ?? "",
        location: locationString(t.city ?? "", t.state_prov ?? "", t.country ?? ""),
      },
    });
  }
  return { type: "FeatureCollection", features };
}

export function eventsToGeoJSON(
  events: MapEvent[],
  zoom = 6,
  lat = 39,
): FeatureCollection<Point, EventFeatureProps> {
  const spread = spreadByCoords(
    events,
    (e) =>
      typeof e.lat === "number" && typeof e.lng === "number" ? { lat: e.lat, lng: e.lng } : null,
    stackRadiusForZoom(zoom, lat),
    (e) => e.event_key,
  );
  const features: Feature<Point, EventFeatureProps>[] = [];
  for (const { item: e, lat, lng, stackSize } of spread) {
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lng, lat] },
      properties: {
        kind: "event",
        event_key: e.event_key,
        name: e.name ?? e.event_key,
        location: locationString(e.city ?? "", e.state_prov ?? "", e.country ?? ""),
        event_type: e.event_type ?? "",
        week: eventWeekLabel(e.week) ?? "",
        dates: formatDateRange(e.start_date, e.end_date),
        color: eventTypeColor(e.event_type),
        stack_size: stackSize,
        true_lat: e.lat!,
        true_lng: e.lng!,
      },
    });
  }
  return { type: "FeatureCollection", features };
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Popup markup styled to the app's dark theme. Links carry data-spa-href so the
// map's delegated click handler can route them through react-router (no reload).
export function teamPopupHTML(p: TeamFeatureProps): string {
  const num = p.team_number;
  const title = p.nickname ? `${num} | ${escapeHtml(p.nickname)}` : `Team ${num}`;
  const loc = p.location ? `<div class="peeko-popup-sub">${escapeHtml(p.location)}</div>` : "";
  return `
    <div class="peeko-popup">
      <div class="peeko-popup-badge">Team</div>
      <div class="peeko-popup-title">${title}</div>
      ${loc}
      <a class="peeko-popup-link" data-spa-href="/team/${num}" href="/team/${num}">View team →</a>
    </div>`;
}

export function eventPopupHTML(p: EventFeatureProps): string {
  const meta: string[] = [];
  if (p.event_type) meta.push(escapeHtml(p.event_type));
  if (p.week) meta.push(escapeHtml(p.week));
  const metaLine = meta.length
    ? `<div class="peeko-popup-sub">${meta.join(" &middot; ")}</div>`
    : "";
  const loc = p.location ? `<div class="peeko-popup-sub">${escapeHtml(p.location)}</div>` : "";
  const dates = p.dates ? `<div class="peeko-popup-sub">${escapeHtml(p.dates)}</div>` : "";
  return `
    <div class="peeko-popup">
      <div class="peeko-popup-badge" style="background:${p.color}">Event</div>
      <div class="peeko-popup-title">${escapeHtml(p.name)}</div>
      ${loc}
      ${metaLine}
      ${dates}
      <a class="peeko-popup-link" data-spa-href="/event/${p.event_key}" href="/event/${p.event_key}">View event →</a>
    </div>`;
}

/** Compact row for stacked popups (many teams/events at one click). */
export function teamStackRowHTML(p: TeamFeatureProps): string {
  const title = p.nickname
    ? `${p.team_number} | ${escapeHtml(p.nickname)}`
    : `Team ${p.team_number}`;
  return `<a class="peeko-popup-stack-row" data-spa-href="/team/${p.team_number}" href="/team/${p.team_number}">
    <span class="peeko-popup-stack-title">${title}</span>
    <span class="peeko-popup-stack-go">→</span>
  </a>`;
}

export function eventStackRowHTML(p: EventFeatureProps): string {
  return `<a class="peeko-popup-stack-row" data-spa-href="/event/${p.event_key}" href="/event/${p.event_key}">
    <span class="peeko-popup-stack-swatch" style="background:${p.color}"></span>
    <span class="peeko-popup-stack-title">${escapeHtml(p.name)}</span>
    <span class="peeko-popup-stack-go">→</span>
  </a>`;
}

export function stackPopupHTML(label: string, rowsHtml: string[]): string {
  if (rowsHtml.length === 0) return "";
  return `
    <div class="peeko-popup peeko-popup-stack">
      <div class="peeko-popup-badge">${rowsHtml.length} ${escapeHtml(label)}</div>
      <div class="peeko-popup-stack-list">${rowsHtml.join("")}</div>
    </div>`;
}
