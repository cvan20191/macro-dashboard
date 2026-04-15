from datetime import date

from app.services.rules.speaker_forward_pe import compute_speaker_forward_pe


def _payload(
    ticker: str,
    *,
    price: float = 100.0,
    shares: float = 10.0,
    current_eps: float | None = 5.0,
    next_eps: float | None = 6.0,
) -> dict:
    annual_eps_by_year: dict[int, float] = {}
    estimate_dates_by_year: dict[int, str] = {}

    if current_eps is not None:
        annual_eps_by_year[2026] = current_eps
        estimate_dates_by_year[2026] = "2026-12-31"

    if next_eps is not None:
        annual_eps_by_year[2027] = next_eps
        estimate_dates_by_year[2027] = "2027-12-31"

    return {
        "ticker": ticker,
        "price": price,
        "shares": shares,
        "annual_eps_by_year": annual_eps_by_year,
        "estimate_dates_by_year": estimate_dates_by_year,
        "estimate_as_of": "2026-04-15",
    }


def test_selects_current_year_when_not_near_year_end() -> None:
    payloads = [
        _payload("AAA"),
        _payload("BBB"),
        _payload("CCC"),
        _payload("DDD"),
        _payload("EEE"),
        _payload("FFF"),
        _payload("GGG"),
    ]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 6, 1))

    assert result.valid is True
    assert result.selected_year == 2026
    assert result.horizon_label == "speaker_fye_proximity_current_year"
    assert result.speaker_forward_pe == result.current_year_forward_pe


def test_selects_next_year_when_weighted_days_to_fye_are_near_year_end() -> None:
    payloads = [
        _payload("AAA"),
        _payload("BBB"),
        _payload("CCC"),
        _payload("DDD"),
        _payload("EEE"),
        _payload("FFF"),
        _payload("GGG"),
    ]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 10, 15))

    assert result.valid is True
    assert result.selected_year == 2027
    assert result.horizon_label == "speaker_fye_proximity_next_year"
    assert result.speaker_forward_pe == result.next_year_forward_pe


def test_selected_year_incomplete_is_directional_only() -> None:
    payloads = [
        _payload("AAA"),
        _payload("BBB"),
        _payload("CCC"),
        _payload("DDD"),
        _payload("EEE"),
        _payload("FFF"),
        _payload("GGG", next_eps=None),
    ]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 10, 15))

    assert result.valid is True
    assert result.selected_year == 2027
    assert result.signal_mode == "directional_only"
    assert result.coverage_ratio < 0.90


def test_market_cap_weighted_completeness_can_still_be_actionable() -> None:
    payloads = [
        _payload("AAA", shares=100.0),
        _payload("BBB", shares=100.0),
        _payload("CCC", shares=100.0),
        _payload("DDD", shares=100.0),
        _payload("EEE", shares=100.0),
        _payload("FFF", shares=100.0),
        _payload("GGG", shares=0.1, next_eps=None),
    ]

    result = compute_speaker_forward_pe(payloads, as_of=date(2026, 10, 15))

    assert result.valid is True
    assert result.selected_year == 2027
    assert result.coverage_count == 6
    assert result.coverage_ratio > 0.99
    assert result.signal_mode == "actionable"
