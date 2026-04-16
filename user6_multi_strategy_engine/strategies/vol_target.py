from __future__ import annotations

from typing import Set

import numpy as np
import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import daily_vol, fill_weights_with_cash, month_end_index
from .base import StrategyBase


class VolTargetStrategy(StrategyBase):
    name = "vol_target"

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return set(cfg.risk_parity_assets) | {cfg.signal_symbol, cfg.cash_symbol}

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        idx = data.idx
        out = pd.DataFrame(0.0, index=idx, columns=list(self.required_symbols(cfg)))
        month_ends = month_end_index(idx)

        bench_m = data.adj_close[cfg.signal_symbol].groupby(pd.Grouper(freq="ME")).last().dropna()
        bench_gate = (bench_m.pct_change(cfg.gspc_bear_gate_months) > 0.0).astype(float)

        vol_cache = {sym: daily_vol(data.adj_close[sym], cfg.vol_lookback_d) for sym in cfg.risk_parity_assets if sym in data.adj_close}

        for d in month_ends:
            mkey = pd.Timestamp(d).to_period("M").to_timestamp("M")
            gate = float(bench_gate.get(mkey, 0.0))
            if gate <= 0.0:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            vols = pd.Series({sym: float(vol_cache[sym].get(d, np.nan)) for sym in cfg.risk_parity_assets if sym in vol_cache})
            vols = vols.replace([np.inf, -np.inf], np.nan).dropna()
            vols = vols[vols > 0.0]
            if vols.empty:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            inv = 1.0 / vols
            w = inv / inv.sum()

            # Approximate portfolio vol using diagonal risk only for simplicity here.
            port_vol = float(np.sqrt(np.sum((w.values * vols.values) ** 2)))
            lev = min(cfg.max_leverage, cfg.target_vol / port_vol) if port_vol > 0 else 1.0
            w *= lev

            for sym, wt in w.items():
                out.loc[d, sym] = float(wt)

        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=cfg.max_leverage)
