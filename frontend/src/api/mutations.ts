import { apiFetch } from './client'
import type { Match, PlayoffMatch, MutationResponse, CreateLeagueResponse } from '@/types'

// POST /api/add-results
export interface AddResultsPayload {
  week: number
  matches: Omit<Match, 'week'>[]
}

export interface DeleteWeekPayload {
  delete_week: number
}

export const addResults = (
  payload: AddResultsPayload | DeleteWeekPayload,
  leagueId?: string,
) =>
  apiFetch<MutationResponse>(
    `/add-results${leagueId ? `?league=${leagueId}` : ''}`,
    { method: 'POST', body: JSON.stringify(payload) },
  )

// POST /api/playoff-results
export interface PlayoffResultsPayload {
  semifinal_1?: Pick<PlayoffMatch, 'games_a' | 'games_b'>
  semifinal_2?: Pick<PlayoffMatch, 'games_a' | 'games_b'>
  final?: Pick<PlayoffMatch, 'games_a' | 'games_b'>
  third_place?: Pick<PlayoffMatch, 'games_a' | 'games_b'>
}

export const savePlayoffResults = (
  payload: PlayoffResultsPayload,
  leagueId?: string,
) =>
  apiFetch<MutationResponse>(
    `/playoff-results${leagueId ? `?league=${leagueId}` : ''}`,
    { method: 'POST', body: JSON.stringify(payload) },
  )

// POST /api/leagues/create
export interface CreateLeaguePayload {
  name: string
  display_name?: string
  carry_over_players?: boolean
}

export const createLeague = (payload: CreateLeaguePayload) =>
  apiFetch<CreateLeagueResponse>('/leagues/create', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

// POST /api/leagues/switch
export interface SwitchLeaguePayload {
  id: string
}

export const switchLeague = (payload: SwitchLeaguePayload) =>
  apiFetch<MutationResponse>('/leagues/switch', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

// POST /api/leagues/complete
export interface CompleteLeaguePayload {
  id: string
}

export const completeLeague = (payload: CompleteLeaguePayload) =>
  apiFetch<MutationResponse>('/leagues/complete', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
