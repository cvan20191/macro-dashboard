from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StockSnapshot(BaseModel):
    ticker: str
    sector: str
    peer_tickers: list[str] = Field(default_factory=list)
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    forward_pe: float | None = None
    ev_ebitda: float | None = None
    debt_ebitda: float | None = None
    interest_coverage: float | None = None
    negative_eps: bool = False
    asset_heavy: bool = False


class MetricSelectionResult(BaseModel):
    primary_metric: Literal["forward_pe", "ev_ebitda"]
    reasons: list[str] = Field(default_factory=list)


class PeerRegressionResult(BaseModel):
    r_squared: float | None = None
    residual: float | None = None
    comparable_peer_count: int = 0
    confidence_note: str | None = None


class StockFitResult(BaseModel):
    regime_fit_score: float
    preferred_archetype: str
    primary_metric: Literal["forward_pe", "ev_ebitda"]
    reasons: list[str] = Field(default_factory=list)
    peer_regression: PeerRegressionResult = Field(default_factory=PeerRegressionResult)
