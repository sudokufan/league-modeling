import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  addResults,
  savePlayoffResults,
  createLeague,
  switchLeague,
  completeLeague,
} from '@/api/mutations'
import type {
  AddResultsPayload,
  DeleteWeekPayload,
  PlayoffResultsPayload,
  CreateLeaguePayload,
  SwitchLeaguePayload,
  CompleteLeaguePayload,
} from '@/api/mutations'

export function useAddResults(leagueId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: AddResultsPayload | DeleteWeekPayload) =>
      addResults(payload, leagueId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['league-data', leagueId] })
      void queryClient.invalidateQueries({ queryKey: ['simulation', leagueId] })
    },
  })
}

export function useSavePlayoffResults(leagueId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PlayoffResultsPayload) =>
      savePlayoffResults(payload, leagueId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['league-data', leagueId] })
    },
  })
}

export function useCreateLeague() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateLeaguePayload) => createLeague(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['leagues'] })
    },
  })
}

export function useSwitchLeague() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SwitchLeaguePayload) => switchLeague(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['leagues'] })
      void queryClient.invalidateQueries({ queryKey: ['league-data'] })
    },
  })
}

export function useCompleteLeague() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CompleteLeaguePayload) => completeLeague(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['leagues'] })
      void queryClient.invalidateQueries({ queryKey: ['league-data'] })
    },
  })
}
