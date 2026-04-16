from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


@dataclass(frozen=True)
class EngineConfig:
    start_date: str = "2012-01-01"
    end_date: Optional[str] = None

    # Keep GSPC as the main signal and the benchmark.
    signal_symbol: str = "^GSPC"
    benchmark_symbol: str = "^GSPC"
    channel_symbol: str = "SPY"
    cash_symbol: str = "SHY"

    strategy_name: str = "generalized_momentum"
    slippage_bps: float = 5.0
    initial_equity: float = 100000.0

    # Core horizons discussed in the papers.
    monthly_lookbacks: tuple[int, int, int] = (1, 3, 12)
    momentum_top_n: int = 3
    factor_top_n: int = 2

    # Volatility and covariance settings.
    vol_lookback_d: int = 60
    cov_lookback_d: int = 126
    atr_lookback_d: int = 20
    target_vol: float = 0.10
    max_leverage: float = 1.00
    min_train_months: int = 60

    # Regime thresholds.
    bull_prob_high: float = 0.67
    bull_prob_mid: float = 0.40
    gspc_bear_gate_months: int = 12

    # Channel settings.
    channel_window: int = 252
    channel_stdev_len: int = 12
    channel_price_src: Literal["hl2", "close"] = "close"
    channel_ddof: int = 0
    channel_entry_band: Literal["LB3", "LB4"] = "LB3"
    channel_exit_mode: Literal["mid", "ub1"] = "mid"
    channel_max_hold_bars: int = 10
    channel_stop_atr_mult: float = 6.0

    # Risk assets tied to user6-style testing.
    risk_on_assets: tuple[str, ...] = (
        "TQQQ",
        "SPXL",
        "UPRO",
        "SOXL",
        "TECL",
        "FNGU",
    )
    moderate_assets: tuple[str, ...] = (
        "QLD",
        "SSO",
        "ROM",
        "DDM",
    )
    defensive_assets: tuple[str, ...] = (
        "IEF",
        "GLD",
        "SHY",
    )

    # Multi-asset sleeves for weighted strategies.
    risk_parity_assets: tuple[str, ...] = (
        "SPY",
        "IEF",
        "GLD",
        "TIP",
        "DBC",
        "VNQ",
    )
    factor_assets: tuple[str, ...] = (
        "MTUM",
        "QUAL",
        "USMV",
        "VLUE",
        "SIZE",
    )

    # Ensemble weights.
    ensemble_weights: tuple[float, float, float] = (0.45, 0.35, 0.20)

    # ML / RL.
    ridge_alpha: float = 1.0
    rl_alpha: float = 0.10
    rl_gamma: float = 0.90
    rl_epsilon: float = 0.0

    report_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)

    def all_symbols(self) -> set[str]:
        out = {
            self.signal_symbol,
            self.benchmark_symbol,
            self.channel_symbol,
            self.cash_symbol,
            "SPY",
            "IEF",
            "GLD",
            "TIP",
            "DBC",
            "VNQ",
        }
        out.update(self.risk_on_assets)
        out.update(self.moderate_assets)
        out.update(self.defensive_assets)
        out.update(self.risk_parity_assets)
        out.update(self.factor_assets)
        out.update({"^NDX", "GC=F"})
        return out
