from __future__ import annotations

from dataclasses import dataclass

from app.schemas.dashboard_state import ExitDisciplineSignal
from app.services.rules.chessboard import ChessboardResult


@dataclass(frozen=True)
class ExitDisciplineResult:
    signal: ExitDisciplineSignal
    active: bool


def compute_exit_discipline_signal(cb: ChessboardResult) -> ExitDisciplineResult:
    """
    Transcript-faithful exit discipline for the Regime A / stock D-type setup.

    The speaker's rule is not a generic stop-loss. It is:
    - in the most liquid regime, hyper-growth / highly levered profiles can work best
    - but any sign of rates turning back up or liquidity support fading should trigger exit discipline
    """
    if cb.quadrant != "A":
        signal = ExitDisciplineSignal(
            active=False,
            scope="none",
            rate_reversal_watch_active=False,
            qe_fade_watch_active=False,
            note=None,
        )
        return ExitDisciplineResult(signal=signal, active=False)

    rate_reversal_watch_active = cb.chessboard.rate_impulse_short == "mixed"
    qe_fade_watch_active = cb.chessboard.balance_sheet_pace == "expanding_slower"
    active = rate_reversal_watch_active or qe_fade_watch_active

    note_parts: list[str] = []
    if rate_reversal_watch_active:
        note_parts.append("Short-rate impulse is no longer cleanly supportive.")
    if qe_fade_watch_active:
        note_parts.append("Balance-sheet expansion pace is slowing.")

    note = None
    if active:
        note = (
            "Exit discipline active for the A-regime / stock-D profile. "
            + " ".join(note_parts)
            + " Reduce risk if broader liquidity support stops confirming."
        )

    signal = ExitDisciplineSignal(
        active=active,
        scope="stock_d_type_a_regime",
        rate_reversal_watch_active=rate_reversal_watch_active,
        qe_fade_watch_active=qe_fade_watch_active,
        note=note,
    )
    return ExitDisciplineResult(signal=signal, active=active)
