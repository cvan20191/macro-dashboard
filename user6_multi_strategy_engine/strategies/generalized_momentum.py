from __future__ import annotations

from typing import Set

import numpy as np
import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import daily_vol, fill_weights_with_cash, month_end_index, monthly_return
from .base import StrategyBase


class GeneralizedMomentumStrategy(StrategyBase):
    name = "generalized_momentum"

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return (
            set(cfg.risk_on_assets)
            | set(cfg.moderate_assets)
            | set(cfg.defensive_assets)
            | {cfg.signal_symbol, cfg.cash_symbol}
        )

    def _market_regime(self, data: DataBundle, cfg: EngineConfig) -> pd.Series:
        r1 = monthly_return(data.adj_close[cfg.signal_symbol], cfg.monthly_lookbacks[0])
        r3 = monthly_return(data.adj_close[cfg.signal_symbol], cfg.monthly_lookbacks[1])
        r12 = monthly_return(data.adj_close[cfg.signal_symbol], cfg.monthly_lookbacks[2])
        score = (r1 > 0.0).astype(int) + (r3 > 0.0).astype(int) + (r12 > 0.0).astype(int)
        regime = pd.Series(0, index=score.index, dtype=int)
        regime[score >= 2] = 2
        regime[score == 1] = 1
        return regime

    def _asset_score(self, series: pd.Series, cfg: EngineConfig) -> tuple[pd.Series, pd.Series]:
        r1 = monthly_return(series, cfg.monthly_lookbacks[0])
        r3 = monthly_return(series, cfg.monthly_lookbacks[1])
        r12 = monthly_return(series, cfg.monthly_lookbacks[2])
        vote = (r1 > 0.0).astype(int) + (r3 > 0.0).astype(int) + (r12 > 0.0).astype(int)
        strength = r1.fillna(0.0) + r3.fillna(0.0) + r12.fillna(0.0)
        return vote, strength

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        idx = data.idx
        cols = list(self.required_symbols(cfg))
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        month_ends = month_end_index(idx)
        regime = self._market_regime(data, cfg)
        vol_cache = {sym: daily_vol(data.adj_close[sym], cfg.vol_lookback_d) for sym in self.required_symbols(cfg) if sym in data.adj_close}

        score_cache = {}
        strength_cache = {}
        tradable = set(cfg.risk_on_assets) | set(cfg.moderate_assets)
        for sym in tradable:
            if sym in data.adj_close:
                score_cache[sym], strength_cache[sym] = self._asset_score(data.adj_close[sym], cfg)

        for d in month_ends:
            mkey = pd.Timestamp(d).to_period("M").to_timestamp("M")
            reg = int(regime.get(mkey, 0))
            if reg == 2:
                universe = list(cfg.risk_on_assets)
            elif reg == 1:
                universe = list(cfg.moderate_assets)
            else:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            rows = []
            for sym in universe:
                if sym not in score_cache:
                    continue
                vote = float(score_cache[sym].get(mkey, np.nan))
                strength = float(strength_cache[sym].get(mkey, np.nan))
                vol = float(vol_cache[sym].get(d, np.nan))
                if not np.isfinite(vote) or not np.isfinite(strength) or not np.isfinite(vol) or vol <= 0.0:
                    continue
                if vote <= 0.0:
                    continue
                rows.append((sym, vote, strength, vol))
            if not rows:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            ranked = sorted(rows, key=lambda x: (x[1], x[2]), reverse=True)[: cfg.momentum_top_n]
            inv = pd.Series({sym: 1.0 / vol for sym, _, _, vol in ranked})
            w = inv / inv.sum()
            for sym, wt in w.items():
                out.loc[d, sym] = float(wt)

        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=cfg.max_leverage)
