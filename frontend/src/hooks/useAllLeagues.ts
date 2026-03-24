import { useQuery } from '@tanstack/react-query'
import { getLeagues, getLeagueData } from '@/api/leagues'
import type { DerivedLeague, LeagueInfo } from '@/types'

export function useAllLeaguesData() {
  return useQuery({
    queryKey: ['all-leagues-data'],
    queryFn: async () => {
      const config = await getLeagues()
      const leagues: DerivedLeague[] = []
      for (const lg of config.leagues) {
        const data = await getLeagueData(lg.id)
        leagues.push(data)
      }
      return { leagues, leagueInfos: config.leagues }
    },
    staleTime: 60_000,
  })
}

export type AllLeaguesData = {
  leagues: DerivedLeague[]
  leagueInfos: LeagueInfo[]
}
