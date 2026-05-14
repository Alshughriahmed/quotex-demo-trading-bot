# Backtesting guide

This project is a DEMO-only trading bot. The tools in this guide are for offline engineering measurement only. They do not prove profitability and they do not enable real-money execution.

## Why backtesting exists here

Before changing the strategy, every change should be measured on the same candle data. This helps compare versions by repeatable numbers instead of guessing from a few demo trades.

The current offline flow is:

```text
candle data -> backtest report -> compare reports -> decide whether a strategy change is worth keeping
```

## Candle data format

The backtest tool accepts `.json` and `.csv` candle files.

Each candle must contain:

```text
time, open, high, low, close
```

A JSON file can be a direct list:

```json
[
  {"time": 1, "open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005},
  {"time": 2, "open": 1.1005, "high": 1.1015, "low": 1.1000, "close": 1.1010}
]
```

Or an object with a `candles` key:

```json
{
  "candles": [
    {"time": 1, "open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005}
  ]
}
```

A CSV file should have a header like:

```csv
time,open,high,low,close
1,1.1000,1.1010,1.0990,1.1005
2,1.1005,1.1015,1.1000,1.1010
```

## Run a basic backtest

```bash
python tools/backtest_strategy.py candles.json \
  --asset EUR/USD \
  --duration 180 \
  --min-confidence 75 \
  --lookback 90
```

The console report shows:

```text
Signals
Wins
Losses
Draws
No-trade windows
Closed trades
Win rate excluding draws
Win rate including draws
```

## Export JSON and CSV reports

Use JSON for later comparison and CSV for spreadsheet review:

```bash
mkdir -p reports

python tools/backtest_strategy.py candles.json \
  --asset EUR/USD \
  --duration 180 \
  --min-confidence 75 \
  --lookback 90 \
  --json-out reports/eurusd_m75_l90.json \
  --csv-out reports/eurusd_m75_l90_trades.csv
```

The JSON report contains:

```text
settings: parameters used in the run
summary: win/loss/draw and win-rate metrics
trades: one object per simulated trade
```

The CSV report contains one row per simulated trade.

## Compare multiple backtests

After producing several JSON reports, compare them:

```bash
python tools/compare_backtests.py reports/ --csv-out reports/comparison.csv
```

The comparison table ranks reports using a simple engineering score that rewards win rate and enough closed trades.

Important: the score is only a comparison helper. A high score does not guarantee profit.

## Suggested experiment naming

Use names that show the tested parameters:

```text
eurusd_m70_l60.json
eurusd_m75_l90.json
eurusd_m80_l120.json
```

Where:

```text
m70 = min confidence 70
l60 = lookback 60 candles
```

## Safe engineering rules

1. Do not judge a strategy from one small file.
2. Do not keep a strategy only because it has a high win rate with very few trades.
3. Compare the same candle data across strategy versions.
4. Watch losses and no-trade windows, not only wins.
5. Keep real-money execution disabled. This project remains DEMO-only.

## Current recommended workflow

```bash
python tools/backtest_strategy.py candles.json --asset EUR/USD --duration 180 --min-confidence 70 --lookback 60 --json-out reports/eurusd_m70_l60.json
python tools/backtest_strategy.py candles.json --asset EUR/USD --duration 180 --min-confidence 75 --lookback 90 --json-out reports/eurusd_m75_l90.json
python tools/backtest_strategy.py candles.json --asset EUR/USD --duration 180 --min-confidence 80 --lookback 120 --json-out reports/eurusd_m80_l120.json
python tools/compare_backtests.py reports/ --csv-out reports/comparison.csv
```

The next planned improvement is a parameter sweep tool that runs these combinations automatically.
