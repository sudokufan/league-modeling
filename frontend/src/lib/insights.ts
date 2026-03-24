import type { DerivedLeague, InsightCard, Match } from '@/types'
import { bestNScore } from './scoring'

const MAX_WEEKLY_POINTS = 9

/**
 * Generate insight cards from a DerivedLeague.
 * Ported from generate_insights() in simulate.py.
 */
export function generateInsights(league: DerivedLeague): InsightCard[] {
  const insights: InsightCard[] = []

  const {
    players,
    unofficial_players,
    weekly_scores,
    overall_stats,
    overall_omw,
    weeks_completed,
    best_of_n,
    matches,
  } = league

  if (!weekly_scores || !overall_stats) return insights

  const unofficialSet = new Set(unofficial_players ?? [])
  const officialPlayers = players.filter(p => !unofficialSet.has(p))
  const omw = overall_omw ?? {}

  // Build a simple results-like object for ranking (no simulation needed)
  const ranked = [...officialPlayers].sort((a, b) => {
    const aBestN = bestNScore(weekly_scores[a] ?? [], best_of_n)
    const bBestN = bestNScore(weekly_scores[b] ?? [], best_of_n)
    if (bBestN !== aBestN) return bBestN - aBestN

    const aTmp = (weekly_scores[a] ?? []).reduce<number>((s, v) => s + (v ?? 0), 0)
    const bTmp = (weekly_scores[b] ?? []).reduce<number>((s, v) => s + (v ?? 0), 0)
    if (bTmp !== aTmp) return bTmp - aTmp

    return (omw[b] ?? 0) - (omw[a] ?? 0)
  })

  // 1. Best win rate (min 3 matches played)
  let bestWrPlayer: string | null = null
  let bestWr = 0
  for (const p of officialPlayers) {
    const s = overall_stats[p]
    if (!s) continue
    const total = s.w + s.l + s.d
    if (total >= 3) {
      const wr = (s.w + s.d * 0.5) / total
      if (wr > bestWr) {
        bestWr = wr
        bestWrPlayer = p
      }
    }
  }
  if (bestWrPlayer) {
    const s = overall_stats[bestWrPlayer]
    insights.push({
      title: 'Highest Win Rate',
      player: bestWrPlayer,
      value: `${(bestWr * 100).toFixed(0)}%`,
      detail: `${s.w}-${s.l}-${s.d} record`,
    })
  }

  // 2. Most 9-point nights
  const nineCounts: Record<string, number> = {}
  for (const p of officialPlayers) {
    const nines = (weekly_scores[p] ?? []).filter(s => s === MAX_WEEKLY_POINTS).length
    if (nines > 0) nineCounts[p] = nines
  }
  if (Object.keys(nineCounts).length > 0) {
    const topNine = Object.entries(nineCounts).sort((a, b) => b[1] - a[1])[0][0]
    insights.push({
      title: 'Most Perfect Nights',
      player: topNine,
      value: String(nineCounts[topNine]),
      detail: 'Undefeated 9-point weeks',
    })
  }

  // 3. Best attendance (Iron Player)
  const attendCounts: Record<string, number> = {}
  for (const p of officialPlayers) {
    attendCounts[p] = (weekly_scores[p] ?? []).filter(s => s !== null).length
  }
  if (Object.keys(attendCounts).length > 0) {
    const bestAttend = Object.entries(attendCounts).sort((a, b) => b[1] - a[1])[0][0]
    insights.push({
      title: 'Iron Player',
      player: bestAttend,
      value: `${attendCounts[bestAttend]}/${weeks_completed}`,
      detail: 'Weeks attended',
    })
  }

  // 4. Worst to First (min 4 weeks completed)
  if (weeks_completed >= 4) {
    const finalRank: Record<string, number> = {}
    ranked.forEach((p, i) => { finalRank[p] = i + 1 })

    const worstRank: Record<string, number> = {}
    for (const p of officialPlayers) worstRank[p] = 1

    for (let w = 1; w <= weeks_completed; w++) {
      const weekRanked = [...officialPlayers].sort((a, b) => {
        const aBn = bestNScore((weekly_scores[a] ?? []).slice(0, w), Math.min(w, best_of_n))
        const bBn = bestNScore((weekly_scores[b] ?? []).slice(0, w), Math.min(w, best_of_n))
        return bBn - aBn
      })
      weekRanked.forEach((p, i) => {
        worstRank[p] = Math.max(worstRank[p], i + 1)
      })
    }

    let bestClimb = 0
    let climber: string | null = null
    let worstAt = 0
    for (const p of officialPlayers) {
      const climb = worstRank[p] - finalRank[p]
      if (climb > bestClimb) {
        bestClimb = climb
        climber = p
        worstAt = worstRank[p]
      }
    }

    if (climber && bestClimb > 1) {
      const ordinal = (n: number): string => {
        if (n > 3) return `${n}th`
        return ['st', 'nd', 'rd'][n - 1] ? `${n}${['st', 'nd', 'rd'][n - 1]}` : `${n}th`
      }
      insights.push({
        title: 'Worst to First',
        player: climber,
        value: `+${bestClimb}`,
        detail: `Ranked ${ordinal(worstAt)} at worst → finished ${ordinal(finalRank[climber])}`,
      })
    }
  }

  // 5. Undefeated Club / Highest single week score
  const bestWeekScore = Math.max(
    0,
    ...officialPlayers.flatMap(p => (weekly_scores[p] ?? []).filter((s): s is number => s !== null))
  )
  if (bestWeekScore === MAX_WEEKLY_POINTS) {
    const ninePlayers = officialPlayers.filter(p =>
      (weekly_scores[p] ?? []).some(s => s === MAX_WEEKLY_POINTS)
    )
    if (ninePlayers.length <= 3) {
      insights.push({
        title: 'Undefeated Club',
        player: ninePlayers.join(', '),
        value: '9 pts',
        detail: 'Achieved a perfect night',
      })
    }
  }

  // 6. Almost There (2-0 then lost round 3, never had a 9-point night)
  if (matches && matches.length > 0) {
    const weeklyNinesSet = new Set(
      officialPlayers.filter(p =>
        (weekly_scores[p] ?? []).some(s => s === MAX_WEEKLY_POINTS)
      )
    )

    // round_results[player][week][round] = 'W' | 'L' | 'D'
    const roundResults: Record<string, Record<number, Record<number, string>>> = {}

    for (const m of matches as Match[]) {
      const week = m.week
      const roundNum = m.round
      const pa = m.player_a
      const pb = m.player_b
      const ga = m.games_a
      const gb = m.games_b

      if (!pb || pb === '-' || pb === '') {
        const resultA = ga === 0 && gb === 0 ? 'L' : 'W'
        if (officialPlayers.includes(pa)) {
          if (!roundResults[pa]) roundResults[pa] = {}
          if (!roundResults[pa][week]) roundResults[pa][week] = {}
          roundResults[pa][week][roundNum] = resultA
        }
        continue
      }

      let resultA: string, resultB: string
      if (ga > gb) {
        resultA = 'W'; resultB = 'L'
      } else if (gb > ga) {
        resultA = 'L'; resultB = 'W'
      } else {
        resultA = 'D'; resultB = 'D'
      }

      if (officialPlayers.includes(pa)) {
        if (!roundResults[pa]) roundResults[pa] = {}
        if (!roundResults[pa][week]) roundResults[pa][week] = {}
        roundResults[pa][week][roundNum] = resultA
      }
      if (officialPlayers.includes(pb)) {
        if (!roundResults[pb]) roundResults[pb] = {}
        if (!roundResults[pb][week]) roundResults[pb][week] = {}
        roundResults[pb][week][roundNum] = resultB
      }
    }

    const almostThereCounts: Record<string, number> = {}
    for (const p of officialPlayers) {
      if (weeklyNinesSet.has(p)) continue
      let count = 0
      const weekMap = roundResults[p] ?? {}
      for (const weekData of Object.values(weekMap)) {
        if (weekData[1] === 'W' && weekData[2] === 'W' && weekData[3] === 'L') {
          count++
        }
      }
      if (count > 0) almostThereCounts[p] = count
    }

    if (Object.keys(almostThereCounts).length > 0) {
      const topCount = Math.max(...Object.values(almostThereCounts))
      const leaders = Object.entries(almostThereCounts)
        .filter(([, count]) => count === topCount)
        .map(([p]) => p)
        .sort()
      insights.push({
        title: 'Almost There',
        player: leaders.join(', '),
        value: String(topCount),
        detail: 'Started 2-0, then lost Round 3',
      })
    }
  }

  return insights
}
