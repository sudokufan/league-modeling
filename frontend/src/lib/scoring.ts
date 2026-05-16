// Pure scoring utility functions, ported from simulate.py

// Default cap: 3 rounds × 3 pts. Per-week cap is rounds_in_week × 3.
export const MAX_WEEKLY_POINTS = 9

/** Max possible score for a week with `rounds` rounds (= rounds * 3). */
export function weekCap(rounds: number): number {
  return rounds * 3
}

/**
 * Was this week a "perfect" week — i.e. score equals the week's cap.
 * Returns false if the round count is unknown (defensive default).
 */
export function isPerfectWeek(score: number | null, roundsInThatWeek: number | undefined): boolean {
  if (score == null || !roundsInThatWeek) return false
  return score === roundsInThatWeek * 3
}

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
 * Maximum possible best-N score. Remaining weeks are projected at the league's
 * default cap (`roundsPerWeek` × 3 pts), since future weeks default to the
 * configured round count.
 */
export function maxPossibleBestN(
  scores: (number | null)[],
  weeksCompleted: number,
  totalWeeks: number,
  n: number,
  roundsPerWeek: number = 3
): number {
  const existing = scores.filter((s): s is number => s !== null)
  const remainingWeeks = totalWeeks - weeksCompleted
  const remainingCap = roundsPerWeek * 3
  const allScores = [...existing, ...Array(remainingWeeks).fill(remainingCap)]
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

/**
 * Compute weekly scores with bye points removed.
 * A bye awards 3 match points; this subtracts those from the relevant weeks.
 */
export function noByeWeeklyScores(
  playerScores: (number | null)[],
  player: string,
  matches: { week: number; player_a: string; player_b?: string | null; games_a: number; games_b: number }[]
): (number | null)[] {
  // Count bye points per week for this player
  const byePointsByWeek: Record<number, number> = {}
  for (const m of matches) {
    const isBye = m.player_b == null || m.player_b === '-' || m.player_b === ''
    if (!isBye) continue
    if (m.player_a !== player) continue
    // A bye with 0-0 is a DQ (0 pts), otherwise 3 pts
    const pts = (m.games_a === 0 && m.games_b === 0) ? 0 : 3
    byePointsByWeek[m.week] = (byePointsByWeek[m.week] ?? 0) + pts
  }

  return playerScores.map((score, i) => {
    if (score == null) return null
    const week = i + 1
    const byePts = byePointsByWeek[week] ?? 0
    return Math.max(0, score - byePts)
  })
}
