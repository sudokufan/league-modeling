import { useQuery } from '@tanstack/react-query'
import { getLeagueData } from '@/api/leagues'
import type { DerivedLeague } from '@/types'

export function useLeagueData(leagueId?: string, enabled = true) {
  return useQuery<DerivedLeague>({
    queryKey: ['league-data', leagueId],
    queryFn: () => getLeagueData(leagueId),
    enabled,
  })
}
