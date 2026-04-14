from __future__ import annotations

from app.schemas.indicator_snapshot import PlumbingInput
from app.services.rules.liquidity_plumbing import compute_liquidity_plumbing


def test_plumbing_stress_marks_walcl_uptick_as_not_qe() -> None:
    result = compute_liquidity_plumbing(
        PlumbingInput(
            total_reserves=2800.0,
            reserves_trend_1m="down",
            reserves_buffer_ratio=0.96,
            repo_total=150.0,
            repo_trend_1m="up",
            repo_spike_ratio=2.75,
            reverse_repo_total=90.0,
            reverse_repo_trend_1m="down",
            reverse_repo_buffer_ratio=0.22,
            walcl_trend_1m="up",
        )
    )

    assert result.state == "severe"
    assert result.balance_sheet_expansion_not_qe is True
    assert result.plumbing.state == "severe"
    assert "not QE" in (result.plumbing.caution_note or "")


def test_plumbing_caution_when_repo_rises_and_reserves_fall() -> None:
    result = compute_liquidity_plumbing(
        PlumbingInput(
            total_reserves=2950.0,
            reserves_trend_1m="down",
            reserves_buffer_ratio=0.99,
            repo_total=45.0,
            repo_trend_1m="up",
            repo_spike_ratio=1.25,
            reverse_repo_total=180.0,
            reverse_repo_trend_1m="flat",
            reverse_repo_buffer_ratio=0.80,
            walcl_trend_1m="flat",
        )
    )

    assert result.state == "elevated"
    assert result.balance_sheet_expansion_not_qe is False


def test_plumbing_normal_when_buffers_are_stable() -> None:
    result = compute_liquidity_plumbing(
        PlumbingInput(
            total_reserves=3100.0,
            reserves_trend_1m="flat",
            reserves_buffer_ratio=1.01,
            repo_total=5.0,
            repo_trend_1m="flat",
            repo_spike_ratio=0.90,
            reverse_repo_total=250.0,
            reverse_repo_trend_1m="flat",
            reverse_repo_buffer_ratio=0.95,
            walcl_trend_1m="down",
        )
    )

    assert result.state == "normal"
    assert result.balance_sheet_expansion_not_qe is False


def test_plumbing_unknown_when_inputs_missing() -> None:
    result = compute_liquidity_plumbing(PlumbingInput())

    assert result.state == "unknown"
    assert result.plumbing.state == "unknown"
