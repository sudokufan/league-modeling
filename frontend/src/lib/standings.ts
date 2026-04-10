import type { DerivedLeague, PlayerStats, PlayerSimResult } from '@/types'
import { bestNScore } from './scoring'

/**
 * Sort official players by standings tiebreakers:
 * (current_best_n, overall_omw, gwp) descending.
 * Excludes unofficial players.
 * Returns sorted array of player names.
 */
export function sortStandings(
  players: string[],
  weeklyScores: Record<string, (number | null)[]>,
  overallOmw: Record<string, number>,
  overallStats: Record<string, PlayerStats>,
  unofficialPlayers: string[],
  bestOfN: number
): string[] {
  const unofficialSet = new Set(unofficialPlayers)
  const official = players.filter(p => !unofficialSet.has(p))

  return [...official].sort((a, b) => {
    const aBestN = bestNScore(weeklyScores[a] ?? [], bestOfN)
    const bBestN = bestNScore(weeklyScores[b] ?? [], bestOfN)
    if (bBestN !== aBestN) return bBestN - aBestN

    const aOmw = overallOmw[a] ?? 0
    const bOmw = overallOmw[b] ?? 0
    if (bOmw !== aOmw) return bOmw - aOmw

    const aGwp = overallStats[a]?.gwp ?? 0
    const bGwp = overallStats[b]?.gwp ?? 0
    return bGwp - aGwp
  })
}

/**
 * For each week 1..totalWeeks, return the top-N official players sorted by
 * (bestNScore through that week, avgOmwThroughWeek).
 * Returns null for future weeks (w > weeksCompleted).
 *
 * perWeekOmw keys are strings ("1", "2", ...) as they come from JSON.
 */
export function weeklyTopN(
  players: string[],
  weeklyScores: Record<string, (number | null)[]>,
  perWeekOmw: Record<string, Record<string, number>>,
  bestOfN: number,
  weeksCompleted: number,
  totalWeeks: number,
  n: number
): (string[] | null)[] {
  const snapshots: (string[] | null)[] = []

  for (let w = 1; w <= totalWeeks; w++) {
    if (w > weeksCompleted) {
      snapshots.push(null)
      continue
    }

    // Average OMW through week w for a player
    const omwThrough = (p: string): number => {
      const omws: number[] = []
      for (let wk = 1; wk <= w; wk++) {
        const weekKey = String(wk)
        const weekData = perWeekOmw[weekKey]
        if (weekData && p in weekData) {
          omws.push(weekData[p])
        }
      }
      return omws.length > 0 ? omws.reduce((a, b) => a + b, 0) / omws.length : 0
    }

    const sorted = [...players].sort((a, b) => {
      const scoresA = weeklyScores[a] ?? []
      const scoresB = weeklyScores[b] ?? []
      const aBestN = bestNScore(scoresA.slice(0, w), bestOfN)
      const bBestN = bestNScore(scoresB.slice(0, w), bestOfN)
      if (bBestN !== aBestN) return bBestN - aBestN

      return omwThrough(b) - omwThrough(a)
    })

    snapshots.push(sorted.slice(0, n))
  }

  return snapshots
}

/**
 * Given the already-loaded previous league's DerivedLeague, return the winner's name
 * by sorting official players with the same standings tiebreaker logic.
 */
export function getDefendingChampion(prevLeagueData: DerivedLeague): string | null {
  const unofficialSet = new Set(prevLeagueData.unofficial_players ?? [])
  const prevPlayers = prevLeagueData.players.filter(p => !unofficialSet.has(p))

  if (prevPlayers.length === 0) return null

  const sorted = sortStandings(
    prevPlayers,
    prevLeagueData.weekly_scores,
    prevLeagueData.overall_omw,
    prevLeagueData.overall_stats,
    [], // already filtered out unofficial above
    prevLeagueData.best_of_n
  )

  return sorted[0] ?? null
}

/**
 * Determine which players are mathematically clinched or eliminated.
 * Works on per-player results containing max_possible_best7 and min_guaranteed_best7.
 */
export function checkEliminationClinch(
  results: Record<string, Pick<PlayerSimResult, 'max_possible_best7' | 'min_guaranteed_best7'>>,
  players: string[],
  playoffSpots: number
): Record<string, { status: 'clinched' | 'eliminated' | 'alive' }> {
  const maxScores: Record<string, number> = {}
  const minScores: Record<string, number> = {}
  for (const p of players) {
    maxScores[p] = results[p].max_possible_best7
    minScores[p] = results[p].min_guaranteed_best7
  }

  const status: Record<string, { status: 'clinched' | 'eliminated' | 'alive' }> = {}

  for (const p of players) {
    // Check elimination: p's max < the playoffSpots-th best minimum of others
    const otherMins = players
      .filter(q => q !== p)
      .map(q => minScores[q])
      .sort((a, b) => b - a)

    if (otherMins.length >= playoffSpots && maxScores[p] < otherMins[playoffSpots - 1]) {
      status[p] = { status: 'eliminated' }
    } else {
      status[p] = { status: 'alive' }
    }

    // Check clinch: p's min > the playoffSpots-th best maximum of others
    const otherMaxes = players
      .filter(q => q !== p)
      .map(q => maxScores[q])
      .sort((a, b) => b - a)

    if (otherMaxes.length >= playoffSpots && minScores[p] > otherMaxes[playoffSpots - 1]) {
      status[p] = { status: 'clinched' }
    }
  }

  return status
}
