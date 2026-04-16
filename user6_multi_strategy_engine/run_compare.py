from __future__ import annotations

import argparse
from dataclasses import replace

from .backtest import run_strategy_backtest
from .config import EngineConfig


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run modular user6 multi-strategy backtests.")
    p.add_argument("--strategy", default="generalized_momentum", choices=[
        "vol_target",
        "generalized_momentum",
        "regime_switching",
        "channel_mean_reversion",
        "ensemble",
        "risk_parity",
        "factor_rotation",
        "ml_policy",
        "rl_policy",
    ])
    p.add_argument("--start", dest="start_date", default="2012-01-01")
    p.add_argument("--end", dest="end_date", default=None)
    p.add_argument("--signal-symbol", dest="signal_symbol", default="^GSPC")
    p.add_argument("--benchmark-symbol", dest="benchmark_symbol", default="^GSPC")
    p.add_argument("--slippage-bps", dest="slippage_bps", type=float, default=5.0)
    p.add_argument("--target-vol", dest="target_vol", type=float, default=0.10)
    p.add_argument("--top-n", dest="top_n", type=int, default=3)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = EngineConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        signal_symbol=args.signal_symbol,
        benchmark_symbol=args.benchmark_symbol,
        strategy_name=args.strategy,
        slippage_bps=args.slippage_bps,
        target_vol=args.target_vol,
        momentum_top_n=max(1, int(args.top_n)),
        factor_top_n=max(1, min(3, int(args.top_n))),
    )
    result = run_strategy_backtest(cfg)
    m = result.metrics
    print("\n===== user6 multi-strategy engine =====")
    print(f"strategy         : {result.strategy_name}")
    print(f"window           : {result.equity_curve.index.min().date()} .. {result.equity_curve.index.max().date()}")
    print(f"signal / bench   : {cfg.signal_symbol} / {cfg.benchmark_symbol}")
    print(f"cagr             : {100.0 * m.cagr:.2f}%")
    print(f"annualized vol   : {100.0 * m.annualized_vol:.2f}%")
    print(f"sharpe           : {m.sharpe:.2f}")
    print(f"max drawdown     : {100.0 * m.max_drawdown:.2f}%")
    print(f"info ratio       : {m.info_ratio:.2f}")
    print(f"benchmark cagr   : {100.0 * m.benchmark_cagr:.2f}%")
    print(f"benchmark maxdd  : {100.0 * m.benchmark_max_drawdown:.2f}%")
    print(f"turnover / year  : {m.turnover_annualized:.2f}")
    print("\nlast weights:")
    print(result.executed_weights.tail(3).to_string())


if __name__ == "__main__":
    main()
