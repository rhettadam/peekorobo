// Formatting helpers ported/adapted from utils.py.

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** Convert an ISO date/datetime or 'YYYY-MM-DD' to 'Month D, YYYY'. Returns '' if invalid. */
export function formatHumanDate(value?: string | null): string {
  if (!value) return "";
  const datePart = value.length >= 10 ? value.slice(0, 10) : value;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(datePart);
  if (!m) return "";
  const [, y, mo, d] = m;
  const month = MONTHS[Number(mo) - 1];
  if (!month) return "";
  return `${month} ${Number(d)}, ${y}`;
}

export function formatDateRange(start?: string | null, end?: string | null): string {
  const s = formatHumanDate(start);
  const e = formatHumanDate(end);
  if (s && e) return `${s} - ${e}`;
  return s || e || "";
}

export function truncate(name: string, maxLength = 32): string {
  if (!name) return "";
  return name.length <= maxLength ? name : name.slice(0, maxLength - 3) + "...";
}

/** Format a metric to a fixed number of decimals, or a dash when missing. */
export function formatNumber(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toFixed(decimals);
}

export function ordinal(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

export function recordString(
  wins?: number | null,
  losses?: number | null,
  ties?: number | null,
): string {
  const w = wins ?? 0;
  const l = losses ?? 0;
  const t = ties ?? 0;
  return t > 0 ? `${w}-${l}-${t}` : `${w}-${l}`;
}

/** Human label for a 0-based stored week index, e.g. 0 -> 'Week 1'. */
export function eventWeekLabel(week?: number | null): string | null {
  if (week === null || week === undefined) return null;
  const idx = Number(week);
  if (!Number.isFinite(idx) || idx < 0) return null;
  return `Week ${idx + 1}`;
}

/** Extract base district code from a TBA key: '2024fim' -> 'FIM', 'fim' -> 'FIM'. */
export function normalizeDistrictKey(key?: string | null): string | null {
  if (!key || typeof key !== "string") return null;
  const s = key.trim();
  if (!s) return null;
  if (s.length > 4 && /^\d{4}$/.test(s.slice(0, 4))) return s.slice(4).toUpperCase();
  return s.toUpperCase();
}

/** The season year encoded at the front of an event key, e.g. '2024cmp' -> 2024. */
export function yearFromEventKey(eventKey: string): number | null {
  const m = /^(\d{4})/.exec(eventKey);
  return m ? Number(m[1]) : null;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  "0": "Regional",
  "1": "District",
  "2": "District Championship",
  "3": "Championship Division",
  "4": "Championship",
  "5": "District Championship Division",
  "6": "Festival of Champions",
  "99": "Offseason",
  "100": "Preseason",
};

/** Friendly event-type label; accepts numeric codes or already-friendly strings. */
export function eventTypeLabel(eventType?: string | null): string {
  if (eventType === null || eventType === undefined) return "";
  const raw = String(eventType).trim();
  if (raw in EVENT_TYPE_LABELS) return EVENT_TYPE_LABELS[raw];
  return raw;
}

export function locationString(city?: string, state?: string, country?: string): string {
  return [city, state, country].map((p) => (p || "").trim()).filter(Boolean).join(", ");
}
