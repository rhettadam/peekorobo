// Blue banner classification.
//
// In FRC only a specific set of awards earn a "blue banner" that teams hang:
//   1. Chairman's / Impact Award (the top award, at any level)
//   2. Event / division / championship Winner (the team won)
//   3. Woodie Flowers Award (including the regional/district "Finalist" variant)
//
// Award names have drifted a lot across seasons (1999-present), so matching is
// keyword-based and case-insensitive. The old Dash app used the naive keyword
// list ["chairman's", "impact", "woodie flowers", "winner"]; we keep that intent
// but robustify it to also catch "Champion(s)"/"Division Champion" wins while
// avoiding the classic pitfalls below.

export type BlueBannerKind = "chairmans" | "impact" | "winner" | "woodie";

// A win is "Winner"/"Winners" or a standalone "Champion"/"Champions". The word
// boundaries are load-bearing: they let "Division Champion" match while keeping
// "Championship" (which merely *contains* "champion") from matching on its own.
const WINNER_RE = /\b(?:winners?|champions?)\b/i;

// "Finalist"/"Finalists" is never a win. Guarded only in the winner branch so
// the legitimate "Woodie Flowers Finalist Award" banner still counts.
const FINALIST_RE = /finalists?/i;

/**
 * Classify an award name into the kind of blue banner it earns, or null if it
 * earns no banner (Finalist, Quality, Engineering, Dean's List, #1 Seed, etc.).
 */
export function blueBannerKind(awardName: string): BlueBannerKind | null {
  const name = (awardName || "").toLowerCase();
  if (!name) return null;

  // Chairman's / Impact — the top award at regional/district/championship level.
  // We only test "chairman", so straight (') and curly (’) apostrophes both work.
  if (name.includes("chairman")) return "chairmans";
  if (name.includes("impact")) return "impact";

  // Woodie Flowers. Both the championship "Woodie Flowers Award" and the
  // regional/district "Woodie Flowers Finalist Award" hang a banner, matching
  // the old app's broad "woodie flowers" keyword.
  if (name.includes("woodie flowers")) return "woodie";

  // Event/division/championship wins, but never a Finalist.
  if (WINNER_RE.test(name) && !FINALIST_RE.test(name)) return "winner";

  return null;
}

/** True when the award earns a blue banner. */
export function isBlueBanner(awardName: string): boolean {
  return blueBannerKind(awardName) !== null;
}

/**
 * Partition a list of awards into blue-banner-worthy vs regular, preserving the
 * input order within each bucket.
 */
export function splitBanners<T extends { award_name: string }>(
  awards: T[],
): { banners: T[]; regular: T[] } {
  const banners: T[] = [];
  const regular: T[] = [];
  for (const a of awards) {
    if (isBlueBanner(a.award_name)) banners.push(a);
    else regular.push(a);
  }
  return { banners, regular };
}

/** Short human label for a banner kind, e.g. for a caption or badge. */
export const BLUE_BANNER_LABEL: Record<BlueBannerKind, string> = {
  chairmans: "Chairman's",
  impact: "Impact",
  winner: "Winner",
  woodie: "Woodie Flowers",
};
