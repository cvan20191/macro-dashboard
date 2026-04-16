from __future__ import annotations

from typing import Set

import numpy as np
import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import compute_atr, compute_channel_features, fill_weights_with_cash, monthly_return
from .base import StrategyBase


class ChannelMeanReversionStrategy(StrategyBase):
    name = "channel_mean_reversion"

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return set(cfg.risk_on_assets) | set(cfg.defensive_assets) | {cfg.signal_symbol, cfg.channel_symbol, cfg.cash_symbol}

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        idx = data.idx
        cols = list(self.required_symbols(cfg))
        out = pd.DataFrame(0.0, index=idx, columns=cols)

        channel = compute_channel_features(data, cfg)
        atr = compute_atr(
            data.raw_high[cfg.channel_symbol],
            data.raw_low[cfg.channel_symbol],
            data.raw_close[cfg.channel_symbol],
            cfg.atr_lookback_d,
        )
        gspc12 = monthly_return(data.adj_close[cfg.signal_symbol], cfg.gspc_bear_gate_months)
        gspc12_daily = gspc12.reindex(idx).ffill()

        top_asset = cfg.risk_on_assets[0]
        entry_price = np.nan
        hold_bars = 0
        in_trade = False

        for i, d in enumerate(idx):
            if i == len(idx) - 1:
                out.loc[d, cfg.cash_symbol] = 1.0 if not in_trade else 0.0
                if in_trade:
                    out.loc[d, top_asset] = 1.0
                continue

            row = channel.loc[d]
            bearish = float(gspc12_daily.get(d, np.nan)) <= 0.0
            slope_ok = bool(pd.notna(row.get("lr_slope_ols")) and float(row["lr_slope_ols"]) > 0.0)
            entry_hit = bool(row.get("close_lb4", False)) if cfg.channel_entry_band == "LB4" else bool(row.get("close_lb3", False))
            exit_hit = bool(row.get("ub1_exit", False)) if cfg.channel_exit_mode == "ub1" else bool(row.get("mid_exit", False))
            stop_hit = False
            if in_trade and np.isfinite(entry_price):
                atr_now = float(atr.get(d, np.nan))
                if np.isfinite(atr_now) and atr_now > 0.0:
                    stop_level = entry_price - cfg.channel_stop_atr_mult * atr_now
                    stop_hit = bool(pd.notna(row.get("close")) and float(row["close"]) < stop_level)

            if in_trade:
                hold_bars += 1
                if exit_hit or stop_hit or hold_bars >= cfg.channel_max_hold_bars:
                    in_trade = False
                    entry_price = np.nan
                    hold_bars = 0
                    out.loc[d, cfg.cash_symbol] = 1.0
                else:
                    out.loc[d, top_asset] = 1.0
            else:
                if bearish and slope_ok and entry_hit:
                    in_trade = True
                    entry_price = float(row.get("close", np.nan))
                    hold_bars = 0
                    out.loc[d, top_asset] = 1.0
                else:
                    out.loc[d, cfg.cash_symbol] = 1.0

        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=1.0)
