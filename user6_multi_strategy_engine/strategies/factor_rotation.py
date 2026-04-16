from __future__ import annotations

from typing import Set

import numpy as np
import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import daily_vol, fill_weights_with_cash, month_end_index, monthly_return
from .base import StrategyBase


class FactorRotationStrategy(StrategyBase):
    name = "factor_rotation"

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return set(cfg.factor_assets) | {cfg.signal_symbol, cfg.cash_symbol}

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        idx = data.idx
        cols = list(self.required_symbols(cfg))
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        month_ends = month_end_index(idx)

        gate = (monthly_return(data.adj_close[cfg.signal_symbol], cfg.gspc_bear_gate_months) > 0.0).astype(float)
        vol_cache = {sym: daily_vol(data.adj_close[sym], cfg.vol_lookback_d) for sym in cfg.factor_assets if sym in data.adj_close}
        r6 = {sym: monthly_return(data.adj_close[sym], 6) for sym in cfg.factor_assets if sym in data.adj_close}
        r12 = {sym: monthly_return(data.adj_close[sym], 12) for sym in cfg.factor_assets if sym in data.adj_close}

        for d in month_ends:
            mkey = pd.Timestamp(d).to_period("M").to_timestamp("M")
            if float(gate.get(mkey, 0.0)) <= 0.0:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            rows = []
            for sym in cfg.factor_assets:
                if sym not in r6 or sym not in r12:
                    continue
                s6 = float(r6[sym].get(mkey, np.nan))
                s12 = float(r12[sym].get(mkey, np.nan))
                vol = float(vol_cache[sym].get(d, np.nan))
                if not np.isfinite(s6) or not np.isfinite(s12) or not np.isfinite(vol) or vol <= 0.0:
                    continue
                if s12 <= 0.0:
                    continue
                score = 0.5 * s6 + 0.5 * s12
                rows.append((sym, score, vol))
            if not rows:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            ranked = sorted(rows, key=lambda x: x[1], reverse=True)[: cfg.factor_top_n]
            inv = pd.Series({sym: 1.0 / vol for sym, _, vol in ranked})
            w = inv / inv.sum()
            for sym, wt in w.items():
                out.loc[d, sym] = float(wt)

        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=cfg.max_leverage)
