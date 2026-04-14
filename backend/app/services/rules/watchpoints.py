"""
Top Watchpoints Ranker — Module 8.

Scores a deterministic candidate list and returns the top 3.
"""

from __future__ import annotations

from app.schemas.dashboard_state import ReasonedText
from app.services.rules.chessboard import ChessboardResult
from app.services.rules.liquidity_plumbing import LiquidityPlumbingResult
from app.services.rules.stagflation import StagflationResult
from app.services.rules.stress import DollarResult, StressResult
from app.services.rules.valuation import ValuationResult


def compute_watchpoint_details(
    cb: ChessboardResult,
    stag: StagflationResult,
    val: ValuationResult,
    stress: StressResult,
    dollar: DollarResult,
    regime: str,
    plumbing: LiquidityPlumbingResult | None = None,
) -> list[ReasonedText]:
    """Return exactly 3 watchpoint strings ranked by current relevance."""
    candidates: list[tuple[int, str, str]] = []

    # ── WTI Oil ──────────────────────────────────────────────────────────────
    wti = stag.trap.wti_oil
    if wti is not None:
        if stag.oil_risk_active:
            candidates.append((90, "oil_risk_active", f"WTI crude is holding above $100 — inflation-risk zone active"))
        elif wti >= 95:
            candidates.append((60, "oil_near_threshold", f"WTI crude near $100 threshold at ${wti:.0f}"))
        else:
            candidates.append((20, "oil_below_threshold", f"WTI crude at ${wti:.0f} — below inflation-risk threshold"))

    # ── Shelter / Services CPI ───────────────────────────────────────────────
    if (stag.trap.shelter_status or "").lower() == "sticky":
        candidates.append((85, "shelter_sticky", "Shelter CPI is not rolling over — services inflation remains sticky"))
    if (stag.trap.services_ex_energy_status or "").lower() == "sticky":
        candidates.append((80, "services_ex_energy_sticky", "Services ex-energy inflation is still elevated and not easing"))

    # ── Forward Valuation ────────────────────────────────────────────────────
    pe = val.valuation.forward_pe
    if pe is not None:
        _is_proxy = val.valuation.is_fallback
        _pe_label = "Proxy valuation" if _is_proxy else "Forward big-tech P/E"
        _proxy_suffix = " (directional proxy — apply softer interpretation)" if _is_proxy else ""
        if val.is_stretched:
            candidates.append((88, "valuation_stretched", f"{_pe_label} at {pe:.1f}x — above the speaker's pause threshold{_proxy_suffix}"))
        elif 25 < pe < 30:
            candidates.append((55, "valuation_approaching_stretch", f"{_pe_label} at {pe:.1f}x — approaching the stretched zone{_proxy_suffix}"))
        elif val.is_buy_zone:
            candidates.append((40, "valuation_buy_zone", f"{_pe_label} at {pe:.1f}x — inside the historical accumulation zone{_proxy_suffix}"))

    # ── Fed Balance Sheet ─────────────────────────────────────────────────────
    bs = cb.chessboard.balance_sheet_trend_1m
    if bs == "down":
        candidates.append((75, "balance_sheet_contracting", "Fed balance sheet is still contracting — net liquidity withdrawal ongoing"))
    elif bs == "flat":
        candidates.append((55, "balance_sheet_flat", "Fed balance sheet is flat — contraction has paused but not reversed"))
    elif bs == "up":
        candidates.append((30, "balance_sheet_expanding", "Fed balance sheet is expanding — liquidity is being injected"))

    # ── Unemployment ─────────────────────────────────────────────────────────
    unemp = stag.trap.unemployment_rate
    if unemp is not None:
        if unemp > 4.3:
            candidates.append((70, "unemployment_above_trap_band", f"Unemployment at {unemp:.1f}% — rising above the Fed's tolerated range"))
        elif 4.0 <= unemp <= 4.3:
            candidates.append((65, "unemployment_trap_band", f"Unemployment at {unemp:.1f}% — in the trap band; not weak enough to justify easy cuts"))

    # ── Core CPI ─────────────────────────────────────────────────────────────
    cpi = stag.trap.core_cpi_yoy
    if cpi is not None:
        if cpi > 3.0:
            candidates.append((78, "core_cpi_sticky", f"Core CPI at {cpi:.1f}% YoY — above the speaker's sticky threshold"))
        elif 2.5 <= cpi <= 3.0:
            candidates.append((50, "core_cpi_near_sticky", f"Core CPI at {cpi:.1f}% — approaching the sticky threshold"))

    # ── NPL Ratio ────────────────────────────────────────────────────────────
    npl = stress.stress.npl_ratio
    if npl is not None:
        if stress.stress.npl_zone == "Warning":
            candidates.append((82, "broad_bank_npl_warning", f"Bank NPL ratio at {npl:.2f}% — above systemic warning threshold"))
        elif stress.stress.npl_zone == "Caution":
            candidates.append((58, "broad_bank_npl_caution", f"Bank NPL ratio at {npl:.2f}% — entering caution band"))

    # ── Credit card charge-offs ─────────────────────────────────────────────
    cc = stress.stress.credit_card_chargeoff_rate
    if cc is not None:
        if stress.stress.credit_card_chargeoff_zone == "Warning":
            candidates.append((80, "credit_card_stress_warning", f"Credit card charge-off rate at {cc:.2f}% — consumer credit stress elevated"))
        elif stress.stress.credit_card_chargeoff_zone == "Caution":
            candidates.append((52, "credit_card_stress_caution", f"Credit card charge-off rate at {cc:.2f}% — watch consumer credit"))

    # ── Z.1 equities / M2 (or legacy SPY proxy) ─────────────────────────────
    mcm2 = stress.stress.corporate_equities_m2_ratio
    if mcm2 is not None:
        label = (
            "Corporate equities/M2 proxy (Z.1)"
            if stress.stress.equity_m2_ratio_source != "spy_fallback"
            else "Corporate equities/M2 proxy (SPY fallback)"
        )
        if stress.stress.corporate_equities_m2_zone == "Extreme":
            candidates.append((88, "corporate_equities_m2_extreme", f"{label} at {mcm2:.2f} — in extreme froth territory"))
        elif stress.stress.corporate_equities_m2_zone == "Warning":
            candidates.append((65, "corporate_equities_m2_warning", f"{label} at {mcm2:.2f} — above the proxy warning level"))

    # ── Yield Curve ──────────────────────────────────────────────────────────
    yc = stress.stress.yield_curve_value
    if yc is not None and stress.stress.yield_curve_inverted:
        candidates.append((72, "yield_curve_inverted", f"Yield curve inverted at {yc:.2f}% — recession-watch signal active"))

    # ── DXY ──────────────────────────────────────────────────────────────────
    dxy = dollar.dollar.dxy
    if dxy is not None and dollar.dxy_pressure:
        candidates.append((48, "dxy_pressure", f"DXY at {dxy:.1f} — strong dollar adding macro friction"))

    # ── Chessboard direction ─────────────────────────────────────────────────
    if cb.liquidity_tight and cb.quadrant == "D":
        candidates.append((70, "quadrant_d_tight", "Fed Chessboard is in max illiquidity — rates elevated, balance sheet contracting"))
    elif cb.quadrant == "C" and cb.chessboard.balance_sheet_pace == "contracting_slower":
        candidates.append((62, "qt_still_contracting_but_slowing", "The balance sheet is still contracting, but the pace is slowing — a transition signal, not full expansion"))

    # ── Plumbing overlay ─────────────────────────────────────────────────────
    if plumbing is not None and plumbing.state in {"elevated", "severe"}:
        if plumbing.state == "severe":
            candidates.append((89, "repo_reserve_plumbing_stress", "Repo / reverse-repo / reserve plumbing is showing clear funding stress — treat any balance-sheet lift as plumbing support, not QE"))
        else:
            candidates.append((68, "repo_reserve_plumbing_caution", "Repo / reverse-repo / reserve plumbing is tightening — balance-sheet stabilization here may be support, not clean QE"))

    # Sort descending, deduplicate, take top 3
    candidates.sort(key=lambda x: x[0], reverse=True)

    seen_starts: set[str] = set()
    unique: list[ReasonedText] = []
    for _, code, text in candidates:
        key = text[:30]
        if key not in seen_starts:
            seen_starts.add(key)
            unique.append(ReasonedText(code=code, text=text))
        if len(unique) == 3:
            break

    # Pad to exactly 3 if fewer candidates exist
    fallbacks = [
        ReasonedText(code="monitor_chessboard_shift", text="Monitor the Fed Chessboard for any shift in rate or balance sheet direction"),
        ReasonedText(code="monitor_core_cpi_rollover", text="Watch Core CPI for signs of rolling over toward the 2.5% zone"),
        ReasonedText(code="monitor_forward_pe", text="Track forward big-tech P/E for compression into the buy-zone range"),
    ]
    for fb in fallbacks:
        if len(unique) >= 3:
            break
        unique.append(fb)

    return unique[:3]


def compute_watchpoints(
    cb: ChessboardResult,
    stag: StagflationResult,
    val: ValuationResult,
    stress: StressResult,
    dollar: DollarResult,
    regime: str,
    plumbing: LiquidityPlumbingResult | None = None,
) -> list[str]:
    return [item.text for item in compute_watchpoint_details(cb, stag, val, stress, dollar, regime, plumbing)]
