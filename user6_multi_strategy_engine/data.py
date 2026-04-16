from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from pandas.tseries.offsets import BDay, Day

from .config import EngineConfig


@dataclass
class DataBundle:
    px: pd.DataFrame
    idx: pd.DatetimeIndex
    raw_open: dict[str, pd.Series]
    raw_high: dict[str, pd.Series]
    raw_low: dict[str, pd.Series]
    raw_close: dict[str, pd.Series]
    adj_open: dict[str, pd.Series]
    adj_close: dict[str, pd.Series]
    gap: dict[str, pd.Series]
    intra: dict[str, pd.Series]


def adj_open_from_prices(open_s: pd.Series, close_s: pd.Series, adj_close_s: pd.Series) -> pd.Series:
    return open_s * (adj_close_s / close_s.replace(0.0, np.nan))


def seg_returns(ao: pd.Series, ac: pd.Series) -> tuple[pd.Series, pd.Series]:
    gap = ao / ac.shift(1) - 1.0
    intra = ac / ao - 1.0
    return gap.fillna(0.0), intra.fillna(0.0)


def synthetic_close_from_segments(
    gap: pd.Series,
    intra: pd.Series,
    idx: pd.DatetimeIndex,
    seed: float = 100.0,
) -> pd.Series:
    out = pd.Series(index=idx, dtype=float)
    level = float(seed)
    for i, d in enumerate(idx):
        if i == 0:
            level *= 1.0 + float(intra.get(d, 0.0))
        else:
            level *= (1.0 + float(gap.get(d, 0.0))) * (1.0 + float(intra.get(d, 0.0)))
        out.loc[d] = level
    return out


def build_proxy_asset_from_base(
    real_ao: pd.Series,
    real_ac: pd.Series,
    base_ao: pd.Series,
    base_ac: pd.Series,
    lev: float,
    idx: pd.DatetimeIndex,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    base_gap, base_intra = seg_returns(base_ao, base_ac)
    proxy_gap = (lev * base_gap).clip(lower=-0.95).fillna(0.0)
    den = (1.0 + proxy_gap).replace(-1.0, -0.999999)
    proxy_daily = ((1.0 + base_gap).fillna(1.0) * (1.0 + base_intra).fillna(1.0) - 1.0)
    proxy_intra = ((1.0 + lev * proxy_daily) / den - 1.0).clip(lower=-0.95).fillna(0.0)

    real_gap, real_intra = seg_returns(real_ao, real_ac)
    has_real = real_ao.notna() & real_ac.notna()
    gap = real_gap.where(has_real, proxy_gap).fillna(0.0)
    intra = real_intra.where(has_real, proxy_intra).fillna(0.0)
    synth_ac = synthetic_close_from_segments(gap, intra, idx)
    ac = real_ac.where(real_ac.notna(), synth_ac)
    return gap, intra, ac


def build_proxy_gld_asset(
    real_ao: pd.Series,
    real_ac: pd.Series,
    proxy_ao: pd.Series,
    proxy_ac: pd.Series,
    idx: pd.DatetimeIndex,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    real_gap, real_intra = seg_returns(real_ao, real_ac)
    proxy_gap, proxy_intra = seg_returns(proxy_ao, proxy_ac)
    has_real = real_ao.notna() & real_ac.notna()
    gap = real_gap.where(has_real, proxy_gap).fillna(0.0)
    intra = real_intra.where(has_real, proxy_intra).fillna(0.0)
    synth_ac = synthetic_close_from_segments(gap, intra, idx)
    ac = real_ac.where(real_ac.notna(), synth_ac)
    return gap, intra, ac


def normalize_download_frame(px: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if px is None or px.empty:
        return pd.DataFrame()
    if isinstance(px.columns, pd.MultiIndex):
        return px.sort_index(axis=1)
    if len(symbols) != 1:
        raise RuntimeError("Expected a single-symbol download when columns are not MultiIndex.")
    sym = symbols[0]
    px = px.copy()
    px.columns = pd.MultiIndex.from_product([px.columns, [sym]])
    return px.sort_index(axis=1)


def download_tickers_batched(
    tickers: list[str],
    start: str,
    end: str,
    batch_size: int = 8,
    max_passes: int = 2,
) -> pd.DataFrame:
    batches = [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]
    frames: list[pd.DataFrame] = []
    for batch in batches:
        batch_frame = pd.DataFrame()
        for _ in range(max_passes):
            px = yf.download(
                batch,
                start=start,
                end=end,
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=30,
            )
            batch_frame = normalize_download_frame(px, list(batch))
            if not batch_frame.empty:
                break
        if not batch_frame.empty:
            frames.append(batch_frame)
    if not frames:
        raise RuntimeError("Price download returned no usable data.")
    return pd.concat(frames, axis=1).sort_index(axis=1)


def has_symbol(px: pd.DataFrame, field_name: str, symbol: str) -> bool:
    return field_name in px.columns.get_level_values(0) and symbol in px[field_name].columns


def get_raw_series(px: pd.DataFrame, field_name: str, symbol: str, idx: pd.DatetimeIndex) -> pd.Series:
    if has_symbol(px, field_name, symbol):
        return pd.to_numeric(px[field_name][symbol].reindex(idx), errors="coerce")
    return pd.Series(index=idx, dtype=float)


def get_adj_ohlc(
    px: pd.DataFrame,
    symbol: str,
    idx: pd.DatetimeIndex,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    close_s = get_raw_series(px, "Close", symbol, idx)
    adj_close_s = get_raw_series(px, "Adj Close", symbol, idx)
    open_s = get_raw_series(px, "Open", symbol, idx)
    high_s = get_raw_series(px, "High", symbol, idx)
    low_s = get_raw_series(px, "Low", symbol, idx)
    ao = adj_open_from_prices(open_s, close_s, adj_close_s)
    return ao, adj_close_s, open_s, high_s, low_s


def warmup_business_days(cfg: EngineConfig) -> int:
    return max(
        cfg.vol_lookback_d,
        cfg.cov_lookback_d,
        cfg.atr_lookback_d,
        cfg.channel_window + cfg.channel_stdev_len,
        252,
    ) + 40


def download_end_exclusive(end_date: Optional[str]) -> str:
    if end_date is None:
        return (pd.Timestamp.today() + BDay(1)).date().isoformat()
    return (pd.Timestamp(end_date) + Day(1)).date().isoformat()


def load_market_data(cfg: EngineConfig, extra_symbols: Optional[set[str]] = None) -> DataBundle:
    warmup = warmup_business_days(cfg)
    dl_start = (pd.Timestamp(cfg.start_date) - BDay(warmup)).date().isoformat()
    dl_end = download_end_exclusive(cfg.end_date)
    symbols = set(cfg.all_symbols())
    if extra_symbols:
        symbols.update(extra_symbols)
    tickers = sorted(symbols)

    px = download_tickers_batched(tickers, start=dl_start, end=dl_end)
    if not has_symbol(px, "Adj Close", cfg.signal_symbol):
        raise RuntimeError(f"No usable price history for signal symbol {cfg.signal_symbol}.")
    signal_idx = pd.to_numeric(px["Adj Close"][cfg.signal_symbol], errors="coerce").dropna().index
    idx = signal_idx

    raw_open: dict[str, pd.Series] = {}
    raw_high: dict[str, pd.Series] = {}
    raw_low: dict[str, pd.Series] = {}
    raw_close: dict[str, pd.Series] = {}
    adj_open_map: dict[str, pd.Series] = {}
    adj_close_map: dict[str, pd.Series] = {}
    gap_map: dict[str, pd.Series] = {}
    intra_map: dict[str, pd.Series] = {}

    for sym in tickers:
        ao, ac, ro, rh, rl = get_adj_ohlc(px, sym, idx)
        raw_open[sym] = ro
        raw_high[sym] = rh
        raw_low[sym] = rl
        raw_close[sym] = get_raw_series(px, "Close", sym, idx)
        adj_open_map[sym] = ao
        adj_close_map[sym] = ac
        gap_map[sym], intra_map[sym] = seg_returns(ao, ac)

    # Proxy a few major leveraged funds from index bases where that helps warm-up.
    ndx_ao, ndx_ac, *_ = get_adj_ohlc(px, "^NDX", idx)
    spy_ao, spy_ac, *_ = get_adj_ohlc(px, "SPY", idx)
    gcf_ao, gcf_ac, *_ = get_adj_ohlc(px, "GC=F", idx)

    proxy_specs = (
        ("TQQQ", 3.0, ndx_ao, ndx_ac),
        ("QLD", 2.0, ndx_ao, ndx_ac),
        ("SPXL", 3.0, spy_ao, spy_ac),
        ("SSO", 2.0, spy_ao, spy_ac),
    )
    for sym, lev, base_ao, base_ac in proxy_specs:
        if sym in adj_open_map and base_ac.notna().any():
            pg, pi, pac = build_proxy_asset_from_base(
                adj_open_map[sym],
                adj_close_map[sym],
                base_ao,
                base_ac,
                lev,
                idx,
            )
            gap_map[sym] = pg
            intra_map[sym] = pi
            adj_close_map[sym] = pac

    if "GLD" in adj_open_map and gcf_ac.notna().any():
        pg, pi, pac = build_proxy_gld_asset(
            adj_open_map["GLD"],
            adj_close_map["GLD"],
            gcf_ao,
            gcf_ac,
            idx,
        )
        gap_map["GLD"] = pg
        intra_map["GLD"] = pi
        adj_close_map["GLD"] = pac

    return DataBundle(
        px=px,
        idx=idx,
        raw_open=raw_open,
        raw_high=raw_high,
        raw_low=raw_low,
        raw_close=raw_close,
        adj_open=adj_open_map,
        adj_close=adj_close_map,
        gap=gap_map,
        intra=intra_map,
    )
