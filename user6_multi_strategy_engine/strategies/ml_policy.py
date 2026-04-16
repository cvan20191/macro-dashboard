from __future__ import annotations

from typing import Set

import numpy as np
import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import daily_vol, fill_weights_with_cash, month_end_index, monthly_last_close, monthly_return, rolling_drawdown
from ..models import fit_ridge_closed_form
from .base import StrategyBase
from .generalized_momentum import GeneralizedMomentumStrategy


class MLPolicyStrategy(StrategyBase):
    name = "ml_policy"

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return set(cfg.risk_on_assets) | {cfg.signal_symbol, cfg.cash_symbol}

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        idx = data.idx
        cols = list(self.required_symbols(cfg))
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        month_ends = month_end_index(idx)
        fallback = GeneralizedMomentumStrategy().generate_target_weights(data, cfg)

        g = data.adj_close[cfg.signal_symbol]
        g1 = monthly_return(g, 1)
        g3 = monthly_return(g, 3)
        g12 = monthly_return(g, 12)

        features_by_sym = {}
        target_by_sym = {}

        for sym in cfg.risk_on_assets:
            if sym not in data.adj_close:
                continue
            s = data.adj_close[sym]
            m = monthly_last_close(s)
            feat = pd.DataFrame(index=m.index)
            feat["r1"] = m.pct_change(1)
            feat["r3"] = m.pct_change(3)
            feat["r6"] = m.pct_change(6)
            feat["r12"] = m.pct_change(12)
            feat["g1"] = g1.reindex(m.index)
            feat["g3"] = g3.reindex(m.index)
            feat["g12"] = g12.reindex(m.index)
            daily_v = daily_vol(s, cfg.vol_lookback_d).reindex(idx)
            feat["vol"] = daily_v.groupby(pd.Grouper(freq="ME")).last().reindex(m.index)
            dd = rolling_drawdown(s, 252).reindex(idx)
            feat["dd"] = dd.groupby(pd.Grouper(freq="ME")).last().reindex(m.index)
            y = m.pct_change().shift(-1)
            features_by_sym[sym] = feat
            target_by_sym[sym] = y

        for d in month_ends:
            mkey = pd.Timestamp(d).to_period("M").to_timestamp("M")
            X_train = []
            y_train = []
            X_pred = []
            pred_syms = []

            for sym in cfg.risk_on_assets:
                feat = features_by_sym.get(sym)
                tgt = target_by_sym.get(sym)
                if feat is None or tgt is None or mkey not in feat.index:
                    continue
                hist_idx = feat.index[feat.index < mkey]
                if len(hist_idx) < cfg.min_train_months:
                    continue
                train_idx = hist_idx[-cfg.min_train_months :]
                train = feat.loc[train_idx].join(tgt.loc[train_idx].rename("y")).dropna()
                if len(train) < max(24, cfg.min_train_months // 2):
                    continue
                X_train.append(train.drop(columns=["y"]).to_numpy(float))
                y_train.append(train["y"].to_numpy(float))
                row = feat.loc[[mkey]].dropna()
                if len(row) == 1:
                    X_pred.append(row.to_numpy(float)[0])
                    pred_syms.append(sym)

            if not X_train or not X_pred:
                out.loc[d] = fallback.reindex(columns=cols).loc[d].fillna(0.0)
                continue

            X = np.vstack(X_train)
            y = np.concatenate(y_train)
            model = fit_ridge_closed_form(X, y, alpha=cfg.ridge_alpha)
            preds = model.predict(np.vstack(X_pred))
            if np.all(~np.isfinite(preds)):
                out.loc[d] = fallback.reindex(columns=cols).loc[d].fillna(0.0)
                continue

            pred_s = pd.Series(preds, index=pred_syms).dropna()
            pred_s = pred_s[pred_s > 0.0].sort_values(ascending=False).iloc[: cfg.momentum_top_n]
            if pred_s.empty:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            vols = pd.Series({sym: float(daily_vol(data.adj_close[sym], cfg.vol_lookback_d).get(d, np.nan)) for sym in pred_s.index})
            vols = vols.replace([np.inf, -np.inf], np.nan).dropna()
            vols = vols[vols > 0.0]
            pred_s = pred_s.reindex(vols.index).dropna()
            if pred_s.empty:
                out.loc[d, cfg.cash_symbol] = 1.0
                continue

            inv = 1.0 / vols
            w = inv / inv.sum()
            for sym, wt in w.items():
                out.loc[d, sym] = float(wt)

        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=cfg.max_leverage)
