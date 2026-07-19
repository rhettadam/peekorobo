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

// Event marker colors by type, mirroring geo/createmap.py's get_event_marker_color.
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
}

export function teamToPopupProps(t: MapTeam): TeamFeatureProps {
  return {
    kind: "team",
    team_number: t.team_number,
    nickname: t.nickname ?? "",
    location: locationString(t.city ?? "", t.state_prov ?? "", t.country ?? ""),
  };
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

export function eventsToGeoJSON(events: MapEvent[]): FeatureCollection<Point, EventFeatureProps> {
  const features: Feature<Point, EventFeatureProps>[] = [];
  for (const e of events) {
    if (typeof e.lat !== "number" || typeof e.lng !== "number") continue;
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [e.lng, e.lat] },
      properties: {
        kind: "event",
        event_key: e.event_key,
        name: e.name ?? e.event_key,
        location: locationString(e.city ?? "", e.state_prov ?? "", e.country ?? ""),
        event_type: e.event_type ?? "",
        week: eventWeekLabel(e.week) ?? "",
        dates: formatDateRange(e.start_date, e.end_date),
        color: eventTypeColor(e.event_type),
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
