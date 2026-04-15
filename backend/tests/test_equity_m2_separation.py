from __future__ import annotations

from app.schemas.indicator_snapshot import (
    DollarContextInput,
    GrowthInput,
    InflationInput,
    LiquidityInput,
    SystemicStressInput,
    ValuationInput,
)
from app.services.ingestion.normalizer import compute_equity_m2_views
from app.services.rules.chessboard import compute_chessboard
from app.services.rules.stagflation import compute_stagflation
from app.services.rules.stress import compute_dollar, compute_stress
from app.services.rules.valuation import compute_valuation
from app.services.rules.watchpoints import compute_watchpoint_details


def test_equity_m2_views_keep_z1_and_spy_separate() -> None:
    views = compute_equity_m2_views(
        manual_billions=None,
        z1_millions=5_400_000.0,
        m2_billions=20_000.0,
        sp500_price=600.0,
    )

    assert views["z1_ratio"] == 0.27
    assert views["spy_ratio"] is not None
    assert views["active_ratio"] == views["z1_ratio"]
    assert views["active_source"] == "fred_z1"
    assert views["speaker_ratio"] is None


def test_spy_fallback_does_not_populate_corporate_equities_ratio() -> None:
    views = compute_equity_m2_views(
        manual_billions=None,
        z1_millions=None,
        m2_billions=20_000.0,
        sp500_price=600.0,
    )

    assert views["active_source"] == "spy_fallback"
    assert views["z1_ratio"] is None
    assert views["spy_ratio"] is not None

    result = compute_stress(
        SystemicStressInput(
            yield_curve_10y_2y=-0.25,
            npl_ratio=0.9,
            cre_delinquency_rate=1.0,
            credit_card_chargeoff_rate=2.5,
            market_cap_m2_ratio=views["active_ratio"],
            equity_m2_ratio_source=views["active_source"],
            speaker_market_cap_m2_ratio=views["speaker_ratio"],
            speaker_market_cap_m2_source=views["speaker_source"],
            corporate_equities_m2_ratio=views["z1_ratio"],
            corporate_equities_m2_source=views["z1_source"],
            spy_fallback_equity_m2_ratio=views["spy_ratio"],
            equity_m2_numerator_as_of="2026-04-15",
            equity_m2_numerator_freshness="fresh",
        )
    )

    assert result.stress.market_cap_m2_ratio == views["active_ratio"]
    assert result.stress.corporate_equities_m2_ratio is None
    assert result.stress.spy_fallback_equity_m2_ratio == views["spy_ratio"]
    assert result.stress.proxy_warning_active is True


def test_manual_override_is_explicitly_separated_as_speaker_proxy() -> None:
    views = compute_equity_m2_views(
        manual_billions=45_000.0,
        z1_millions=5_400_000.0,
        m2_billions=20_000.0,
        sp500_price=600.0,
    )

    assert views["speaker_ratio"] == 2.25
    assert views["speaker_source"] == "manual_override"
    assert views["active_ratio"] == 2.25
    assert views["active_source"] == "manual_override"
    assert views["z1_ratio"] == 0.27


def test_spy_fallback_watchpoint_is_explicitly_labeled() -> None:
    cb = compute_chessboard(LiquidityInput())
    stag = compute_stagflation(GrowthInput(), InflationInput())
    val = compute_valuation(ValuationInput())
    stress = compute_stress(
        SystemicStressInput(
            market_cap_m2_ratio=3.1,
            equity_m2_ratio_source="spy_fallback",
            spy_fallback_equity_m2_ratio=3.1,
        )
    )
    dollar = compute_dollar(DollarContextInput())

    details = compute_watchpoint_details(
        cb,
        stag,
        val,
        stress,
        dollar,
        "Quadrant Unknown / Wait",
    )

    assert any("SPY fallback" in detail.text for detail in details)
