import type { DerivedLeague } from '@/types'
import { generateInsights } from '@/lib/insights'

interface InsightsSectionProps {
  league: DerivedLeague
}

export default function InsightsSection({ league }: InsightsSectionProps) {
  const insights = generateInsights(league)

  if (insights.length === 0) return null

  return (
    <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
      <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
        Key Insights
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {insights.map((ins) => (
          <div
            key={ins.title}
            className="bg-[#1a1a2e] border-t-[3px] border-t-[#e94560] p-4 rounded-lg text-center"
          >
            <div className="text-[0.75em] uppercase tracking-widest text-[#e94560] mb-2">
              {ins.title}
            </div>
            <div className="text-lg font-bold mb-1">{ins.player}</div>
            <div className="text-2xl font-bold text-[#2ecc71] mb-1">{ins.value}</div>
            <div className="text-xs text-[#888]">{ins.detail}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
