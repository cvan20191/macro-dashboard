# user6_multi_strategy_engine

A modular multi-file research package for testing the strategy families discussed in the integration report against `^GSPC`, while keeping `^GSPC` as the main market signal.

Included strategies:
- volatility targeting
- generalized momentum
- probabilistic regime switching
- conditional channel mean reversion
- ensemble / hybrid policy
- risk parity
- ETF factor rotation
- ML policy
- RL policy

## Quick start

```bash
python -m user6_multi_strategy_engine.run_compare --strategy generalized_momentum
python -m user6_multi_strategy_engine.run_compare --strategy regime_switching
python -m user6_multi_strategy_engine.run_compare --strategy channel_mean_reversion
python -m user6_multi_strategy_engine.run_compare --strategy ensemble
```

Or from the repo root if you copy this folder beside your existing files:

```bash
python -m user6_multi_strategy_engine.run_compare --strategy generalized_momentum --start 2012-01-01
```

## Notes

- Default benchmark: `^GSPC`
- Default market signal / regime anchor: `^GSPC`
- Rebalance timing: signals formed at close, traded at next open through gap/intraday decomposition
- Data source: `yfinance`
- Optional channel import: `TOS_LR_Channels_Calc_v2.compute_std_lines_strict`
