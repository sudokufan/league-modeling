import type { DerivedLeague, LeagueInfo } from '@/types'
import { bestNScore } from './scoring'

export interface LeagueChampion {
  league: string
  player: string
}

export interface RecordCard {
  title: string
  player: string
  value: string
}

export interface CareerEntry {
  name: string
  leagues: number
  weeksPlayed: number
  nines: number
  avgWeekly: number
  bestFinish: number | null // null if no completed finishes
  totalBestN: number
}

export interface AllTimeStats {
  champions: LeagueChampion[]
  records: RecordCard[]
  careerStats: CareerEntry[]
}

interface PlayerCareer {
  leagues: number
  weeksPlayed: number
  nines: number
  weeklyScoresAll: number[]
  highestWeekly: number
  totalBestN: number
  bestWeekRank: number
  bestWeekTied: boolean
  bestFinishes: { league: string; position: number }[]
  completedFinishes: { league: string; position: number }[]
  maxAttendanceStreak: number
  maxUndefeatedStreak: number
  top4: number
  titles: number
}

function newPlayerCareer(): PlayerCareer {
  return {
    leagues: 0, weeksPlayed: 0, nines: 0,
    weeklyScoresAll: [], highestWeekly: 0, totalBestN: 0,
    bestWeekRank: 999, bestWeekTied: false,
    bestFinishes: [], completedFinishes: [],
    maxAttendanceStreak: 0, maxUndefeatedStreak: 0,
    top4: 0, titles: 0,
  }
}

function getMatchWinner(match: { player_a?: string | null; player_b?: string | null; games_a?: number | null; games_b?: number | null }): string | null {
  if (match.games_a == null || match.games_b == null) return null
  if (match.games_a > match.games_b) return match.player_a ?? null
  if (match.games_b > match.games_a) return match.player_b ?? null
  return null
}

export function computeAllTimeStats(
  leagues: DerivedLeague[],
  leagueInfos: LeagueInfo[]
): AllTimeStats {
  const sortedInfos = [...leagueInfos].sort((a, b) =>
    (a.created ?? '').localeCompare(b.created ?? '') || a.id.localeCompare(b.id)
  )

  const playerCareer = new Map<string, PlayerCareer>()
  const leagueChampions: LeagueChampion[] = []

  // Collect per-league week sequences for streak computation
  const leagueWeekSequences: { officialPlayers: Set<string>; weeklyScores: Record<string, (number | null)[]>; weeks: number }[] = []

  for (const lgInfo of sortedInfos) {
    const league = leagues.find(l => l._league_info?.id === lgInfo.id)
    if (!league) continue

    const unofficial = new Set(league.unofficial_players ?? [])
    const players = league.players
    const ws = league.weekly_scores
    const bestOfN = league.best_of_n
    const displayName = lgInfo.display_name ?? lgInfo.name
    const isCompleted = lgInfo.status === 'completed'
    const totalWeeksInLeague = Object.values(ws)[0]?.length ?? 0

    leagueWeekSequences.push({
      officialPlayers: new Set(players.filter(p => !unofficial.has(p))),
      weeklyScores: ws,
      weeks: totalWeeksInLeague,
    })

    // Compute standings for this league
    const officialPlayers = players.filter(p => !unofficial.has(p))
    const overallOmw = league.overall_omw ?? {}
    const overallStats = league.overall_stats ?? {}

    const standings = [...officialPlayers].sort((a, b) => {
      const aB = bestNScore(ws[a] ?? [], bestOfN)
      const bB = bestNScore(ws[b] ?? [], bestOfN)
      if (bB !== aB) return bB - aB
      const aT = (ws[a] ?? []).filter(s => s !== null).reduce<number>((sum, s) => sum + (s ?? 0), 0)
      const bT = (ws[b] ?? []).filter(s => s !== null).reduce<number>((sum, s) => sum + (s ?? 0), 0)
      if (bT !== aT) return bT - aT
      const aO = overallOmw[a] ?? 0
      const bO = overallOmw[b] ?? 0
      if (bO !== aO) return bO - aO
      return (overallStats[b]?.gwp ?? 0) - (overallStats[a]?.gwp ?? 0)
    })

    // Check for champion via playoffs
    const playoffs = league.playoffs
    if (playoffs?.final) {
      const champion = getMatchWinner(playoffs.final)
      if (champion) {
        leagueChampions.push({ league: displayName, player: champion })
      }
    }

    // Per-week rankings for best-week-rank stat
    for (let w = 0; w < totalWeeksInLeague; w++) {
      const weekParticipants: { player: string; score: number }[] = []
      for (const p of officialPlayers) {
        const score = ws[p]?.[w]
        if (score != null) weekParticipants.push({ player: p, score })
      }
      if (weekParticipants.length === 0) continue
      weekParticipants.sort((a, b) => b.score - a.score)
      for (const { player: p, score } of weekParticipants) {
        const rank = weekParticipants.filter(x => x.score > score).length + 1
        const tied = weekParticipants.filter(x => x.score === score).length > 1
        const pc = getOrCreate(playerCareer, p)
        if (rank < pc.bestWeekRank || (rank === pc.bestWeekRank && pc.bestWeekTied && !tied)) {
          pc.bestWeekRank = rank
          pc.bestWeekTied = tied
        }
      }
    }

    // Accumulate player stats
    for (const p of players) {
      if (unofficial.has(p)) continue
      const pc = getOrCreate(playerCareer, p)
      pc.leagues += 1
      const scores = ws[p] ?? []
      const playedScores = scores.filter((s): s is number => s !== null)
      pc.weeksPlayed += playedScores.length
      pc.nines += playedScores.filter(s => s === 9).length
      pc.weeklyScoresAll.push(...playedScores)
      if (playedScores.length > 0) {
        pc.highestWeekly = Math.max(pc.highestWeekly, Math.max(...playedScores))
      }
      pc.totalBestN += bestNScore(scores, bestOfN)

      const posIdx = standings.indexOf(p)
      if (posIdx >= 0) {
        const pos = posIdx + 1
        pc.bestFinishes.push({ league: displayName, position: pos })
        if (isCompleted) {
          pc.completedFinishes.push({ league: displayName, position: pos })
        }
      }
    }
  }

  // Attendance and undefeated streaks (carry across league boundaries)
  for (const [p, pc] of playerCareer) {
    let attendStreak = 0
    let undefStreak = 0

    for (const seq of leagueWeekSequences) {
      let scores: (number | null)[]
      if (seq.officialPlayers.has(p)) {
        scores = [...(seq.weeklyScores[p] ?? [])]
      } else {
        scores = []
      }
      while (scores.length < seq.weeks) scores.push(null)

      for (const s of scores) {
        if (s !== null) {
          attendStreak++
          pc.maxAttendanceStreak = Math.max(pc.maxAttendanceStreak, attendStreak)
        } else {
          attendStreak = 0
        }
        if (s === 9) {
          undefStreak++
          pc.maxUndefeatedStreak = Math.max(pc.maxUndefeatedStreak, undefStreak)
        } else if (s !== null) {
          undefStreak = 0
        }
      }
    }
  }

  // Compute top4 and titles
  for (const [, pc] of playerCareer) {
    pc.top4 = pc.completedFinishes.filter(f => f.position <= 4).length
    pc.titles = pc.completedFinishes.filter(f => f.position === 1).length
  }

  // Build records
  const records: RecordCard[] = []
  const allPlayers = [...playerCareer.keys()]

  function findLeaders(keyFn: (p: string) => number, minVal = 1): { leaders: string[]; val: number } {
    const bestVal = Math.max(...allPlayers.map(keyFn))
    if (bestVal < minVal) return { leaders: [], val: bestVal }
    return { leaders: allPlayers.filter(p => keyFn(p) === bestVal), val: bestVal }
  }

  let r = findLeaders(p => playerCareer.get(p)!.maxAttendanceStreak)
  if (r.leaders.length) records.push({ title: 'Longest Attendance Streak', player: r.leaders.join(', '), value: `${r.val} weeks` })

  r = findLeaders(p => playerCareer.get(p)!.maxUndefeatedStreak)
  if (r.leaders.length) records.push({ title: 'Longest Undefeated Streak', player: r.leaders.join(', '), value: `${r.val} weeks` })

  r = findLeaders(p => playerCareer.get(p)!.nines)
  if (r.leaders.length) records.push({ title: 'Most Perfect Nights (9 pts)', player: r.leaders.join(', '), value: String(r.val) })

  r = findLeaders(p => playerCareer.get(p)!.weeksPlayed)
  if (r.leaders.length) records.push({ title: 'Most Weeks Played', player: r.leaders.join(', '), value: String(r.val) })

  r = findLeaders(p => playerCareer.get(p)!.top4)
  if (r.leaders.length) records.push({ title: 'Most Top-4 Finishes', player: r.leaders.join(', '), value: String(r.val) })

  r = findLeaders(p => playerCareer.get(p)!.titles)
  if (r.leaders.length) records.push({ title: 'Most League Titles (1st Place)', player: r.leaders.join(', '), value: String(r.val) })

  // Career stats table
  const careerStats: CareerEntry[] = allPlayers
    .sort((a, b) => {
      const pcA = playerCareer.get(a)!
      const pcB = playerCareer.get(b)!
      if (pcB.totalBestN !== pcA.totalBestN) return pcB.totalBestN - pcA.totalBestN
      return pcB.weeksPlayed - pcA.weeksPlayed
    })
    .map(p => {
      const pc = playerCareer.get(p)!
      const avgWeekly = pc.weeklyScoresAll.length > 0
        ? pc.weeklyScoresAll.reduce((a, b) => a + b, 0) / pc.weeklyScoresAll.length
        : 0
      const bestFinish = pc.completedFinishes.length > 0
        ? Math.min(...pc.completedFinishes.map(f => f.position))
        : null
      return {
        name: p,
        leagues: pc.leagues,
        weeksPlayed: pc.weeksPlayed,
        nines: pc.nines,
        avgWeekly,
        bestFinish,
        totalBestN: pc.totalBestN,
      }
    })

  return { champions: leagueChampions, records, careerStats }
}

function getOrCreate(map: Map<string, PlayerCareer>, key: string): PlayerCareer {
  let val = map.get(key)
  if (!val) {
    val = newPlayerCareer()
    map.set(key, val)
  }
  return val
}
