import { useQuery } from '@tanstack/react-query'
import { getLeagues } from '@/api/leagues'
import type { LeaguesConfig } from '@/types'

export function useLeagues() {
  return useQuery<LeaguesConfig>({
    queryKey: ['leagues'],
    queryFn: getLeagues,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}
