from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.services.rules.speaker_forward_pe import compute_speaker_forward_pe


_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "equity_cohort_registry.json"


@dataclass(frozen=True)
class CohortForwardPEBasket:
    cohort_code: str
    label: str
    note: str | None
    tickers: list[str]
    forward_pe: float | None
    current_year_forward_pe: float | None
    next_year_forward_pe: float | None
    selected_year: int | None
    horizon_label: str | None
    signal_mode: str
    coverage_count: int
    coverage_ratio: float
    basis_confidence: float | None


def load_equity_cohort_registry() -> dict[str, dict[str, Any]]:
    raw = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("equity_cohort_registry.json must contain an object.")
    return raw


def _cohort_note(label: str, note: str | None) -> str | None:
    if note is None:
        return None
    return note.replace("Mag 7", label)


def compute_cohort_forward_pe_baskets(
    *,
    payloads: list[dict[str, Any]],
    as_of: date,
    registry: dict[str, dict[str, Any]] | None = None,
) -> list[CohortForwardPEBasket]:
    resolved_registry = registry or load_equity_cohort_registry()
    payload_by_ticker = {
        str(payload.get("ticker")): payload for payload in payloads if payload.get("ticker")
    }

    baskets: list[CohortForwardPEBasket] = []
    for cohort_code, config in resolved_registry.items():
        tickers = [str(ticker) for ticker in config.get("tickers", [])]
        cohort_payloads = [payload_by_ticker[ticker] for ticker in tickers if ticker in payload_by_ticker]
        result = compute_speaker_forward_pe(cohort_payloads, as_of=as_of)
        baskets.append(
            CohortForwardPEBasket(
                cohort_code=cohort_code,
                label=str(config.get("label") or cohort_code),
                note=_cohort_note(str(config.get("label") or cohort_code), result.note),
                tickers=tickers,
                forward_pe=result.speaker_forward_pe,
                current_year_forward_pe=result.current_year_forward_pe,
                next_year_forward_pe=result.next_year_forward_pe,
                selected_year=result.selected_year,
                horizon_label=result.horizon_label if result.valid else None,
                signal_mode=result.signal_mode,
                coverage_count=result.coverage_count,
                coverage_ratio=result.coverage_ratio,
                basis_confidence=result.basis_confidence,
            )
        )

    return baskets
