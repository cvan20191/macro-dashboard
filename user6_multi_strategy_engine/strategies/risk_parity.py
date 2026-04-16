from __future__ import annotations

from typing import Set

import numpy as np
import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import fill_weights_with_cash, month_end_index, rolling_cov_matrix
from .base import StrategyBase


def erc_weights(cov: pd.DataFrame, n_iter: int = 500, tol: float = 1e-8) -> pd.Series:
    cov = cov.fillna(0.0)
    cols = cov.columns
    n = len(cols)
    if n == 0:
        return pd.Series(dtype=float)
    w = np.full(n, 1.0 / n, dtype=float)
    C = cov.to_numpy(float)
    for _ in range(n_iter):
        mrc = C @ w
        rc = w * mrc
        target = rc.mean() if np.isfinite(rc).all() else np.nan
        if not np.isfinite(target) or target <= 0.0:
            break
        new_w = w * target / np.maximum(rc, 1e-12)
        new_w = np.clip(new_w, 1e-12, None)
        new_w /= new_w.sum()
        if np.max(np.abs(new_w - w)) < tol:
            w = new_w
            break
        w = new_w
    return pd.Series(w, index=cols)


class RiskParityStrategy(StrategyBase):
    name = "risk_parity"

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return set(cfg.risk_parity_assets) | {cfg.cash_symbol, cfg.signal_symbol}

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        idx = data.idx
        cols = list(self.required_symbols(cfg))
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        month_ends = month_end_index(idx)

        ret_df = pd.DataFrame({sym: data.adj_close[sym].pct_change() for sym in cfg.risk_parity_assets if sym in data.adj_close}, index=idx)
        bench_gate = data.adj_close[cfg.signal_symbol].pct_change(252).reindex(idx)

        for d in month_ends:
            loc = idx.get_loc(d)
            cov = rolling_cov_matrix(ret_df, loc, cfg.cov_lookback_d)
            cov = cov.dropna(axis=0, how="all").dropna(axis=1, how="all")
            common = [c for c in cov.columns if c in cov.index]
            cov = cov.loc[common, common]
            if cov.empty:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            w = erc_weights(cov)
            port_vol = float(np.sqrt(np.dot(w.values, cov.to_numpy(float) @ w.values) * 252.0))
            lev = min(cfg.max_leverage, cfg.target_vol / port_vol) if port_vol > 0.0 else 1.0
            gate = float(bench_gate.get(d, np.nan))
            if np.isfinite(gate) and gate <= 0.0:
                lev *= 0.5
            for sym, wt in (w * lev).items():
                out.loc[d, sym] = float(wt)

        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=cfg.max_leverage)
