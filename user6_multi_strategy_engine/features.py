from __future__ import annotations

from typing import Optional

import math
import numpy as np
import pandas as pd

try:
    from TOS_LR_Channels_Calc_v2 import compute_std_lines_strict  # type: ignore
except Exception:  # pragma: no cover
    compute_std_lines_strict = None

from .config import EngineConfig
from .data import DataBundle


def month_end_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(idx, index=idx)
    out = s.groupby(pd.Grouper(freq="ME")).last().dropna()
    return pd.DatetimeIndex(out.values)


def monthly_last_close(series: pd.Series) -> pd.Series:
    return series.groupby(pd.Grouper(freq="ME")).last().dropna()


def monthly_return(series: pd.Series, months: int) -> pd.Series:
    m = monthly_last_close(series)
    return m.pct_change(months)


def daily_vol(series: pd.Series, lookback: int) -> pd.Series:
    rets = series.pct_change()
    return rets.rolling(lookback, min_periods=lookback).std() * math.sqrt(252.0)


def rolling_cov_matrix(df: pd.DataFrame, end_loc: int, lookback: int) -> pd.DataFrame:
    start = max(0, end_loc - lookback + 1)
    window = df.iloc[start : end_loc + 1]
    return window.cov()


def rolling_drawdown(series: pd.Series, lookback: int = 252) -> pd.Series:
    rolling_max = series.rolling(lookback, min_periods=max(10, lookback // 2)).max()
    return series / rolling_max - 1.0


def compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, lookback: int = 20) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(lookback, min_periods=lookback).mean()


def rolling_lr_slope_ols(price: pd.Series, n: int) -> pd.Series:
    y = price.to_numpy(float)
    t = y.size
    out = np.full(t, np.nan, dtype=float)
    if n <= 1 or t < n:
        return pd.Series(out, index=price.index, name="lr_slope_ols")
    k = np.arange(n, dtype=float)
    sx = float(k.sum())
    sxx = float((k * k).sum())
    den = n * sxx - sx * sx
    if den == 0.0:
        return pd.Series(out, index=price.index, name="lr_slope_ols")
    for i in range(n - 1, t):
        win = y[i - n + 1 : i + 1]
        sy = float(win.sum())
        sxy = float((k * win).sum())
        out[i] = (n * sxy - sx * sy) / den
    return pd.Series(out, index=price.index, name="lr_slope_ols")


def fallback_channel_features(
    open_s: pd.Series,
    high_s: pd.Series,
    low_s: pd.Series,
    close_s: pd.Series,
    cfg: EngineConfig,
) -> pd.DataFrame:
    src = (high_s + low_s) / 2.0 if cfg.channel_price_src == "hl2" else close_s
    mid = src.rolling(cfg.channel_window, min_periods=cfg.channel_window).mean()
    resid = src - mid
    sd = resid.rolling(cfg.channel_stdev_len, min_periods=cfg.channel_stdev_len).std(ddof=cfg.channel_ddof)
    out = pd.DataFrame(index=close_s.index)
    out["open"] = open_s
    out["high"] = high_s
    out["low"] = low_s
    out["close"] = close_s
    out["mid"] = mid
    out["LB1"] = mid - sd
    out["LB2"] = mid - 2.0 * sd
    out["LB3"] = mid - 3.0 * sd
    out["LB4"] = mid - 4.0 * sd
    out["UB1"] = mid + sd
    out["sd_with_width1"] = sd
    out["lr_slope_ols"] = rolling_lr_slope_ols(src, cfg.channel_window)
    return out


def compute_channel_features(data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
    sym = cfg.channel_symbol
    open_s = data.raw_open[sym]
    high_s = data.raw_high[sym]
    low_s = data.raw_low[sym]
    close_s = data.raw_close[sym]
    if compute_std_lines_strict is None:
        ch = fallback_channel_features(open_s, high_s, low_s, close_s, cfg)
    else:
        ohlc = pd.DataFrame(
            {"open": open_s, "high": high_s, "low": low_s, "close": close_s},
            index=close_s.index,
        )
        ch = compute_std_lines_strict(
            ohlc,
            n=cfg.channel_window,
            stdev_len=cfg.channel_stdev_len,
            price_src=cfg.channel_price_src,
            ddof=cfg.channel_ddof,
        )
        ch.index.name = "date"
        src = (ohlc["high"] + ohlc["low"]) / 2.0 if cfg.channel_price_src == "hl2" else ohlc["close"]
        ch["lr_slope_ols"] = rolling_lr_slope_ols(src, n=cfg.channel_window)
    ch["close_lb3"] = ch["close"] <= ch["LB3"]
    ch["close_lb4"] = ch["close"] <= ch["LB4"]
    ch["mid_exit"] = ch["close"] >= ch["mid"]
    ch["ub1_exit"] = ch["close"] >= ch["UB1"]
    return ch.reindex(data.idx)


def gspc_bear_gate(series: pd.Series, months: int = 12) -> pd.Series:
    r = monthly_return(series, months)
    out = (r > 0.0).astype(float)
    return out


def fill_weights_with_cash(
    weights: pd.DataFrame,
    cash_symbol: str,
    max_leverage: float = 1.0,
) -> pd.DataFrame:
    out = weights.copy()
    out[out < 0.0] = 0.0
    row_sums = out.sum(axis=1)
    for idx, s in row_sums.items():
        gross = min(float(s), max_leverage)
        if s > 0:
            out.loc[idx] = out.loc[idx] * (gross / float(s))
        out.loc[idx, cash_symbol] = max(0.0, 1.0 - float(out.loc[idx].drop(labels=[cash_symbol], errors="ignore").sum()))
    if cash_symbol not in out.columns:
        out[cash_symbol] = 0.0
        row_sums = out.drop(columns=[cash_symbol]).sum(axis=1)
        out[cash_symbol] = (1.0 - row_sums).clip(lower=0.0)
    return out.fillna(0.0)


def inverse_vol_weights(
    vols: pd.Series,
    max_assets: Optional[int] = None,
) -> pd.Series:
    s = vols.replace([np.inf, -np.inf], np.nan).dropna()
    s = s[s > 0.0]
    if s.empty:
        return pd.Series(dtype=float)
    inv = 1.0 / s
    inv = inv.sort_values(ascending=False)
    if max_assets is not None:
        inv = inv.iloc[:max_assets]
    w = inv / inv.sum()
    return w
