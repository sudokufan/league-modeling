import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useLeagues } from "@/hooks/useLeagues";
import { useCompleteLeague } from "@/hooks/useMutations";
import NewLeagueModal from "@/components/modals/NewLeagueModal";

export default function LeagueSelector() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { data: leaguesConfig } = useLeagues();
  const { mutate: completeLeague } = useCompleteLeague();
  const [modalOpen, setModalOpen] = useState(false);

  if (!leaguesConfig || leaguesConfig.leagues.length <= 1) return null;

  const currentLeagueId =
    searchParams.get("league") ?? leaguesConfig.active_league;
  const currentLeague = leaguesConfig.leagues.find(
    (l) => l.id === currentLeagueId,
  );
  const isActive = currentLeague?.status === "active";

  function handleLeagueChange(e: React.ChangeEvent<HTMLSelectElement>) {
    navigate(`/?league=${encodeURIComponent(e.target.value)}`);
  }

  function handleComplete() {
    if (!currentLeagueId) return;
    if (
      !confirm(
        "Mark this league as completed? Simulation will no longer run for it.",
      )
    )
      return;
    completeLeague({ id: currentLeagueId });
  }

  const currentPlayers: string[] = []; // populated when league data is available in parent

  return (
    <>
      <div className="flex items-center justify-center gap-3 my-4 flex-wrap">
        <select
          value={currentLeagueId}
          onChange={handleLeagueChange}
          className="bg-[#0f3460] border border-[#e94560]/25 text-[#e0e0e0] px-3.5 py-2 rounded-lg text-[0.88em] cursor-pointer appearance-none min-w-[200px] pr-8 transition-colors hover:border-[#e94560] focus:border-[#e94560] focus:outline-none"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23888' d='M6 8L1 3h10z'/%3E%3C/svg%3E\")",
            backgroundRepeat: "no-repeat",
            backgroundPosition: "right 10px center",
          }}
        >
          {leaguesConfig.leagues.map((lg) => {
            const label = lg.display_name
              ? `${lg.name} — ${lg.display_name}`
              : lg.name;
            const statusSuffix =
              lg.status !== "active" ? ` (${lg.status})` : "";
            return (
              <option key={lg.id} value={lg.id}>
                {label}
                {statusSuffix}
              </option>
            );
          })}
        </select>

        <div className="flex gap-1.5">
          <button
            onClick={() => setModalOpen(true)}
            className="bg-transparent border border-[#0f3460] text-[#888] px-3.5 py-1.5 rounded-lg text-[0.8em] cursor-pointer transition-all tracking-[0.3px] hover:border-[#e94560] hover:text-[#e94560]"
          >
            New League
          </button>
          {isActive && (
            <button
              onClick={handleComplete}
              className="bg-transparent border border-[#f1c40f]/25 text-[#f1c40f] px-3.5 py-1.5 rounded-lg text-[0.8em] cursor-pointer transition-all tracking-[0.3px] hover:border-[#f1c40f]"
            >
              Complete Season
            </button>
          )}
        </div>
      </div>

      <NewLeagueModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        currentPlayers={currentPlayers}
      />
    </>
  );
}
