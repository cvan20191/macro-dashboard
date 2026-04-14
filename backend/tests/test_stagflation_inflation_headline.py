"""Stagflation inflation headline must not read as 'not sticky' when inputs are missing."""

from __future__ import annotations

from app.schemas.indicator_snapshot import GrowthInput, InflationInput
from app.services.rules.stagflation import compute_stagflation


def _minimal_growth() -> GrowthInput:
    return GrowthInput(
        pmi_manufacturing=51.0,
        pmi_services=51.0,
        unemployment_rate=4.1,
        unemployment_trend="flat",
        initial_claims_trend="flat",
        payrolls_trend="flat",
    )


def test_headline_incomplete_when_core_cpi_missing() -> None:
    inf = InflationInput(
        core_cpi_yoy=None,
        core_cpi_mom=None,
        shelter_status="unknown",
        services_ex_energy_status="unknown",
        wti_oil=90.0,
        oil_risk_active=False,
    )
    r = compute_stagflation(_minimal_growth(), inf)
    assert r.trap.inflation_inputs_incomplete is True
    assert "Not Sticky" not in r.trap.inflation_headline
    assert "incomplete" in r.trap.inflation_headline.lower() or "not confirmed" in r.trap.inflation_headline.lower()


def test_headline_oil_path_when_core_missing() -> None:
    inf = InflationInput(
        core_cpi_yoy=None,
        core_cpi_mom=None,
        shelter_status="unknown",
        services_ex_energy_status="unknown",
        wti_oil=105.0,
        oil_risk_active=True,
    )
    r = compute_stagflation(_minimal_growth(), inf)
    assert "oil" in r.trap.inflation_headline.lower()
    assert "core" in r.trap.inflation_headline.lower()


def test_headline_sticky_when_confirmed() -> None:
    inf = InflationInput(
        core_cpi_yoy=3.5,
        core_cpi_mom=0.2,
        shelter_status="sticky",
        services_ex_energy_status="rising",
        wti_oil=85.0,
        oil_risk_active=False,
    )
    r = compute_stagflation(_minimal_growth(), inf)
    assert r.trap.inflation_inputs_incomplete is False
    assert r.trap.sticky_inflation is True
    assert r.trap.inflation_headline == "Sticky"


def test_headline_not_sticky_confirmed_when_core_low() -> None:
    inf = InflationInput(
        core_cpi_yoy=2.2,
        core_cpi_mom=0.1,
        shelter_status="rising",
        services_ex_energy_status="rising",
        wti_oil=80.0,
        oil_risk_active=False,
    )
    r = compute_stagflation(_minimal_growth(), inf)
    assert r.trap.inflation_inputs_incomplete is False
    assert r.trap.sticky_inflation is False
    assert "not confirmed" in r.trap.inflation_headline.lower()


def test_trap_note_when_inactive_and_incomplete() -> None:
    inf = InflationInput(
        core_cpi_yoy=None,
        core_cpi_mom=None,
        shelter_status=None,
        services_ex_energy_status=None,
        wti_oil=None,
        oil_risk_active=False,
    )
    r = compute_stagflation(_minimal_growth(), inf)
    assert r.trap.active is False
    assert r.trap.trap_assessment_note is not None
    assert "limited" in (r.trap.trap_assessment_note or "").lower()
