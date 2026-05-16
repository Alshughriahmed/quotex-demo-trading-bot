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
python main.py```

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
