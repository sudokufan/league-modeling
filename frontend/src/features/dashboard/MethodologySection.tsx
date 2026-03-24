import type { DerivedLeague } from '@/types'

interface MethodologySectionProps {
  league: DerivedLeague
}

export default function MethodologySection({ league }: MethodologySectionProps) {
  const isCompleted = league._league_info.status === 'completed'
  if (isCompleted) return null

  const remaining = league.total_weeks - league.weeks_completed
  const { best_of_n, total_weeks, playoff_spots, num_simulations } = league

  return (
    <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
      <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
        Methodology
      </h2>
      <div className="text-sm text-[#999] leading-relaxed">
        <p>
          This model runs {num_simulations.toLocaleString()} Monte Carlo simulations of the
          remaining {remaining} week{remaining !== 1 ? 's' : ''}. Each simulation models player
          attendance based on historical patterns (core players at 100%, occasional players at 20%),
          random 1v1 pairings with bye handling for odd player counts, and match outcomes weighted by
          Bayesian-regressed historical match win percentages. The global draw rate is set at 5%
          based on observed data.
        </p>
        <p className="mt-3">
          Final standings use best-{best_of_n}-of-{total_weeks} scoring, with ties broken by total
          match points, then Opponent Match Win percentage (OMW%), then game win percentage. OMW% is
          computed per-week as the average of each opponent&#39;s match win percentage (floored at
          33.3%), then averaged across all weeks played. A player is marked &ldquo;CLINCHED&rdquo; if
          their minimum guaranteed best-{best_of_n} exceeds the maximum possible best-{best_of_n} of
          enough opponents, and &ldquo;ELIMINATED&rdquo; if their maximum possible best-{best_of_n}{' '}
          cannot reach the minimum guaranteed of enough opponents to break into the
          top {playoff_spots}.
        </p>
      </div>
    </div>
  )
}
