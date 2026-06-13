import type { DerivedLeague, PlayerStats, PlayerSimResult, Playoffs, PlayoffMatch } from '@/types'
import { bestNScore } from './scoring'

/**
 * Return (winner, loser) for a completed playoff match. A draw breaks toward
 * player_a (higher seed) — mirrors simulate.get_match_winner_loser.
 */
function matchWinnerLoser(match?: PlayoffMatch | null): { winner: string | null; loser: string | null } {
  if (!match || match.games_a == null || match.games_b == null) return { winner: null, loser: null }
  if (!match.player_a || !match.player_b) return { winner: null, loser: null }
  if (match.games_a >= match.games_b) return { winner: match.player_a, loser: match.player_b }
  return { winner: match.player_b, loser: match.player_a }
}

/**
 * True iff every playoff match (semis, final, third place) has a recorded score.
 * Mirrors simulate.are_playoffs_complete.
 */
export function arePlayoffsComplete(playoffs?: Playoffs | null): boolean {
  if (!playoffs) return false
  for (const m of [playoffs.semifinal_1, playoffs.semifinal_2, playoffs.final, playoffs.third_place]) {
    if (!m || m.games_a == null || m.games_b == null) return false
  }
  return true
}

/**
 * Given regular-season standings, override the top 4 with the actual playoff
 * finishing order: champion, runner-up, third, fourth. Players outside the top 4
 * keep their regular-season order. Returns the input unchanged if playoffs are
 * not complete or any expected player is missing.
 */
export function applyPlayoffOrdering(
  regularSorted: string[],
  playoffs?: Playoffs | null
): string[] {
  if (!arePlayoffsComplete(playoffs)) return regularSorted
  const final = matchWinnerLoser(playoffs!.final)
  const third = matchWinnerLoser(playoffs!.third_place)
  const finishOrder = [final.winner, final.loser, third.winner, third.loser].filter(
    (p): p is string => p != null
  )
  if (finishOrder.length !== 4) return regularSorted
  // Anyone not in the top-4 finish keeps their regular-season order.
  const top4Set = new Set(finishOrder)
  const remainder = regularSorted.filter(p => !top4Set.has(p))
  return [...finishOrder, ...remainder]
}

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
 * Rank all official players by their standings *as of the end of week `throughWeek`*.
 * Uses the same dominant key as the live standings — best-N over scores up to and
 * including `throughWeek` — with average OMW through that week as the tiebreaker
 * (mirrors weeklyTopN, since season-total OMW/GWP aren't meaningful mid-season).
 *
 * Returns a map of player -> 1-based rank. Unofficial players are excluded.
 * Returns an empty map for throughWeek < 1.
 */
export function rankAllThroughWeek(
  players: string[],
  weeklyScores: Record<string, (number | null)[]>,
  perWeekOmw: Record<string, Record<string, number>>,
  unofficialPlayers: string[],
  bestOfN: number,
  throughWeek: number
): Record<string, number> {
  const ranks: Record<string, number> = {}
  if (throughWeek < 1) return ranks

  const unofficialSet = new Set(unofficialPlayers)
  const official = players.filter(p => !unofficialSet.has(p))

  const omwThrough = (p: string): number => {
    const omws: number[] = []
    for (let wk = 1; wk <= throughWeek; wk++) {
      const weekData = perWeekOmw[String(wk)]
      if (weekData && p in weekData) omws.push(weekData[p])
    }
    return omws.length > 0 ? omws.reduce((a, b) => a + b, 0) / omws.length : 0
  }

  const sorted = [...official].sort((a, b) => {
    const aBestN = bestNScore((weeklyScores[a] ?? []).slice(0, throughWeek), bestOfN)
    const bBestN = bestNScore((weeklyScores[b] ?? []).slice(0, throughWeek), bestOfN)
    if (bBestN !== aBestN) return bBestN - aBestN
    return omwThrough(b) - omwThrough(a)
  })

  sorted.forEach((p, i) => {
    ranks[p] = i + 1
  })
  return ranks
}

/**
 * Given the already-loaded previous league's DerivedLeague, return the winner's name
 * by sorting official players with the same standings tiebreaker logic.
 */
export function getDefendingChampion(prevLeagueData: DerivedLeague): string | null {
  const unofficialSet = new Set(prevLeagueData.unofficial_players ?? [])
  const prevPlayers = prevLeagueData.players.filter(p => !unofficialSet.has(p))

  if (prevPlayers.length === 0) return null

  const regularSorted = sortStandings(
    prevPlayers,
    prevLeagueData.weekly_scores,
    prevLeagueData.overall_omw,
    prevLeagueData.overall_stats,
    [], // already filtered out unofficial above
    prevLeagueData.best_of_n
  )

  // If the previous league's playoffs were played out, the actual champion
  // is the final's winner — not the regular-season #1.
  const sorted = applyPlayoffOrdering(regularSorted, prevLeagueData.playoffs)

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
