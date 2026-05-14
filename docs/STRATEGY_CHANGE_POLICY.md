# Strategy change policy

This project is DEMO-only. Strategy changes are engineering experiments, not trading guarantees.

The purpose of this policy is to prevent random or emotional strategy edits. A strategy change should only be accepted when it is supported by repeatable offline evidence and does not weaken safety guardrails.

## Non-negotiable rules

1. Real-money execution must remain disabled.
2. Secrets, session files, local databases, and logs must never be committed.
3. Strategy changes must not bypass DEMO-only guardrails.
4. Strategy changes must not remove audit logging.
5. Strategy changes must not disable CI checks.

## Required evidence before changing strategy defaults

A pull request that changes default strategy behavior should include:

1. What changed in the strategy.
2. Why the change was proposed.
3. Which candle files were tested.
4. The exact sweep command used.
5. The Strategy Lab report summary.
6. The acceptance gate result.
7. Known limitations and risks.

## Minimum validation flow

Run a portfolio sweep:

```bash
python tools/sweep_portfolio.py candles/ \
  --durations 120 180 300 \
  --min-confidences 65 70 75 80 \
  --lookbacks 60 90 120 \
  --steps 1 3 \
  --csv-out reports/portfolio_sweep.csv \
  --json-out reports/portfolio_sweep.json
```

Generate a Strategy Lab report:

```bash
python tools/strategy_lab.py reports/portfolio_sweep.json \
  --top 10 \
  --markdown-out reports/strategy_lab.md
```

Run the acceptance gate:

```bash
python tools/strategy_acceptance_gate.py reports/portfolio_sweep.json \
  --min-files 3 \
  --min-closed-trades 50 \
  --min-win-rate 60 \
  --min-worst-file-score 1 \
  --min-consistency-score 35 \
  --max-loss-rate 45
```

## When to reject a strategy change

Reject or postpone the change when any of these are true:

1. It was tested on only one file.
2. The number of closed trades is too small.
3. The worst-file score is weak or negative.
4. The loss rate is too high.
5. The Strategy Lab decision is `REJECT`.
6. The Strategy Lab decision is only `WATCHLIST` and there is no fresh-data validation.
7. The change makes fewer trades look better only by avoiding almost everything.
8. The change improves CALL but seriously weakens PUT, or the opposite.
9. The change reduces logging or makes decisions harder to audit.
10. The change is justified by screenshots or feelings instead of repeatable reports.

## Interpreting PASS

A passing acceptance gate means:

```text
The candidate is strong enough for further demo validation.
```

It does not mean:

```text
The strategy is profitable.
The bot is safe for real money.
The settings should never be changed again.
```

## Recommended PR template for strategy changes

```markdown
## Strategy change

Explain the strategy logic changed in this PR.

## Why

Explain why this change is worth testing.

## Offline evidence

- Candle files tested:
- Portfolio sweep command:
- Strategy Lab report path or summary:
- Acceptance gate command:
- Acceptance gate result:

## Risk review

- What got better?
- What got worse?
- Which assets/time periods were weak?
- Is the trade count meaningful?

## Safety

- DEMO-only guardrails unchanged: yes/no
- Audit logging unchanged: yes/no
- CI checks passing: yes/no
```

## Demo validation after merge

After merging a strategy change, treat it as a demo experiment.

Watch:

```text
live AUDIT decision reasons
blocked trades
trade frequency
loss clusters
PUT vs CALL behavior
asset-specific weakness
```

If demo behavior contradicts the offline reports, revert or reduce the change.

## Final rule

No strategy result is accepted because it looks exciting. It is accepted only when it survives measurement, review, and conservative safety rules.
