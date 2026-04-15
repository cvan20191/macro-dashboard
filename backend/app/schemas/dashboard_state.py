from __future__ import annotations

from pydantic import BaseModel, Field

from app.doctrine import SignalMode, TriState


class DataFreshness(BaseModel):
    overall_status: str = "unknown"
    stale_series: list[str] = Field(default_factory=list)


class FedChessboard(BaseModel):
    quadrant: str | None = None
    label: str | None = None
    # Legacy compatibility fields — retained for debug / backward compatibility.
    rate_trend_1m: str | None = None
    rate_trend_3m: str | None = None
    balance_sheet_trend_1m: str | None = None
    balance_sheet_trend_3m: str | None = None
    direction_vs_1m_ago: str | None = None
    # Existing surfaced helpers.
    # Debug-only compatibility field; live doctrine output should leave this unset.
    policy_stance: str | None = None
    rate_impulse: str | None = None
    balance_sheet_direction: str | None = None
    balance_sheet_pace: str | None = None
    # Doctrine-facing explanation fields.
    rate_direction_medium_term: str | None = None
    rate_impulse_short: str | None = None
    balance_sheet_direction_medium_term: str | None = None
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
    liquidity_plumbing: LiquidityPlumbing | None = None
    stagflation_trap: StagflationTrap | None = None
    valuation: Valuation | None = None
    systemic_stress: SystemicStress | None = None
    dollar_context: DollarContext | None = None
    rally_conditions: RallyConditions | None = None
    top_watchpoints: list[str] = Field(default_factory=list)
    top_watchpoint_details: list[ReasonedText] = Field(default_factory=list)
    what_changed: list[str] = Field(default_factory=list)
    what_changed_details: list[ReasonedText] = Field(default_factory=list)
    what_changes_call: list[str] = Field(default_factory=list)
    what_changes_call_details: list[ReasonedText] = Field(default_factory=list)
