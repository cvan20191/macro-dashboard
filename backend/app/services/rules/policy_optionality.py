from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import PolicyOptionality
from app.schemas.indicator_snapshot import GrowthInput, InflationInput

# Internal implementation helpers only. These are not surfaced as doctrine laws.
_LABOR_SLACK_PRESENT_UR = 4.8
_LABOR_SLACK_ABSENT_UR = 4.3
_INFLATION_COOLING_CORE_CPI = 2.6
_INFLATION_STICKY_CORE_CPI = 3.0


@dataclass(frozen=True)
class PolicyOptionalityResult:
    optionality: PolicyOptionality
    constraint_level: str
    fed_can_ease: bool
    fed_trapped: bool
    bad_data_is_good_enabled: bool


def _labor_slack_state(growth: GrowthInput) -> str:
    ur = growth.unemployment_rate
    ut = (growth.unemployment_trend or "").lower()
    ict = (growth.initial_claims_trend or "").lower()

    if ur is None:
        return "unknown"
    if ur >= _LABOR_SLACK_PRESENT_UR:
        return "present"
    if ut == "up" and ict == "up":
        return "present"
    if ur <= _LABOR_SLACK_ABSENT_UR and ut != "up" and ict != "up":
        return "absent"
    return "mixed"


def _inflation_state(inflation: InflationInput) -> str:
    core = inflation.core_cpi_yoy
    shelter = (inflation.shelter_status or "").lower()
    services = (inflation.services_ex_energy_status or "").lower()
    oil_risk = bool(inflation.oil_risk_active)

    if core is None:
        return "unknown"
    if (
        core <= _INFLATION_COOLING_CORE_CPI
        and shelter != "sticky"
        and services != "sticky"
        and not oil_risk
    ):
        return "cooling"
    if (
        core >= _INFLATION_STICKY_CORE_CPI
        or shelter == "sticky"
        or services == "sticky"
        or oil_risk
    ):
        return "sticky_or_hot"
    return "mixed"


def compute_policy_optionality(
    growth: GrowthInput,
    inflation: InflationInput,
) -> PolicyOptionalityResult:
    labor_slack_state = _labor_slack_state(growth)
    inflation_state = _inflation_state(inflation)

    if labor_slack_state == "absent" and inflation_state == "sticky_or_hot":
        constraint_level = "trapped"
        note = (
            "Weak data is not automatically bullish because inflation is still sticky/hot "
            "and labor slack is not clearly present."
        )
    elif labor_slack_state == "present" and inflation_state == "cooling":
        constraint_level = "free"
        note = "The Fed has room to ease because labor slack is present and inflation is cooling."
    elif labor_slack_state == "unknown" or inflation_state == "unknown":
        constraint_level = "unknown"
        note = "Policy optionality cannot be determined cleanly from the current inputs."
    else:
        constraint_level = "limited"
        note = (
            "The Fed may have some room to ease, but the labor/inflation mix is not clean enough "
            "to treat bad data as automatically bullish."
        )

    fed_can_ease = constraint_level in {"free", "limited"}
    fed_trapped = constraint_level == "trapped"
    bad_data_is_good_enabled = constraint_level == "free"

    optionality = PolicyOptionality(
        constraint_level=constraint_level,
        labor_slack_state=labor_slack_state,
        inflation_state=inflation_state,
        fed_can_ease=fed_can_ease,
        fed_trapped=fed_trapped,
        bad_data_is_good_enabled=bad_data_is_good_enabled,
        note=note,
    )

    return PolicyOptionalityResult(
        optionality=optionality,
        constraint_level=constraint_level,
        fed_can_ease=fed_can_ease,
        fed_trapped=fed_trapped,
        bad_data_is_good_enabled=bad_data_is_good_enabled,
    )
