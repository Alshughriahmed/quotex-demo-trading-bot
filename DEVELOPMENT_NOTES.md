# Development Notes

## Priority 1

1. Keep DEMO-only execution.
2. Add clear logging for every rejected signal.
3. Add a backtesting module before adding more strategies.
4. Split strategy logic later into `strategy_engine.py` and `strategies/`.

## First bug fixed

Old behavior in `TradingRunner.can_scan_by_schedule` calculated elapsed time but always returned `True`.
Now it returns `elapsed >= signal_interval_seconds`.

## Recommended risk defaults

- `max_daily_trades`: 20
- `daily_loss_limit`: 30
- `stop_after_losses`: 3
- `single_open_trade`: true
