import { useQuery } from '@tanstack/react-query'
import { runSimulation } from '@/api/leagues'
import type { SimulationResults } from '@/types'

export function useSimulation(leagueId?: string) {
  return useQuery<SimulationResults>({
    queryKey: ['simulation', leagueId],
    queryFn: () => runSimulation(leagueId),
    enabled: false,
    staleTime: Infinity,
  })
}
