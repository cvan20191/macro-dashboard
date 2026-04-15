from app.schemas.indicator_snapshot import GrowthInput, InflationInput
from app.services.rules.policy_optionality import compute_policy_optionality


def test_policy_optionality_trapped_when_labor_is_tight_and_inflation_is_sticky() -> None:
    growth = GrowthInput(
        pmi_manufacturing=49.0,
        pmi_services=52.0,
        unemployment_rate=4.1,
        unemployment_trend="flat",
        initial_claims_trend="flat",
        payrolls_trend="down",
    )
    inflation = InflationInput(
        core_cpi_yoy=3.1,
        core_cpi_mom=0.3,
        shelter_status="sticky",
        services_ex_energy_status="sticky",
        wti_oil=85.0,
        oil_risk_active=False,
    )

    result = compute_policy_optionality(growth, inflation)

    assert result.constraint_level == "trapped"
    assert result.fed_trapped is True
    assert result.fed_can_ease is False
    assert result.bad_data_is_good_enabled is False


def test_policy_optionality_free_when_labor_slack_and_inflation_cooling() -> None:
    growth = GrowthInput(
        pmi_manufacturing=48.0,
        pmi_services=49.0,
        unemployment_rate=5.0,
        unemployment_trend="up",
        initial_claims_trend="up",
        payrolls_trend="down",
    )
    inflation = InflationInput(
        core_cpi_yoy=2.4,
        core_cpi_mom=0.2,
        shelter_status="easing",
        services_ex_energy_status="easing",
        wti_oil=70.0,
        oil_risk_active=False,
    )

    result = compute_policy_optionality(growth, inflation)

    assert result.constraint_level == "free"
    assert result.fed_trapped is False
    assert result.fed_can_ease is True
    assert result.bad_data_is_good_enabled is True
