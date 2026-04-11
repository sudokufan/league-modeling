import type { DerivedLeague, PlayerSimResult, PlayoffMatch } from '@/types'
import { sortStandings } from '@/lib/standings'

interface PlayoffBracketProps {
  league: DerivedLeague
  simulationResults?: Record<string, PlayerSimResult>
}

function getSeeds(league: DerivedLeague): string[] {
  return sortStandings(
    league.players,
    league.weekly_scores,
    league.overall_omw,
    league.overall_stats,
    league.unofficial_players ?? [],
    league.best_of_n
  )
}

function getWinner(match?: PlayoffMatch | null): string | null {
  if (!match || match.games_a == null || match.games_b == null) return null
  if (!match.player_a || !match.player_b) return null
  if (match.games_a > match.games_b) return match.player_a
  if (match.games_b > match.games_a) return match.player_b
  return null
}

function getLoser(match?: PlayoffMatch | null): string | null {
  if (!match || match.games_a == null || match.games_b == null) return null
  if (!match.player_a || !match.player_b) return null
  if (match.games_a > match.games_b) return match.player_b
  if (match.games_b > match.games_a) return match.player_a
  return null
}

function SlotRow({
  name,
  seed,
  score,
  isWinner,
  isLoser,
}: {
  name?: string | null
  seed?: number
  score?: number | null
  isWinner: boolean
  isLoser: boolean
}) {
  const cls = isWinner
    ? 'bg-[#1a3a2e] border-l-2 border-l-[#2ecc71]'
    : isLoser
      ? 'opacity-50'
      : ''

  return (
    <div className={`flex items-center justify-between px-3 py-2 bg-[#1a1a2e] ${cls}`}>
      <div className="flex items-center gap-2">
        {seed != null && (
          <span className="text-xs text-[#888] font-mono w-4">{seed}</span>
        )}
        <span className={`text-sm ${isWinner ? 'font-bold' : ''}`}>
          {name || 'TBD'}
        </span>
      </div>
      {score != null && (
        <span className="text-sm font-mono text-[#888]">{score}</span>
      )}
    </div>
  )
}

function MatchBlock({
  label,
  match,
  seedMap,
}: {
  label: string
  match: PlayoffMatch
  seedMap: Record<string, number>
}) {
  const winner = getWinner(match)
  const hasScores = match.games_a != null && match.games_b != null

  return (
    <div className="mb-4">
      <div className="text-[10px] uppercase tracking-wider text-[#888] mb-1">
        {label}
      </div>
      <div className="border border-[#0f3460] rounded overflow-hidden divide-y divide-[#0f3460]">
        <SlotRow
          name={match.player_a}
          seed={match.player_a ? seedMap[match.player_a] : undefined}
          score={hasScores ? match.games_a : undefined}
          isWinner={winner === match.player_a}
          isLoser={hasScores && winner != null && winner !== match.player_a}
        />
        <SlotRow
          name={match.player_b}
          seed={match.player_b ? seedMap[match.player_b] : undefined}
          score={hasScores ? match.games_b : undefined}
          isWinner={winner === match.player_b}
          isLoser={hasScores && winner != null && winner !== match.player_b}
        />
      </div>
    </div>
  )
}

export default function PlayoffBracket({ league }: PlayoffBracketProps) {
  if (league.playoff_spots < 4) return null

  const seeds = getSeeds(league)
  const topSeeds = seeds.slice(0, league.playoff_spots)
  const seedMap: Record<string, number> = {}
  topSeeds.forEach((p, i) => { seedMap[p] = i + 1 })

  const isProjected = league.weeks_completed < league.total_weeks
  const hasPlayoffData = league.playoffs != null

  // Build bracket data
  let sf1: PlayoffMatch
  let sf2: PlayoffMatch
  let final_match: PlayoffMatch
  let third_match: PlayoffMatch

  if (hasPlayoffData && league.playoffs) {
    sf1 = league.playoffs.semifinal_1
    sf2 = league.playoffs.semifinal_2
    final_match = league.playoffs.final ?? { player_a: null, player_b: null }
    third_match = league.playoffs.third_place ?? { player_a: null, player_b: null }
  } else {
    // Projected bracket from seeds: 1v4, 2v3
    sf1 = { player_a: topSeeds[0] ?? null, player_b: topSeeds[3] ?? null }
    sf2 = { player_a: topSeeds[1] ?? null, player_b: topSeeds[2] ?? null }
    final_match = {
      player_a: getWinner(sf1),
      player_b: getWinner(sf2),
    }
    third_match = {
      player_a: getLoser(sf1),
      player_b: getLoser(sf2),
    }
  }

  const champion = getWinner(final_match)
  const thirdWinner = getWinner(third_match)
  const thirdLoser = getLoser(third_match)

  const title = isProjected ? 'Playoff Bracket (Projected)' : 'Playoff Bracket'

  return (
    <div className={`bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6 ${isProjected ? 'opacity-90' : ''}`}>
      <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
        {title}
      </h2>

      {champion && (
        <div className="text-center mb-6">
          <div className="text-3xl mb-1">&#127942;</div>
          <div className="text-xl font-bold text-[#f1c40f]">{champion}</div>
          <div className="text-xs uppercase tracking-widest text-[#888]">League Champion</div>
        </div>
      )}

      <div className="flex flex-col md:flex-row items-start md:items-center gap-4 md:gap-0">
        {/* Semifinals */}
        <div className="flex-1 w-full md:w-auto">
          <MatchBlock label="Semifinal 1 (1 vs 4)" match={sf1} seedMap={seedMap} />
          <MatchBlock label="Semifinal 2 (2 vs 3)" match={sf2} seedMap={seedMap} />
        </div>

        {/* Connectors - hidden on mobile */}
        <div className="hidden md:flex flex-col items-center w-12 self-stretch justify-center">
          <div className="border-l-2 border-[#0f3460] h-8" />
          <div className="border-t-2 border-[#0f3460] w-full" />
          <div className="border-l-2 border-[#0f3460] h-8" />
        </div>

        {/* Final */}
        <div className="flex-1 w-full md:w-auto">
          <MatchBlock label="Final" match={final_match} seedMap={seedMap} />
        </div>
      </div>

      {/* Third place */}
      <div className="mt-4 pt-4 border-t border-[#0f3460]">
        <MatchBlock label="Third Place Match" match={third_match} seedMap={seedMap} />
        {thirdWinner && thirdLoser && (
          <div className="text-xs text-[#888] text-center">
            {thirdWinner} (3rd) / {thirdLoser} (4th)
          </div>
        )}
      </div>
    </div>
  )
}
