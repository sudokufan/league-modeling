import type { DerivedLeague } from '@/types'
import { weeklyTopN } from '@/lib/standings'

interface PlayoffRaceTableProps {
  league: DerivedLeague
}

export default function PlayoffRaceTable({ league }: PlayoffRaceTableProps) {
  const {
    players,
    unofficial_players,
    weekly_scores,
    per_week_omw,
    best_of_n,
    weeks_completed,
    total_weeks,
    playoff_spots,
  } = league

  if (playoff_spots <= 0 || weeks_completed <= 0) return null

  const officialPlayers = players.filter(
    (p) => !(unofficial_players ?? []).includes(p),
  )

  const snapshots = weeklyTopN(
    officialPlayers,
    weekly_scores,
    per_week_omw,
    best_of_n,
    weeks_completed,
    total_weeks,
    playoff_spots,
  )

  // Current standings order (last non-null snapshot) for highlighting
  const currentSnapshot = snapshots[weeks_completed - 1]

  return (
    <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
      <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
        Playoff Race
      </h2>
      <p className="text-[#888] text-[0.85em] mb-3">
        Top {playoff_spots} standings after each week.
      </p>

      <div className="overflow-x-auto">
        <table className="border-collapse text-[0.85em] whitespace-nowrap">
          <thead>
            <tr>
              <th className="px-2.5 py-1.5 border border-[#222] text-center text-[#888] font-normal w-[30px]">
                #
              </th>
              {Array.from({ length: total_weeks }, (_, i) => (
                <th
                  key={i}
                  className="px-2.5 py-1.5 border border-[#222] text-center text-[#888] font-normal min-w-[70px]"
                >
                  Wk {i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: playoff_spots }, (_, rankIdx) => {
              const rank = rankIdx + 1
              return (
                <tr key={rank}>
                  <td className="px-2.5 py-1.5 border border-[#222] text-center text-[#555] text-[0.85em]">
                    {rank}
                  </td>
                  {snapshots.map((snapshot, wIdx) => {
                    if (snapshot === null) {
                      return (
                        <td
                          key={wIdx}
                          className="px-2.5 py-1.5 border border-[#222] text-center bg-[#111]"
                        />
                      )
                    }

                    const name =
                      snapshot.length >= rank ? snapshot[rankIdx] : ''
                    const isCurrent =
                      wIdx + 1 === weeks_completed &&
                      currentSnapshot &&
                      currentSnapshot.length >= rank &&
                      name === currentSnapshot[rankIdx]

                    return (
                      <td
                        key={wIdx}
                        className={`px-2.5 py-1.5 border border-[#222] text-center ${
                          isCurrent
                            ? 'text-[#2ecc71] font-bold'
                            : 'text-[#ccc]'
                        }`}
                      >
                        {name}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
