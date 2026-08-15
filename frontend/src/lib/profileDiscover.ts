import type { MapEvent, MapTeam, UserSummary } from "../types/api";

const EARTH_RADIUS_MI = 3958.8;

export function haversineMiles(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_MI * Math.asin(Math.sqrt(a));
}

function stateKey(state: string | null | undefined): string {
  return (state ?? "").trim().toLowerCase();
}

function isChampionship(ev: MapEvent): boolean {
  const t = (ev.event_type ?? "").toLowerCase();
  const n = (ev.name ?? "").toLowerCase();
  return (
    t === "3" ||
    t === "4" ||
    t.includes("championship") ||
    n.includes("championship") ||
    n.includes("champs")
  );
}

export interface SuggestedTeam {
  teamNumber: number;
  nickname: string;
  reason: string;
  city?: string | null;
  state?: string | null;
}

export interface SuggestedEvent {
  eventKey: string;
  name: string;
  reason: string;
  city?: string | null;
  state?: string | null;
  week?: number | null;
  startDate?: string | null;
}

export interface SuggestedUser extends UserSummary {
  reason: string;
}

export function suggestTeams(params: {
  favoriteTeams: string[];
  mapTeams: MapTeam[];
  topTeamNumbers: number[];
  userTeam?: string | null;
}): SuggestedTeam[] {
  const favSet = new Set(params.favoriteTeams.map(Number));
  const byNum = new Map(params.mapTeams.map((t) => [t.team_number, t]));
  const anchors = params.favoriteTeams
    .map((t) => byNum.get(Number(t)))
    .filter((t): t is MapTeam => Boolean(t));

  if (params.userTeam && !favSet.has(Number(params.userTeam))) {
    const own = byNum.get(Number(params.userTeam));
    if (own) anchors.push(own);
  }

  const scored: Array<{ score: number; item: SuggestedTeam }> = [];

  for (const candidate of params.mapTeams) {
    if (favSet.has(candidate.team_number)) continue;
    let bestDist = Infinity;
    let anchor: MapTeam | null = null;
    for (const a of anchors) {
      const d = haversineMiles(a.lat, a.lng, candidate.lat, candidate.lng);
      if (d < bestDist) {
        bestDist = d;
        anchor = a;
      }
    }

    if (anchor && bestDist < 150) {
      scored.push({
        score: bestDist,
        item: {
          teamNumber: candidate.team_number,
          nickname: candidate.nickname ?? "",
          reason: `${Math.round(bestDist)} mi from #${anchor.team_number}`,
          city: candidate.city,
          state: candidate.state_prov,
        },
      });
      continue;
    }

    if (anchor && stateKey(anchor.state_prov) && stateKey(anchor.state_prov) === stateKey(candidate.state_prov)) {
      scored.push({
        score: 180,
        item: {
          teamNumber: candidate.team_number,
          nickname: candidate.nickname ?? "",
          reason: `Also in ${candidate.state_prov || candidate.country || "your area"}`,
          city: candidate.city,
          state: candidate.state_prov,
        },
      });
    }
  }

  for (const num of params.topTeamNumbers) {
    if (favSet.has(num)) continue;
    if (scored.some((s) => s.item.teamNumber === num)) continue;
    const t = byNum.get(num);
    scored.push({
      score: 500 + num,
      item: {
        teamNumber: num,
        nickname: t?.nickname ?? "",
        reason: "Top ACE this season",
        city: t?.city,
        state: t?.state_prov,
      },
    });
  }

  scored.sort((a, b) => a.score - b.score);
  const out: SuggestedTeam[] = [];
  const seen = new Set<number>();
  for (const row of scored) {
    if (seen.has(row.item.teamNumber)) continue;
    seen.add(row.item.teamNumber);
    out.push(row.item);
    if (out.length >= 5) break;
  }
  return out;
}

export function suggestEvents(params: {
  favoriteEvents: string[];
  favoriteTeams: string[];
  mapEvents: MapEvent[];
  mapTeams: MapTeam[];
  attendedEventKeys?: string[];
}): SuggestedEvent[] {
  const favEvents = new Set(params.favoriteEvents);
  const attended = new Set(params.attendedEventKeys ?? []);
  const byTeam = new Map(params.mapTeams.map((t) => [t.team_number, t]));
  const anchors = params.favoriteTeams
    .map((t) => byTeam.get(Number(t)))
    .filter((t): t is MapTeam => Boolean(t));

  for (const key of params.favoriteEvents) {
    const ev = params.mapEvents.find((e) => e.event_key === key);
    if (ev && ev.lat && ev.lng) {
      anchors.push({
        team_number: 0,
        nickname: ev.name,
        city: ev.city,
        state_prov: ev.state_prov,
        country: ev.country,
        lat: ev.lat,
        lng: ev.lng,
      });
    }
  }

  const states = new Set(anchors.map((a) => stateKey(a.state_prov)).filter(Boolean));
  const today = new Date().toISOString().slice(0, 10);

  const scored: Array<{ score: number; item: SuggestedEvent }> = [];

  for (const ev of params.mapEvents) {
    if (favEvents.has(ev.event_key)) continue;

    let score = 800;
    const reasons: string[] = [];

    if (attended.has(ev.event_key) && params.favoriteTeams.length > 0) {
      score = Math.min(score, 40);
      reasons.push("A team you follow competed here");
    }

    let bestDist = Infinity;
    for (const a of anchors) {
      if (!ev.lat || !ev.lng || !a.lat || !a.lng) continue;
      const d = haversineMiles(a.lat, a.lng, ev.lat, ev.lng);
      if (d < bestDist) bestDist = d;
    }
    if (bestDist < 250) {
      score = Math.min(score, 50 + bestDist);
      reasons.push(`${Math.round(bestDist)} mi away`);
    } else if (states.has(stateKey(ev.state_prov))) {
      score = Math.min(score, 160);
      reasons.push(`In ${ev.state_prov}`);
    }

    if (isChampionship(ev)) {
      score = Math.min(score, 90);
      reasons.push("Championship");
    }

    if (ev.start_date && ev.start_date >= today) {
      score -= 40;
      reasons.push("Upcoming");
    }

    if (reasons.length === 0) continue;

    scored.push({
      score,
      item: {
        eventKey: ev.event_key,
        name: ev.name ?? ev.event_key,
        reason: reasons[0],
        city: ev.city,
        state: ev.state_prov,
        week: ev.week,
        startDate: ev.start_date,
      },
    });
  }

  // Offseason / sparse-anchor fallback: still surface champs and nearby-state events.
  if (scored.length < 5) {
    const extra = [...params.mapEvents]
      .filter((ev) => !favEvents.has(ev.event_key) && !scored.some((s) => s.item.eventKey === ev.event_key))
      .sort((a, b) => {
        const champ = Number(isChampionship(b)) - Number(isChampionship(a));
        if (champ !== 0) return champ;
        return (a.week ?? 99) - (b.week ?? 99);
      })
      .slice(0, 8);
    for (const ev of extra) {
      scored.push({
        score: 900,
        item: {
          eventKey: ev.event_key,
          name: ev.name ?? ev.event_key,
          reason: isChampionship(ev)
            ? "Championship"
            : ev.state_prov
              ? `${ev.state_prov} event`
              : "This season",
          city: ev.city,
          state: ev.state_prov,
          week: ev.week,
          startDate: ev.start_date,
        },
      });
    }
  }

  scored.sort((a, b) => a.score - b.score);
  const out: SuggestedEvent[] = [];
  const seen = new Set<string>();
  for (const row of scored) {
    if (seen.has(row.item.eventKey)) continue;
    seen.add(row.item.eventKey);
    out.push(row.item);
    if (out.length >= 5) break;
  }
  return out;
}

export function suggestUsers(params: {
  selfId: number;
  selfUsername: string;
  following: UserSummary[];
  teamMembers: UserSummary[];
  coFavoriters: UserSummary[];
}): SuggestedUser[] {
  const followingNames = new Set(params.following.map((u) => u.username.toLowerCase()));
  const seen = new Set<number>([params.selfId]);
  const out: SuggestedUser[] = [];

  const push = (u: UserSummary, reason: string) => {
    if (seen.has(u.id)) return;
    if (u.username.toLowerCase() === params.selfUsername.toLowerCase()) return;
    if (followingNames.has(u.username.toLowerCase())) return;
    seen.add(u.id);
    out.push({ ...u, reason });
  };

  for (const u of params.teamMembers) push(u, u.team ? `Also on Team ${u.team}` : "Same team");
  for (const u of params.coFavoriters) push(u, "Favorites teams you like");

  return out.slice(0, 5);
}
