import { useState, useCallback, useMemo } from 'react'
import type { DerivedLeague } from '@/types'
import { useSavePlayoffResults } from '@/hooks/useMutations'
import type { PlayoffResultsPayload } from '@/api/mutations'

interface PlayoffModalProps {
  isOpen: boolean
  onClose: () => void
  league: DerivedLeague
}

interface MatchScores {
  gamesA: number | null
  gamesB: number | null
}

const selectClass =
  'bg-[#1a1a2e] border border-[#0f3460] text-[#e0e0e0] px-3 py-2 rounded-lg w-full focus:border-[#e94560] focus:outline-none'
const labelClass = 'text-[#888] text-sm mb-1 block'
const btnPrimary =
  'bg-[#e94560] text-white px-4 py-2 rounded-lg font-semibold hover:bg-[#d63851] disabled:opacity-50 disabled:cursor-not-allowed'
const btnSecondary =
  'bg-[#0f3460] text-[#e0e0e0] px-4 py-2 rounded-lg hover:bg-[#153a72]'

const SCORE_OPTIONS = [0, 1, 2]

function getWinnerLoser(
  gamesA: number | null,
  gamesB: number | null,
  playerA: string,
  playerB: string
): { winner: string | null; loser: string | null } {
  if (gamesA === null || gamesB === null) return { winner: null, loser: null }
  if (gamesA > gamesB) return { winner: playerA, loser: playerB }
  if (gamesB > gamesA) return { winner: playerB, loser: playerA }
  // Draw: higher seed (player A) wins
  return { winner: playerA, loser: playerB }
}

function ScoreSelect({
  value,
  onChange,
  disabled,
}: {
  value: number | null
  onChange: (v: number | null) => void
  disabled?: boolean
}) {
  return (
    <select
      value={value === null ? '' : value}
      onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))}
      disabled={disabled}
      className={`${selectClass} !w-16 text-center ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <option value="">-</option>
      {SCORE_OPTIONS.map(n => (
        <option key={n} value={n}>{n}</option>
      ))}
    </select>
  )
}

export default function PlayoffModal({ isOpen, onClose, league }: PlayoffModalProps) {
  const playoffs = league.playoffs
  const sf1PlayerA = playoffs?.semifinal_1?.player_a || 'Seed 1'
  const sf1PlayerB = playoffs?.semifinal_1?.player_b || 'Seed 4'
  const sf2PlayerA = playoffs?.semifinal_2?.player_a || 'Seed 2'
  const sf2PlayerB = playoffs?.semifinal_2?.player_b || 'Seed 3'

  // Initialize from existing playoff data if present
  const [sf1, setSf1] = useState<MatchScores>({
    gamesA: playoffs?.semifinal_1?.games_a ?? null,
    gamesB: playoffs?.semifinal_1?.games_b ?? null,
  })
  const [sf2, setSf2] = useState<MatchScores>({
    gamesA: playoffs?.semifinal_2?.games_a ?? null,
    gamesB: playoffs?.semifinal_2?.games_b ?? null,
  })
  const [final, setFinal] = useState<MatchScores>({
    gamesA: playoffs?.final?.games_a ?? null,
    gamesB: playoffs?.final?.games_b ?? null,
  })
  const [third, setThird] = useState<MatchScores>({
    gamesA: playoffs?.third_place?.games_a ?? null,
    gamesB: playoffs?.third_place?.games_b ?? null,
  })
  const [error, setError] = useState<string | null>(null)

  const mutation = useSavePlayoffResults(league._league_info?.id)

  // Compute advancement
  const sf1Result = useMemo(
    () => getWinnerLoser(sf1.gamesA, sf1.gamesB, sf1PlayerA, sf1PlayerB),
    [sf1, sf1PlayerA, sf1PlayerB]
  )
  const sf2Result = useMemo(
    () => getWinnerLoser(sf2.gamesA, sf2.gamesB, sf2PlayerA, sf2PlayerB),
    [sf2, sf2PlayerA, sf2PlayerB]
  )

  const finalPlayerA = sf1Result.winner || 'TBD'
  const finalPlayerB = sf2Result.winner || 'TBD'
  const thirdPlayerA = sf1Result.loser || 'TBD'
  const thirdPlayerB = sf2Result.loser || 'TBD'

  const semisComplete = sf1Result.winner !== null && sf2Result.winner !== null

  const handleSubmit = useCallback(async () => {
    setError(null)

    const payload: PlayoffResultsPayload = {}
    let hasData = false

    if (sf1.gamesA !== null && sf1.gamesB !== null) {
      payload.semifinal_1 = { games_a: sf1.gamesA, games_b: sf1.gamesB }
      hasData = true
    }
    if (sf2.gamesA !== null && sf2.gamesB !== null) {
      payload.semifinal_2 = { games_a: sf2.gamesA, games_b: sf2.gamesB }
      hasData = true
    }
    if (final.gamesA !== null && final.gamesB !== null) {
      if (!semisComplete) {
        setError('Both semifinals must be completed before entering the final')
        return
      }
      payload.final = { games_a: final.gamesA, games_b: final.gamesB }
      hasData = true
    }
    if (third.gamesA !== null && third.gamesB !== null) {
      if (!semisComplete) {
        setError('Both semifinals must be completed before entering the third place match')
        return
      }
      payload.third_place = { games_a: third.gamesA, games_b: third.gamesB }
      hasData = true
    }

    if (!hasData) {
      setError('Please enter at least one match result')
      return
    }

    try {
      await mutation.mutateAsync(payload)
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit playoff results')
    }
  }, [sf1, sf2, final, third, semisComplete, mutation, onClose])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-[#e0e0e0]">Enter Playoff Results</h2>
          <button
            onClick={onClose}
            className="text-[#888] hover:text-[#e0e0e0] text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Semifinal 1 */}
        <div className="mb-5 p-4 bg-[#1a1a2e] rounded-lg border border-[#0f3460]/50">
          <label className={labelClass}>
            Semifinal 1: {sf1PlayerA} vs {sf1PlayerB}
          </label>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-[#e0e0e0] font-semibold min-w-[80px]">{sf1PlayerA}</span>
            <ScoreSelect value={sf1.gamesA} onChange={v => setSf1(p => ({ ...p, gamesA: v }))} />
            <span className="text-[#888]">-</span>
            <ScoreSelect value={sf1.gamesB} onChange={v => setSf1(p => ({ ...p, gamesB: v }))} />
            <span className="text-[#e0e0e0] font-semibold min-w-[80px] text-right">{sf1PlayerB}</span>
          </div>
        </div>

        {/* Semifinal 2 */}
        <div className="mb-5 p-4 bg-[#1a1a2e] rounded-lg border border-[#0f3460]/50">
          <label className={labelClass}>
            Semifinal 2: {sf2PlayerA} vs {sf2PlayerB}
          </label>
          <div className="flex items-center gap-3 mt-2">
            <span className="text-[#e0e0e0] font-semibold min-w-[80px]">{sf2PlayerA}</span>
            <ScoreSelect value={sf2.gamesA} onChange={v => setSf2(p => ({ ...p, gamesA: v }))} />
            <span className="text-[#888]">-</span>
            <ScoreSelect value={sf2.gamesB} onChange={v => setSf2(p => ({ ...p, gamesB: v }))} />
            <span className="text-[#e0e0e0] font-semibold min-w-[80px] text-right">{sf2PlayerB}</span>
          </div>
        </div>

        {/* Final */}
        <div className="mb-5 p-4 bg-[#1a1a2e] rounded-lg border border-[#0f3460]/50">
          <label className={labelClass}>
            Final: {finalPlayerA} vs {finalPlayerB}
          </label>
          <div className="flex items-center gap-3 mt-2">
            <span className={`font-semibold min-w-[80px] ${semisComplete ? 'text-[#e0e0e0]' : 'text-[#555]'}`}>
              {finalPlayerA}
            </span>
            <ScoreSelect
              value={final.gamesA}
              onChange={v => setFinal(p => ({ ...p, gamesA: v }))}
              disabled={!semisComplete}
            />
            <span className="text-[#888]">-</span>
            <ScoreSelect
              value={final.gamesB}
              onChange={v => setFinal(p => ({ ...p, gamesB: v }))}
              disabled={!semisComplete}
            />
            <span className={`font-semibold min-w-[80px] text-right ${semisComplete ? 'text-[#e0e0e0]' : 'text-[#555]'}`}>
              {finalPlayerB}
            </span>
          </div>
        </div>

        {/* Third Place */}
        <div className="mb-5 p-4 bg-[#1a1a2e] rounded-lg border border-[#0f3460]/50">
          <label className={labelClass}>
            Third Place: {thirdPlayerA} vs {thirdPlayerB}
          </label>
          <div className="flex items-center gap-3 mt-2">
            <span className={`font-semibold min-w-[80px] ${semisComplete ? 'text-[#e0e0e0]' : 'text-[#555]'}`}>
              {thirdPlayerA}
            </span>
            <ScoreSelect
              value={third.gamesA}
              onChange={v => setThird(p => ({ ...p, gamesA: v }))}
              disabled={!semisComplete}
            />
            <span className="text-[#888]">-</span>
            <ScoreSelect
              value={third.gamesB}
              onChange={v => setThird(p => ({ ...p, gamesB: v }))}
              disabled={!semisComplete}
            />
            <span className={`font-semibold min-w-[80px] text-right ${semisComplete ? 'text-[#e0e0e0]' : 'text-[#555]'}`}>
              {thirdPlayerB}
            </span>
          </div>
        </div>

        {error && (
          <div className="text-[#e94560] text-sm mb-4 p-3 bg-[#e94560]/10 rounded-lg border border-[#e94560]/30">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-3 mt-4">
          <button onClick={onClose} className={btnSecondary}>
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={mutation.isPending}
            className={btnPrimary}
          >
            {mutation.isPending ? 'Submitting...' : 'Submit Playoff Results'}
          </button>
        </div>
      </div>
    </div>
  )
}
