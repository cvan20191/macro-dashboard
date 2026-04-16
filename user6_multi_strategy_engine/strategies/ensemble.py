from __future__ import annotations

from typing import Set

import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle
from ..features import fill_weights_with_cash
from .base import StrategyBase
from .generalized_momentum import GeneralizedMomentumStrategy
from .regime_switching import RegimeSwitchingStrategy
from .risk_parity import RiskParityStrategy


class EnsembleStrategy(StrategyBase):
    name = "ensemble"

    def __init__(self) -> None:
        self._gm = GeneralizedMomentumStrategy()
        self._rs = RegimeSwitchingStrategy()
        self._rp = RiskParityStrategy()

    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        return self._gm.required_symbols(cfg) | self._rs.required_symbols(cfg) | self._rp.required_symbols(cfg) | {cfg.cash_symbol}

    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        w1 = self._gm.generate_target_weights(data, cfg)
        w2 = self._rs.generate_target_weights(data, cfg)
        w3 = self._rp.generate_target_weights(data, cfg)
        cols = sorted(set(w1.columns) | set(w2.columns) | set(w3.columns) | {cfg.cash_symbol})
        w1 = w1.reindex(columns=cols).fillna(0.0)
        w2 = w2.reindex(columns=cols).fillna(0.0)
        w3 = w3.reindex(columns=cols).fillna(0.0)

        a, b, c = cfg.ensemble_weights
        out = a * w1 + b * w2 + c * w3
        return fill_weights_with_cash(out, cfg.cash_symbol, max_leverage=cfg.max_leverage)
