from __future__ import annotations

from typing import Set

import numpy as np
import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import daily_vol, fill_weights_with_cash, month_end_index, monthly_last_close, monthly_return
from ..models import TabularQLearner
from .base import StrategyBase
from .generalized_momentum import GeneralizedMomentumStrategy


def encode_state(r1: float, r3: float, r12: float, vol: float, g12: float) -> int:
    b1 = int(np.isfinite(r1) and r1 > 0.0)
    b3 = int(np.isfinite(r3) and r3 > 0.0)
    b12 = int(np.isfinite(r12) and r12 > 0.0)
    bv = int(np.isfinite(vol) and vol > 0.35)
    bg = int(np.isfinite(g12) and g12 > 0.0)
    return b1 + 2 * b3 + 4 * b12 + 8 * bv + 16 * bg


class RLPolicyStrategy(StrategyBase):
    name = "rl_policy"

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return set(cfg.risk_on_assets) | {cfg.signal_symbol, cfg.cash_symbol}

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        idx = data.idx
        cols = list(self.required_symbols(cfg))
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        month_ends = month_end_index(idx)
        fallback = GeneralizedMomentumStrategy().generate_target_weights(data, cfg)

        g12 = monthly_return(data.adj_close[cfg.signal_symbol], 12)
        state_by_sym = {}
        reward_by_sym = {}

        for sym in cfg.risk_on_assets:
            if sym not in data.adj_close:
                continue
            m = monthly_last_close(data.adj_close[sym])
            r1 = m.pct_change(1)
            r3 = m.pct_change(3)
            r12 = m.pct_change(12)
            vol = daily_vol(data.adj_close[sym], cfg.vol_lookback_d).reindex(idx).groupby(pd.Grouper(freq="ME")).last().reindex(m.index)
            states = pd.Series(index=m.index, dtype=float)
            for t in m.index:
                states.loc[t] = encode_state(
                    float(r1.get(t, np.nan)),
                    float(r3.get(t, np.nan)),
                    float(r12.get(t, np.nan)),
                    float(vol.get(t, np.nan)),
                    float(g12.get(t, np.nan)),
                )
            reward = m.pct_change().shift(-1)
            state_by_sym[sym] = states
            reward_by_sym[sym] = reward

        for d in month_ends:
            mkey = pd.Timestamp(d).to_period("M").to_timestamp("M")
            learner = TabularQLearner(alpha=cfg.rl_alpha, gamma=cfg.rl_gamma, epsilon=cfg.rl_epsilon)
            enough = False
            for sym in cfg.risk_on_assets:
                states = state_by_sym.get(sym)
                rewards = reward_by_sym.get(sym)
                if states is None or rewards is None:
                    continue
                hist = states.index[states.index < mkey]
                if len(hist) < cfg.min_train_months:
                    continue
                enough = True
                hist = hist[-cfg.min_train_months :]
                for t0, t1 in zip(hist[:-1], hist[1:]):
                    s0 = int(states.loc[t0])
                    s1 = int(states.loc[t1])
                    reward = float(rewards.get(t0, 0.0))
                    a = 1 if reward > 0.0 else 0
                    learner.update(s0, a, reward, s1)

            if not enough:
                out.loc[d] = fallback.reindex(columns=cols).loc[d].fillna(0.0)
                continue

            picks = []
            for sym in cfg.risk_on_assets:
                states = state_by_sym.get(sym)
                if states is None or mkey not in states.index:
                    continue
                state = int(states.loc[mkey])
                action = learner.best_action(state)
                if action != 1:
                    continue
                vol = float(daily_vol(data.adj_close[sym], cfg.vol_lookback_d).get(d, np.nan))
                if not np.isfinite(vol) or vol <= 0.0:
                    continue
                score = learner.get(state, 1) - learner.get(state, 0)
                picks.append((sym, score, vol))

            if not picks:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            picks = sorted(picks, key=lambda x: x[1], reverse=True)[: cfg.momentum_top_n]
            inv = pd.Series({sym: 1.0 / vol for sym, _, vol in picks})
            w = inv / inv.sum()
            for sym, wt in w.items():
                out.loc[d, sym] = float(wt)

        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=cfg.max_leverage)
