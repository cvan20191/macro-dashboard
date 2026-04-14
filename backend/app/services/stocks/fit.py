from __future__ import annotations

from math import sqrt

from app.schemas.stock_fit import (
    MetricSelectionResult,
    PeerRegressionResult,
    StockFitResult,
    StockSnapshot,
)


def select_primary_metric(stock: StockSnapshot) -> MetricSelectionResult:
    reasons: list[str] = []
    if stock.negative_eps:
        reasons.append("negative_eps")
    if stock.asset_heavy:
        reasons.append("asset_heavy")
    if stock.debt_ebitda is not None and stock.debt_ebitda >= 3.0:
        reasons.append("meaningful_leverage")
    if reasons:
        return MetricSelectionResult(primary_metric="ev_ebitda", reasons=reasons)
    return MetricSelectionResult(
        primary_metric="forward_pe",
        reasons=["default_forward_pe"],
    )


def compute_peer_regression(x: list[float], y: list[float], subject_x: float, subject_y: float) -> PeerRegressionResult:
    if len(x) < 3 or len(x) != len(y):
        return PeerRegressionResult(confidence_note="Not enough comparable peers for regression")

    x_mean = sum(x) / len(x)
    y_mean = sum(y) / len(y)
    ss_x = sum((v - x_mean) ** 2 for v in x)
    ss_y = sum((v - y_mean) ** 2 for v in y)
    if ss_x == 0 or ss_y == 0:
        return PeerRegressionResult(comparable_peer_count=len(x), confidence_note="Peer set has no usable dispersion")

    cov = sum((vx - x_mean) * (vy - y_mean) for vx, vy in zip(x, y))
    slope = cov / ss_x
    intercept = y_mean - slope * x_mean
    y_hat = [intercept + slope * vx for vx in x]
    ss_res = sum((actual - pred) ** 2 for actual, pred in zip(y, y_hat))
    r_squared = max(0.0, min(1.0, 1.0 - (ss_res / ss_y)))
    subject_hat = intercept + slope * subject_x
    residual = subject_y - subject_hat
    note = "Peer relationship is reasonably coherent" if r_squared >= 0.8 else "Peer relationship is noisy; treat relative valuation carefully"

    return PeerRegressionResult(
        r_squared=round(r_squared, 4),
        residual=round(residual, 4),
        comparable_peer_count=len(x),
        confidence_note=note,
    )


def compute_stock_fit(
    stock: StockSnapshot,
    regime: str,
    peer_regression: PeerRegressionResult | None = None,
) -> StockFitResult:
    metric = select_primary_metric(stock)
    score = 50.0
    reasons = list(metric.reasons)

    if stock.revenue_growth is not None:
        score += min(15.0, max(-10.0, stock.revenue_growth))
    if stock.earnings_growth is not None:
        score += min(15.0, max(-12.0, stock.earnings_growth))
    if stock.debt_ebitda is not None:
        score -= min(18.0, max(0.0, stock.debt_ebitda * 4.0))
    if stock.interest_coverage is not None and stock.interest_coverage < 3:
        score -= 8.0
        reasons.append("thin_interest_coverage")

    preferred = "profitable_cashflow_compounders"
    regime_upper = regime.upper().strip()
    if regime_upper == "A":
        preferred = "hyper_growth_manageable_debt"
        if stock.revenue_growth is not None and stock.revenue_growth > 15:
            score += 10.0
        if stock.debt_ebitda is not None and stock.debt_ebitda <= 3:
            score += 4.0
    elif regime_upper in {"B", "C"}:
        preferred = "moderate_growth_moderate_leverage" if regime_upper == "B" else "high_growth_refinancing_beneficiary"
        if stock.debt_ebitda is not None and stock.debt_ebitda <= 2.5:
            score += 6.0
        if stock.earnings_growth is not None and stock.earnings_growth > 0:
            score += 5.0
    elif regime_upper == "D":
        preferred = "defensive_low_debt_low_valuation"
        if metric.primary_metric == "forward_pe" and stock.forward_pe is not None and stock.forward_pe <= 18:
            score += 8.0
        if stock.debt_ebitda is not None and stock.debt_ebitda > 2.5:
            score -= 8.0
            reasons.append("defensive_regime_leverage_penalty")

    if peer_regression is not None:
        if peer_regression.r_squared is not None and peer_regression.r_squared < 0.8:
            score -= 5.0
            reasons.append("peer_relationship_noisy")
        if peer_regression.residual is not None and peer_regression.residual < 0:
            score += 4.0
            reasons.append("below_peer_fit_line")

    return StockFitResult(
        regime_fit_score=round(max(0.0, min(100.0, score)), 2),
        preferred_archetype=preferred,
        primary_metric=metric.primary_metric,
        reasons=reasons,
        peer_regression=peer_regression or PeerRegressionResult(),
    )
