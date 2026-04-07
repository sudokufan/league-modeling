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
  highestBestN: number
  bestWeekRank: number
  bestWeekTied: boolean
  bestFinishes: { league: string; position: number }[]
  completedFinishes: { league: string; position: number }[]
  maxAttendanceStreak: number
  maxUndefeatedStreak: number
  top4: number
  titles: number
  // Match-level stats
  matchWins: number
  matchLosses: number
  matchDraws: number
  gameWins: number
  gameLosses: number
  sweeps: number // 2-0 match wins
  matchWinStreak: number
  maxMatchWinStreak: number
  byes: number
  // Rivalry tracking
  h2h: Map<string, { wins: number; losses: number; total: number }>
}

function newPlayerCareer(): PlayerCareer {
  return {
    leagues: 0, weeksPlayed: 0, nines: 0,
    weeklyScoresAll: [], highestWeekly: 0, totalBestN: 0, highestBestN: 0,
    bestWeekRank: 999, bestWeekTied: false,
    bestFinishes: [], completedFinishes: [],
    maxAttendanceStreak: 0, maxUndefeatedStreak: 0,
    top4: 0, titles: 0,
    matchWins: 0, matchLosses: 0, matchDraws: 0,
    gameWins: 0, gameLosses: 0,
    sweeps: 0, matchWinStreak: 0, maxMatchWinStreak: 0,
    byes: 0,
    h2h: new Map(),
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
      const leagueBestN = bestNScore(scores, bestOfN)
      pc.totalBestN += leagueBestN
      pc.highestBestN = Math.max(pc.highestBestN, leagueBestN)

      const posIdx = standings.indexOf(p)
      if (posIdx >= 0) {
        const pos = posIdx + 1
        pc.bestFinishes.push({ league: displayName, position: pos })
        if (isCompleted) {
          pc.completedFinishes.push({ league: displayName, position: pos })
        }
      }
    }

    // Process matches for match-level stats
    const leagueMatches = league.matches ?? []
    // Track match results for win streak computation within this league
    const weekMatchResults = new Map<string, { week: number; round: number; result: 'W' | 'L' | 'D' }[]>()

    for (const m of leagueMatches) {
      const pa = m.player_a
      const pb = m.player_b
      const ga = m.games_a ?? 0
      const gb = m.games_b ?? 0

      if (!pb || pb === '-' || pb === '') {
        // Bye
        if (!unofficial.has(pa)) {
          const pc = getOrCreate(playerCareer, pa)
          pc.byes += 1
        }
        continue
      }

      const paOfficial = !unofficial.has(pa)
      const pbOfficial = !unofficial.has(pb)

      if (paOfficial) {
        const pc = getOrCreate(playerCareer, pa)
        pc.gameWins += ga
        pc.gameLosses += gb
        if (!weekMatchResults.has(pa)) weekMatchResults.set(pa, [])
      }
      if (pbOfficial) {
        const pc = getOrCreate(playerCareer, pb)
        pc.gameWins += gb
        pc.gameLosses += ga
        if (!weekMatchResults.has(pb)) weekMatchResults.set(pb, [])
      }

      if (ga > gb) {
        if (paOfficial) {
          const pc = getOrCreate(playerCareer, pa)
          pc.matchWins += 1
          if (ga === 2 && gb === 0) pc.sweeps += 1
          weekMatchResults.get(pa)!.push({ week: m.week, round: m.round, result: 'W' })
        }
        if (pbOfficial) {
          const pc = getOrCreate(playerCareer, pb)
          pc.matchLosses += 1
          weekMatchResults.get(pb)!.push({ week: m.week, round: m.round, result: 'L' })
        }
        // H2H
        if (paOfficial && pbOfficial) {
          const h2hA = getOrCreate(playerCareer, pa).h2h
          const recA = h2hA.get(pb) ?? { wins: 0, losses: 0, total: 0 }
          recA.wins += 1; recA.total += 1
          h2hA.set(pb, recA)
          const h2hB = getOrCreate(playerCareer, pb).h2h
          const recB = h2hB.get(pa) ?? { wins: 0, losses: 0, total: 0 }
          recB.losses += 1; recB.total += 1
          h2hB.set(pa, recB)
        }
      } else if (gb > ga) {
        if (pbOfficial) {
          const pc = getOrCreate(playerCareer, pb)
          pc.matchWins += 1
          if (gb === 2 && ga === 0) pc.sweeps += 1
          weekMatchResults.get(pb)!.push({ week: m.week, round: m.round, result: 'W' })
        }
        if (paOfficial) {
          const pc = getOrCreate(playerCareer, pa)
          pc.matchLosses += 1
          weekMatchResults.get(pa)!.push({ week: m.week, round: m.round, result: 'L' })
        }
        if (paOfficial && pbOfficial) {
          const h2hB = getOrCreate(playerCareer, pb).h2h
          const recB = h2hB.get(pa) ?? { wins: 0, losses: 0, total: 0 }
          recB.wins += 1; recB.total += 1
          h2hB.set(pa, recB)
          const h2hA = getOrCreate(playerCareer, pa).h2h
          const recA = h2hA.get(pb) ?? { wins: 0, losses: 0, total: 0 }
          recA.losses += 1; recA.total += 1
          h2hA.set(pb, recA)
        }
      } else {
        if (paOfficial) {
          const pc = getOrCreate(playerCareer, pa)
          pc.matchDraws += 1
          weekMatchResults.get(pa)!.push({ week: m.week, round: m.round, result: 'D' })
        }
        if (pbOfficial) {
          const pc = getOrCreate(playerCareer, pb)
          pc.matchDraws += 1
          weekMatchResults.get(pb)!.push({ week: m.week, round: m.round, result: 'D' })
        }
        if (paOfficial && pbOfficial) {
          const h2hA = getOrCreate(playerCareer, pa).h2h
          const recA = h2hA.get(pb) ?? { wins: 0, losses: 0, total: 0 }
          recA.total += 1
          h2hA.set(pb, recA)
          const h2hB = getOrCreate(playerCareer, pb).h2h
          const recB = h2hB.get(pa) ?? { wins: 0, losses: 0, total: 0 }
          recB.total += 1
          h2hB.set(pa, recB)
        }
      }
    }

    // Compute match win streaks per player for this league (sorted by week/round)
    for (const [p, results] of weekMatchResults) {
      results.sort((a, b) => a.week - b.week || a.round - b.round)
      const pc = playerCareer.get(p)!
      for (const r of results) {
        if (r.result === 'W') {
          pc.matchWinStreak += 1
          pc.maxMatchWinStreak = Math.max(pc.maxMatchWinStreak, pc.matchWinStreak)
        } else {
          pc.matchWinStreak = 0
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

  // Build records — only show records with a single definitive leader (no ties)
  const records: RecordCard[] = []
  const allPlayers = [...playerCareer.keys()]

  function findSoleLeader(keyFn: (p: string) => number, minVal = 1): { leader: string; val: number } | null {
    const bestVal = Math.max(...allPlayers.map(keyFn))
    if (bestVal < minVal) return null
    const leaders = allPlayers.filter(p => keyFn(p) === bestVal)
    if (leaders.length !== 1) return null
    return { leader: leaders[0], val: bestVal }
  }

  // Find sole leader for float stats (use epsilon for comparison)
  function findSoleLeaderFloat(keyFn: (p: string) => number | null): { leader: string; val: number } | null {
    const eligible = allPlayers.filter(p => keyFn(p) !== null)
    if (eligible.length === 0) return null
    const bestVal = Math.max(...eligible.map(p => keyFn(p)!))
    if (bestVal < 0.001) return null
    const leaders = eligible.filter(p => Math.abs(keyFn(p)! - bestVal) < 0.0001)
    if (leaders.length !== 1) return null
    return { leader: leaders[0], val: bestVal }
  }

  let r = findSoleLeader(p => playerCareer.get(p)!.maxAttendanceStreak)
  if (r) records.push({ title: 'Longest Attendance Streak', player: r.leader, value: `${r.val} weeks` })

  r = findSoleLeader(p => playerCareer.get(p)!.maxUndefeatedStreak)
  if (r) records.push({ title: 'Longest Undefeated Streak', player: r.leader, value: `${r.val} weeks` })

  r = findSoleLeader(p => playerCareer.get(p)!.nines)
  if (r) records.push({ title: 'Most Perfect Nights (9 pts)', player: r.leader, value: String(r.val) })

  r = findSoleLeader(p => playerCareer.get(p)!.weeksPlayed)
  if (r) records.push({ title: 'Most Weeks Played', player: r.leader, value: String(r.val) })

  r = findSoleLeader(p => playerCareer.get(p)!.top4)
  if (r) records.push({ title: 'Most Top-4 Finishes', player: r.leader, value: String(r.val) })

  r = findSoleLeader(p => playerCareer.get(p)!.titles)
  if (r) records.push({ title: 'Most League Titles (1st Place)', player: r.leader, value: String(r.val) })

  r = findSoleLeader(p => playerCareer.get(p)!.leagues)
  if (r) records.push({ title: 'Most Leagues Played', player: r.leader, value: String(r.val) })

  r = findSoleLeader(p => playerCareer.get(p)!.highestBestN)
  if (r) records.push({ title: 'Highest Points Finish', player: r.leader, value: String(r.val) })

  // Match-based records (only meaningful if we have match data)
  const hasMatchData = allPlayers.some(p => {
    const pc = playerCareer.get(p)!
    return pc.matchWins + pc.matchLosses + pc.matchDraws > 0
  })

  if (hasMatchData) {
    const MIN_MATCHES = 9 // at least 3 weeks of matches

    const rFloat = findSoleLeaderFloat(p => {
      const pc = playerCareer.get(p)!
      const total = pc.matchWins + pc.matchLosses + pc.matchDraws
      if (total < MIN_MATCHES) return null
      return (pc.matchWins + pc.matchDraws * 0.5) / total
    })
    if (rFloat) records.push({ title: 'Best Match Win Rate', player: rFloat.leader, value: `${(rFloat.val * 100).toFixed(0)}%` })

    const rFloat2 = findSoleLeaderFloat(p => {
      const pc = playerCareer.get(p)!
      const totalGames = pc.gameWins + pc.gameLosses
      if (totalGames < MIN_MATCHES * 2) return null
      return pc.gameWins / totalGames
    })
    if (rFloat2) records.push({ title: 'Best Game Win Rate', player: rFloat2.leader, value: `${(rFloat2.val * 100).toFixed(0)}%` })

    r = findSoleLeader(p => playerCareer.get(p)!.sweeps)
    if (r) records.push({ title: 'Most 2-0 Sweeps', player: r.leader, value: String(r.val) })

    r = findSoleLeader(p => playerCareer.get(p)!.maxMatchWinStreak)
    if (r) records.push({ title: 'Longest Match Win Streak', player: r.leader, value: `${r.val} matches` })

    r = findSoleLeader(p => playerCareer.get(p)!.byes)
    if (r) records.push({ title: 'Most Byes Received', player: r.leader, value: String(r.val) })

    // Biggest Rivalry — pair with most total matches, sole leader
    const pairCounts = new Map<string, { key: string; playerA: string; playerB: string; total: number }>()
    for (const [p, pc] of playerCareer) {
      for (const [opp, rec] of pc.h2h) {
        const key = [p, opp].sort().join(' vs ')
        if (!pairCounts.has(key)) {
          pairCounts.set(key, { key, playerA: p, playerB: opp, total: rec.total })
        }
      }
    }
    if (pairCounts.size > 0) {
      const pairs = [...pairCounts.values()]
      const maxTotal = Math.max(...pairs.map(p => p.total))
      const topPairs = pairs.filter(p => p.total === maxTotal)
      if (topPairs.length === 1 && maxTotal >= 3) {
        const pair = topPairs[0]
        const recA = playerCareer.get(pair.playerA)!.h2h.get(pair.playerB)!
        records.push({
          title: 'Biggest Rivalry',
          player: `${pair.playerA} vs ${pair.playerB}`,
          value: `${recA.wins}-${recA.losses} (${maxTotal} matches)`,
        })
      }
    }
  }

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
