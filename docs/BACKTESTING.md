# Backtesting guide

This project is a DEMO-only trading bot. The tools in this guide are for offline engineering measurement only. They do not prove profitability and they do not enable real-money execution.

## Why backtesting exists here

Before changing the strategy, every change should be measured on the same candle data. This helps compare versions by repeatable numbers instead of guessing from a few demo trades.

The current offline flow is:

```text
candle data
-> single backtest
-> report export
-> report comparison
-> parameter sweep
-> portfolio sweep
-> Strategy Lab decision report
```

## Candle data format

The backtest tools accept `.json` and `.csv` candle files.

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

## 1. Run a basic backtest

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

## 2. Export JSON and CSV reports

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

## 3. Compare multiple backtests

After producing several JSON reports, compare them:

```bash
python tools/compare_backtests.py reports/ --csv-out reports/comparison.csv
```

The comparison table ranks reports using a simple engineering score that rewards win rate and enough closed trades.

Important: the score is only a comparison helper. A high score does not guarantee profit.

## 4. Run a parameter sweep on one candle file

Use `sweep_strategy.py` to test many parameter combinations on one file:

```bash
python tools/sweep_strategy.py candles/eurusd.json \
  --asset EUR/USD \
  --durations 120 180 300 \
  --min-confidences 65 70 75 80 \
  --lookbacks 60 90 120 \
  --steps 1 3 \
  --csv-out reports/eurusd_sweep.csv \
  --json-out reports/eurusd_sweep.json
```

This helps find which settings behave better on a specific asset or time period.

Do not accept a setting only because it wins on one file. One-file sweep is a search tool, not a final decision.

## 5. Run a portfolio sweep across multiple files

Use `sweep_portfolio.py` when you have several candle files:

```bash
python tools/sweep_portfolio.py candles/ \
  --durations 120 180 300 \
  --min-confidences 65 70 75 80 \
  --lookbacks 60 90 120 \
  --steps 1 3 \
  --csv-out reports/portfolio_sweep.csv \
  --json-out reports/portfolio_sweep.json
```

This is stronger than a one-file sweep because it ranks combinations by consistency across files.

The portfolio ranking considers:

```text
average score
worst-file score
closed trades
win rate
losses
```

A good candidate should not only perform well on average. It should also avoid collapsing on the worst file.

## 6. Generate a Strategy Lab report

After creating a portfolio sweep JSON, generate a human-readable decision report:

```bash
python tools/strategy_lab.py reports/portfolio_sweep.json \
  --top 10 \
  --markdown-out reports/strategy_lab.md
```

Strategy Lab classifies top candidates as:

```text
PROMISING = good enough to keep as a temporary benchmark
WATCHLIST = interesting, but needs more validation
REJECT = not good enough for strategy changes
```

Strategy Lab also writes:

```text
best candidate
risk notes
recommended next action
DEMO-only safety note
```

## Decision rules before changing strategy defaults

Do not change the default strategy settings unless all of these are true:

1. The candidate is not based on one file only.
2. The candidate has enough closed trades to be meaningful.
3. The worst-file score is not weak or negative.
4. The loss count is acceptable compared with closed trades.
5. The Strategy Lab decision is `PROMISING`, not only `WATCHLIST`.
6. The same candidate still looks reasonable on fresh candle data not used in the first sweep.

If any rule fails, keep the candidate as research only.

## Suggested experiment naming

Use names that show the tested parameters:

```text
eurusd_m70_l60.json
eurusd_m75_l90.json
eurusd_m80_l120.json
portfolio_sweep_2026_05_14.json
strategy_lab_2026_05_14.md
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
5. Validate on fresh data before changing defaults.
6. Keep real-money execution disabled. This project remains DEMO-only.

## Recommended full workflow

```bash
mkdir -p reports

python tools/sweep_portfolio.py candles/ \
  --durations 120 180 300 \
  --min-confidences 65 70 75 80 \
  --lookbacks 60 90 120 \
  --steps 1 3 \
  --csv-out reports/portfolio_sweep.csv \
  --json-out reports/portfolio_sweep.json

python tools/strategy_lab.py reports/portfolio_sweep.json \
  --top 10 \
  --markdown-out reports/strategy_lab.md
```

Read `reports/strategy_lab.md` first. Only inspect the raw CSV/JSON when you need deeper analysis.

## Next planned improvement

The next improvement should be a strategy decision gate: a small tool that fails the command when a sweep result does not meet minimum acceptance rules. This can later protect strategy-change pull requests from being merged without evidence.
