from __future__ import annotations

from app.schemas.indicator_snapshot import SystemicStressInput
from app.services.rules.stress import compute_stress


def test_z1_equities_m2_warning_does_not_trigger_proxy_flag_or_hard_stress() -> None:
    result = compute_stress(
        SystemicStressInput(
            corporate_equities_m2_ratio=7.0,
            corporate_equities_m2_source="fred_z1",
        )
    )
    assert result.stress.proxy_warning_active is False
    assert result.stress_warning_active is False
    assert result.stress_severe is False


def test_spy_fallback_source_sets_proxy_warning_flag() -> None:
    result = compute_stress(
        SystemicStressInput(
            market_cap_m2_ratio=2.2,
            equity_m2_ratio_source="spy_fallback",
            spy_fallback_equity_m2_ratio=2.2,
        )
    )
    assert result.stress.proxy_warning_active is True
    assert result.stress_warning_active is False
    assert result.stress_severe is False


def test_cre_warning_is_separate_from_broad_bank_npl() -> None:
    result = compute_stress(
        SystemicStressInput(
            npl_ratio=0.8,
            cre_delinquency_rate=2.2,
        )
    )
    assert result.stress.npl_zone == "Normal"
    assert result.stress.cre_delinquency_zone == "Warning"
    assert result.stress_warning_active is False
