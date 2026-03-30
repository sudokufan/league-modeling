import { useSimulation } from "@/hooks/useSimulation";
import type { DerivedLeague, SimPlayerResult } from "@/types";

interface PlayoffProbSectionProps {
  league: DerivedLeague;
}

function barColor(prob: number): string {
  if (prob >= 75) return "#2ecc71";
  if (prob >= 50) return "#f1c40f";
  if (prob >= 25) return "#e67e22";
  return "#e74c3c";
}

function PlayoffProbCard({ player }: { player: SimPlayerResult }) {
  const prob = player.playoff_prob;
  const color = barColor(prob);

  let badge: React.ReactNode = null;
  if (player.status === "clinched" || prob >= 99.9) {
    badge = (
      <span className="bg-[#2ecc71] text-[#1a1a2e] text-xs px-2 py-0.5 rounded font-bold uppercase">
        CLINCHED
      </span>
    );
  } else if (player.status === "eliminated" || prob === 0) {
    badge = (
      <span className="bg-[#e74c3c] text-[#1a1a2e] text-xs px-2 py-0.5 rounded font-bold uppercase">
        ELIMINATED
      </span>
    );
  }

  return (
    <div className="bg-[#1a1a2e] rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="font-bold text-lg">{player.name}</span>
        <span className="text-sm font-semibold" style={{ color }}>
          {prob.toFixed(1)}%
        </span>
      </div>
      {badge && <div className="mb-2">{badge}</div>}
      <div className="bg-[#0f3460] rounded-full h-3 mb-3 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${Math.max(prob, 0.5)}%`, background: color }}
        />
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-[#888]">
        <span>Record: {player.record}</span>
        <span>Best 7: {player.current_best7}</span>
        <span>Max: {player.max_possible}</span>
        <span>OMW%: {(player.omw * 100).toFixed(1)}%</span>
        <span>GW%: {(player.gwp * 100).toFixed(1)}%</span>
      </div>
    </div>
  );
}

export default function PlayoffProbSection({
  league,
}: PlayoffProbSectionProps) {
  const isCompleted = league._league_info.status === "completed";
  const leagueId = league._league_info.id;

  const { data, refetch, isFetching, isSuccess } = useSimulation(leagueId);

  if (isCompleted || league.playoff_spots === 0) return null;

  const sorted =
    isSuccess && data?.players
      ? [...data.players].sort((a, b) => b.playoff_prob - a.playoff_prob)
      : [];

  return (
    <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
      <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
        Predict the Playoffs
      </h2>

      {!isSuccess && !isFetching && (
        <div className="text-center">
          <button
            onClick={() => refetch()}
            className="bg-[#e94560] hover:bg-[#c73850] text-white font-semibold px-6 py-3 rounded-lg transition-colors"
          >
            Predict the Playoffs
          </button>
        </div>
      )}

      {isFetching && (
        <div className="flex items-center justify-center gap-3 py-8">
          <div className="w-5 h-5 border-2 border-[#e94560] border-t-transparent rounded-full animate-spin" />
          <span className="text-[#888]">Running simulation...</span>
        </div>
      )}

      {isSuccess && sorted.length > 0 && (
        <div className="flex flex-col gap-4">
          {sorted.map((p) => (
            <PlayoffProbCard key={p.name} player={p} />
          ))}
        </div>
      )}

      {isSuccess && data?.error && (
        <p className="text-[#e74c3c] text-center">{data.error}</p>
      )}
    </div>
  );
}
