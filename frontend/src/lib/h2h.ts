import type { DerivedLeague, LeagueInfo } from '@/types'

export interface H2HRecord {
  w: number
  l: number
  d: number
  gw: number
  gl: number
}

export interface RivalryEntry {
  p1: string
  p2: string
  w1: number
  w2: number
  d: number
  gw1: number
  gw2: number
  total: number
}

export interface HighlightCard {
  title: string
  value: string
  detail: string
}

export interface LeagueH2HSection {
  name: string
  leagueId: string
  h2h: Record<string, Record<string, H2HRecord>>
  players: string[]  // sorted by total wins
}

export interface H2HStats {
  careerMatrix: Record<string, Record<string, H2HRecord>>
  careerPlayers: string[]  // sorted by total match wins
  leagueSections: LeagueH2HSection[]
  rivalries: RivalryEntry[]
  highlights: HighlightCard[]
}

function emptyRecord(): H2HRecord {
  return { w: 0, l: 0, d: 0, gw: 0, gl: 0 }
}

function getH2H(
  matrix: Record<string, Record<string, H2HRecord>>,
  a: string,
  b: string
): H2HRecord {
  if (!matrix[a]) matrix[a] = {}
  if (!matrix[a][b]) matrix[a][b] = emptyRecord()
  return matrix[a][b]
}

export function computeH2HStats(
  leagues: DerivedLeague[],
  leagueInfos: LeagueInfo[]
): H2HStats {
  const h2hCareer: Record<string, Record<string, H2HRecord>> = {}
  const leagueSections: LeagueH2HSection[] = []
  const allPlayersSet = new Set<string>()

  for (const lgInfo of leagueInfos) {
    const league = leagues.find(l => l._league_info?.id === lgInfo.id)
    if (!league) continue
    const matches = league.matches ?? []
    if (matches.length === 0) continue

    const displayName = lgInfo.display_name ?? lgInfo.name
    const h2hLeague: Record<string, Record<string, H2HRecord>> = {}
    const leaguePlayers = new Set<string>()

    for (const m of matches) {
      const pa = m.player_a
      const pb = m.player_b
      if (!pb || pb === '' || pb === '-') continue
      const ga = m.games_a
      const gb = m.games_b

      leaguePlayers.add(pa)
      leaguePlayers.add(pb)
      allPlayersSet.add(pa)
      allPlayersSet.add(pb)

      // Game wins
      getH2H(h2hLeague, pa, pb).gw += ga
      getH2H(h2hLeague, pa, pb).gl += gb
      getH2H(h2hLeague, pb, pa).gw += gb
      getH2H(h2hLeague, pb, pa).gl += ga
      getH2H(h2hCareer, pa, pb).gw += ga
      getH2H(h2hCareer, pa, pb).gl += gb
      getH2H(h2hCareer, pb, pa).gw += gb
      getH2H(h2hCareer, pb, pa).gl += ga

      // Match result
      if (ga > gb) {
        getH2H(h2hLeague, pa, pb).w += 1
        getH2H(h2hLeague, pb, pa).l += 1
        getH2H(h2hCareer, pa, pb).w += 1
        getH2H(h2hCareer, pb, pa).l += 1
      } else if (gb > ga) {
        getH2H(h2hLeague, pb, pa).w += 1
        getH2H(h2hLeague, pa, pb).l += 1
        getH2H(h2hCareer, pb, pa).w += 1
        getH2H(h2hCareer, pa, pb).l += 1
      } else {
        getH2H(h2hLeague, pa, pb).d += 1
        getH2H(h2hLeague, pb, pa).d += 1
        getH2H(h2hCareer, pa, pb).d += 1
        getH2H(h2hCareer, pb, pa).d += 1
      }
    }

    // Sort players by total wins in this league
    const lpSorted = [...leaguePlayers].sort((a, b) => {
      const aWins = [...leaguePlayers].reduce((s, opp) => s + (h2hLeague[a]?.[opp]?.w ?? 0), 0)
      const bWins = [...leaguePlayers].reduce((s, opp) => s + (h2hLeague[b]?.[opp]?.w ?? 0), 0)
      return bWins - aWins
    })

    leagueSections.push({
      name: displayName,
      leagueId: lgInfo.id,
      h2h: h2hLeague,
      players: lpSorted,
    })
  }

  // Sort career players by total match wins
  const allPlayers = [...allPlayersSet]
  const careerPlayers = allPlayers.sort((a, b) => {
    const aWins = allPlayers.reduce((s, opp) => s + (h2hCareer[a]?.[opp]?.w ?? 0), 0)
    const bWins = allPlayers.reduce((s, opp) => s + (h2hCareer[b]?.[opp]?.w ?? 0), 0)
    return bWins - aWins
  })

  // Build rivalries
  const rivalries: RivalryEntry[] = []
  const seenPairs = new Set<string>()
  for (const p of careerPlayers) {
    for (const opp of careerPlayers) {
      if (p >= opp) continue
      const key = `${p}|${opp}`
      if (seenPairs.has(key)) continue
      seenPairs.add(key)
      const rec = h2hCareer[p]?.[opp] ?? emptyRecord()
      const total = rec.w + rec.l + rec.d
      if (total < 2) continue
      rivalries.push({
        p1: p, p2: opp,
        w1: rec.w, w2: rec.l, d: rec.d,
        gw1: rec.gw, gw2: rec.gl,
        total,
      })
    }
  }
  rivalries.sort((a, b) => b.total - a.total || Math.abs(a.w1 - a.w2) - Math.abs(b.w1 - b.w2))

  // Highlights
  const highlights: HighlightCard[] = []

  // Most played rivalry
  if (rivalries.length > 0) {
    const top = rivalries[0]
    const dStr = top.d > 0 ? `-${top.d}` : ''
    highlights.push({
      title: 'Most Played Rivalry',
      value: `${top.p1} vs ${top.p2}`,
      detail: `${top.total} matches (${top.w1}-${top.w2}${dStr})`,
    })
  }

  // Most dominant H2H
  let bestDom: { winner: string; loser: string; w: number; l: number; d: number; total: number } | null = null
  let bestDomPct = 0
  for (const r of rivalries) {
    if (r.total >= 2) {
      const pct1 = r.w1 / r.total
      const pct2 = r.w2 / r.total
      const mx = Math.max(pct1, pct2)
      if (mx > bestDomPct) {
        bestDomPct = mx
        if (pct1 >= pct2) {
          bestDom = { winner: r.p1, loser: r.p2, w: r.w1, l: r.w2, d: r.d, total: r.total }
        } else {
          bestDom = { winner: r.p2, loser: r.p1, w: r.w2, l: r.w1, d: r.d, total: r.total }
        }
      }
    }
  }
  if (bestDom && bestDom.w > bestDom.l) {
    const dStr = bestDom.d ? `-${bestDom.d}` : ''
    highlights.push({
      title: 'Most Dominant H2H',
      value: `${bestDom.winner} over ${bestDom.loser}`,
      detail: `${bestDom.w}-${bestDom.l}${dStr} (${(bestDomPct * 100).toFixed(0)}% win rate)`,
    })
  }

  // Closest rivalry
  const closest = rivalries.find(r => r.total >= 2 && Math.abs(r.w1 - r.w2) <= 1)
  if (closest) {
    const dStr = closest.d > 0 ? `-${closest.d}` : ''
    highlights.push({
      title: 'Closest Rivalry',
      value: `${closest.p1} vs ${closest.p2}`,
      detail: `${closest.w1}-${closest.w2}${dStr} in ${closest.total} matches`,
    })
  }

  // Most opponents faced
  if (careerPlayers.length > 0) {
    const oppCounts = new Map<string, number>()
    for (const p of careerPlayers) {
      const count = careerPlayers.filter(opp =>
        opp !== p && ((h2hCareer[p]?.[opp]?.w ?? 0) + (h2hCareer[p]?.[opp]?.l ?? 0) + (h2hCareer[p]?.[opp]?.d ?? 0)) > 0
      ).length
      oppCounts.set(p, count)
    }
    const mostOpps = [...oppCounts.entries()].sort((a, b) => b[1] - a[1])[0]
    if (mostOpps) {
      highlights.push({
        title: 'Most Opponents Faced',
        value: mostOpps[0],
        detail: `Played against ${mostOpps[1]} different players`,
      })
    }
  }

  // Best overall win rate (min 5 matches)
  let bestWrPlayer: string | null = null
  let bestWr = 0
  for (const p of careerPlayers) {
    const totalW = careerPlayers.reduce((s, o) => s + (h2hCareer[p]?.[o]?.w ?? 0), 0)
    const totalL = careerPlayers.reduce((s, o) => s + (h2hCareer[p]?.[o]?.l ?? 0), 0)
    const total = totalW + totalL
    if (total >= 5) {
      const wr = totalW / total
      if (wr > bestWr) {
        bestWr = wr
        bestWrPlayer = p
      }
    }
  }
  if (bestWrPlayer) {
    const totalW = careerPlayers.reduce((s, o) => s + (h2hCareer[bestWrPlayer!]?.[o]?.w ?? 0), 0)
    const totalL = careerPlayers.reduce((s, o) => s + (h2hCareer[bestWrPlayer!]?.[o]?.l ?? 0), 0)
    highlights.push({
      title: 'Best Match Win Rate',
      value: bestWrPlayer,
      detail: `${totalW}-${totalL} (${(bestWr * 100).toFixed(0)}%)`,
    })
  }

  return { careerMatrix: h2hCareer, careerPlayers, leagueSections, rivalries, highlights }
}
