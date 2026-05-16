# Local Telegram DEMO Runbook

This runbook documents the current local Telegram DEMO setup for the project.

The goal is to run and test the Telegram bot locally on Windows without real-money trading, without real Quotex credentials, and without production deployment.

## Scope

This stage covers:

- Local Telegram bot startup.
- Telegram connection check.
- Admin user configuration.
- Signals group configuration.
- Admin panel smoke testing.
- DEMO test signal delivery.
- Git safety checks for local secret files.

This stage does not cover:

- Real-money trading.
- Real Quotex credentials.
- Live account execution.
- Production deployment.
- Public hosting.

## Source of Truth

Use GitHub as the only source of truth:

- Repository: `Alshughriahmed/quotex-demo-trading-bot`
- Runtime directory: `bot`
- Branch: `main`

Do not use manually created ZIP archives as the source of truth.

## Safety Rules

- Never commit `bot/.env`.
- Never commit `bot/data.db`.
- Never paste Telegram tokens into chat, screenshots, commits, issues, logs, or documentation.
- Never add Quotex credentials during this stage.
- Keep the project DEMO-only.
- Rotate any Telegram token that was exposed during screenshots or sharing.

## Local Requirements

Tested environment:

- Windows
- Python 3.12.10
- `aiogram`
- `python-dotenv`

Minimal Telegram-only install:

```powershell
cd C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026\bot
python -m pip install --upgrade pip
python -m pip install aiogram python-dotenv
```

Do not install the full `requirements.txt` unless the next stage explicitly needs it.

## Local `.env` Shape

The file must exist locally at:

```text
bot/.env
```

Expected shape:

```env
TELEGRAM_BOT_TOKEN=your_local_token_here
ADMIN_TELEGRAM_IDS=your_telegram_user_id_here
SIGNALS_CHAT_ID=your_signals_group_chat_id_here
DATABASE_PATH=data.db
```

The `.env` file is local only and must not be committed.

## Create Telegram Bot

1. Open `@BotFather`.
2. Run `/newbot`.
3. Create the bot name and username.
4. Copy the token.
5. Put the token only in `bot/.env`.

Do not share the token.

## Check Configuration

From the runtime directory:

```powershell
cd C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026\bot
python main.py --check
```

Expected result:

- Telegram connection succeeds.
- DEMO-only guardrail is active.
- Token is configured.
- Admin IDs are configured after `/id` is completed.
- Signals chat is configured after group setup.

## Run Locally

```powershell
cd C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026\bot
python main.py
```

Keep the PowerShell window open. The bot only responds while the local process is running.

## Get Admin User ID

Open the bot directly in Telegram and send:

```text
/id
```

Copy the returned `user_id` into `bot/.env`:

```env
ADMIN_TELEGRAM_IDS=your_telegram_user_id_here
```

Restart the bot after changing `.env`.

## Configure Signals Group

1. Create a Telegram group for DEMO signals.
2. Add the bot to the group.
3. Send in the group:

```text
/id
```

If needed:

```text
/id@your_bot_username
```

If the displayed ID is unclear, fetch updates directly:

```powershell
python -c "import os,json,urllib.request; from dotenv import load_dotenv; load_dotenv('.env'); token=os.getenv('TELEGRAM_BOT_TOKEN'); url='https://api.telegram.org/bot'+token+'/getUpdates?limit=20'; data=json.loads(urllib.request.urlopen(url,timeout=20).read().decode()); print(json.dumps(data, ensure_ascii=False, indent=2))"
```

Use the `chat.id` value from the group update as `SIGNALS_CHAT_ID`.

## Clear Wrong Local Chat IDs

If wrong group IDs were saved during testing:

```powershell
python -c "import sqlite3; db=sqlite3.connect('data.db'); db.execute('DELETE FROM telegram_chats'); db.commit(); print('telegram_chats cleared')"
```

This only clears local chat routing rows. It does not change the Telegram token or admin ID.

## Smoke Test Commands

From the admin Telegram account:

```text
/status
/signal_chats
/test_signal
/logs
/audit
/menu
```

Expected result:

- `/status` responds.
- `/signal_chats` shows the configured signals group.
- `/test_signal` sends one DEMO test signal to the configured group.
- `/logs` responds without crashing.
- `/audit` responds without crashing.
- `/menu` opens the admin panel.

## Authorization Test

From a second Telegram account, send:

```text
/start
/menu
```

Expected result:

- The second account is rejected.
- The admin panel is not shown.

## Git Safety Checks

From the repository root:

```powershell
cd C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026
git status --short
git check-ignore -v bot/.env
git check-ignore -v bot/data.db
```

Expected result:

- `git status --short` should not show `bot/.env` or `bot/data.db`.
- `bot/.env` should be ignored.
- `bot/data.db` should be ignored.

## Known Non-Issue

This is wrong from the repository root:

```powershell
python main.py
```

`main.py` is inside `bot`. Use:

```powershell
cd C:\Users\alshu_6e3b5qq\Desktop\QTB-GITHUB-FRESH-2026\bot
python main.py
```

## Current Local DEMO Checkpoint

The local Telegram DEMO checkpoint passed with:

- Telegram connection working.
- Local polling working.
- DEMO-only guardrail active.
- Admin panel working.
- Non-admin access blocked.
- Signals group configured.
- DEMO test signal delivered.
- `.env` ignored by Git.
- `data.db` ignored by Git.
- `DEVELOPMENT_NOTES.md` updated.

## Required Before Serious Use

Rotate the exposed Telegram token through BotFather, update `bot/.env`, then re-run:

```powershell
python main.py --check
python main.py
```

Then test:

```text
/menu
/test_signal
```
