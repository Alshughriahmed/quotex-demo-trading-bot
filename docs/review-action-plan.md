# Review hardening action plan

This file tracks the engineering review findings before the first real Telegram run.

## Apply before the Telegram run

1. Re-enable signal chats when an admin adds a previously disabled group again.
2. Protect Telegram callback handling with a clear error answer instead of leaving buttons spinning.
3. Verify that the user adding a signal group is an administrator or creator in that group.
4. Keep the signal group admin button behavior consistent and documented.

## Apply after the first Telegram run

1. Improve Quotex credential storage before any regular use.
2. Make the external pyquotex dependency less fragile in CI.
3. Add focused tests for signal group setup and callback behavior.

## Safety notes

- DEMO-only behavior must remain unchanged.
- Real-money controls must not be enabled.
- Backtests and smoke tests are engineering diagnostics, not profitability proof.
