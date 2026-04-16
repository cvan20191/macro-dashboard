from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Set

import pandas as pd

from ..config import EngineConfig
from ..data import DataBundle


class StrategyBase(ABC):
    name: str = "base"

    @abstractmethod
    def required_symbols(self, cfg: EngineConfig) -> Set[str]:
        raise NotImplementedError

    @abstractmethod
    def generate_target_weights(self, data: DataBundle, cfg: EngineConfig) -> pd.DataFrame:
        raise NotImplementedError


def strategy_from_name(name: str, cfg: EngineConfig) -> StrategyBase:
    if name == "vol_target":
        from .vol_target import VolTargetStrategy
        return VolTargetStrategy()
    if name == "generalized_momentum":
        from .generalized_momentum import GeneralizedMomentumStrategy
        return GeneralizedMomentumStrategy()
    if name == "regime_switching":
        from .regime_switching import RegimeSwitchingStrategy
        return RegimeSwitchingStrategy()
    if name == "channel_mean_reversion":
        from .channel_mean_reversion import ChannelMeanReversionStrategy
        return ChannelMeanReversionStrategy()
    if name == "ensemble":
        from .ensemble import EnsembleStrategy
        return EnsembleStrategy()
    if name == "risk_parity":
        from .risk_parity import RiskParityStrategy
        return RiskParityStrategy()
    if name == "factor_rotation":
        from .factor_rotation import FactorRotationStrategy
        return FactorRotationStrategy()
    if name == "ml_policy":
        from .ml_policy import MLPolicyStrategy
        return MLPolicyStrategy()
    if name == "rl_policy":
        from .rl_policy import RLPolicyStrategy
        return RLPolicyStrategy()
    raise ValueError(f"Unknown strategy {name}")
