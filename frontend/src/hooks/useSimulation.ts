import { useQuery } from '@tanstack/react-query'
import { runSimulation } from '@/api/leagues'
import type { SimulationResults } from '@/types'

export function useSimulation(leagueId?: string, exclude: string[] = []) {
  const excluded = [...exclude].sort()
  return useQuery<SimulationResults>({
    queryKey: ['simulation', leagueId, excluded],
    queryFn: () => runSimulation(leagueId, excluded),
    enabled: false,
    staleTime: Infinity,
  })
}
