# Signal-Only Market Source Plan

## Purpose

The next safe stage is to let the bot read market candles and create signals without automatic DEMO buying.

The project must remain safe by default:

- REAL account behavior stays disabled.
- Automatic DEMO buying stays disabled unless explicitly enabled later.
- Market data can be used for analysis and signal generation only.
- All records must clearly show whether they are simulated, signal-only, or executed DEMO records.

## Current Safety Baseline

The local baseline before adding a market source is:

```text
DEMO scanner: STOPPED
Automatic DEMO buying: DISABLED
Market data source: MISSING
Trades: 0
Exports: 0
```

## Required Behavior

When a market source is configured but `auto_buy_enabled=false`:

1. The bot may fetch candles.
2. The strategy may analyze assets.
3. The bot may send Telegram signals.
4. The bot may create a trade record.
5. The record must be marked as signal-only.
6. The bot must not call automatic DEMO order placement.

## Data Labels

Future records should be easy to separate:

```text
paper_simulated_v1       = generated local test data
SIGNAL_ONLY              = market-sourced signal without buying
OPEN / CLOSED            = executed DEMO record
ERROR                    = failed execution or lifecycle problem
```

## Why This Matters

The project goal is not to rush into execution. The goal is to build a research system that can collect enough clean evidence before deciding whether an execution bot is justified.

Useful sample sizes:

```text
50 signals/trades        = sanity check
100 signals/trades       = weak early comparison
300 signals/trades       = first meaningful tuning review
1000+ signals/trades     = stronger strategy study
4000+ signals/trades     = serious research base
```

## Next Steps

1. Keep auto-buy disabled.
2. Improve reports to show signal-only records separately.
3. Add external dataset tables for imported bot data.
4. Only then configure a market source for signal-only testing.
5. Do not evaluate strategy quality until enough clean records exist.
