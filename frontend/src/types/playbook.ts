// PlaybookResponse — combined state + summary returned by POST /api/playbook
// LivePlaybookResponse — same, extended with source provenance from live endpoints

import type { DashboardState } from './summary'
import type { PlaybookSummary } from './summary'
import type { IndicatorSnapshot } from './indicator'
import type { CatalystState } from './catalysts'

export type { CatalystState }

export interface PlaybookConclusion {
  conclusion_label: string
  new_cash_action:
    | 'accumulate'
    | 'accumulate_selectively'
    | 'hold_and_wait'
    | 'pause_new_buying'
    | 'defensive_preservation'
  existing_positions_action?: 'hold' | 'hold_with_tighter_risk' | 'trim' | 'exit_on_regime_break'
  stock_archetype_preferred: Array<
    | 'hyper_growth_manageable_debt'
    | 'moderate_growth_moderate_leverage'
    | 'high_growth_refinancing_beneficiary'
    | 'defensive_low_debt_low_valuation'
    | 'profitable_cashflow_compounders'
    | 'balance_sheet_strength_priority'
    | 'high_debt_unprofitable_growth'
    | 'valuation_dependent_speculation'
    | 'deep_cyclical_balance_sheet_risk'
  >
  stock_archetype_avoid: Array<
    | 'hyper_growth_manageable_debt'
    | 'moderate_growth_moderate_leverage'
    | 'high_growth_refinancing_beneficiary'
    | 'defensive_low_debt_low_valuation'
    | 'profitable_cashflow_compounders'
    | 'balance_sheet_strength_priority'
    | 'high_debt_unprofitable_growth'
    | 'valuation_dependent_speculation'
    | 'deep_cyclical_balance_sheet_risk'
  >
  can_rally_despite_bad_news: boolean
  warning_urgency: 'cautionary' | 'elevated' | 'urgent'
  leniency_notes: Array<
    | 'valuation_proxy_not_true_forward_pe'
    | 'stress_gauges_warning_lights_not_timers'
    | 'transition_regime_can_overshoot'
    | 'stretched_means_pause_not_forced_sell'
    | 'mixed_signals_reduce_conviction'
  >
  why_now: string
  tactical_overlay_label?: string | null
  reentry_condition?: string | null
  exit_condition?: string | null
}

export interface MacroSourceAttribution {
  provider: string
  fetched_at: string
  stale?: boolean
  note?: string | null
}

export interface MacroUpcomingEventRow {
  event_name: string
  release_time: string
  previous: string
  consensus: string
  importance: number
  status: string
}

export interface MacroFedPricingRow {
  meeting_date: string
  hold_pct: string
  cut_25_pct: string
  cut_50_pct: string
  hike_25_pct: string
  delta_vs_prior: string
}

export interface MacroSurpriseRow {
  event: string
  actual: string
  consensus: string
  surprise: string
  direction: string
  impact_note: string
}

export interface MacroExpectationsState {
  upcoming_events: MacroUpcomingEventRow[]
  fed_pricing: MacroFedPricingRow[]
  recent_surprises: MacroSurpriseRow[]
  regime_impact_narrative: string
  tactical_posture_modifier: string
  sources: MacroSourceAttribution[]
  generated_at: string
}

export interface PlaybookResponse {
  state: DashboardState
  playbook_conclusion?: PlaybookConclusion
  summary: PlaybookSummary
  catalysts: CatalystState
}

// ---------------------------------------------------------------------------
// Source metadata (mirrors backend SourceMeta)
// ---------------------------------------------------------------------------
export interface SourceMeta {
  provider: string
  series_name: string
  series_id: string | null
  fetched_at: string
  observed_at: string | null
  frequency: string | null
  status: string   // fresh | stale | missing | error | fallback
  note: string | null
  source_class?: 'official' | 'licensed' | 'manual' | 'proxy' | null
  confidence_weight?: number | null
  release_date?: string | null
  last_revised_at?: string | null
  staleness_bucket?: string | null
  // valuation-specific: forward | trailing | ttm_derived | unavailable | null (other metrics)
  basis: string | null
}

// ---------------------------------------------------------------------------
// Live response types (mirrors backend LiveSnapshotResponse / LivePlaybookResponse)
// ---------------------------------------------------------------------------
export interface LiveSnapshotResponse {
  snapshot: IndicatorSnapshot
  sources: Record<string, SourceMeta>
  overall_status: string
  stale_series: string[]
  generated_at: string
}

export interface LivePlaybookResponse {
  snapshot: IndicatorSnapshot
  state: DashboardState
  playbook_conclusion?: PlaybookConclusion
  catalysts: CatalystState
  sources: Record<string, SourceMeta>
  overall_status: string
  stale_series: string[]
  generated_at: string
  macro_expectations?: MacroExpectationsState | null
}

export interface FedLiquidityHistoryPoint {
  date: string
  value: number
}

export interface FedLiquidityLever {
  label: string
  series_id: string
  latest_date: string
  latest_value: number | null
  unit: string
  next_release_date: string
  history: FedLiquidityHistoryPoint[]
}

export interface FedLiquidityOverviewResponse {
  as_of: string
  description: string
  fed_balance_sheet: FedLiquidityLever
  fed_rate: FedLiquidityLever
  generated_at: string
}
