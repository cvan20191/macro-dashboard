from __future__ import annotations

from pydantic import BaseModel


class LiquidityHistoryPoint(BaseModel):
    date: str
    value: float


class FedLiquidityLever(BaseModel):
    label: str
    series_id: str
    latest_date: str
    latest_value: float | None
    unit: str
    next_release_date: str
    history: list[LiquidityHistoryPoint]


class FedLiquidityOverviewResponse(BaseModel):
    as_of: str
    description: str
    fed_balance_sheet: FedLiquidityLever
    fed_rate: FedLiquidityLever
    generated_at: str
