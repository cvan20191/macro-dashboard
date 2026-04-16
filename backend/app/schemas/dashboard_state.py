from __future__ import annotations

from pydantic import BaseModel, Field

from app.doctrine import SignalMode, TriState


class DataFreshness(BaseModel):
    overall_status: str = "unknown"
    stale_series: list[str] = Field(default_factory=list)


class FedChessboard(BaseModel):
    quadrant: str | None = None
    label: str | None = None
    # Doctrine-facing explanation fields only.
    rate_direction_medium_term: str | None = None
    rate_impulse_short: str | None = None
    balance_sheet_direction_medium_term: str | None = None
    effective_balance_sheet_direction: str | None = None
    balance_sheet_liquidity_interpretation: str | None = None
    balance_sheet_pace: str | None = None
    liquidity_transition_path: str | None = None
    transition_tag: str | None = None
    quadrant_basis_note: str | None = None
    transition_basis_note: str | None = None


class LiquidityPlumbing(BaseModel):
    state: str = "unknown"  # normal | elevated | severe | unknown
    state_label: str = "Unknown"
    reserves_total: float | None = None
    reserves_trend_1m: str | None = None
    reserves_buffer_ratio: float | None = None
    repo_total: float | None = None
    repo_trend_1m: str | None = None
    repo_spike_ratio: float | None = None
    reverse_repo_total: float | None = None
    reverse_repo_trend_1m: str | None = None
    reverse_repo_buffer_ratio: float | None = None
    balance_sheet_expansion_not_qe: bool = False
    caution_note: str | None = None


class StagflationTrap(BaseModel):
    active: bool = False
    growth_weakening: bool = False
    sticky_inflation: bool = False
    growth_weakening_state: TriState = "unknown"
    sticky_inflation_state: TriState = "unknown"
    trap_state: TriState = "unknown"
    # Display copy — never imply "not sticky" when inputs are missing (see compute_stagflation).
    inflation_headline: str = "Inflation confirmation incomplete"
    inflation_inputs_incomplete: bool = True
    trap_assessment_note: str | None = None
    pmi_manufacturing: float | None = None
    pmi_services: float | None = None
    unemployment_rate: float | None = None
    core_cpi_yoy: float | None = None
    shelter_status: str | None = None
    services_ex_energy_status: str | None = None
    wti_oil: float | None = None
    oil_risk_active: bool = False


class PolicyOptionality(BaseModel):
    constraint_level: str = "unknown"   # free | limited | trapped | unknown
    labor_slack_state: str = "unknown"  # present | absent | mixed | unknown
    labor_balance_state: str = "unknown"  # weak_jobs_tight_ur | clean_slack | mixed | unknown
    inflation_state: str = "unknown"    # cooling | sticky_or_hot | mixed | unknown
    fed_can_ease: bool = False
    fed_trapped: bool = False
    bad_data_is_good_enabled: bool = False
    rate_cut_weirdness_active: bool = False
    note: str | None = None


class ValuationConstituent(BaseModel):
    ticker: str
    price: float | None = None
    forward_eps: float | None = None
    forward_pe: float | None = None
    fy1_eps: float | None = None
    fy2_eps: float | None = None
    shares: float | None = None
    fiscal_year_end: str | None = None
    estimate_as_of: str | None = None
    basis_confidence: float | None = None


class CohortValuation(BaseModel):
    cohort_code: str
    label: str
    forward_pe: float | None = None
    current_year_forward_pe: float | None = None
    next_year_forward_pe: float | None = None
    selected_year: int | None = None
    horizon_label: str | None = None
    signal_mode: SignalMode = "directional_only"
    coverage_count: int | None = None
    coverage_ratio: float | None = None
    basis_confidence: float | None = None
    note: str | None = None
    tickers: list[str] = Field(default_factory=list)


class Valuation(BaseModel):
    forward_pe: float | None = None
    current_year_forward_pe: float | None = None
    next_year_forward_pe: float | None = None
    selected_year: int | None = None
    zone: str | None = None
    zone_label: str | None = None
    buy_zone_low: float | None = None
    buy_zone_high: float | None = None
    pause_threshold: float | None = None
    # ---- valuation data quality fields ----
    # basis: forward | trailing | ttm_derived | unavailable
    basis: str = "unavailable"
    # human-readable basis label shown in the UI
    basis_label: str = "Unavailable"
    # provider note explaining the exact source
    source_note: str | None = None
    # True whenever basis != "forward" and a value is present
    is_fallback: bool = False
    # ---- metric identity fields ----
    metric_name: str | None = None          # e.g. "Mag 7 Forward P/E"
    object_label: str | None = None         # e.g. "Mag 7 Basket"
    provider: str | None = None             # e.g. "fmp" or "yahoo"
    coverage_count: int | None = None       # number of valid basket constituents
    coverage_ratio: float | None = None     # fraction of Mag 7 market cap included
    signal_mode: SignalMode = "directional_only"
    basis_confidence: float | None = None
    estimate_as_of: str | None = None
    horizon_label: str | None = None
    horizon_coverage_ratio: float | None = None
    # per-ticker breakdown for the FMP Mag 7 basket
    constituents: list[ValuationConstituent] = Field(default_factory=list)
    cohort_valuations: list[CohortValuation] = Field(default_factory=list)


class SystemicStress(BaseModel):
    yield_curve_inverted: bool = False
    yield_curve_value: float | None = None
    npl_ratio: float | None = None
    npl_zone: str | None = None
    cre_delinquency_rate: float | None = None
    cre_delinquency_zone: str | None = None
    credit_card_chargeoff_rate: float | None = None
    credit_card_chargeoff_zone: str | None = None
    market_cap_m2_ratio: float | None = None
    market_cap_m2_zone: str | None = None
    speaker_market_cap_m2_ratio: float | None = None
    speaker_market_cap_m2_source: str | None = None
    corporate_equities_m2_ratio: float | None = None
    corporate_equities_m2_zone: str | None = None
    corporate_equities_m2_source: str | None = None
    spy_fallback_equity_m2_ratio: float | None = None
    # How market_cap_m2_ratio was built (for copy / threshold interpretation)
    equity_m2_ratio_source: str | None = None
    equity_m2_numerator_as_of: str | None = None
    equity_m2_numerator_freshness: str | None = None
    corporate_equities_m2_numerator_as_of: str | None = None
    corporate_equities_m2_numerator_freshness: str | None = None
    proxy_warning_active: bool = False


class DollarContext(BaseModel):
    dxy: float | None = None
    dxy_pressure: bool = False


class RallyConditions(BaseModel):
    rally_fuel_score: int | None = None
    fed_put: bool = False
    treasury_put: bool = False
    political_put: bool = False
    market_ignoring_bad_news: bool = False


class ExposureGuidance(BaseModel):
    deployment_style: str = "wait"  # aggressive | selective | defensive | wait
    max_cash_deployment_pct: int = 0
    leverage_allowed: bool = False
    note: str | None = None


class EquityProfileGuidance(BaseModel):
    primary_profile_code: str = "wait"
    primary_profile_label: str = "Wait / no preferred equity profile"
    secondary_profile_code: str | None = None
    secondary_profile_label: str | None = None
    emerging_profile_code: str | None = None
    emerging_profile_label: str | None = None
    exit_discipline_required: bool = False
    same_sector_peer_compare_required: bool = True
    note: str | None = None


class ExitDisciplineSignal(BaseModel):
    active: bool = False
    scope: str = "none"  # stock_d_type_a_regime | none
    rate_reversal_watch_active: bool = False
    qe_fade_watch_active: bool = False
    note: str | None = None


class CohortRotationItem(BaseModel):
    cohort_code: str
    label: str
    stance: str = "neutral"  # overweight | accumulate_slowly | neutral | watch | underweight | avoid
    reason: str | None = None
    forward_pe: float | None = None
    signal_mode: SignalMode = "directional_only"


class CohortRotationGuidance(BaseModel):
    favored_cohort_codes: list[str] = Field(default_factory=list)
    defensive_anchor_code: str | None = None
    items: list[CohortRotationItem] = Field(default_factory=list)
    note: str | None = None


class DeterministicSummary(BaseModel):
    headline: str
    subheadline: str | None = None
    action_line: str | None = None
    deployment_line: str | None = None
    cohort_line: str | None = None
    profile_line: str | None = None
    peer_line: str | None = None
    caution_line: str | None = None


class PeerScoreMetric(BaseModel):
    value: float | None = None
    peer_median: float | None = None
    favorable_percentile: float | None = None
    signal: str = "unknown"  # better_than_peers | in_line | worse_than_peers | unknown


class ValuationGrowthFit(BaseModel):
    fit_growth_metric: str | None = None
    peer_count: int = 0
    r_squared: float | None = None
    expected_forward_pe: float | None = None
    residual_pct: float | None = None
    fit_signal: str = "insufficient"  # undervalued_vs_growth | fairly_priced_vs_growth | overvalued_vs_growth | insufficient
    weighting_active: bool = False
    note: str | None = None


class PeerScorecard(BaseModel):
    ticker: str
    sector: str | None = None
    industry: str | None = None
    peer_tickers: list[str] = Field(default_factory=list)
    revenue_growth: PeerScoreMetric = Field(default_factory=PeerScoreMetric)
    earnings_growth: PeerScoreMetric = Field(default_factory=PeerScoreMetric)
    forward_pe: PeerScoreMetric = Field(default_factory=PeerScoreMetric)
    debt_to_ebitda: PeerScoreMetric = Field(default_factory=PeerScoreMetric)
    valuation_vs_growth_fit: ValuationGrowthFit = Field(default_factory=ValuationGrowthFit)
    verdict: str = "insufficient"  # leader | balanced | fragile | insufficient
    same_sector_peer_compare_required: bool = True
    note: str | None = None


class StrategicWatchlistItem(BaseModel):
    code: str
    label: str
    kind: str = "manual_event"  # manual_event | derived_macro
    status: str = "watch"  # supportive | mixed | warning | watch
    source_mode: str = "manual"  # manual | derived
    priority: int = 3
    note: str | None = None


class StrategicWatchlist(BaseModel):
    items: list[StrategicWatchlistItem] = Field(default_factory=list)
    note: str | None = None


class ReasonedText(BaseModel):
    code: str
    text: str


class RegimeTransition(BaseModel):
    from_regime: str | None = None
    to_regime: str | None = None
    transition_strength: str = "weak"
    direction: str = "unknown"
    reasons: list[str] = Field(default_factory=list)


class DashboardState(BaseModel):
    as_of: str | None = None
    data_freshness: DataFreshness = Field(default_factory=DataFreshness)
    primary_regime: str
    tactical_state: str | None = None
    legacy_regime_label: str | None = None
    secondary_overlays: list[str] = Field(default_factory=list)
    confidence: str = "Medium"
    evidence_confidence: str = "Medium"
    doctrine_confidence: str = "Medium"
    action_confidence: str = "Medium"
    current_posture: str
    regime_transition: RegimeTransition | None = None
    fed_chessboard: FedChessboard | None = None
    policy_optionality: PolicyOptionality | None = None
    liquidity_plumbing: LiquidityPlumbing | None = None
    stagflation_trap: StagflationTrap | None = None
    valuation: Valuation | None = None
    systemic_stress: SystemicStress | None = None
    dollar_context: DollarContext | None = None
    rally_conditions: RallyConditions | None = None
    exposure_guidance: ExposureGuidance | None = None
    equity_profile_guidance: EquityProfileGuidance | None = None
    exit_discipline_signal: ExitDisciplineSignal | None = None
    cohort_rotation_guidance: CohortRotationGuidance | None = None
    deterministic_summary: DeterministicSummary | None = None
    peer_scorecards: list[PeerScorecard] = Field(default_factory=list)
    strategic_watchlist: StrategicWatchlist | None = None
    top_watchpoints: list[str] = Field(default_factory=list)
    top_watchpoint_details: list[ReasonedText] = Field(default_factory=list)
    what_changed: list[str] = Field(default_factory=list)
    what_changed_details: list[ReasonedText] = Field(default_factory=list)
    what_changes_call: list[str] = Field(default_factory=list)
    what_changes_call_details: list[ReasonedText] = Field(default_factory=list)
