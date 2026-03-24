// Pure scoring utility functions, ported from simulate.py

export const MAX_WEEKLY_POINTS = 9

/**
 * Sum of the best N non-null weekly scores.
 * Unplayed weeks (null) are excluded.
 */
export function bestNScore(scores: (number | null)[], n: number): number {
  const played = scores.filter((s): s is number => s !== null)
  played.sort((a, b) => b - a)
  return played.slice(0, n).reduce((sum, s) => sum + s, 0)
}

/**
 * Sum of all non-null weekly scores.
 */
export function totalMatchPoints(scores: (number | null)[]): number {
  return scores.reduce<number>((sum, s) => sum + (s ?? 0), 0)
}

/**
 * Maximum possible best-N score, filling remaining weeks with MAX_WEEKLY_POINTS.
 */
export function maxPossibleBestN(
  scores: (number | null)[],
  weeksCompleted: number,
  totalWeeks: number,
  n: number
): number {
  const existing = scores.filter((s): s is number => s !== null)
  const remainingWeeks = totalWeeks - weeksCompleted
  const allScores = [...existing, ...Array(remainingWeeks).fill(MAX_WEEKLY_POINTS)]
  allScores.sort((a, b) => b - a)
  return allScores.slice(0, n).reduce((sum, s) => sum + s, 0)
}

/**
 * Minimum guaranteed best-N score (current best N, no future weeks assumed).
 */
export function minGuaranteedBestN(scores: (number | null)[], n: number): number {
  const existing = scores.filter((s): s is number => s !== null)
  existing.sort((a, b) => b - a)
  return existing.slice(0, n).reduce((sum, s) => sum + s, 0)
}
