import type { DerivedLeague, PlayerSimResult } from "@/types";
import { sortStandings, applyPlayoffOrdering, rankAllThroughWeek } from "@/lib/standings";
import { bestNScore, maxPossibleBestN } from "@/lib/scoring";

interface StandingsTableProps {
  league: DerivedLeague;
  defendingChampion: string | null;
  simulationResults?: Record<string, PlayerSimResult>;
  onWeekClick?: (week: number) => void;
  selectedWeek?: number | null;
}

function scoreClass(value: number, weekCap: number): string {
  if (value === weekCap) return "text-[#2ecc71] font-bold";
  if (value >= weekCap - 3) return "text-[#a8d8a8]";
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
    playoff_ineligible,
    weekly_scores,
    overall_omw,
    overall_stats,
    weeks_completed,
    total_weeks,
    best_of_n,
    playoff_spots,
    matches,
    rounds_per_week,
    rounds_in_week,
    per_week_omw,
  } = league;

  // Per-week cap. Falls back to the league's configured rounds_per_week when
  // a week has no entered matches (e.g., future weeks or legacy data).
  const weekCap = (weekNum: number): number => {
    const r = rounds_in_week?.[String(weekNum)] ?? rounds_per_week;
    return r * 3;
  };

  const unofficialSet = new Set(unofficial_players ?? []);
  // Ineligible players keep their earned points and standings position, but
  // can't take a playoff seat — their spot falls to the next eligible player.
  const ineligibleSet = new Set(playoff_ineligible ?? []);

  // Sort official players, then append unofficial at the end.
  // When playoffs are complete, override top-N order with the playoff finish
  // (champion, runner-up, 3rd, 4th).
  const officialSorted = applyPlayoffOrdering(
    sortStandings(
      players,
      weekly_scores,
      overall_omw,
      overall_stats,
      unofficial_players,
      best_of_n,
    ),
    league.playoffs,
  );
  const unofficialSorted = players
    .filter((p) => unofficialSet.has(p))
    .sort((a, b) => {
      const aBest = bestNScore(weekly_scores[a] ?? [], best_of_n);
      const bBest = bestNScore(weekly_scores[b] ?? [], best_of_n);
      return bBest - aBest;
    });
  const allSorted = [...officialSorted, ...unofficialSorted];

  // The players actually holding a playoff seat: the top `playoff_spots` in the
  // regular-season order, skipping anyone ineligible (whose spot drops down).
  const qualifierSet = new Set<string>();
  for (const p of officialSorted) {
    if (ineligibleSet.has(p)) continue;
    if (qualifierSet.size < playoff_spots) qualifierSet.add(p);
  }

  // Precompute best-N and maxPossible for all eligible official players to
  // determine clinch status (ineligible players don't compete for spots).
  const officialPlayers = players.filter(
    (p) => !unofficialSet.has(p) && !ineligibleSet.has(p),
  );
  const playerBest: Record<string, number> = {};
  const playerMax: Record<string, number> = {};
  for (const p of officialPlayers) {
    const s = weekly_scores[p] ?? [];
    playerBest[p] = bestNScore(s, best_of_n);
    playerMax[p] = maxPossibleBestN(s, weeks_completed, total_weeks, best_of_n, rounds_per_week);
  }

  // A player has clinched playoffs if fewer than playoff_spots other official
  // players could possibly reach or exceed their current best-N score.
  // When the season is complete, all top-N players are definitively in.
  const seasonComplete = weeks_completed >= total_weeks;
  function hasClinched(player: string): boolean {
    if (unofficialSet.has(player) || ineligibleSet.has(player)) return false;
    if (seasonComplete) return true;
    const myBest = playerBest[player];
    const couldOvertake = officialPlayers.filter(
      (p) => p !== player && playerMax[p] >= myBest,
    ).length;
    return couldOvertake < playoff_spots;
  }

  // Movement vs the previous week. Only meaningful mid-season (>= 2 weeks played)
  // and while ranking by regular-season standings (not the playoff-finish order).
  const showMovement = !seasonComplete && weeks_completed >= 2;
  const prevWeekRanks = showMovement
    ? rankAllThroughWeek(
        players,
        weekly_scores,
        per_week_omw,
        unofficial_players,
        best_of_n,
        weeks_completed - 1,
      )
    : {};

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
              {!seasonComplete && (
                <th
                  className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-2.5 text-center font-semibold"
                  title={`Best possible Best-${best_of_n} (scoring ${rounds_per_week * 3} every remaining week)`}
                >
                  Max
                </th>
              )}
              {seasonComplete && (
                <>
                  <th
                    className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-2.5 text-center font-semibold"
                    title="Opponent Match Win Percentage"
                  >
                    OMW%
                  </th>
                  <th
                    className="bg-[#0f3460] text-[#e0e0e0] text-[0.82em] uppercase tracking-wider px-2 py-2.5 text-center font-semibold"
                    title="Game Win Percentage"
                  >
                    GW%
                  </th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {allSorted.map((player, idx) => {
              const isUnofficial = unofficialSet.has(player);
              const isIneligible = ineligibleSet.has(player);
              const rank = idx + 1;
              const isTop = qualifierSet.has(player);
              const scores = weekly_scores[player] ?? [];
              const best = bestNScore(scores, best_of_n);
              const maxPossible = maxPossibleBestN(scores, weeks_completed, total_weeks, best_of_n, rounds_per_week);
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
                  <td className="px-2 py-2 text-center border-b border-[#1a1a2e] font-bold text-[#888] w-14">
                    <span className="inline-flex items-center justify-center gap-1">
                      {rank}
                      {showMovement && !isUnofficial && (() => {
                        const prev = prevWeekRanks[player];
                        if (prev == null) {
                          return (
                            <span
                              className="text-[#3498db] text-[0.78em] font-semibold"
                              title="New entry this week"
                            >
                              NEW
                            </span>
                          );
                        }
                        const delta = prev - rank; // positive = moved up
                        if (delta === 0) {
                          return (
                            <span
                              className="text-[#666] text-[0.8em]"
                              title="No change since last week"
                            >
                              &ndash;
                            </span>
                          );
                        }
                        const up = delta > 0;
                        return (
                          <span
                            className={`text-[0.78em] font-semibold ${up ? "text-[#2ecc71]" : "text-[#e74c3c]"}`}
                            title={`${up ? "Up" : "Down"} ${Math.abs(delta)} since last week (was #${prev})`}
                          >
                            {up ? "▲" : "▼"}
                            {Math.abs(delta)}
                          </span>
                        );
                      })()}
                    </span>
                  </td>
                  <td
                    className={`px-2 py-2 text-left border-b border-[#1a1a2e] font-semibold whitespace-nowrap ${
                      isChamp
                        ? "text-[#f1c40f]"
                        : isIneligible
                          ? "text-[#999]"
                          : "text-[#f0f0f0]"
                    }`}
                  >
                    {player}
                    {isUnofficial ? " *" : ""}
                    {isIneligible && (
                      <span
                        className="ml-2 text-[0.68em] uppercase tracking-wider text-[#e74c3c] border border-[#e74c3c] rounded px-1 py-0.5 align-middle"
                        title="Ineligible for the playoffs — spot passes to the next player down"
                      >
                        Ineligible
                      </span>
                    )}
                  </td>
                  {Array.from({ length: total_weeks }, (_, i) => {
                    const score = i < scores.length ? scores[i] : undefined;
                    const isCompleted = i < weeks_completed;

                    if (score != null) {
                      return (
                        <td
                          key={i}
                          className={`px-2 py-2 text-center border-b border-[#1a1a2e] ${scoreClass(score, weekCap(i + 1))}`}
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
                  {!seasonComplete && (
                    <td className="px-2 py-2 text-center border-b border-[#1a1a2e] text-[#aaa] text-[0.9em]">
                      {maxPossible}
                    </td>
                  )}
                  {seasonComplete && (
                    <>
                      <td className="px-2 py-2 text-center border-b border-[#1a1a2e] text-[#aaa] text-[0.9em]">
                        {((overall_omw[player] ?? 0) * 100).toFixed(1)}%
                      </td>
                      <td className="px-2 py-2 text-center border-b border-[#1a1a2e] text-[#aaa] text-[0.9em]">
                        {((overall_stats[player]?.gwp ?? 0) * 100).toFixed(1)}%
                      </td>
                    </>
                  )}
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
        {ineligibleSet.size > 0
          ? " \u00b7 Ineligible players keep their points but can't take a playoff seat"
          : ""}
      </p>
    </div>
  );
}
