# Development Notes - Quotex Demo Trading Bot

This file tracks engineering checkpoints, local test results, safety decisions, and next actions for the DEMO-only Telegram bot project.

## Rules

- Never commit `.env`.
- Never commit `data.db`.
- Never write Telegram tokens, Quotex credentials, passwords, or private account data here.
- Current stage: DEMO-only Telegram runtime testing.
- Real-money trading is disabled.
- Live account execution is disabled.
- Update this file after every important engineering checkpoint.

## 2026-05-17 - Local Telegram DEMO Runtime Checkpoint

### Source

- Repository: `Alshughriahmed/quotex-demo-trading-bot`
- Local path: `C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026`
- Runtime directory: `bot`
- Branch: `main`
- Confirmed commit: `bce3ff0 Harden Telegram runtime handlers`
- Source of truth: GitHub fresh clone
- Manual ZIP archives are not used.

### Environment

- OS: Windows
- Python: 3.12.10
- Runtime mode: local polling
- Telegram framework: aiogram
- Environment file: `bot/.env`
- Database file: `bot/data.db`

### Safety Status

- DEMO-only guardrail confirmed active.
- Real account selection is disabled.
- Live-money execution is disabled.
- No Quotex credentials were added.
- No real-money trading was enabled.
- Telegram token is stored locally only in `bot/.env`.
- Current Telegram token was exposed during screenshots and must be rotated before long-running use, sharing, deployment, or production-like testing.

### Local Configuration

- `TELEGRAM_BOT_TOKEN`: configured locally
- `ADMIN_TELEGRAM_IDS`: configured
- `SIGNALS_CHAT_ID`: configured
- `DATABASE_PATH=data.db`

Signals group:

- Name: `QTB Demo Signals`
- Chat ID: `-5178818222`

### Tests Completed

- `python main.py --check`
- `python main.py`
- Telegram polling startup
- `/id`
- `/menu`
- `/status`
- `/signal_chats`
- `/test_signal`
- `/logs`
- `/audit`
- Admin authorization
- Non-admin rejection
- Signals group delivery
- Restart stability
- Git ignore protection for sensitive local files

### Results

- Telegram bot connects successfully.
- Admin user can open the control panel.
- Non-admin users are blocked from the control panel.
- `/test_signal` sends a test signal to exactly one configured group.
- `/signal_chats` shows the correct group ID.
- `/logs` and `/audit` respond without crashing.
- Control panel buttons open without visible runtime errors.
- `bot/.env` is ignored by Git.
- `bot/data.db` is ignored by Git.
- `git status --short` was clean after local testing.

### Known Non-Issue

Running `python main.py` from the repository root fails because `main.py` is inside `bot`.

Correct runtime command:

```powershell
cd C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026\bot
python main.py
```

Correct check command:

```powershell
cd C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026\bot
python main.py --check
```

### Next Actions

1. Rotate the exposed Telegram token through BotFather.
2. Update `bot/.env` locally with the new token.
3. Re-run `python main.py --check`.
4. Re-run `python main.py`.
5. Test `/menu` and `/test_signal` again.
6. Keep the project DEMO-only.
7. Do not add Quotex credentials at this stage.
8. Continue updating this file after every important engineering checkpoint.

## 2026-05-17 - Telegram DEMO Hardening Batch

### Purpose

Apply the first hardening patch after the local Telegram DEMO smoke test and code review.

### Changes

- Disabled Quotex credential input during the Telegram-only DEMO stage.
- Disabled the Quotex settings menu and email/password buttons through the DEMO guardrail.
- Forced local Quotex account status to DEMO and disabled during startup.
- Relabeled the start/stop buttons to `DEMO scanner` to avoid implying real trading.
- Improved signal chat diagnostics:
  - shows whether a chat ID comes from database or `.env fallback`.
  - shows when `.env fallback` exists but is not currently active because database groups exist.
- Added `/clear_signal_chats` and `/clear_groups` to disable saved database signal groups and fall back to `SIGNALS_CHAT_ID`.
- Added friendlier Telegram delivery errors for common group problems.

### Safety Result

- The Telegram-only stage no longer invites the user to enter Quotex credentials.
- The UI is clearer that this is DEMO scanner behavior, not real-money trading.
- Wrong saved group IDs can be disabled without raw SQLite commands.

### Required Local Verification After Pull

Run from `bot`:

```powershell
python main.py --check
python main.py
```

Then test in Telegram:

```text
/menu
/signal_chats
/test_signal
/clear_signal_chats
/signal_chats
/test_signal
```

Expected behavior:

- `/menu` opens normally.
- Start/stop buttons mention `DEMO scanner`.
- Quotex credential entry is not available.
- `/signal_chats` shows source information.
- `/clear_signal_chats` disables database groups and fallback from `.env` becomes active if configured.
- `/test_signal` still sends to the active signals group.

### Still Pending

- Rotate exposed Telegram token before long-running use.
- Add stricter super-admin logic before multi-admin testing.
- Add formal automated tests later.

## 2026-05-17 - Local Verification Of Telegram DEMO Hardening

### Verification Evidence

User pulled commit `3015baa` locally, then verified:

- `git status --short` was clean.
- `git log -1 --oneline` showed `3015baa docs: record telegram demo hardening batch`.
- `python -m py_compile bot/main.py bot/demo_guardrails.py` completed without errors.
- `python main.py --check` connected successfully to Telegram and printed the DEMO-only guardrail.
- `python main.py` started local polling successfully.

### Telegram Tests Verified

- `/menu` opened normally.
- Main buttons showed `DEMO scanner` wording.
- `/signal_chats` initially showed one active group from `database`.
- `/test_signal` sent a test signal successfully to one group.
- `/clear_signal_chats` disabled one saved database group.
- `/signal_chats` then showed one active group from `.env fallback`.
- `/test_signal` still sent successfully to one group after fallback activation.

### Result

Telegram DEMO hardening batch is locally verified.

Current verified status:

- Telegram runtime: PASS
- DEMO guardrail: PASS
- Admin panel: PASS
- Signal group diagnostics: PASS
- Database-to-env fallback behavior: PASS
- Test signal delivery after fallback: PASS

### Still Pending

- Rotate the exposed Telegram token before any long-running use.
- Add stricter super-admin logic before allowing multi-admin testing.
- Add automated tests or a formal manual QA checklist later.
