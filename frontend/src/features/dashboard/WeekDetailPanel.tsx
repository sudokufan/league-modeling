import type { DerivedLeague, Match } from '@/types'

interface WeekDetailPanelProps {
  league: DerivedLeague
  week: number
  onDelete?: () => void
  onClose: () => void
}

interface LocalRecord {
  w: number
  l: number
  d: number
  pts: number
}

export default function WeekDetailPanel({
  league,
  week,
  onDelete,
  onClose,
}: WeekDetailPanelProps) {
  const { matches, per_week_omw } = league

  const weekMatches = matches.filter((m) => m.week === week)

  // Group by round
  const roundsMap = new Map<number, Match[]>()
  for (const m of weekMatches) {
    const list = roundsMap.get(m.round) ?? []
    list.push(m)
    roundsMap.set(m.round, list)
  }
  const roundNumbers = [...roundsMap.keys()].sort((a, b) => a - b)

  // Build weekly standings from match data
  const weekPlayers = new Set<string>()
  const records: Record<string, LocalRecord> = {}

  const getRecord = (p: string): LocalRecord => {
    if (!records[p]) records[p] = { w: 0, l: 0, d: 0, pts: 0 }
    return records[p]
  }

  for (const m of weekMatches) {
    const pa = m.player_a
    const pb = m.player_b
    const ga = m.games_a
    const gb = m.games_b
    weekPlayers.add(pa)

    if (!pb) {
      // Bye
      getRecord(pa).w += 1
      getRecord(pa).pts += 3
    } else {
      weekPlayers.add(pb)
      if (ga > gb) {
        getRecord(pa).w += 1
        getRecord(pa).pts += 3
        getRecord(pb).l += 1
      } else if (gb > ga) {
        getRecord(pb).w += 1
        getRecord(pb).pts += 3
        getRecord(pa).l += 1
      } else {
        getRecord(pa).d += 1
        getRecord(pa).pts += 1
        getRecord(pb).d += 1
        getRecord(pb).pts += 1
      }
    }
  }

  const weekOmw = per_week_omw[String(week)] ?? {}

  const standingsList = [...weekPlayers].sort((a, b) => {
    const aPts = getRecord(a).pts
    const bPts = getRecord(b).pts
    if (bPts !== aPts) return bPts - aPts
    return (weekOmw[b] ?? 0) - (weekOmw[a] ?? 0)
  })

  // Sort matches within a round: byes last, then by player order
  const sortRoundMatches = (roundMatches: Match[]): Match[] => {
    return [...roundMatches].sort((a, b) => {
      const aIsBye = !a.player_b ? 1 : 0
      const bIsBye = !b.player_b ? 1 : 0
      if (aIsBye !== bIsBye) return aIsBye - bIsBye
      return 0
    })
  }

  return (
    <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-[#0f3460]">
        <h2 className="text-[#e94560] text-xl font-semibold">
          Week {week} Results
        </h2>
        <button
          onClick={onClose}
          className="text-[#888] hover:text-[#e94560] text-2xl leading-none font-light px-2"
        >
          &times;
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-6">
        {/* Rounds */}
        <div className="flex-1 space-y-4">
          {roundNumbers.map((r) => {
            const roundMatches = sortRoundMatches(roundsMap.get(r) ?? [])
            return (
              <div key={r}>
                <h4 className="text-[#888] text-sm font-semibold mb-2 uppercase tracking-wide">
                  Round {r}
                </h4>
                <div className="space-y-1">
                  {roundMatches.map((m, i) => {
                    const pa = m.player_a
                    const pb = m.player_b
                    const ga = m.games_a
                    const gb = m.games_b

                    let left: string
                    let right: string
                    let scoreDisplay: string
                    let isDraw = false

                    if (!pb) {
                      left = pa
                      right = 'BYE'
                      scoreDisplay = `${ga} - ${gb}`
                    } else if (ga > gb) {
                      left = pa
                      right = pb
                      scoreDisplay = `${ga} - ${gb}`
                    } else if (gb > ga) {
                      left = pb
                      right = pa
                      scoreDisplay = `${gb} - ${ga}`
                    } else {
                      left = pa
                      right = pb
                      scoreDisplay = `${ga} - ${gb}`
                      isDraw = true
                    }

                    return (
                      <div
                        key={i}
                        className="flex items-center gap-2 text-sm py-1"
                      >
                        <span className="text-[#f0f0f0] font-semibold min-w-[80px] text-right">
                          {left}
                        </span>
                        <span
                          className={`px-2 font-mono text-[0.85em] ${
                            isDraw ? 'text-[#ccc]' : 'text-[#2ecc71]'
                          }`}
                        >
                          {scoreDisplay}
                        </span>
                        <span className="text-[#999] min-w-[80px]">
                          {right}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>

        {/* Weekly Standings */}
        <div className="flex-1">
          <h4 className="text-[#888] text-sm font-semibold mb-2 uppercase tracking-wide">
            Standings
          </h4>
          <table className="w-full border-collapse text-[0.85em]">
            <thead>
              <tr>
                <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-1.5 text-center font-semibold">
                  #
                </th>
                <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-1.5 text-left font-semibold">
                  Player
                </th>
                <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-1.5 text-center font-semibold">
                  Record
                </th>
                <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-1.5 text-center font-semibold">
                  Pts
                </th>
                <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-1.5 text-center font-semibold">
                  OMW%
                </th>
              </tr>
            </thead>
            <tbody>
              {standingsList.map((p, idx) => {
                const rec = getRecord(p)
                const omw = weekOmw[p] ?? 0
                return (
                  <tr key={p} className="hover:bg-[rgba(233,69,96,0.06)]">
                    <td className="px-2 py-1.5 text-center border-b border-[#1a1a2e] text-[#888]">
                      {idx + 1}
                    </td>
                    <td className="px-2 py-1.5 text-left border-b border-[#1a1a2e] text-[#f0f0f0] font-semibold">
                      {p}
                    </td>
                    <td className="px-2 py-1.5 text-center border-b border-[#1a1a2e] text-[#ccc]">
                      {rec.w}-{rec.l}-{rec.d}
                    </td>
                    <td className="px-2 py-1.5 text-center border-b border-[#1a1a2e] text-[#f0f0f0] font-semibold">
                      {rec.pts}
                    </td>
                    <td className="px-2 py-1.5 text-center border-b border-[#1a1a2e] text-[#aaa]">
                      {(omw * 100).toFixed(1)}%
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {onDelete && (
        <button
          onClick={onDelete}
          className="mt-4 px-4 py-2 bg-[#e74c3c] text-white rounded hover:bg-[#c0392b] text-sm"
        >
          Delete Week {week} Data
        </button>
      )}
    </div>
  )
}
