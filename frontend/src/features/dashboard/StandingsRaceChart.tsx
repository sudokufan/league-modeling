import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import type { DerivedLeague } from '@/types'
import { bestNScore } from '@/lib/scoring'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const CHART_COLORS = [
  '#e94560', '#2ecc71', '#3498db', '#f1c40f', '#9b59b6',
  '#e67e22', '#1abc9c', '#e74c3c', '#00bcd4', '#ff9800',
  '#8bc34a', '#ff5722', '#607d8b', '#cddc39', '#795548',
  '#9e9e9e',
]

interface StandingsRaceChartProps {
  league: DerivedLeague
}

export default function StandingsRaceChart({ league }: StandingsRaceChartProps) {
  const { players, unofficial_players, weekly_scores, weeks_completed, best_of_n } = league

  if (weeks_completed < 2) return null

  const unofficialSet = new Set(unofficial_players ?? [])

  // Only include players who played 2+ weeks, sorted by current best-N desc
  const chartPlayers = players
    .filter((p) => !unofficialSet.has(p))
    .filter((p) => {
      const played = (weekly_scores[p] ?? []).filter((s) => s !== null).length
      return played >= 2
    })
    .sort((a, b) => {
      const aBn = bestNScore(weekly_scores[a] ?? [], best_of_n)
      const bBn = bestNScore(weekly_scores[b] ?? [], best_of_n)
      return bBn - aBn
    })

  if (chartPlayers.length === 0) return null

  const weekLabels = Array.from({ length: weeks_completed }, (_, i) => `Week ${i + 1}`)

  const datasets = chartPlayers.map((p, i) => {
    const scores = weekly_scores[p] ?? []
    const runningBest: (number | null)[] = []

    for (let w = 0; w < weeks_completed; w++) {
      const sliced = scores.slice(0, w + 1)
      const played = sliced.filter((s): s is number => s !== null)
      if (played.length > 0) {
        runningBest.push(bestNScore(sliced, best_of_n))
      } else {
        runningBest.push(null)
      }
    }

    const color = CHART_COLORS[i % CHART_COLORS.length]
    return {
      label: p,
      data: runningBest,
      borderColor: color,
      backgroundColor: color,
      tension: 0.3,
      pointRadius: 5,
      pointHoverRadius: 7,
      borderWidth: 2.5,
      spanGaps: true,
    }
  })

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: '#ccc',
          usePointStyle: true,
          padding: 16,
        },
      },
      tooltip: {
        backgroundColor: '#1a1a2e',
        titleColor: '#e94560',
        bodyColor: '#ccc',
        borderColor: '#0f3460',
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        ticks: { color: '#888' },
        grid: { color: 'rgba(15,52,96,0.4)' },
      },
      y: {
        ticks: { color: '#888' },
        grid: { color: 'rgba(15,52,96,0.4)' },
        title: {
          display: true,
          text: `Best-${best_of_n} Score`,
          color: '#888',
        },
      },
    },
  }

  return (
    <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
      <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
        Standings Race
      </h2>
      <div style={{ height: 400 }}>
        <Line data={{ labels: weekLabels, datasets }} options={options} />
      </div>
    </div>
  )
}
