from __future__ import annotations

from app.schemas.indicator_snapshot import SystemicStressInput
from app.services.rules.stress import compute_stress


def test_proxy_equities_m2_does_not_trigger_hard_stress_flags() -> None:
    result = compute_stress(
        SystemicStressInput(
            corporate_equities_m2_ratio=7.0,
            corporate_equities_m2_source="fred_z1",
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
