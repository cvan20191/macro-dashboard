// Raw indicator input types — mirror backend IndicatorSnapshot schema

export interface DataFreshnessInput {
  overall_status?: string
  stale_series?: string[]
}

export interface LiquidityInput {
  fed_funds_rate?: number
  rate_trend_1m?: string
  rate_trend_3m?: string
  balance_sheet_assets?: number
  balance_sheet_trend_1m?: string
  balance_sheet_trend_3m?: string
  rate_cycle_position?: number
}

export interface PlumbingInput {
  total_reserves?: number
  reserves_trend_1m?: string
  reserves_buffer_ratio?: number
  repo_total?: number
  repo_trend_1m?: string
  repo_spike_ratio?: number
  reverse_repo_total?: number
  reverse_repo_trend_1m?: string
  reverse_repo_buffer_ratio?: number
  walcl_trend_1m?: string
}

export interface GrowthInput {
  pmi_manufacturing?: number
  pmi_services?: number
  unemployment_rate?: number
  unemployment_trend?: string
  initial_claims_trend?: string
  payrolls_trend?: string
}

export interface InflationInput {
  core_cpi_yoy?: number
  core_cpi_mom?: number
  shelter_status?: string
  services_ex_energy_status?: string
  wti_oil?: number
  oil_risk_active?: boolean
}

export interface ValuationInput {
  forward_pe?: number
  current_year_forward_pe?: number
  next_year_forward_pe?: number
  selected_year?: number
  basis?: string
  basis_label?: string
  pe_basis?: string
  source_note?: string
  pe_source_note?: string
  is_fallback?: boolean
  metric_name?: string
  object_label?: string
  provider?: string
  pe_provider?: string
  coverage_count?: number
  coverage_ratio?: number
}

export interface SystemicStressInput {
  yield_curve_10y_2y?: number
  npl_ratio?: number
  credit_card_chargeoff_rate?: number
  market_cap_m2_ratio?: number
  equity_m2_ratio_source?: string
  equity_m2_numerator_as_of?: string
  equity_m2_numerator_freshness?: string
}

export interface DollarContextInput {
  dxy?: number
}

export interface PolicySupportInput {
  fed_put?: boolean
  treasury_put?: boolean
  political_put?: boolean
}

export interface IndicatorSnapshot {
  as_of?: string
  data_freshness: DataFreshnessInput
  liquidity: LiquidityInput
  plumbing: PlumbingInput
  growth: GrowthInput
  inflation: InflationInput
  valuation: ValuationInput
  systemic_stress: SystemicStressInput
  dollar_context: DollarContextInput
  policy_support: PolicySupportInput
}
