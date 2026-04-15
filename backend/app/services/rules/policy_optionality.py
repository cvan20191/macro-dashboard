from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import PolicyOptionality
from app.schemas.indicator_snapshot import GrowthInput, InflationInput

# Transcript-anchored implementation helpers.
# These remain implementation helpers, but they follow the transcript's
# explicit easing and weird-cut anchor points instead of generic smoothing.
_LABOR_SLACK_PRESENT_UR = 5.0
_LABOR_SLACK_ABSENT_UR = 4.3
_HEADLINE_CPI_COOLING = 2.5
_INFLATION_STICKY_CORE_CPI = 3.0
_SERVICES_RESILIENT_PMI = 50.0


@dataclass(frozen=True)
class PolicyOptionalityResult:
    optionality: PolicyOptionality
    constraint_level: str
    fed_can_ease: bool
    fed_trapped: bool
    bad_data_is_good_enabled: bool
    rate_cut_weirdness_active: bool


def _labor_slack_state(growth: GrowthInput) -> str:
    ur = growth.unemployment_rate
    ut = (growth.unemployment_trend or "").lower()
    ict = (growth.initial_claims_trend or "").lower()

    if ur is None:
        return "unknown"
    if ur >= _LABOR_SLACK_PRESENT_UR:
        return "present"
    # Labor slack can already be emerging even before the level fully reaches
    # the 5% area when unemployment and claims are both worsening.
    if ut == "up" and ict == "up":
        return "present"
    if ur <= _LABOR_SLACK_ABSENT_UR and ut != "up" and ict != "up":
        return "absent"
    return "mixed"


def _labor_balance_state(growth: GrowthInput) -> str:
    """
    Separate weak payroll creation from the unemployment-rate read so we can
    identify the transcript's "weird cut" setup.
    """
    ur = growth.unemployment_rate
    payrolls = (growth.payrolls_trend or "").lower()
    services_pmi = growth.pmi_services

    if ur is None:
        return "unknown"
    if ur <= _LABOR_SLACK_ABSENT_UR and payrolls == "down":
        return "weak_jobs_tight_ur"
    if ur >= _LABOR_SLACK_PRESENT_UR and payrolls == "down":
        return "clean_slack"
    if services_pmi is not None and services_pmi >= _SERVICES_RESILIENT_PMI and ur <= _LABOR_SLACK_ABSENT_UR:
        return "weak_jobs_tight_ur"
    return "mixed"


def _inflation_state(inflation: InflationInput) -> str:
    headline = inflation.headline_cpi_yoy
    core = inflation.core_cpi_yoy
    shelter = (inflation.shelter_status or "").lower()
    services = (inflation.services_ex_energy_status or "").lower()
    oil_risk = bool(inflation.oil_risk_active)

    if headline is None and core is None:
        return "unknown"
    if (
        headline is not None
        and headline <= _HEADLINE_CPI_COOLING
        and (core is None or core < _INFLATION_STICKY_CORE_CPI)
        and shelter not in {"sticky", "hot"}
        and services not in {"sticky", "hot"}
        and not oil_risk
    ):
        return "cooling"
    if (
        core >= _INFLATION_STICKY_CORE_CPI
        or shelter in {"sticky", "hot"}
        or services in {"sticky", "hot"}
        or oil_risk
    ):
        return "sticky_or_hot"
    return "mixed"


def compute_policy_optionality(
    growth: GrowthInput,
    inflation: InflationInput,
) -> PolicyOptionalityResult:
    labor_slack_state = _labor_slack_state(growth)
    labor_balance_state = _labor_balance_state(growth)
    inflation_state = _inflation_state(inflation)
    services_resilient = growth.pmi_services is not None and growth.pmi_services >= _SERVICES_RESILIENT_PMI

    rate_cut_weirdness_active = (
        labor_balance_state == "weak_jobs_tight_ur"
        and inflation_state == "sticky_or_hot"
        and services_resilient
    )

    if labor_slack_state == "absent" and inflation_state == "sticky_or_hot":
        constraint_level = "trapped"
        note = (
            "Inflation is still sticky/hot while unemployment remains very low. "
            "This is a constrained reaction-function backdrop."
        )
    elif labor_slack_state == "present" and inflation_state == "cooling":
        constraint_level = "free"
        note = (
            "Labor slack is present and CPI is cooling toward the easing backdrop. "
            "The Fed has room to ease."
        )
    elif labor_slack_state == "unknown" or inflation_state == "unknown":
        constraint_level = "unknown"
        note = "Policy optionality cannot be determined cleanly from current inputs."
    else:
        constraint_level = "limited"
        note = (
            "The Fed may have some room to ease, but the labor/inflation mix is not clean enough "
            "to treat bad data as automatically bullish."
        )

    fed_can_ease = constraint_level in {"free", "limited"}
    fed_trapped = constraint_level == "trapped"
    bad_data_is_good_enabled = constraint_level == "free"

    if rate_cut_weirdness_active:
        weird_cut_note = (
            " Payroll creation is weak while unemployment is still very low and services remain resilient; "
            "this is a weird-cut / low-room setup."
        )
        note = f"{note}{weird_cut_note}" if note else weird_cut_note.strip()

    optionality = PolicyOptionality(
        constraint_level=constraint_level,
        labor_slack_state=labor_slack_state,
        labor_balance_state=labor_balance_state,
        inflation_state=inflation_state,
        fed_can_ease=fed_can_ease,
        fed_trapped=fed_trapped,
        bad_data_is_good_enabled=bad_data_is_good_enabled,
        rate_cut_weirdness_active=rate_cut_weirdness_active,
        note=note,
    )

    return PolicyOptionalityResult(
        optionality=optionality,
        constraint_level=constraint_level,
        fed_can_ease=fed_can_ease,
        fed_trapped=fed_trapped,
        bad_data_is_good_enabled=bad_data_is_good_enabled,
        rate_cut_weirdness_active=rate_cut_weirdness_active,
    )
