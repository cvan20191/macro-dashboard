"""Normalized schemas for Macro Expectations / Event Prep overlay."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MacroSourceAttribution(BaseModel):
    provider: str
    fetched_at: str
    stale: bool = False
    note: str | None = None


class CalendarEventNormalized(BaseModel):
    event_id: str | None = None
    release_datetime: str
    country: str
    category: str | None = None
    event_name: str
    importance: int
    previous: str | None = None
    consensus: str | None = None
    actual: str | None = None
    revised_previous: str | None = None
    te_forecast: str | None = None
    last_update: str | None = None
    status: str  # upcoming | released


class UpcomingEventRow(BaseModel):
    """Table row for UI section A."""
    event_name: str
    release_time: str
    previous: str
    consensus: str
    importance: int
    status: str


class FedPricingRangeNormalized(BaseModel):
    lower_rate_bps: int
    upper_rate_bps: int
    probability: float  # 0–1


class FedPricingMeetingNormalized(BaseModel):
    meeting_date: str
    source_timestamp: str
    rate_ranges: list[FedPricingRangeNormalized] = Field(default_factory=list)
    probability_hold: float | None = None
    probability_cut_25: float | None = None
    probability_cut_50: float | None = None
    probability_hike_25: float | None = None
    implied_target_mid_bps: float | None = None
    repricing_delta_label: str = "little changed"  # more dovish | more hawkish | little changed


class FedPricingTableRow(BaseModel):
    meeting_date: str
    hold_pct: str
    cut_25_pct: str
    cut_50_pct: str
    hike_25_pct: str
    delta_vs_prior: str


class NyFedOperationNormalized(BaseModel):
    operation_date: str | None = None
    operation_type: str
    accepted_amount: str | None = None
    submitted_amount: str | None = None
    rate: str | None = None
    maturity: str | None = None
    source_timestamp: str | None = None
    raw_note: str | None = None


class SurpriseRow(BaseModel):
    event: str
    actual: str
    consensus: str
    surprise: str
    direction: str
    impact_note: str


class MacroExpectationsState(BaseModel):
    upcoming_events: list[UpcomingEventRow] = Field(default_factory=list)
    fed_pricing: list[FedPricingTableRow] = Field(default_factory=list)
    recent_surprises: list[SurpriseRow] = Field(default_factory=list)
    regime_impact_narrative: str = ""
    tactical_posture_modifier: str = "mixed — event risk elevated"
    sources: list[MacroSourceAttribution] = Field(default_factory=list)
    generated_at: str = ""
