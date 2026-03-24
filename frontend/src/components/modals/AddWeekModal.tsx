import { useState, useCallback } from 'react'
import type { DerivedLeague } from '@/types'
import { useAddResults } from '@/hooks/useMutations'

interface AddWeekModalProps {
  isOpen: boolean
  onClose: () => void
  league: DerivedLeague
}

interface Matchup {
  playerA: string
  playerB: string
  gamesA: number
  gamesB: number
}

type RoundData = Matchup[]

const emptyMatchup = (): Matchup => ({
  playerA: '',
  playerB: '',
  gamesA: 0,
  gamesB: 0,
})

const inputClass =
  'bg-[#1a1a2e] border border-[#0f3460] text-[#e0e0e0] px-3 py-2 rounded-lg w-full focus:border-[#e94560] focus:outline-none'
const selectClass = inputClass
const labelClass = 'text-[#888] text-sm mb-1 block'
const btnPrimary =
  'bg-[#e94560] text-white px-4 py-2 rounded-lg font-semibold hover:bg-[#d63851] disabled:opacity-50 disabled:cursor-not-allowed'
const btnSecondary =
  'bg-[#0f3460] text-[#e0e0e0] px-4 py-2 rounded-lg hover:bg-[#153a72]'

export default function AddWeekModal({ isOpen, onClose, league }: AddWeekModalProps) {
  const [weekNumber, setWeekNumber] = useState(league.weeks_completed + 1)
  const [rounds, setRounds] = useState<RoundData[]>(() =>
    Array.from({ length: league.rounds_per_week }, () => [emptyMatchup()])
  )
  const [newPlayers, setNewPlayers] = useState<string[]>([])
  const [newPlayerInputs, setNewPlayerInputs] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  const addResultsMutation = useAddResults(league._league_info?.id)

  const allPlayers = [...league.players, ...newPlayers.filter(p => !league.players.includes(p))]

  const updateMatchup = useCallback(
    (roundIdx: number, matchIdx: number, field: keyof Matchup, value: string | number) => {
      setRounds(prev => {
        const next = prev.map(r => r.map(m => ({ ...m })))
        const matchup = next[roundIdx][matchIdx]

        // Handle "add new player" selection
        if ((field === 'playerA' || field === 'playerB') && value === '__NEW__') {
          const key = `${roundIdx}-${matchIdx}-${field}`
          setNewPlayerInputs(prev => ({ ...prev, [key]: '' }))
          return prev // don't update the matchup yet
        }

        if (field === 'gamesA' || field === 'gamesB') {
          matchup[field] = Number(value)
        } else {
          matchup[field] = value as string
        }
        return next
      })
    },
    []
  )

  const confirmNewPlayer = useCallback(
    (roundIdx: number, matchIdx: number, field: 'playerA' | 'playerB') => {
      const key = `${roundIdx}-${matchIdx}-${field}`
      const name = (newPlayerInputs[key] || '').trim()
      if (!name) return

      if (!allPlayers.includes(name)) {
        setNewPlayers(prev => [...prev, name])
      }

      setRounds(prev => {
        const next = prev.map(r => r.map(m => ({ ...m })))
        next[roundIdx][matchIdx][field] = name
        return next
      })

      setNewPlayerInputs(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
    },
    [newPlayerInputs, allPlayers]
  )

  const cancelNewPlayer = useCallback(
    (roundIdx: number, matchIdx: number, field: 'playerA' | 'playerB') => {
      const key = `${roundIdx}-${matchIdx}-${field}`
      setNewPlayerInputs(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
    },
    []
  )

  const addMatchup = useCallback((roundIdx: number) => {
    setRounds(prev => {
      const next = prev.map(r => [...r])
      next[roundIdx] = [...next[roundIdx], emptyMatchup()]
      return next
    })
  }, [])

  const removeMatchup = useCallback((roundIdx: number, matchIdx: number) => {
    setRounds(prev => {
      const next = prev.map(r => [...r])
      next[roundIdx] = next[roundIdx].filter((_, i) => i !== matchIdx)
      return next
    })
  }, [])

  const handleSubmit = useCallback(async () => {
    setError(null)

    // Build matches array
    const matches: { round: number; player_a: string; player_b: string | null; games_a: number; games_b: number }[] = []
    for (let r = 0; r < rounds.length; r++) {
      for (const m of rounds[r]) {
        if (!m.playerA) {
          setError(`Round ${r + 1}: Player A is required for all matchups`)
          return
        }
        matches.push({
          round: r + 1,
          player_a: m.playerA,
          player_b: m.playerB === 'BYE' ? null : m.playerB || null,
          games_a: m.gamesA,
          games_b: m.gamesB,
        })
      }
    }

    if (matches.length === 0) {
      setError('Please add at least one matchup')
      return
    }

    try {
      await addResultsMutation.mutateAsync({ week: weekNumber, matches })
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit results')
    }
  }, [rounds, weekNumber, addResultsMutation, onClose])

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-[#e0e0e0]">Add Week Results</h2>
          <button
            onClick={onClose}
            className="text-[#888] hover:text-[#e0e0e0] text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="mb-4">
          <label className={labelClass}>Week Number</label>
          <input
            type="number"
            min={1}
            max={league.total_weeks}
            value={weekNumber}
            onChange={e => setWeekNumber(Number(e.target.value))}
            className={`${inputClass} !w-24`}
          />
        </div>

        {rounds.map((round, roundIdx) => (
          <div key={roundIdx} className="mb-6">
            <h3 className="text-[#e0e0e0] font-semibold mb-3">Round {roundIdx + 1}</h3>
            {round.map((matchup, matchIdx) => {
              const keyA = `${roundIdx}-${matchIdx}-playerA`
              const keyB = `${roundIdx}-${matchIdx}-playerB`
              const showNewA = keyA in newPlayerInputs
              const showNewB = keyB in newPlayerInputs

              return (
                <div
                  key={matchIdx}
                  className="flex flex-wrap items-end gap-2 mb-3 p-3 bg-[#1a1a2e] rounded-lg border border-[#0f3460]/50"
                >
                  {/* Player A */}
                  <div className="flex-1 min-w-[120px]">
                    <label className={labelClass}>Player A</label>
                    {showNewA ? (
                      <div className="flex gap-1">
                        <input
                          type="text"
                          placeholder="New player name"
                          value={newPlayerInputs[keyA]}
                          onChange={e =>
                            setNewPlayerInputs(prev => ({ ...prev, [keyA]: e.target.value }))
                          }
                          onKeyDown={e => {
                            if (e.key === 'Enter') confirmNewPlayer(roundIdx, matchIdx, 'playerA')
                            if (e.key === 'Escape') cancelNewPlayer(roundIdx, matchIdx, 'playerA')
                          }}
                          className={inputClass}
                          autoFocus
                        />
                        <button
                          onClick={() => confirmNewPlayer(roundIdx, matchIdx, 'playerA')}
                          className="bg-[#e94560] text-white px-2 rounded-lg text-sm"
                        >
                          OK
                        </button>
                        <button
                          onClick={() => cancelNewPlayer(roundIdx, matchIdx, 'playerA')}
                          className="text-[#888] px-1 text-sm"
                        >
                          X
                        </button>
                      </div>
                    ) : (
                      <select
                        value={matchup.playerA}
                        onChange={e => updateMatchup(roundIdx, matchIdx, 'playerA', e.target.value)}
                        className={selectClass}
                      >
                        <option value="">-- Select --</option>
                        {allPlayers.map(p => (
                          <option key={p} value={p}>{p}</option>
                        ))}
                        <option value="__NEW__">+ Add New Player</option>
                      </select>
                    )}
                  </div>

                  {/* Player B */}
                  <div className="flex-1 min-w-[120px]">
                    <label className={labelClass}>Player B</label>
                    {showNewB ? (
                      <div className="flex gap-1">
                        <input
                          type="text"
                          placeholder="New player name"
                          value={newPlayerInputs[keyB]}
                          onChange={e =>
                            setNewPlayerInputs(prev => ({ ...prev, [keyB]: e.target.value }))
                          }
                          onKeyDown={e => {
                            if (e.key === 'Enter') confirmNewPlayer(roundIdx, matchIdx, 'playerB')
                            if (e.key === 'Escape') cancelNewPlayer(roundIdx, matchIdx, 'playerB')
                          }}
                          className={inputClass}
                          autoFocus
                        />
                        <button
                          onClick={() => confirmNewPlayer(roundIdx, matchIdx, 'playerB')}
                          className="bg-[#e94560] text-white px-2 rounded-lg text-sm"
                        >
                          OK
                        </button>
                        <button
                          onClick={() => cancelNewPlayer(roundIdx, matchIdx, 'playerB')}
                          className="text-[#888] px-1 text-sm"
                        >
                          X
                        </button>
                      </div>
                    ) : (
                      <select
                        value={matchup.playerB}
                        onChange={e => updateMatchup(roundIdx, matchIdx, 'playerB', e.target.value)}
                        className={selectClass}
                      >
                        <option value="">-- Select --</option>
                        {allPlayers.map(p => (
                          <option key={p} value={p}>{p}</option>
                        ))}
                        <option value="BYE">BYE</option>
                        <option value="__NEW__">+ Add New Player</option>
                      </select>
                    )}
                  </div>

                  {/* Games A */}
                  <div className="w-16">
                    <label className={labelClass}>W(A)</label>
                    <input
                      type="number"
                      min={0}
                      max={2}
                      value={matchup.gamesA}
                      onChange={e => updateMatchup(roundIdx, matchIdx, 'gamesA', e.target.value)}
                      className={inputClass}
                    />
                  </div>

                  {/* Games B */}
                  <div className="w-16">
                    <label className={labelClass}>W(B)</label>
                    <input
                      type="number"
                      min={0}
                      max={2}
                      value={matchup.gamesB}
                      onChange={e => updateMatchup(roundIdx, matchIdx, 'gamesB', e.target.value)}
                      className={inputClass}
                    />
                  </div>

                  {/* Remove */}
                  <button
                    onClick={() => removeMatchup(roundIdx, matchIdx)}
                    className="text-[#888] hover:text-[#e94560] text-xl pb-2"
                    title="Remove matchup"
                  >
                    &times;
                  </button>
                </div>
              )
            })}
            <button
              onClick={() => addMatchup(roundIdx)}
              className={`${btnSecondary} text-sm mt-1`}
            >
              + Add Matchup
            </button>
          </div>
        ))}

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
            disabled={addResultsMutation.isPending}
            className={btnPrimary}
          >
            {addResultsMutation.isPending ? 'Submitting...' : 'Submit Week Results'}
          </button>
        </div>
      </div>
    </div>
  )
}
