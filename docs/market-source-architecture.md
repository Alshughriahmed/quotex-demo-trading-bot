# Market Source Architecture

## Purpose

The bot needs a clean separation between market data and execution.

A market source should provide candles/prices for analysis only. It must not place orders, buy positions, or enable REAL trading.

## Core Separation

```text
Market Source  -> candles/prices only
Strategy       -> analysis and signal decision
Telegram       -> signal/report delivery
Database       -> signal-only or DEMO records
Execution      -> separate layer, disabled by default
```

## Current Safe State

The current project state is intentionally not ready for real DEMO data collection:

```text
DEMO scanner: STOPPED
Automatic DEMO buying: DISABLED
Market data source: MISSING
Native trades: 0
External research tables: initialized
```

## Signal-Only Rule

When a market source is later configured while `auto_buy_enabled=false`:

1. Candles may be read.
2. Strategy analysis may run.
3. Telegram signals may be sent.
4. Database records may be created as `SIGNAL_ONLY`.
5. Automatic DEMO buying must not happen.
6. REAL mode stays disabled.

## Market Source Contract

Every market source should expose a small, inspectable status:

```text
source_key
label
configured: true/false
enabled: true/false
safe_for_signal_only: true/false
reason
```

Future candle models should normalize these fields:

```text
asset
open_time
open
high
low
close
volume
source
```

## Planned Source Types

```text
none/local_missing       = current state, no market data
quotex_demo_local        = possible future local source for candles only
external_csv_replay      = possible research/replay source from files
paper_simulator          = simulation source for UI/report testing only
```

## Safety Requirements

Before any real market source is enabled:

- auto-buy must remain disabled.
- startup guard must stop scanner if source is missing.
- data quality report must show readiness clearly.
- source check must print no secrets.
- external datasets must stay separate from native trades.

## Not In Scope Yet

This document does not enable:

- REAL account behavior
- automatic DEMO buying
- broker account input
- live execution
- strategy quality claims

The next step is to add source status tooling and a clean placeholder registry.
