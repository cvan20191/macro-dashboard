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
  rate_direction_medium_term?: string
  rate_impulse_short?: string
  balance_sheet_direction_medium_term?: string
  effective_balance_sheet_direction?: string
  balance_sheet_liquidity_interpretation?: string
  balance_sheet_pace?: string
  liquidity_transition_path?: string
  transition_tag?: string
  quadrant_basis_note?: string | null
  transition_basis_note?: string | null
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

export interface PolicyOptionality {
  constraint_level?: string
  labor_slack_state?: string
  labor_balance_state?: string
  inflation_state?: string
  fed_can_ease?: boolean
  fed_trapped?: boolean
  bad_data_is_good_enabled?: boolean
  rate_cut_weirdness_active?: boolean
  note?: string | null
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

export interface CohortValuation {
  cohort_code?: string
  label?: string
  forward_pe?: number
  current_year_forward_pe?: number
  next_year_forward_pe?: number
  selected_year?: number
  horizon_label?: string | null
  signal_mode?: string
  coverage_count?: number
  coverage_ratio?: number
  basis_confidence?: number
  note?: string | null
  tickers?: string[]
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
  cohort_valuations?: CohortValuation[]
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
  speaker_market_cap_m2_ratio?: number
  speaker_market_cap_m2_source?: string
  corporate_equities_m2_ratio?: number
  corporate_equities_m2_zone?: string
  corporate_equities_m2_source?: string
  spy_fallback_equity_m2_ratio?: number
  /** fred_z1 | manual_override | spy_fallback */
  equity_m2_ratio_source?: string
  /** Z.1 observed_at, manual JSON as_of, or SPY quote date */
  equity_m2_numerator_as_of?: string
  /** fresh | stale | manual | historical | … from live/replay freshness */
  equity_m2_numerator_freshness?: string
  corporate_equities_m2_numerator_as_of?: string
  corporate_equities_m2_numerator_freshness?: string
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

export interface ExposureGuidance {
  deployment_style?: string
  max_cash_deployment_pct?: number
  leverage_allowed?: boolean
  note?: string | null
}

export interface EquityProfileGuidance {
  primary_profile_code?: string
  primary_profile_label?: string
  secondary_profile_code?: string | null
  secondary_profile_label?: string | null
  emerging_profile_code?: string | null
  emerging_profile_label?: string | null
  exit_discipline_required?: boolean
  same_sector_peer_compare_required?: boolean
  note?: string | null
}

export interface ExitDisciplineSignal {
  active?: boolean
  scope?: string
  rate_reversal_watch_active?: boolean
  qe_fade_watch_active?: boolean
  note?: string | null
}

export interface CohortRotationItem {
  cohort_code?: string
  label?: string
  stance?: string
  reason?: string | null
  forward_pe?: number
  signal_mode?: string
}

export interface CohortRotationGuidance {
  favored_cohort_codes?: string[]
  defensive_anchor_code?: string | null
  items?: CohortRotationItem[]
  note?: string | null
}

export interface DeterministicSummary {
  headline?: string
  subheadline?: string | null
  action_line?: string | null
  deployment_line?: string | null
  cohort_line?: string | null
  profile_line?: string | null
  peer_line?: string | null
  caution_line?: string | null
}

export interface PeerScoreMetric {
  value?: number
  peer_median?: number
  favorable_percentile?: number
  signal?: string
  signal_mode?: string | null
  hard_actionable?: boolean
  note?: string | null
}

export interface ValuationGrowthFit {
  fit_growth_metric?: string | null
  peer_count?: number
  r_squared?: number
  expected_forward_pe?: number
  residual_pct?: number
  fit_signal?: string
  weighting_active?: boolean
  note?: string | null
}

export interface PeerScorecard {
  ticker?: string
  sector?: string | null
  industry?: string | null
  peer_tickers?: string[]
  revenue_growth?: PeerScoreMetric
  earnings_growth?: PeerScoreMetric
  forward_pe?: PeerScoreMetric
  debt_to_ebitda?: PeerScoreMetric
  valuation_vs_growth_fit?: ValuationGrowthFit
  verdict?: string
  same_sector_peer_compare_required?: boolean
  note?: string | null
}

export interface StrategicWatchlistItem {
  code?: string
  label?: string
  kind?: string
  status?: string
  source_mode?: string
  priority?: number
  note?: string | null
}

export interface StrategicWatchlist {
  items?: StrategicWatchlistItem[]
  note?: string | null
}

export interface AllocationLane {
  cohort_code?: string
  label?: string
  permission?: string
  reason?: string | null
}

export interface AllocationPlan {
  portfolio_action?: string
  total_cash_cap_pct?: number
  lanes?: AllocationLane[]
  note?: string | null
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
  policy_optionality?: PolicyOptionality
  liquidity_plumbing?: LiquidityPlumbing
  stagflation_trap?: StagflationTrap
  valuation?: Valuation
  systemic_stress?: SystemicStress
  dollar_context?: DollarContext
  rally_conditions?: RallyConditions
  exposure_guidance?: ExposureGuidance
  equity_profile_guidance?: EquityProfileGuidance
  exit_discipline_signal?: ExitDisciplineSignal
  cohort_rotation_guidance?: CohortRotationGuidance
  deterministic_summary?: DeterministicSummary
  peer_scorecards?: PeerScorecard[]
  strategic_watchlist?: StrategicWatchlist
  allocation_plan?: AllocationPlan
  top_watchpoints: string[]
  top_watchpoint_details?: Array<{ code: string; text: string }>
  what_changed: string[]
  what_changed_details?: Array<{ code: string; text: string }>
  what_changes_call: string[]
  what_changes_call_details?: Array<{ code: string; text: string }>
}
