import type { DerivedLeague, PlayerSimResult } from "@/types";
import { sortStandings } from "@/lib/standings";
import { bestNScore, maxPossibleBestN } from "@/lib/scoring";

interface StandingsTableProps {
  league: DerivedLeague;
  defendingChampion: string | null;
  simulationResults?: Record<string, PlayerSimResult>;
  onWeekClick?: (week: number) => void;
  selectedWeek?: number | null;
}

function scoreClass(value: number): string {
  if (value === 9) return "text-[#2ecc71] font-bold";
  if (value >= 6) return "text-[#a8d8a8]";
  if (value >= 3) return "text-[#ccc]";
  return "text-[#e74c3c]";
}

export default function StandingsTable({
  league,
  defendingChampion,
  onWeekClick,
  selectedWeek,
}: StandingsTableProps) {
  const {
    players,
    unofficial_players,
    weekly_scores,
    overall_omw,
    overall_stats,
    weeks_completed,
    total_weeks,
    best_of_n,
    playoff_spots,
    matches,
  } = league;

  const unofficialSet = new Set(unofficial_players ?? []);

  // Sort official players, then append unofficial at the end
  const officialSorted = sortStandings(
    players,
    weekly_scores,
    overall_omw,
    overall_stats,
    unofficial_players,
    best_of_n,
  );
  const unofficialSorted = players
    .filter((p) => unofficialSet.has(p))
    .sort((a, b) => {
      const aBest = bestNScore(weekly_scores[a] ?? [], best_of_n);
      const bBest = bestNScore(weekly_scores[b] ?? [], best_of_n);
      return bBest - aBest;
    });
  const allSorted = [...officialSorted, ...unofficialSorted];

  // Precompute best-N and maxPossible for all official players to determine clinch status
  const officialPlayers = players.filter((p) => !unofficialSet.has(p));
  const playerBest: Record<string, number> = {};
  const playerMax: Record<string, number> = {};
  for (const p of officialPlayers) {
    const s = weekly_scores[p] ?? [];
    playerBest[p] = bestNScore(s, best_of_n);
    playerMax[p] = maxPossibleBestN(s, weeks_completed, total_weeks, best_of_n);
  }

  // A player has clinched playoffs if fewer than playoff_spots other official
  // players could possibly reach or exceed their current best-N score
  function hasClinched(player: string): boolean {
    if (unofficialSet.has(player)) return false;
    const myBest = playerBest[player];
    const couldOvertake = officialPlayers.filter(
      (p) => p !== player && playerMax[p] >= myBest,
    ).length;
    return couldOvertake < playoff_spots;
  }

  // Which weeks have match data (clickable)
  const enteredWeeks = new Set(matches.map((m) => m.week));

  return (
    <div className="bg-[#16213e] rounded-xl p-6 border border-[#0f3460] mb-6">
      <h2 className="text-[#e94560] text-xl font-semibold mb-4 pb-2 border-b border-[#0f3460]">
        Standings
      </h2>

      <div className="overflow-x-auto -mx-1 px-1">
        <table className="w-full border-collapse text-[0.9em]">
          <thead>
            <tr>
              <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-2.5 text-center font-semibold">
                #
              </th>
              <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-2.5 text-left font-semibold">
                Player
              </th>
              {Array.from({ length: total_weeks }, (_, i) => {
                const w = i + 1;
                const isEntered = enteredWeeks.has(w);
                const isFuture = w > weeks_completed;
                const isSelected = selectedWeek === w;
                const clickable = isEntered && onWeekClick;

                return (
                  <th
                    key={w}
                    className={`bg-[#0f3460] text-[0.82em] uppercase tracking-wider px-2 py-2.5 text-center font-semibold ${
                      isFuture
                        ? "text-[#555]"
                        : clickable
                          ? `text-[#ccc] cursor-pointer hover:text-[#e94560] hover:bg-[#1a2744] ${isSelected ? "text-[#e94560] border-b-2 border-[#e94560]" : ""}`
                          : "text-[#ccc]"
                    }`}
                    onClick={clickable ? () => onWeekClick(w) : undefined}
                    title={
                      clickable ? `Click to view Week ${w} details` : undefined
                    }
                  >
                    W{w}
                  </th>
                );
              })}
              <th className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-2.5 text-center font-semibold">
                Best-{best_of_n}
              </th>
              <th
                className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-2.5 text-center font-semibold"
                title={`Best possible Best-${best_of_n} (scoring 9 every remaining week)`}
              >
                Max
              </th>
            </tr>
          </thead>
          <tbody>
            {allSorted.map((player, idx) => {
              const isUnofficial = unofficialSet.has(player);
              const rank = idx + 1;
              const isTop = !isUnofficial && rank <= playoff_spots;
              const scores = weekly_scores[player] ?? [];
              const best = bestNScore(scores, best_of_n);
              const maxPossible = maxPossibleBestN(scores, weeks_completed, total_weeks, best_of_n);
              const isChamp = player === defendingChampion;
              const clinched = isTop && hasClinched(player);

              return (
                <tr
                  key={player}
                  className={`hover:bg-[rgba(233,69,96,0.06)] ${
                    isUnofficial
                      ? "opacity-45"
                      : clinched
                        ? "bg-[rgba(46,204,113,0.18)] hover:bg-[rgba(46,204,113,0.28)]"
                        : isTop
                          ? "bg-[rgba(46,204,113,0.08)] hover:bg-[rgba(46,204,113,0.15)]"
                          : ""
                  }`}
                >
                  <td className="px-2 py-2 text-center border-b border-[#1a1a2e] font-bold text-[#888] w-10">
                    {rank}
                  </td>
                  <td
                    className={`px-2 py-2 text-left border-b border-[#1a1a2e] font-semibold whitespace-nowrap ${
                      isChamp ? "text-[#f1c40f]" : "text-[#f0f0f0]"
                    }`}
                  >
                    {player}
                    {isUnofficial ? " *" : ""}
                  </td>
                  {Array.from({ length: total_weeks }, (_, i) => {
                    const score = i < scores.length ? scores[i] : undefined;
                    const isCompleted = i < weeks_completed;

                    if (score != null) {
                      return (
                        <td
                          key={i}
                          className={`px-2 py-2 text-center border-b border-[#1a1a2e] ${scoreClass(score)}`}
                        >
                          {score}
                        </td>
                      );
                    }
                    if (isCompleted) {
                      return (
                        <td
                          key={i}
                          className="px-2 py-2 text-center border-b border-[#1a1a2e] text-[#555]"
                        >
                          -
                        </td>
                      );
                    }
                    return (
                      <td
                        key={i}
                        className="px-2 py-2 text-center border-b border-[#1a1a2e] text-[#333]"
                      />
                    );
                  })}
                  <td className="px-2 py-2 text-center border-b border-[#1a1a2e] font-bold text-[#2ecc71] text-[1.05em]">
                    {best}
                  </td>
                  <td className="px-2 py-2 text-center border-b border-[#1a1a2e] text-[#aaa] text-[0.9em]">
                    {maxPossible}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-[#888] text-[0.82em] mt-4">
        Top {playoff_spots} qualify for playoffs &middot; Best {best_of_n} of{" "}
        {total_weeks} weekly scores count
        {onWeekClick ? " \u00b7 Click a week header to view details" : ""}
      </p>
    </div>
  );
}
