// ---------------------------------------------------------------------------
// Response types (mirror backend Pydantic models exactly)
// ---------------------------------------------------------------------------

export interface SummaryMeta {
  used_fallback: boolean
  generated_at: string
  model: string | null
  data_status: string
}

export interface PlaybookSummary {
  headline_summary: string
  expanded_summary: string
  regime_label: string
  posture_label: string
  watch_now: [string, string, string]
  what_changed_bullets: [string, string, string]
  what_changes_call_bullets: [string, string, string]
  risk_flags: string[]
  teaching_note: string
  meta: SummaryMeta
}

// ---------------------------------------------------------------------------
// Request types (mirror backend DashboardState input schema)
// ---------------------------------------------------------------------------

export interface DataFreshness {
  overall_status: string
  stale_series: string[]
}

export interface FedChessboard {
  quadrant?: string
  label?: string
  // Legacy/debug.
  rate_trend_1m?: string
  rate_trend_3m?: string
  balance_sheet_trend_1m?: string
  balance_sheet_trend_3m?: string
  direction_vs_1m_ago?: string
  policy_stance?: string
  rate_impulse?: string
  balance_sheet_direction?: string
  balance_sheet_pace?: string
  transition_tag?: string
  // Doctrine-facing explanation.
  rate_direction_medium_term?: string
  rate_impulse_short?: string
  balance_sheet_direction_medium_term?: string
  quadrant_basis_note?: string | null
}

export interface LiquidityPlumbing {
  state?: string
  state_label?: string
  reserves_total?: number
  reserves_trend_1m?: string
  reserves_buffer_ratio?: number
  repo_total?: number
  repo_trend_1m?: string
  repo_spike_ratio?: number
  reverse_repo_total?: number
  reverse_repo_trend_1m?: string
  reverse_repo_buffer_ratio?: number
  balance_sheet_expansion_not_qe?: boolean
  caution_note?: string | null
}

export interface StagflationTrap {
  active: boolean
  growth_weakening: boolean
  sticky_inflation: boolean
  growth_weakening_state?: 'true' | 'false' | 'unknown'
  sticky_inflation_state?: 'true' | 'false' | 'unknown'
  trap_state?: 'true' | 'false' | 'unknown'
  inflation_headline?: string
  inflation_inputs_incomplete?: boolean
  trap_assessment_note?: string | null
  pmi_manufacturing?: number
  pmi_services?: number
  unemployment_rate?: number
  core_cpi_yoy?: number
  shelter_status?: string
  services_ex_energy_status?: string
  wti_oil?: number
  oil_risk_active: boolean
}

export interface ValuationConstituent {
  ticker: string
  price?: number
  forward_eps?: number
  forward_pe?: number
  fy1_eps?: number
  fy2_eps?: number
  shares?: number
  fiscal_year_end?: string
  estimate_as_of?: string
  basis_confidence?: number
}

export interface Valuation {
  forward_pe?: number
  current_year_forward_pe?: number
  next_year_forward_pe?: number
  selected_year?: number
  zone?: string
  zone_label?: string
  buy_zone_low?: number
  buy_zone_high?: number
  pause_threshold?: number
  // basis metadata — forward | trailing | ttm_derived | unavailable
  basis?: string
  basis_label?: string
  source_note?: string
  is_fallback?: boolean
  // metric identity
  metric_name?: string       // e.g. "Mag 7 Forward P/E" or "QQQ P/E Proxy"
  object_label?: string      // e.g. "Mag 7 Basket" or "QQQ (QQQ)"
  provider?: string          // e.g. "fmp" or "yahoo"
  coverage_count?: number    // number of basket constituents used
  coverage_ratio?: number    // fraction of Mag 7 market cap included
  signal_mode?: 'actionable' | 'directional_only'
  basis_confidence?: number
  estimate_as_of?: string
  horizon_label?: string
  horizon_coverage_ratio?: number
  // per-ticker breakdown — only populated for FMP Mag 7 basket
  constituents?: ValuationConstituent[]
}

export interface SystemicStress {
  yield_curve_inverted: boolean
  yield_curve_value?: number
  npl_ratio?: number
  npl_zone?: string
  cre_delinquency_rate?: number
  cre_delinquency_zone?: string
  credit_card_chargeoff_rate?: number
  credit_card_chargeoff_zone?: string
  market_cap_m2_ratio?: number
  market_cap_m2_zone?: string
  corporate_equities_m2_ratio?: number
  corporate_equities_m2_zone?: string
  /** fred_z1 | manual_override | spy_fallback */
  equity_m2_ratio_source?: string
  /** Z.1 observed_at, manual JSON as_of, or SPY quote date */
  equity_m2_numerator_as_of?: string
  /** fresh | stale | manual | historical | … from live/replay freshness */
  equity_m2_numerator_freshness?: string
  proxy_warning_active?: boolean
}

export interface DollarContext {
  dxy?: number
  dxy_pressure: boolean
}

export interface RallyConditions {
  rally_fuel_score?: number
  fed_put: boolean
  treasury_put: boolean
  political_put: boolean
  market_ignoring_bad_news: boolean
}

export interface DashboardState {
  as_of?: string
  data_freshness: DataFreshness
  primary_regime: string
  tactical_state?: string | null
  legacy_regime_label?: string | null
  secondary_overlays: string[]
  confidence: string
  evidence_confidence?: string
  doctrine_confidence?: string
  action_confidence?: string
  current_posture: string
  regime_transition?: {
    from_regime?: string
    to_regime?: string
    transition_strength?: string
    direction?: string
    reasons?: string[]
  }
  fed_chessboard?: FedChessboard
  liquidity_plumbing?: LiquidityPlumbing
  stagflation_trap?: StagflationTrap
  valuation?: Valuation
  systemic_stress?: SystemicStress
  dollar_context?: DollarContext
  rally_conditions?: RallyConditions
  top_watchpoints: string[]
  top_watchpoint_details?: Array<{ code: string; text: string }>
  what_changed: string[]
  what_changed_details?: Array<{ code: string; text: string }>
  what_changes_call: string[]
  what_changes_call_details?: Array<{ code: string; text: string }>
}
