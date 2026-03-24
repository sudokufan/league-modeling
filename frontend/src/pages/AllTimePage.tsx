import { useMemo, useState } from 'react'
import AppHeader from '@/components/layout/AppHeader'
import { useAllLeaguesData } from '@/hooks/useAllLeagues'
import { computeAllTimeStats } from '@/lib/alltime'
import type { CareerEntry } from '@/lib/alltime'

type SortCol = keyof Pick<
  CareerEntry,
  'leagues' | 'weeksPlayed' | 'nines' | 'avgWeekly' | 'bestFinish' | 'totalBestN'
>

const SORTABLE_COLS: { key: SortCol; label: string; defaultDir: 'asc' | 'desc' }[] = [
  { key: 'leagues', label: 'Seasons', defaultDir: 'desc' },
  { key: 'weeksPlayed', label: 'Weeks', defaultDir: 'desc' },
  { key: 'nines', label: '9-pt Nights', defaultDir: 'desc' },
  { key: 'avgWeekly', label: 'Avg/Week', defaultDir: 'desc' },
  { key: 'bestFinish', label: 'Best Finish', defaultDir: 'asc' },
]

export default function AllTimePage() {
  const { data, isLoading, error } = useAllLeaguesData()

  const stats = useMemo(() => {
    if (!data) return null
    return computeAllTimeStats(data.leagues, data.leagueInfos)
  }, [data])

  const [sortCol, setSortCol] = useState<SortCol | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const sortedCareer = useMemo(() => {
    if (!stats) return []
    if (!sortCol) return stats.careerStats
    return [...stats.careerStats].sort((a, b) => {
      const av = a[sortCol] ?? 999
      const bv = b[sortCol] ?? 999
      return sortDir === 'asc'
        ? (av as number) - (bv as number)
        : (bv as number) - (av as number)
    })
  }, [stats, sortCol, sortDir])

  function handleSort(col: SortCol, defaultDir: 'asc' | 'desc') {
    if (sortCol === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortCol(col)
      setSortDir(defaultDir)
    }
  }

  function sortIndicator(col: SortCol) {
    if (sortCol !== col) return ''
    return sortDir === 'asc' ? ' \u25B2' : ' \u25BC'
  }

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

      {/* League Champions */}
      {stats.champions.length > 0 && (
        <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
          <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
            League Champions
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[0.88em]">
              <thead>
                <tr>
                  <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-left text-[0.82em] uppercase tracking-wider">
                    Season
                  </th>
                  <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-left text-[0.82em] uppercase tracking-wider">
                    Champion
                  </th>
                </tr>
              </thead>
              <tbody>
                {stats.champions.map((c, i) => (
                  <tr key={i} className="hover:bg-[#e94560]/5">
                    <td className="p-2 text-left border-b border-white/[0.04]">
                      {c.league}
                    </td>
                    <td className="p-2 text-left font-semibold border-b border-white/[0.04]">
                      {c.player}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Records */}
      {stats.records.length > 0 && (
        <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
          <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
            Records
          </h2>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3">
            {stats.records.map((r, i) => (
              <div
                key={i}
                className="bg-[#1a1a2e] border-t-[3px] border-t-[#e94560] p-4 rounded-lg text-center"
              >
                <div className="text-[0.75em] uppercase tracking-[1px] text-[#e94560] mb-2">
                  {r.title}
                </div>
                <div className="text-[1.1em] font-bold text-[#e0e0e0] mb-1">
                  {r.player}
                </div>
                <div className="text-[1.6em] font-bold text-[#2ecc71]">
                  {r.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Career Stats */}
      <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
        <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
          Career Stats
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[0.88em]">
            <thead>
              <tr>
                <th className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-left text-[0.82em] uppercase tracking-wider">
                  Player
                </th>
                {SORTABLE_COLS.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key, col.defaultDir)}
                    className="bg-[#0f3460] text-[#e0e0e0] p-2.5 text-center text-[0.82em] uppercase tracking-wider cursor-pointer select-none hover:bg-[#153a72]"
                  >
                    {col.label}
                    {sortIndicator(col.key)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedCareer.map((entry) => (
                <tr key={entry.name} className="hover:bg-[#e94560]/5">
                  <td className="p-2 text-left font-semibold whitespace-nowrap border-b border-white/[0.04]">
                    {entry.name}
                  </td>
                  <td className="p-2 text-center border-b border-white/[0.04]">
                    {entry.leagues}
                  </td>
                  <td className="p-2 text-center border-b border-white/[0.04]">
                    {entry.weeksPlayed}
                  </td>
                  <td className="p-2 text-center border-b border-white/[0.04]">
                    {entry.nines}
                  </td>
                  <td className="p-2 text-center border-b border-white/[0.04]">
                    {entry.avgWeekly.toFixed(1)}
                  </td>
                  <td className="p-2 text-center border-b border-white/[0.04]">
                    {entry.bestFinish != null ? entry.bestFinish : '\u2014'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
