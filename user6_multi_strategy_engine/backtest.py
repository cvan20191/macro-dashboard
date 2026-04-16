from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .config import EngineConfig
from .data import DataBundle, load_market_data
from .evaluation import Metrics, summarize_metrics
from .strategies.base import StrategyBase, strategy_from_name


@dataclass
class BacktestResult:
    config: EngineConfig
    strategy_name: str
    equity_curve: pd.Series
    benchmark_curve: pd.Series
    daily_log: pd.DataFrame
    desired_weights: pd.DataFrame
    executed_weights: pd.DataFrame
    metrics: Metrics


def normalize_target_row(row: pd.Series, cash_symbol: str, max_leverage: float) -> pd.Series:
    row = row.fillna(0.0).copy()
    if cash_symbol not in row.index:
        row[cash_symbol] = 0.0
    row[row < 0.0] = 0.0
    risky = row.drop(labels=[cash_symbol], errors="ignore")
    gross = float(risky.sum())
    if gross > max_leverage and gross > 0.0:
        risky *= max_leverage / gross
    row.loc[risky.index] = risky
    row[cash_symbol] = max(0.0, 1.0 - float(risky.sum()))
    return row


def run_strategy_backtest(
    cfg: EngineConfig,
    strategy: Optional[StrategyBase] = None,
) -> BacktestResult:
    if strategy is None:
        strategy = strategy_from_name(cfg.strategy_name, cfg)
    data: DataBundle = load_market_data(cfg, extra_symbols=strategy.required_symbols(cfg))
    desired = strategy.generate_target_weights(data, cfg).reindex(data.idx).ffill()
    if desired.empty:
        raise RuntimeError(f"Strategy {strategy.name} produced no target weights.")
    for c in desired.columns:
        desired[c] = pd.to_numeric(desired[c], errors="coerce")
    if cfg.cash_symbol not in desired.columns:
        desired[cfg.cash_symbol] = 0.0
    desired = desired.fillna(0.0)
    desired = desired.apply(normalize_target_row, axis=1, args=(cfg.cash_symbol, cfg.max_leverage))

    exec_weights = desired.shift(1).fillna(0.0)
    if cfg.cash_symbol not in exec_weights.columns:
        exec_weights[cfg.cash_symbol] = 1.0
    exec_weights.iloc[0] = 0.0
    exec_weights.iloc[0, exec_weights.columns.get_loc(cfg.cash_symbol)] = 1.0

    idx = data.idx
    start = pd.Timestamp(cfg.start_date)
    if start not in idx:
        pos = int(idx.searchsorted(start))
        if pos >= len(idx):
            raise RuntimeError("Backtest start is after the last available date.")
        start = idx[pos]
    run_idx = idx[idx >= start]
    equity = float(cfg.initial_equity)
    curve = []
    current_weights = exec_weights.loc[run_idx[0]].copy()

    logs = []
    total_turnover = 0.0

    bench = pd.to_numeric(data.adj_close[cfg.benchmark_symbol].reindex(run_idx), errors="coerce")
    benchmark_curve = cfg.initial_equity * (bench / float(bench.iloc[0]))

    for i, d in enumerate(run_idx):
        if i > 0:
            gap_ret = 0.0
            for sym, w in current_weights.items():
                if abs(float(w)) <= 0:
                    continue
                gap_ret += float(w) * float(data.gap.get(sym, pd.Series(dtype=float)).get(d, 0.0))
            equity *= 1.0 + gap_ret

        target = exec_weights.loc[d].copy()
        target = normalize_target_row(target, cfg.cash_symbol, cfg.max_leverage)
        turnover = 0.5 * float((target - current_weights).abs().sum())
        total_turnover += turnover
        if turnover > 0:
            equity *= 1.0 - turnover * (cfg.slippage_bps / 10000.0)
            current_weights = target

        intra_ret = 0.0
        for sym, w in current_weights.items():
            if abs(float(w)) <= 0:
                continue
            intra_ret += float(w) * float(data.intra.get(sym, pd.Series(dtype=float)).get(d, 0.0))
        equity *= 1.0 + intra_ret

        curve.append(equity)
        logs.append(
            {
                "date": d,
                "equity_close": equity,
                "turnover": turnover,
                "active_cash_weight": float(current_weights.get(cfg.cash_symbol, 0.0)),
                "gross_exposure": float(current_weights.drop(labels=[cfg.cash_symbol], errors="ignore").sum()),
            }
        )

    daily_log = pd.DataFrame(logs).set_index("date")
    equity_curve = pd.Series(curve, index=run_idx, name="equity_close")
    years = max((run_idx[-1] - run_idx[0]).days / 365.25, 1 / 365.25)
    turnover_annualized = total_turnover / years
    metrics = summarize_metrics(equity_curve, benchmark_curve, turnover_annualized)

    return BacktestResult(
        config=cfg,
        strategy_name=strategy.name,
        equity_curve=equity_curve,
        benchmark_curve=benchmark_curve,
        daily_log=daily_log,
        desired_weights=desired.loc[run_idx],
        executed_weights=exec_weights.loc[run_idx],
        metrics=metrics,
    )
