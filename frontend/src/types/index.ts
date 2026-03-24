// League registry
export interface LeagueInfo {
  id: string
  name: string
  display_name?: string
  file: string
  status: 'active' | 'completed'
  created: string
}

export interface LeaguesConfig {
  active_league: string
  leagues: LeagueInfo[]
}

// League config (from JSON file config block)
export interface LeagueConfig {
  total_weeks: number
  rounds_per_week: number
  best_of_n: number
  playoff_spots: number
  num_simulations: number
}

// Match data
export interface Match {
  week: number
  round: number
  player_a: string
  player_b?: string | null
  games_a: number
  games_b: number
}

// Per-player record in a week
export interface WeekRecord {
  w: number
  l: number
  d: number
}

// Overall player stats
export interface PlayerStats {
  mp: number
  w: number
  l: number
  d: number
  gw: number
  gl: number
  gwp: number
  omw?: number
}

// Playoffs
export interface PlayoffMatch {
  player_a?: string | null
  player_b?: string | null
  games_a?: number | null
  games_b?: number | null
}

export interface Playoffs {
  semifinal_1: PlayoffMatch
  semifinal_2: PlayoffMatch
  final?: PlayoffMatch
  third_place?: PlayoffMatch
}

// derive_stats() output — this is what /api/league-data returns
// NOTE: per_week_* dicts have integer week numbers as keys, but JSON serializes them as strings
export interface DerivedLeague {
  config: LeagueConfig
  players: string[]
  unofficial_players: string[]
  weekly_scores: Record<string, (number | null)[]>  // player -> scores array
  overall_stats: Record<string, PlayerStats>
  attendance_prob: Record<string, number>
  weeks_completed: number
  total_weeks: number
  rounds_per_week: number
  best_of_n: number
  playoff_spots: number
  num_simulations: number
  matches: Match[]
  per_week_records: Record<string, Record<string, WeekRecord>>  // week(str) -> player -> record
  per_week_opponents: Record<string, Record<string, string[]>> // week(str) -> player -> opponent list
  per_week_mwp: Record<string, Record<string, number>>         // week(str) -> player -> mwp
  per_week_omw: Record<string, Record<string, number>>         // week(str) -> player -> omw
  overall_omw: Record<string, number>
  playoffs?: Playoffs | null
  _league_info: LeagueInfo
  _all_leagues: LeagueInfo[]
}

// run_simulation_api() output — this is what /api/simulate returns
// The API returns a shaped list of players with pre-computed fields, not raw per-player dicts
export interface SimPlayerResult {
  name: string
  playoff_prob: number
  current_best7: number
  max_possible: number
  record: string
  omw: number
  gwp: number
  status: string
}

export interface SimulationResults {
  players: SimPlayerResult[]
  num_simulations: number
  error?: string
}

// Raw per-player simulation result (from run_simulation() directly, not the API)
export interface PlayerSimResult {
  playoff_prob: number
  playoff_count?: number
  positions?: Record<string, number>
  current_best7: number
  max_possible_best7: number
  min_guaranteed_best7: number
  total_match_pts: number
  weeks_played: number
}

// Insight card (computed client-side from DerivedLeague)
export interface InsightCard {
  title: string
  player: string
  value: string
  detail: string
}

// Mutation response shapes
export interface MutationResponse {
  success: boolean
  message: string
}

export interface CreateLeagueResponse extends MutationResponse {
  id: string
}
