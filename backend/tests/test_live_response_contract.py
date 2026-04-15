import asyncio

from app.schemas.catalysts import CatalystState
from app.schemas.dashboard_state import (
    DashboardState,
    DataFreshness,
    DeterministicSummary,
    FedChessboard,
)
from app.schemas.indicator_snapshot import IndicatorSnapshot
from app.schemas.live_snapshot_response import LivePlaybookResponse, LiveSnapshotResponse
from app.schemas.macro_expectations import MacroExpectationsState
from app.schemas.playbook_conclusion import PlaybookConclusion
from app.services.ingestion import live_snapshot_service


def test_public_fed_chessboard_contract_has_no_legacy_window_fields() -> None:
    state = DashboardState(
        as_of="2026-04-15T00:00:00Z",
        data_freshness=DataFreshness(overall_status="fresh", stale_series=[]),
        primary_regime="Quadrant D / Illiquid Regime",
        current_posture="defensive",
        fed_chessboard=FedChessboard(
            quadrant="D",
            label="MAX ILLIQUIDITY",
            rate_direction_medium_term="tightening",
            rate_impulse_short="stable",
            balance_sheet_direction_medium_term="contracting",
            effective_balance_sheet_direction="contracting",
            balance_sheet_liquidity_interpretation="contracting",
            balance_sheet_pace="contracting_slower",
            liquidity_transition_path="D_to_C",
            transition_tag="Improving",
            quadrant_basis_note="test",
            transition_basis_note="test",
        ),
    )

    payload = state.model_dump()
    chessboard = payload["fed_chessboard"]

    assert "rate_trend_1m" not in chessboard
    assert "rate_trend_3m" not in chessboard
    assert "balance_sheet_trend_1m" not in chessboard
    assert "balance_sheet_trend_3m" not in chessboard
    assert "direction_vs_1m_ago" not in chessboard
    assert "policy_stance" not in chessboard
    assert "rate_impulse" not in chessboard
    assert "balance_sheet_direction" not in chessboard
    assert chessboard["rate_direction_medium_term"] == "tightening"
    assert chessboard["liquidity_transition_path"] == "D_to_C"


def test_live_response_contract_has_no_legacy_summary_field(monkeypatch) -> None:
    async def _fake_get_live_snapshot(*args, **kwargs):
        return LiveSnapshotResponse(
            snapshot=IndicatorSnapshot(as_of="2026-04-15T00:00:00Z"),
            sources={},
            overall_status="fresh",
            stale_series=[],
            generated_at="2026-04-15T00:00:00Z",
        )

    def _fake_build_dashboard_state_with_conclusion(snapshot):
        state = DashboardState(
            as_of="2026-04-15T00:00:00Z",
            data_freshness=DataFreshness(overall_status="fresh", stale_series=[]),
            primary_regime="Quadrant C / Liquidity Transition",
            current_posture="selective",
        )
        conclusion = PlaybookConclusion(
            conclusion_label="Transition regime",
            new_cash_action="hold_and_wait",
            warning_urgency="cautionary",
            why_now="liquidity_quadrant_c_transition",
        )
        return state, conclusion

    def _fake_build_deterministic_summary(state, conclusion):
        return DeterministicSummary(
            headline=state.primary_regime,
            subheadline="Liquidity is improving, but QT is still not fully over.",
            action_line="Action: hold and wait.",
        )

    def _fake_get_macro_expectations_state(*args, **kwargs):
        return MacroExpectationsState(
            regime_impact_narrative="Macro expectations unavailable for test.",
            tactical_posture_modifier="mixed — event risk elevated",
            generated_at="2026-04-15T00:00:00Z",
        )

    def _fake_build_catalyst_state(*args, **kwargs):
        return CatalystState()

    monkeypatch.setattr(live_snapshot_service, "get_live_snapshot", _fake_get_live_snapshot)
    monkeypatch.setattr(
        live_snapshot_service,
        "build_dashboard_state_with_conclusion",
        _fake_build_dashboard_state_with_conclusion,
    )
    monkeypatch.setattr(
        live_snapshot_service,
        "build_deterministic_summary",
        _fake_build_deterministic_summary,
    )
    monkeypatch.setattr(
        live_snapshot_service,
        "get_macro_expectations_state",
        _fake_get_macro_expectations_state,
    )
    monkeypatch.setattr(
        live_snapshot_service,
        "build_catalyst_state",
        _fake_build_catalyst_state,
    )

    result = asyncio.run(live_snapshot_service.get_live_playbook())
    payload = result.model_dump()

    assert "summary" not in payload
    assert payload["state"]["deterministic_summary"]["headline"] == "Quadrant C / Liquidity Transition"
    assert isinstance(result, LivePlaybookResponse)
