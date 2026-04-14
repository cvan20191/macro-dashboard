from __future__ import annotations

from app.schemas.stock_fit import StockSnapshot
from app.services.stocks.fit import compute_peer_regression, compute_stock_fit, select_primary_metric


def test_metric_selection_prefers_ev_ebitda_for_negative_eps() -> None:
    result = select_primary_metric(
        StockSnapshot(
            ticker="XYZ",
            sector="Software",
            negative_eps=True,
            forward_pe=None,
            ev_ebitda=18.0,
        )
    )
    assert result.primary_metric == "ev_ebitda"
    assert "negative_eps" in result.reasons


def test_peer_regression_computes_r_squared() -> None:
    result = compute_peer_regression(
        x=[10.0, 15.0, 20.0, 25.0],
        y=[12.0, 16.0, 20.0, 24.0],
        subject_x=18.0,
        subject_y=18.5,
    )
    assert result.r_squared is not None
    assert result.r_squared > 0.9


def test_stock_fit_scores_growth_in_quadrant_a() -> None:
    peer = compute_peer_regression(
        x=[10.0, 12.0, 14.0],
        y=[15.0, 18.0, 21.0],
        subject_x=13.0,
        subject_y=18.0,
    )
    result = compute_stock_fit(
        StockSnapshot(
            ticker="ABC",
            sector="Software",
            revenue_growth=22.0,
            earnings_growth=18.0,
            forward_pe=24.0,
            debt_ebitda=1.5,
        ),
        regime="A",
        peer_regression=peer,
    )
    assert result.preferred_archetype == "hyper_growth_manageable_debt"
    assert result.regime_fit_score > 60
