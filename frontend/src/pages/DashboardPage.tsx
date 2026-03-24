import { useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useLeagueData } from '@/hooks/useLeagueData'
import { useAddResults } from '@/hooks/useMutations'
import { getDefendingChampion } from '@/lib/standings'
import AppHeader from '@/components/layout/AppHeader'
import StandingsTable from '@/features/dashboard/StandingsTable'
import WeekDetailPanel from '@/features/dashboard/WeekDetailPanel'
import PlayoffRaceTable from '@/features/dashboard/PlayoffRaceTable'
import PlayoffProbSection from '@/features/dashboard/PlayoffProbSection'
import PlayoffBracket from '@/features/dashboard/PlayoffBracket'
import InsightsSection from '@/features/dashboard/InsightsSection'
import StandingsRaceChart from '@/features/dashboard/StandingsRaceChart'
import MethodologySection from '@/features/dashboard/MethodologySection'
import AddWeekModal from '@/components/modals/AddWeekModal'
import PlayoffModal from '@/components/modals/PlayoffModal'

export default function DashboardPage() {
  const [searchParams] = useSearchParams()
  const leagueId = searchParams.get('league') ?? undefined

  const { data: league, isLoading, error } = useLeagueData(leagueId)

  // Find previous completed league for defending champion lookup
  const prevLeagueId = useMemo(() => {
    const allLeagues = league?._all_leagues ?? []
    const currentId = league?._league_info?.id
    if (!currentId) return undefined
    const idx = allLeagues.findIndex((l) => l.id === currentId)
    for (let i = idx - 1; i >= 0; i--) {
      if (allLeagues[i].status === 'completed') return allLeagues[i].id
    }
    return undefined
  }, [league])

  const { data: prevLeague } = useLeagueData(prevLeagueId, !!prevLeagueId)
  const defendingChampion = prevLeague ? getDefendingChampion(prevLeague) : null

  // Local UI state
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null)
  const [showAddWeekModal, setShowAddWeekModal] = useState(false)
  const [showPlayoffModal, setShowPlayoffModal] = useState(false)

  const deleteWeekMutation = useAddResults(league?._league_info?.id)

  const handleWeekClick = (week: number) => {
    setSelectedWeek((prev) => (prev === week ? null : week))
  }

  const handleDeleteWeek = () => {
    if (selectedWeek == null) return
    if (!confirm(`Delete all data for Week ${selectedWeek}?`)) return
    deleteWeekMutation.mutate(
      { delete_week: selectedWeek },
      { onSuccess: () => setSelectedWeek(null) },
    )
  }

  if (isLoading) {
    return (
      <div className="w-full">
        <AppHeader />
        <div className="text-center text-[#888] py-12">Loading...</div>
      </div>
    )
  }

  if (error || !league) {
    return (
      <div className="w-full">
        <AppHeader />
        <div className="text-center text-[#e74c3c] py-12">
          Failed to load league data.
        </div>
      </div>
    )
  }

  const isActive = league._league_info.status === 'active'
  const isCompleted = league._league_info.status === 'completed'

  return (
    <div className="w-full">
      <AppHeader league={league} />

      {isCompleted && (
        <div className="bg-[#2ecc71]/10 border border-[#2ecc71]/30 rounded-xl p-4 mb-6 text-center text-[#2ecc71] font-semibold">
          This league has been completed.
        </div>
      )}

      {isActive && (
        <div className="flex justify-center mb-6">
          <button
            onClick={() => setShowAddWeekModal(true)}
            className="bg-[#e94560] text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-[#d63851] transition-colors"
          >
            Add Week Results
          </button>
        </div>
      )}

      <StandingsTable
        league={league}
        defendingChampion={defendingChampion}
        onWeekClick={handleWeekClick}
        selectedWeek={selectedWeek}
      />

      {selectedWeek != null && (
        <WeekDetailPanel
          league={league}
          week={selectedWeek}
          onClose={() => setSelectedWeek(null)}
          onDelete={isActive ? handleDeleteWeek : undefined}
        />
      )}

      <PlayoffRaceTable league={league} />

      {isActive && <PlayoffProbSection league={league} />}

      <PlayoffBracket league={league} />

      <InsightsSection league={league} />

      <StandingsRaceChart league={league} />

      <MethodologySection league={league} />

      {isActive && league.playoff_spots > 0 && (
        <div className="flex justify-center mb-6">
          <button
            onClick={() => setShowPlayoffModal(true)}
            className="bg-[#0f3460] text-[#e0e0e0] px-5 py-2.5 rounded-lg font-semibold hover:bg-[#153a72] transition-colors border border-[#e94560]/25"
          >
            Enter Playoff Results
          </button>
        </div>
      )}

      {showAddWeekModal && (
        <AddWeekModal
          isOpen={showAddWeekModal}
          onClose={() => setShowAddWeekModal(false)}
          league={league}
        />
      )}

      {showPlayoffModal && (
        <PlayoffModal
          isOpen={showPlayoffModal}
          onClose={() => setShowPlayoffModal(false)}
          league={league}
        />
      )}
    </div>
  )
}
