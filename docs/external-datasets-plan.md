# External Datasets Plan

## Purpose

The user may later provide a compressed project from another DEMO trading bot. That project may contain useful historical logs, CSV files, SQLite databases, strategies, or trade results.

Those records must be treated as external research data, not as native records from this project.

## Core Rule

Do not mix external records directly into the main `trades` table.

External data should be imported into separate tables so it can be analyzed, compared, validated, and discarded if it is not trustworthy.

## Proposed Tables

```text
external_datasets
external_trades
external_strategies
external_import_logs
```

## Why Separation Matters

External records may have different assumptions:

- different broker
- different candle source
- different timezone
- different asset naming
- different duration
- different payout logic
- manual vs automatic execution
- incomplete logs
- unknown strategy rules
- unknown reliability

Mixing those records with native records would pollute analysis.

## Import Workflow

When an external bot archive is provided:

1. Extract safely outside Git-tracked source files.
2. Search for databases, CSV files, logs, and strategy files.
3. Identify trade-like records.
4. Map available columns to a normalized external schema.
5. Record missing fields and confidence level.
6. Import into external tables only.
7. Generate an external data quality report.
8. Compare with native signal-only or DEMO results later.

## Minimum Metadata Per Dataset

Each imported dataset should store:

- dataset name
- source description
- import timestamp
- original file names
- detected format
- row counts
- trust level
- notes

## Analysis Goal

External datasets can help answer:

- Which strategies are worth testing?
- Which symbols appear consistently strong or weak?
- Which timeframes are risky?
- Which indicators appear useful?
- How large is the historical sample?
- Are the results trustworthy enough to influence our next experiment?

## Safety

External archives may contain secrets. Before importing:

- never commit raw archives
- never commit `.env` files
- never print tokens/passwords/cookies/session files
- keep raw imports local
- only commit safe import tools and documentation
