import { useMemo } from 'react'
import AppHeader from '@/components/layout/AppHeader'
import { useAllLeaguesData } from '@/hooks/useAllLeagues'
import { computeH2HStats } from '@/lib/h2h'
import type { H2HRecord, RivalryEntry } from '@/lib/h2h'

interface H2HMatrixProps {
  players: string[]
  h2h: Record<string, Record<string, H2HRecord>>
  showGames?: boolean
}

function H2HMatrix({ players, h2h, showGames }: H2HMatrixProps) {
  return (
    <div className="overflow-x-auto">
      <table className="border-collapse text-[0.85em] min-w-full w-auto">
        <thead>
          <tr>
            <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider min-w-[100px]" />
            {players.map((p) => (
              <th
                key={p}
                title={p}
                className="bg-[#0f3460] text-[#e0e0e0] text-[0.72em] [writing-mode:vertical-lr] [text-orientation:mixed] rotate-180 py-3 px-1 min-w-[36px] whitespace-nowrap"
              >
                {p.length > 8 ? p.slice(0, 8) : p}
              </th>
            ))}
            <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.72em] [writing-mode:vertical-lr] [text-orientation:mixed] rotate-180 py-3 px-1 min-w-[36px] whitespace-nowrap border-l-2 border-l-[#0f3460]">
              W-L-D
            </th>
          </tr>
        </thead>
        <tbody>
          {players.map((p) => {
            let totalW = 0
            let totalL = 0
            let totalD = 0
            return (
              <tr key={p} className="hover:bg-[#e94560]/5">
                <td className="text-left font-semibold whitespace-nowrap pr-3 sticky left-0 bg-[#16213e] z-[1] p-1.5 border-b border-white/[0.04]">
                  {p}
                </td>
                {players.map((opp) => {
                  if (p === opp) {
                    return (
                      <td
                        key={opp}
                        className="bg-[#0a0a1a] p-1.5 border-b border-white/[0.04]"
                      />
                    )
                  }
                  const rec = h2h[p]?.[opp]
                  const w = rec?.w ?? 0
                  const l = rec?.l ?? 0
                  const d = rec?.d ?? 0
                  totalW += w
                  totalL += l
                  totalD += d
                  const total = w + l + d

                  if (total === 0) {
                    return (
                      <td
                        key={opp}
                        className="text-center text-[#555] text-[0.85em] whitespace-nowrap min-w-[44px] p-1.5 border-b border-white/[0.04]"
                      >
                        -
                      </td>
                    )
                  }

                  let colorClass = ''
                  if (w > l) colorClass = 'text-[#2ecc71] font-semibold'
                  else if (l > w) colorClass = 'text-[#e74c3c]'
                  else colorClass = 'text-[#f1c40f]'

                  let recordStr = `${w}-${l}`
                  if (d > 0) recordStr += `-${d}`

                  return (
                    <td
                      key={opp}
                      className={`text-center text-[0.85em] whitespace-nowrap min-w-[44px] p-1.5 border-b border-white/[0.04] ${colorClass}`}
                    >
                      {recordStr}
                      {showGames && (
                        <span className="block text-[0.75em] text-[#555] font-normal">
                          ({rec?.gw ?? 0}-{rec?.gl ?? 0})
                        </span>
                      )}
                    </td>
                  )
                })}
                <td className="text-center font-semibold text-[#ccc] text-[0.85em] whitespace-nowrap min-w-[44px] p-1.5 border-b border-white/[0.04] border-l-2 border-l-[rgba(15,52,96,0.5)]">
                  {totalW}-{totalL}
                  {totalD > 0 ? `-${totalD}` : ''}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function RivalriesTable({ rivalries }: { rivalries: RivalryEntry[] }) {
  const rows = rivalries.slice(0, 20)
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[0.88em]">
        <thead>
          <tr>
            <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-left text-[0.82em] uppercase tracking-wider">
              Player 1
            </th>
            <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-left text-[0.82em] uppercase tracking-wider">
              Player 2
            </th>
            <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider">
              Match Record
            </th>
            <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider">
              Game Record
            </th>
            <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider">
              Matches
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const p1Lead = r.w1 > r.w2
            const p2Lead = r.w2 > r.w1
            let record = `${r.w1}-${r.w2}`
            if (r.d > 0) record += `-${r.d}`
            const games = `${r.gw1}-${r.gw2}`

            return (
              <tr key={i} className="hover:bg-[#e94560]/5">
                <td
                  className={`p-2 text-left font-semibold whitespace-nowrap border-b border-white/[0.04] ${p1Lead ? 'text-[#2ecc71]' : ''}`}
                >
                  {r.p1}
                </td>
                <td
                  className={`p-2 text-left font-semibold whitespace-nowrap border-b border-white/[0.04] ${p2Lead ? 'text-[#2ecc71]' : ''}`}
                >
                  {r.p2}
                </td>
                <td className="p-2 text-center border-b border-white/[0.04]">
                  {record}
                </td>
                <td className="p-2 text-center border-b border-white/[0.04]">
                  {games}
                </td>
                <td className="p-2 text-center border-b border-white/[0.04]">
                  {r.total}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="text-[0.8em] text-[#555] mt-2.5">
        Match record shows Player 1's wins-losses-draws. Game record shows
        total games won.
      </p>
    </div>
  )
}

export default function H2HPage() {
  const { data, isLoading, error } = useAllLeaguesData()

  const stats = useMemo(() => {
    if (!data) return null
    return computeH2HStats(data.leagues, data.leagueInfos)
  }, [data])

  if (isLoading) {
    return (
      <div className="w-full">
        <AppHeader />
        <div className="text-center text-[#888] py-12">Loading...</div>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="w-full">
        <AppHeader />
        <div className="text-center text-[#e74c3c] py-12">
          Failed to load league data.
        </div>
      </div>
    )
  }

  return (
    <div className="w-full">
      <AppHeader />

      {/* Highlights */}
      {stats.highlights.length > 0 && (
        <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
          <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
            Highlights
          </h2>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
            {stats.highlights.map((h, i) => (
              <div
                key={i}
                className="bg-[#1a1a2e] border-t-[3px] border-t-[#e94560] p-4 rounded-lg text-center"
              >
                <div className="text-[0.75em] uppercase tracking-[1px] text-[#e94560] mb-2">
                  {h.title}
                </div>
                <div className="text-[1em] font-bold text-[#e0e0e0] mb-1">
                  {h.value}
                </div>
                <div className="text-[0.78em] text-[#888]">{h.detail}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Career Head-to-Head */}
      <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
        <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
          Career Head-to-Head
        </h2>
        <p className="text-[0.8em] text-[#555] mb-3">
          Rows show each player's record against the column player.{' '}
          <span className="text-[#2ecc71]">Green</span> = winning record,{' '}
          <span className="text-[#e74c3c]">red</span> = losing. Game scores
          shown in parentheses.
        </p>
        <H2HMatrix
          players={stats.careerPlayers}
          h2h={stats.careerMatrix}
          showGames
        />
      </div>

      {/* All Rivalries */}
      {stats.rivalries.length > 0 && (
        <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
          <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
            All Rivalries
          </h2>
          <RivalriesTable rivalries={stats.rivalries} />
        </div>
      )}

      {/* Per-league H2H sections */}
      {stats.leagueSections.map((sec) => (
        <div
          key={sec.leagueId}
          className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6"
        >
          <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
            {sec.name}
          </h2>
          <H2HMatrix players={sec.players} h2h={sec.h2h} />
        </div>
      ))}
    </div>
  )
}
