from __future__ import annotations

from fastapi import APIRouter

from app.schemas.stock_fit import (
    MetricSelectionResult,
    PeerRegressionResult,
    StockFitResult,
    StockSnapshot,
)
from app.services.stocks.fit import compute_peer_regression, compute_stock_fit, select_primary_metric

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.post("/metric-selection", response_model=MetricSelectionResult)
async def metric_selection(snapshot: StockSnapshot) -> MetricSelectionResult:
    return select_primary_metric(snapshot)


@router.post("/fit", response_model=StockFitResult)
async def stock_fit(snapshot: StockSnapshot, regime: str = "C") -> StockFitResult:
    return compute_stock_fit(snapshot, regime=regime)


@router.post("/peer-regression", response_model=PeerRegressionResult)
async def peer_regression(
    x: list[float],
    y: list[float],
    subject_x: float,
    subject_y: float,
) -> PeerRegressionResult:
    return compute_peer_regression(x=x, y=y, subject_x=subject_x, subject_y=subject_y)
