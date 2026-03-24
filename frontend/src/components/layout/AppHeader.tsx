import type { DerivedLeague } from "@/types";
import Header from "./Header";
import LeagueSelector from "./LeagueSelector";
import Nav from "./Nav";

interface AppHeaderProps {
  league?: DerivedLeague;
}

export default function AppHeader({ league }: AppHeaderProps) {
  return (
    <div className="text-center">
      <Nav />
      {league ? (
        <Header
          leagueName={league._league_info.name}
          displayName={league._league_info.display_name}
          weeksCompleted={league.weeks_completed}
          totalWeeks={league.total_weeks}
          bestOfN={league.best_of_n}
          playoffSpots={league.playoff_spots}
          isCompleted={league._league_info.status === "completed"}
        />
      ) : (
        <h1 className="text-[1.8em] text-[#e94560] tracking-wide">
          MTG League
        </h1>
      )}
      <LeagueSelector />
    </div>
  );
}
