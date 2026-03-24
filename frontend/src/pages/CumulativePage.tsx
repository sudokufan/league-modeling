import { useMemo } from 'react'
import AppHeader from '@/components/layout/AppHeader'
import { useAllLeaguesData } from '@/hooks/useAllLeagues'
import { computeCumulativeStandings } from '@/lib/cumulative'

export default function CumulativePage() {
  const { data, isLoading, error } = useAllLeaguesData()

  const year = 2026

  const yearLeagues = useMemo(() => {
    if (!data) return []
    return data.leagues.filter(
      (lg) => lg._league_info.created?.startsWith(String(year))
    )
  }, [data])

  const standings = useMemo(() => {
    if (yearLeagues.length === 0) return []
    return computeCumulativeStandings(yearLeagues)
  }, [yearLeagues])

  // Collect ordered league columns from the filtered leagues
  const leagueColumns = useMemo(() => {
    return yearLeagues.map((lg) => ({
      id: lg._league_info.id,
      displayName: lg._league_info.display_name ?? lg._league_info.name,
      status: lg._league_info.status,
    }))
  }, [yearLeagues])

  const hasUnofficial = standings.some((p) => p.isUnofficial)

  if (isLoading) {
    return (
      <div className="w-full">
        <AppHeader />
        <div className="text-center text-[#888] py-12">Loading...</div>
      </div>
    )
  }

  if (error) {
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

      <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
        <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
          Cumulative Standings
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[0.88em]">
            <thead>
              <tr>
                <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider w-[30px]">
                  #
                </th>
                <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-left text-[0.82em] uppercase tracking-wider">
                  Player
                </th>
                {leagueColumns.map((col) => (
                  <th
                    key={col.id}
                    className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider"
                  >
                    {col.displayName}
                    {col.status === 'active' && (
                      <span className="text-[#888] text-[0.75em] normal-case">
                        {' '}
                        (in progress)
                      </span>
                    )}
                  </th>
                ))}
                <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider">
                  Cumulative
                </th>
                <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider">
                  Weeks
                </th>
                <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider">
                  9-pt Nights
                </th>
              </tr>
            </thead>
            <tbody>
              {standings.map((entry, idx) => (
                <tr
                  key={entry.name}
                  className={`hover:bg-[#e94560]/5 ${entry.isUnofficial ? 'opacity-45' : ''}`}
                >
                  <td className="p-2 text-center border-b border-white/[0.04] text-[#888] text-[0.85em] w-[30px]">
                    {idx + 1}
                  </td>
                  <td className="p-2 text-left font-semibold whitespace-nowrap border-b border-white/[0.04]">
                    {entry.name}
                    {entry.isUnofficial && ' *'}
                  </td>
                  {leagueColumns.map((col) => {
                    const val = entry.seasons[col.id]
                    return (
                      <td
                        key={col.id}
                        className={`p-2 text-center border-b border-white/[0.04] ${val == null ? 'text-[#555]' : ''}`}
                      >
                        {val != null ? val : '\u2014'}
                      </td>
                    )
                  })}
                  <td className="p-2 text-center border-b border-white/[0.04] text-[#2ecc71] font-bold">
                    {entry.cumulativeTotal}
                  </td>
                  <td className="p-2 text-center border-b border-white/[0.04]">
                    {entry.totalWeeksPlayed}
                  </td>
                  <td className="p-2 text-center border-b border-white/[0.04]">
                    {entry.nines}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="text-[0.8em] text-[#555] mt-2.5">
          Cumulative = sum of best-N scores from each league season.
          {hasUnofficial && (
            <>
              <br />* Unofficial participant
            </>
          )}
        </div>
      </div>
    </div>
  )
}
