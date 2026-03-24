import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreateLeague } from '@/hooks/useMutations'

interface NewLeagueModalProps {
  isOpen: boolean
  onClose: () => void
  currentPlayers: string[]
}

export default function NewLeagueModal({ isOpen, onClose, currentPlayers: _currentPlayers }: NewLeagueModalProps) {
  const navigate = useNavigate()
  const { mutate: createLeague, isPending } = useCreateLeague()

  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [carryOver, setCarryOver] = useState(true)
  const [error, setError] = useState('')

  if (!isOpen) return null

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      setError('Please enter a league name')
      return
    }
    setError('')
    createLeague(
      {
        name: trimmed,
        display_name: displayName.trim() || undefined,
        carry_over_players: carryOver,
      },
      {
        onSuccess: (result) => {
          onClose()
          navigate(`/?league=${encodeURIComponent(result.id)}`)
        },
        onError: (err) => {
          setError(err instanceof Error ? err.message : 'An error occurred')
        },
      },
    )
  }

  function handleOverlayClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center"
      onClick={handleOverlayClick}
    >
      <div className="bg-[#16213e] rounded-xl p-6 w-full max-w-[450px] mx-4">
        {/* Modal header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-[1.1em] font-semibold text-[#e0e0e0]">Create New League</h2>
          <button
            className="text-[#888] hover:text-[#e0e0e0] text-xl leading-none transition-colors"
            onClick={onClose}
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        {/* Modal body */}
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-[0.85em] font-semibold text-[#ccc] mb-1.5 tracking-[0.3px]">
              Season Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. 2026 Season 2"
              className="w-full bg-[#0a0a1a] border border-[#0f3460] text-[#e0e0e0] px-3.5 py-2.5 rounded-lg text-[1em] transition-colors focus:border-[#e94560] focus:outline-none placeholder:text-[#555]"
            />
          </div>

          <div className="mb-4">
            <label className="block text-[0.85em] font-semibold text-[#ccc] mb-1.5 tracking-[0.3px]">
              League Name{' '}
              <span className="text-[#555] font-normal text-[0.85em]">(optional)</span>
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Lorwyn League"
              className="w-full bg-[#0a0a1a] border border-[#0f3460] text-[#e0e0e0] px-3.5 py-2.5 rounded-lg text-[1em] transition-colors focus:border-[#e94560] focus:outline-none placeholder:text-[#555]"
            />
          </div>

          <div className="mb-4">
            <label className="flex items-center gap-2 cursor-pointer text-[0.92em] text-[#ccc]">
              <input
                type="checkbox"
                checked={carryOver}
                onChange={(e) => setCarryOver(e.target.checked)}
                className="w-4 h-4 accent-[#e94560]"
              />
              <span>Carry over player list from current league</span>
            </label>
          </div>

          {error && (
            <div className="text-[#e74c3c] text-[0.85em] mb-4">{error}</div>
          )}

          <div className="flex gap-3 justify-end mt-5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-[0.88em] border border-[#0f3460] text-[#888] hover:text-[#e0e0e0] hover:border-[#e94560] transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="px-4 py-2 rounded-lg text-[0.88em] bg-[#e94560] text-white font-semibold hover:bg-[#c73652] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending ? 'Creating...' : 'Create League'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
