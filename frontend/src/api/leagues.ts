import { apiFetch } from './client'
import type { LeaguesConfig, DerivedLeague, SimulationResults } from '@/types'

export const getLeagues = () => apiFetch<LeaguesConfig>('/leagues')
export const getLeagueData = (leagueId?: string) =>
  apiFetch<DerivedLeague>(`/league-data${leagueId ? `?league=${leagueId}` : ''}`)
export const runSimulation = (leagueId?: string, exclude?: string[]) => {
  const params = new URLSearchParams()
  if (leagueId) params.set('league', leagueId)
  if (exclude?.length) params.set('exclude', exclude.join(','))
  const query = params.toString()
  return apiFetch<SimulationResults>(`/simulate${query ? `?${query}` : ''}`)
}
