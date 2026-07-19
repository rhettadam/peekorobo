export const CURRENT_YEAR: number = Number(import.meta.env.VITE_CURRENT_YEAR) || 2026;

// Earliest FRC season (1992). Year pickers go back to the beginning, matching
// the original app's range(1992, current+1).
export const EPA_MIN_YEAR = 1992;

export function availableYears(minYear = EPA_MIN_YEAR, maxYear = CURRENT_YEAR): number[] {
  const years: number[] = [];
  for (let y = maxYear; y >= minYear; y--) years.push(y);
  return years;
}

// Demo teams (9970-9999) are excluded from ranking totals and comparisons.
export function isDemoTeam(teamNumber: number): boolean {
  return Number.isFinite(teamNumber) && teamNumber >= 9970 && teamNumber <= 9999;
}
