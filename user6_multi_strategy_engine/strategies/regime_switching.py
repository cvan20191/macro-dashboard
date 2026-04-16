from __future__ import annotations

from typing import Set

import numpy as np
import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import daily_vol, fill_weights_with_cash, month_end_index, monthly_last_close, monthly_return
from ..models import fit_two_state_gaussian_hmm
from .base import StrategyBase


class RegimeSwitchingStrategy(StrategyBase):
    name = "regime_switching"

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return (
            set(cfg.risk_on_assets)
            | set(cfg.moderate_assets)
            | set(cfg.defensive_assets)
            | {cfg.signal_symbol, cfg.cash_symbol}
        )

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        idx = data.idx
        cols = list(self.required_symbols(cfg))
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        month_ends = month_end_index(idx)

        gspc_m = monthly_last_close(data.adj_close[cfg.signal_symbol])
        gspc_r = gspc_m.pct_change().dropna()
        vol_cache = {sym: daily_vol(data.adj_close[sym], cfg.vol_lookback_d) for sym in self.required_symbols(cfg) if sym in data.adj_close}

        for d in month_ends:
            mkey = pd.Timestamp(d).to_period("M").to_timestamp("M")
            hist = gspc_r.loc[gspc_r.index <= mkey].dropna()
            if len(hist) < cfg.min_train_months:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            hmm = fit_two_state_gaussian_hmm(hist.values, n_iter=20)
            mu = hmm["mu"]
            bull_state = int(np.argmax(mu))
            p_bull = float(hmm["filtered"][-1, bull_state])

            if p_bull >= cfg.bull_prob_high:
                universe = list(cfg.risk_on_assets)
                mom_h = 3
            elif p_bull >= cfg.bull_prob_mid:
                universe = list(cfg.moderate_assets)
                mom_h = 3
            else:
                universe = list(cfg.defensive_assets)
                mom_h = 1

            scored = []
            for sym in universe:
                if sym not in data.adj_close:
                    continue
                mom = float(monthly_return(data.adj_close[sym], mom_h).get(mkey, np.nan))
                vol = float(vol_cache[sym].get(d, np.nan))
                if not np.isfinite(mom) or not np.isfinite(vol) or vol <= 0.0:
                    continue
                scored.append((sym, mom, vol))
            if not scored:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            if universe == list(cfg.defensive_assets):
                inv = pd.Series({sym: 1.0 / vol for sym, _, vol in scored})
                w = inv / inv.sum()
            else:
                scored = sorted(scored, key=lambda x: x[1], reverse=True)
                pick = scored[0]
                w = pd.Series({pick[0]: 1.0})
            for sym, wt in w.items():
                out.loc[d, sym] = float(wt)

        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=cfg.max_leverage)
