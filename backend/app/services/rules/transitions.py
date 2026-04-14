"""
What Changed & What Changes the Call — Module 9 & 10.

Both functions return exactly 3 bullets grounded in indicator trends and
the current regime. No LLM involvement.
"""

from __future__ import annotations

from app.schemas.dashboard_state import ReasonedText
from app.schemas.indicator_snapshot import IndicatorSnapshot
from app.services.rules.chessboard import ChessboardResult
from app.services.rules.regime import RegimeResult
from app.services.rules.stagflation import StagflationResult
from app.services.rules.stress import StressResult
from app.services.rules.valuation import ValuationResult

_FILLER_CHANGED = "No significant recent change detected for this indicator"
_FILLER_TRIGGER = "No additional change trigger identified"


def compute_what_changed_details(
    snapshot: IndicatorSnapshot,
    cb: ChessboardResult,
    stag: StagflationResult,
    val: ValuationResult,
    stress: StressResult,
) -> list[ReasonedText]:
    """Return exactly 3 bullets describing recent changes in indicator state."""
    bullets: list[ReasonedText] = []

    liq = snapshot.liquidity
    infl = snapshot.inflation

    # Rate direction
    r1 = (liq.rate_trend_1m or "").lower()
    if r1 == "down":
        bullets.append(ReasonedText(code="rates_softened_1m", text="Rate direction has softened over the last month"))
    elif r1 == "up":
        bullets.append(ReasonedText(code="rates_higher_1m", text="Rates moved higher over the last month, adding pressure to valuations"))
    elif r1 == "flat":
        bullets.append(ReasonedText(code="rates_flat_1m", text="Rates have held steady — no material change in the cost of capital"))
    elif r1 == "mixed":
        bullets.append(ReasonedText(code="rates_mixed_1m", text="Rate direction is mixed across short and medium windows — policy impulse is less clear than a month ago"))

    # Balance sheet
    b1 = (liq.balance_sheet_trend_1m or "").lower()
    if b1 == "down":
        bullets.append(ReasonedText(code="balance_sheet_contracting", text="Fed balance sheet is still contracting — net liquidity support has not arrived"))
    elif b1 == "flat":
        bullets.append(ReasonedText(code="balance_sheet_flat", text="Balance-sheet contraction has paused; while liquidity remains supportive, the trend has not yet clearly turned into a sustained expansion."))
    elif b1 == "up":
        bullets.append(ReasonedText(code="balance_sheet_expanding", text="Fed balance sheet has begun expanding — a liquidity tailwind is building"))

    # Oil
    if stag.oil_risk_active:
        wti = infl.wti_oil
        wti_str = f" at ${wti:.0f}" if wti else ""
        bullets.append(ReasonedText(code="oil_risk_active", text=f"WTI crude{wti_str} has moved into the speaker's inflation-risk zone"))
    elif infl.wti_oil is not None and infl.wti_oil < 100 and infl.wti_oil > 85:
        bullets.append(ReasonedText(code="oil_near_threshold", text=f"WTI crude at ${infl.wti_oil:.0f} — below the risk threshold but worth monitoring"))

    # Valuation
    _is_proxy = val.valuation.is_fallback
    _val_label = "Proxy valuation" if _is_proxy else "Forward valuation"
    _proxy_note = " (directional proxy — confirm with true Forward P/E before acting)" if _is_proxy else ""
    if val.is_stretched:
        pe = val.valuation.forward_pe
        pe_str = f" at {pe:.1f}x" if pe else ""
        bullets.append(ReasonedText(code="valuation_stretched", text=f"{_val_label} remains stretched{pe_str} — above the pause threshold{_proxy_note}"))
    elif val.is_buy_zone:
        bullets.append(ReasonedText(code="valuation_buy_zone", text=f"{_val_label} has compressed into the historical accumulation zone{_proxy_note}"))

    # Unemployment trend
    u_trend = (snapshot.growth.unemployment_trend or "").lower()
    if u_trend == "up":
        bullets.append(ReasonedText(code="unemployment_up", text="Labor slack is beginning to build — unemployment has been trending higher"))
    elif u_trend == "down":
        bullets.append(ReasonedText(code="unemployment_down", text="Labor market has tightened — unemployment is still falling"))

    # PMI contraction
    pmi = snapshot.growth.pmi_manufacturing
    if pmi is not None and pmi < 50:
        bullets.append(ReasonedText(code="manufacturing_pmi_contraction", text=f"Manufacturing PMI at {pmi:.1f} — remains in contraction territory"))

    # Yield curve
    if stress.stress.yield_curve_inverted:
        yc = stress.stress.yield_curve_value
        yc_str = f" at {yc:.2f}%" if yc is not None else ""
        bullets.append(ReasonedText(code="yield_curve_inverted", text=f"Yield curve remains inverted{yc_str} — recession-watch signal persists"))

    # CPI stickiness
    cpi = snapshot.inflation.core_cpi_yoy
    if cpi is not None and cpi > 3.0:
        bullets.append(ReasonedText(code="core_cpi_sticky", text=f"Core CPI at {cpi:.1f}% — remains above the speaker's sticky threshold"))

    # Pad or truncate to exactly 3
    while len(bullets) < 3:
        bullets.append(ReasonedText(code="no_significant_change", text=_FILLER_CHANGED))
    return bullets[:3]


def compute_what_changed(
    snapshot: IndicatorSnapshot,
    cb: ChessboardResult,
    stag: StagflationResult,
    val: ValuationResult,
    stress: StressResult,
) -> list[str]:
    return [item.text for item in compute_what_changed_details(snapshot, cb, stag, val, stress)]


def compute_what_changes_call_details(
    regime_result: RegimeResult,
    val: ValuationResult,
    stag: StagflationResult,
    stress: StressResult,
    cb: ChessboardResult,
) -> list[ReasonedText]:
    """Return exactly 3 trigger bullets that would change the current posture."""
    bullets: list[ReasonedText] = []

    regime = regime_result.legacy_regime_label or regime_result.primary_regime

    # Valuation trigger
    _is_proxy = val.valuation.is_fallback
    _confirm_note = " — confirm with true Forward P/E before acting" if _is_proxy else ""
    if val.is_stretched:
        bullets.append(ReasonedText(code="valuation_compresses_below_25x", text=f"{'Proxy valuation' if _is_proxy else 'Forward P/E'} compresses below 25x through earnings growth or a price reset{_confirm_note}"))
    elif val.is_buy_zone:
        bullets.append(ReasonedText(code="valuation_moves_above_buy_zone", text=f"{'Proxy valuation' if _is_proxy else 'Valuation'} moves back above the buy zone — reassess accumulation pace{_confirm_note}"))
    else:
        bullets.append(ReasonedText(code="valuation_enters_buy_zone", text=f"{'Proxy valuation' if _is_proxy else 'Forward P/E'} falls into the 20–25x accumulation zone — a cleaner entry signal{_confirm_note}"))

    # Inflation / oil trigger
    if stag.oil_risk_active:
        bullets.append(ReasonedText(code="oil_risk_resolves", text="WTI crude drops back below $100 and sustains lower — removing the oil inflation risk"))
    if stag.sticky_inflation:
        bullets.append(ReasonedText(code="core_services_rollover", text="Core services inflation decisively rolls over toward the 2.5% range"))

    # Liquidity trigger
    bs = cb.chessboard.balance_sheet_trend_1m
    if bs in {"down", "flat"}:
        bullets.append(ReasonedText(code="balance_sheet_turns_expansionary", text="Fed balance sheet turns clearly expansionary for multiple consecutive weeks"))
    elif bs == "up":
        bullets.append(ReasonedText(code="balance_sheet_expansion_stalls", text="Fed balance sheet expansion reverses or stalls — reducing the liquidity tailwind"))

    # Trap / labor trigger
    if stag.trap.active:
        bullets.append(ReasonedText(code="cleaner_cut_window_reopens", text="Unemployment rises enough to reopen a cleaner rate-cut path, or CPI falls below 3%"))

    # Stress triggers
    if stress.stress.yield_curve_inverted:
        bullets.append(ReasonedText(code="yield_curve_uninverts", text="Yield curve un-inverts as growth expectations improve alongside falling short rates"))
    if stress.stress.npl_zone in {"Caution", "Warning"}:
        bullets.append(ReasonedText(code="broad_bank_npl_worsens", text=f"NPL ratio accelerates toward or past the {1.5:.1f}% warning threshold"))

    # Regime-specific additions
    if regime == "Crash Watch":
        bullets.append(ReasonedText(code="systemic_stress_stabilizes", text="Systemic stress gauges stabilize or reverse — NPL and card charge-offs stop worsening"))
    if regime_result.primary_regime == "Quadrant A / Max Liquidity":
        bullets.append(ReasonedText(code="inflation_reaccelerates", text="Inflation re-accelerates and forces the Fed to pause or reverse cuts"))

    while len(bullets) < 3:
        bullets.append(ReasonedText(code="no_additional_trigger", text=_FILLER_TRIGGER))
    return bullets[:3]


def compute_what_changes_call(
    regime_result: RegimeResult,
    val: ValuationResult,
    stag: StagflationResult,
    stress: StressResult,
    cb: ChessboardResult,
) -> list[str]:
    return [item.text for item in compute_what_changes_call_details(regime_result, val, stag, stress, cb)]
