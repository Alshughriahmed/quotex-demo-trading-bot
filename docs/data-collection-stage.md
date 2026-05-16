# Data Collection Stage

## Purpose

This stage turns the Telegram DEMO bot into a measurable testing system.

The goal is not real-money execution. The goal is to collect enough clean DEMO records to evaluate whether the strategy deserves deeper testing.

## Current Data Source

The local SQLite database file is:

```text
bot/data.db
```

The main data table is:

```text
trades
```

This table already stores useful DEMO testing fields such as:

- asset
- direction
- signal time
- entry time
- expiry time
- duration
- confidence
- amount
- result
- profit/loss
- entry price
- exit price
- RSI
- EMA values
- EMA gap
- ADX
- ATR
- payout
- market session
- entry delay
- buy latency
- loss streak
- candle body ratio
- price slippage
- broker open delay
- execution offset
- trend
- volatility
- strategy name
- decision reason
- Telegram message references
- status
- error message

## New Local Export Tool

A local CSV export tool was added:

```powershell
cd C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026\bot
python tools\export_trades.py
```

Optional examples:

```powershell
python tools\export_trades.py --status CLOSED
python tools\export_trades.py --limit 50
python tools\export_trades.py --output exports\latest_trades.csv
```

Exports are written locally under:

```text
bot/exports/
```

The export directory must remain local and should not be committed to Git.

## Stage Rules

- Keep the bot DEMO-only.
- Do not add Quotex credentials during this stage.
- Do not commit `bot/data.db`.
- Do not commit exported CSV files unless they have been intentionally anonymized for documentation.
- Do not judge the strategy from a few trades.
- Collect a meaningful sample before tuning.

## Minimum Useful Sample

Before changing strategy rules, collect at least:

- 50+ closed DEMO trades for basic sanity review.
- 100+ closed DEMO trades for first weak/strong pair review.
- 300+ closed DEMO trades before making serious confidence-threshold decisions.

## First Analysis Questions

After enough records exist, evaluate:

1. Which assets have the highest and lowest win rate?
2. Which market sessions perform best?
3. Which confidence ranges are actually useful?
4. Does high ADX improve results?
5. Does high ATR or high volatility hurt results?
6. Does payout filtering improve or reduce opportunity quality?
7. Do entry delay and broker open delay correlate with losses?
8. Which decision reasons produce weak trades?

## Next Engineering Steps

1. Verify the export tool locally.
2. Add `bot/exports/` to `.gitignore` if missing.
3. Add a Telegram report command later for data quality status.
4. Add an offline analysis script after a meaningful sample exists.
5. Only after DEMO data is credible, discuss paper trading and deeper broker integration.
