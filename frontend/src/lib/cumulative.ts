import type { DerivedLeague } from '@/types'
import { bestNScore, totalMatchPoints } from './scoring'

const MAX_WEEKLY_POINTS = 9

export interface CumulativeLeagueDetail {
  leagueId: string
  displayName: string
  bestN: number
  weeksPlayed: number
  status: 'active' | 'completed'
}

export interface CumulativePlayerEntry {
  name: string
  /** leagueId -> bestN score (null if player didn't participate) */
  seasons: Record<string, number | null>
  cumulativeTotal: number
  totalWeeksPlayed: number
  totalMatchPts: number
  nines: number
  isUnofficial: boolean
  leagueDetails: CumulativeLeagueDetail[]
}

/**
 * Aggregate best-N scores across all provided leagues for a given year.
 * Ported from generate_cumulative_page() in simulate.py.
 *
 * leagues should already be filtered to the desired year by the caller.
 */
export function computeCumulativeStandings(leagues: DerivedLeague[]): CumulativePlayerEntry[] {
  const allUnofficial = new Set<string>()
  const playerTotals: Record<string, {
    bestNTotal: number
    leaguesPlayed: number
    totalWeeksPlayed: number
    totalMatchPts: number
    nines: number
    leagueDetails: CumulativeLeagueDetail[]
    seasons: Record<string, number | null>
  }> = {}

  for (const league of leagues) {
    const unofficial = new Set(league.unofficial_players ?? [])
    for (const u of unofficial) allUnofficial.add(u)

    const leagueInfo = league._league_info
    const leagueId = leagueInfo.id
    const displayName = leagueInfo.display_name ?? leagueInfo.name
    const bestOfN = league.best_of_n

    for (const p of league.players) {
      const scores = league.weekly_scores[p] ?? []
      const bestN = bestNScore(scores, bestOfN)
      const weeksPlayed = scores.filter(s => s !== null).length
      const totalPts = totalMatchPoints(scores)
      const nines = scores.filter(s => s === MAX_WEEKLY_POINTS).length

      if (!playerTotals[p]) {
        playerTotals[p] = {
          bestNTotal: 0,
          leaguesPlayed: 0,
          totalWeeksPlayed: 0,
          totalMatchPts: 0,
          nines: 0,
          leagueDetails: [],
          seasons: {},
        }
      }

      const pt = playerTotals[p]
      pt.bestNTotal += bestN
      pt.leaguesPlayed += 1
      pt.totalWeeksPlayed += weeksPlayed
      pt.totalMatchPts += totalPts
      pt.nines += nines
      pt.seasons[leagueId] = bestN
      pt.leagueDetails.push({
        leagueId,
        displayName,
        bestN,
        weeksPlayed,
        status: leagueInfo.status,
      })
    }
  }

  // For players who didn't appear in some leagues, set seasons entry to null
  for (const league of leagues) {
    const leagueId = league._league_info.id
    for (const p of Object.keys(playerTotals)) {
      if (!(leagueId in playerTotals[p].seasons)) {
        playerTotals[p].seasons[leagueId] = null
      }
    }
  }

  // Sort: official players first (by bestNTotal desc), then unofficial (by bestNTotal desc)
  // Python: key=lambda p: (p not in all_unofficial, player_totals[p]["best_n_total"]), reverse=True
  // "p not in all_unofficial" is True (1) for official, False (0) for unofficial
  // reversed = official first, then by bestNTotal desc
  const allPlayers = Object.keys(playerTotals)
  allPlayers.sort((a, b) => {
    const aOfficial = allUnofficial.has(a) ? 0 : 1
    const bOfficial = allUnofficial.has(b) ? 0 : 1
    if (bOfficial !== aOfficial) return bOfficial - aOfficial
    return playerTotals[b].bestNTotal - playerTotals[a].bestNTotal
  })

  return allPlayers.map(name => {
    const pt = playerTotals[name]
    return {
      name,
      seasons: pt.seasons,
      cumulativeTotal: pt.bestNTotal,
      totalWeeksPlayed: pt.totalWeeksPlayed,
      totalMatchPts: pt.totalMatchPts,
      nines: pt.nines,
      isUnofficial: allUnofficial.has(name),
      leagueDetails: pt.leagueDetails,
    }
  })
}
