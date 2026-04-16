from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
import pandas as pd


@dataclass
class Metrics:
    cagr: float
    annualized_vol: float
    sharpe: float
    max_drawdown: float
    info_ratio: float
    benchmark_cagr: float
    benchmark_max_drawdown: float
    turnover_annualized: float


def cagr_from_curve(curve: pd.Series) -> float:
    if len(curve) < 2:
        return float("nan")
    years = (curve.index[-1] - curve.index[0]).days / 365.25
    if years <= 0:
        return float("nan")
    return float((curve.iloc[-1] / curve.iloc[0]) ** (1.0 / years) - 1.0)


def max_drawdown_from_curve(curve: pd.Series) -> float:
    if curve.empty:
        return float("nan")
    running_max = curve.cummax()
    dd = curve / running_max - 1.0
    return float(dd.min())


def annualized_vol_from_curve(curve: pd.Series) -> float:
    rets = curve.pct_change().dropna()
    if rets.empty:
        return float("nan")
    return float(rets.std() * math.sqrt(252.0))


def sharpe_from_curve(curve: pd.Series) -> float:
    rets = curve.pct_change().dropna()
    if rets.empty:
        return float("nan")
    vol = rets.std() * math.sqrt(252.0)
    if vol <= 0.0:
        return float("nan")
    ann = (1.0 + rets.mean()) ** 252 - 1.0
    return float(ann / vol)


def information_ratio(curve: pd.Series, benchmark_curve: pd.Series) -> float:
    a = curve.pct_change().dropna()
    b = benchmark_curve.pct_change().dropna()
    common = a.index.intersection(b.index)
    if len(common) < 5:
        return float("nan")
    diff = a.loc[common] - b.loc[common]
    te = diff.std() * math.sqrt(252.0)
    if te <= 0.0:
        return float("nan")
    ann = diff.mean() * 252.0
    return float(ann / te)


def summarize_metrics(
    curve: pd.Series,
    benchmark_curve: pd.Series,
    turnover_annualized: float,
) -> Metrics:
    return Metrics(
        cagr=cagr_from_curve(curve),
        annualized_vol=annualized_vol_from_curve(curve),
        sharpe=sharpe_from_curve(curve),
        max_drawdown=max_drawdown_from_curve(curve),
        info_ratio=information_ratio(curve, benchmark_curve),
        benchmark_cagr=cagr_from_curve(benchmark_curve),
        benchmark_max_drawdown=max_drawdown_from_curve(benchmark_curve),
        turnover_annualized=float(turnover_annualized),
    )
