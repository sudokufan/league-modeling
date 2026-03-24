import { apiFetch } from './client'
import type { LeaguesConfig, DerivedLeague, SimulationResults } from '@/types'

export const getLeagues = () => apiFetch<LeaguesConfig>('/leagues')
export const getLeagueData = (leagueId?: string) =>
  apiFetch<DerivedLeague>(`/league-data${leagueId ? `?league=${leagueId}` : ''}`)
export const runSimulation = (leagueId?: string) =>
  apiFetch<SimulationResults>(`/simulate${leagueId ? `?league=${leagueId}` : ''}`)
