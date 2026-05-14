## What changed

- 

## Why

- 

## Type of change

- [ ] Documentation only
- [ ] Safety / guardrails
- [ ] CI / tests
- [ ] Backtesting / analysis tools
- [ ] Strategy logic
- [ ] Telegram UI / bot behavior
- [ ] Bug fix

## Validation

- [ ] `python -m compileall bot tools`
- [ ] `python tools/strategy_smoke_test.py`
- [ ] `python tools/backtest_smoke_test.py`
- [ ] `python tools/compare_backtests_smoke_test.py`
- [ ] `python tools/sweep_strategy_smoke_test.py`
- [ ] `python tools/sweep_portfolio_smoke_test.py`
- [ ] `python tools/strategy_lab_smoke_test.py`
- [ ] `python tools/strategy_acceptance_gate_smoke_test.py`
- [ ] `python tools/safety_check.py`

## Strategy evidence

Fill this section only when strategy defaults or strategy logic are changed.

- Candle files tested:
- Portfolio sweep command:
- Strategy Lab report path or summary:
- Acceptance gate command:
- Acceptance gate result:
- Known weak files/assets:
- Known risks:

## Safety checklist

- [ ] DEMO-only behavior remains unchanged
- [ ] Real-money controls were not enabled
- [ ] Secrets/session/database/log files were not committed
- [ ] Audit logging remains intact
- [ ] CI checks remain enabled
- [ ] The change does not claim or imply guaranteed profit

## Notes for reviewer

- 
