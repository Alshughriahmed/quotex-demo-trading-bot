# Experiment Manifest Workflow

This project is DEMO-only. The files described here improve reproducibility and review quality for offline experiments. They do not prove profitability and do not enable real-money trading.

## Why manifests matter

Backtest and sweep reports are only useful when they can be traced back to the exact inputs and command that produced them. A manifest records:

- UTC creation time.
- Current repository commit when available.
- The command used to run the experiment.
- Input candle files with file size and SHA-256 hash.
- Output artifacts with file size and SHA-256 hash.
- A DEMO-only safety note and profitability warning.

## Single-file backtest

Use `--manifest-out` together with at least one output artifact:

```bash
python tools/backtest_strategy.py data/eurusd.json \
  --asset EURUSD \
  --duration 180 \
  --candle-seconds 60 \
  --min-confidence 75 \
  --lookback 90 \
  --step 3 \
  --json-out reports/eurusd_backtest.json \
  --csv-out reports/eurusd_trades.csv \
  --manifest-out reports/eurusd_backtest_manifest.json
```

The manifest will reference the candle input file and the generated JSON/CSV artifacts.

## Strategy parameter sweep

Use this when comparing several parameter combinations on one candle file:

```bash
python tools/sweep_strategy.py data/eurusd.json \
  --asset EURUSD \
  --durations 120 180 300 \
  --candle-seconds 60 \
  --min-confidences 70 75 80 \
  --lookbacks 60 90 120 \
  --steps 3 \
  --csv-out reports/eurusd_sweep.csv \
  --json-out reports/eurusd_sweep.json \
  --manifest-out reports/eurusd_sweep_manifest.json
```

## Portfolio sweep

Use this when checking whether a setting is stable across multiple candle files:

```bash
python tools/sweep_portfolio.py data/candles/ \
  --durations 120 180 300 \
  --candle-seconds 60 \
  --min-confidences 70 75 80 \
  --lookbacks 60 90 120 \
  --steps 3 \
  --csv-out reports/portfolio_sweep.csv \
  --json-out reports/portfolio_sweep.json \
  --manifest-out reports/portfolio_sweep_manifest.json
```

The portfolio manifest records every resolved `.json` and `.csv` candle file found in the provided paths.

## Acceptance gate after portfolio sweep

After creating `portfolio_sweep.json`, run the acceptance gate:

```bash
python tools/strategy_acceptance_gate.py reports/portfolio_sweep.json \
  --top-candidates 3 \
  --min-files 2 \
  --min-closed-trades 30 \
  --min-win-rate 60 \
  --max-loss-rate 45 \
  --max-consecutive-losses 5 \
  --max-drawdown-units 8 \
  --min-final-equity-units 1
```

`PASS` only means the candidate passed conservative engineering filters. It is not a profit guarantee.

## Review checklist before changing strategy logic

Before accepting a strategy change, keep these artifacts together:

1. The input candle files.
2. The backtest or sweep JSON report.
3. The CSV report when available.
4. The matching manifest JSON.
5. The acceptance gate output for portfolio sweeps.

Do not compare reports from different commits or different candle files unless the manifests make that difference explicit.

## Safety rule

All strategy research in this repository remains DEMO-only. Do not use these tools to justify real-money trading.
