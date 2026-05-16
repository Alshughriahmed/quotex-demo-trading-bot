# Telegram Runtime Code Review

Date: 2026-05-17

Scope: Telegram runtime, admin authorization, callback handling, local DEMO safety, test-signal routing, and obvious risk points before adding any new feature.

Repository state reviewed: `main` after local Telegram DEMO checkpoint and runbook creation.

## Executive Result

Telegram local DEMO runtime is good enough for local smoke testing, but it is not yet clean enough for the next engineering stage without hardening.

Current status:

- Local Telegram runtime works.
- Admin authorization works.
- Non-admin users are blocked from the control panel.
- Test signal delivery works.
- DEMO-only guardrail is active.
- Secret files are ignored by Git.

Required before next feature work:

1. Disable or hide Quotex credential inputs during the Telegram-only stage.
2. Make `Start bot` behavior clearly DEMO-scan-only or block it behind an explicit stage flag.
3. Improve signal group diagnostics so DB-stored groups and `.env` fallback are clear.
4. Add removal/clear tooling for wrong signal groups.
5. Add stronger admin-management guardrails.

## Reviewed Files

- `bot/main.py`
- `bot/menu.py`
- `bot/database.py`
- `bot/config.py`
- `bot/demo_guardrails.py`
- `bot/states.py`
- `bot/trading/trader.py`

## What Is Solid

### 1. Admin gate exists on the important Telegram entry points

Commands such as `/menu`, `/status`, `/logs`, `/audit`, `/test_signal`, and `/signal_chats` check `is_admin()` before responding with admin content.

Callback queries also pass through `safe_callback_handler()`, which rejects non-admin users before routing button actions.

Result: non-admin control-panel access is blocked.

### 2. `/id` is intentionally open

`/id` responds without admin authorization. This is useful during initial setup because the admin needs to discover their own Telegram user ID before `ADMIN_TELEGRAM_IDS` is configured.

This is acceptable for the current stage.

### 3. Callback runtime has a defensive wrapper

The outer callback handler catches unexpected exceptions, logs the failure, tries to clear FSM state, and shows a generic error alert.

This protects the Telegram UI from completely breaking on callback errors.

### 4. DEMO-only guardrail exists and runs during startup

Startup calls `enforce_demo_only()`, which forces `account_type=DEMO`, disables confusing REAL account buttons, and forces the Quotex account type to DEMO.

The runtime also blocks non-DEMO auto buying in `TradingRunner.create_and_send_trade()`.

### 5. Configuration validation is reasonable

`config.py` validates placeholder tokens, validates numeric admin IDs, validates negative-capable signal chat IDs, normalizes `DATABASE_PATH`, and prints startup summaries without leaking the actual token.

### 6. Logs are read from the tail, not the full file

`menu.read_recent_log_lines()` reads only the last 120 KB of `trader.log`, which reduces event-loop blocking risk compared with reading the full log file.

## Findings And Required Actions

## P0 - Keep Token Rotation Pending But Mandatory

Current test token was exposed during screenshots. This does not block local testing, but it blocks any serious or long-running use.

Required action:

- Rotate token through BotFather before any extended run, public sharing, deployment, or production-like test.
- Update only local `bot/.env`.
- Re-run:

```powershell
python main.py --check
python main.py
```

Then test:

```text
/menu
/test_signal
```

## P1 - Quotex credential input should be disabled in the Telegram-only stage

Problem:

The UI still contains buttons for changing Quotex email and password. The handlers store those values in `quotex_accounts` inside SQLite. Even if DEMO-only guardrails exist, this is too early and creates a bad operational habit.

Why this matters:

- The current project stage explicitly does not use Quotex credentials.
- SQLite local DB stores the password as plain text.
- A user can accidentally enter real credentials.

Required action:

- Disable the `quotex_menu`, `change_quotex_email`, and `change_quotex_password` buttons for the current stage.
- Or replace the screen with a clear blocked message: `Quotex credential input is disabled during Telegram-only DEMO testing.`
- Keep `clear_quotex_account` available only if credentials already exist locally.

Acceptance criteria:

- The admin panel does not invite the user to enter Quotex credentials.
- Any attempt to reach credential input returns a blocked DEMO-stage message.
- Existing local credential clearing remains possible.

## P1 - `Start bot` can start the trading runner path too early

Problem:

The main menu has `Start bot` / `Stop bot` buttons that set `bot_enabled=true/false`. `TradingRunner.tick()` starts scanning when `bot_enabled=true`.

Even though live-money execution is blocked and account type is forced to DEMO, this button can move the system beyond simple Telegram smoke testing.

Required action:

- Rename the button to make the stage clear, for example: `Start DEMO scanner`.
- Or block it with a stage flag until the next milestone is explicitly approved.
- Add a clear message that no real trading or real account execution is available.

Acceptance criteria:

- Pressing `Start bot` cannot accidentally imply real trading.
- The UI language makes clear that this is DEMO-only and not connected to real money.

## P1 - Signal group source is confusing: DB first, `.env` fallback second

Problem:

`configured_signal_chat_ids()` reads saved groups from `telegram_chats` first. Only if the database has no signal groups does it fall back to `SIGNALS_CHAT_ID` from `.env`.

This caused real confusion during local testing because an old/wrong DB chat ID can override a corrected `.env` value.

Required action:

- Update `/signal_chats` to show the source of each group: `database` or `.env fallback`.
- Add a UI action or command to remove wrong signal groups from the database.
- Add a diagnostic warning when database groups exist and `.env` also has a different fallback value.

Acceptance criteria:

- `/signal_chats` makes it obvious which ID is active and where it came from.
- Wrong groups can be removed without running raw SQLite commands.

## P2 - Add safer signal group management

Problem:

Adding a group validates `get_chat()` and verifies the admin is group manager, which is good. But there is no remove/list-with-title/manage flow beyond simple listing.

Required action:

- Add `remove_group` workflow.
- Show group title, chat ID, type, enabled status, and source.
- Prefer soft-disable over delete for safety.

Acceptance criteria:

- Admin can add, list, and disable a signal group from Telegram UI.
- No manual DB cleanup is needed for normal mistakes.

## P2 - Admin management needs stronger guardrails

Problem:

Any current admin can add another admin by entering a Telegram user ID. For single-user local testing this is acceptable. For wider testing it is too permissive.

Required action:

- Introduce a `super_admin` concept based on `ADMIN_TELEGRAM_IDS` from `.env`.
- Only super-admins should add new admins.
- Add audit entry when an admin is added.
- Consider two-step confirmation before adding an admin.

Acceptance criteria:

- Normal admins cannot silently add other admins unless explicitly allowed.
- Every admin-add event is auditable.

## P2 - Callback parsing should be stricter

Problem:

`asset:toggle:<id>` converts the last segment directly to int. The outer safe callback wrapper catches errors, so this is not catastrophic, but it is still sloppy.

Required action:

- Validate callback format before converting.
- Return a friendly error for invalid asset callback data.

Acceptance criteria:

- Malformed callback data never reaches an exception path for expected invalid input.

## P2 - Improve Telegram error messages for test signal delivery

Problem:

`send_test_signal()` catches broad exceptions and displays the raw Telegram error. That helped debugging, but normal admin UX should be clearer.

Required action:

- Detect common Telegram errors:
  - `chat not found`
  - bot removed from group
  - bot lacks permission
  - invalid chat ID
- Return a short admin-friendly diagnosis and a suggested fix.

Acceptance criteria:

- If test-signal delivery fails, the message tells the admin exactly what to check.

## P3 - Avoid storing future credentials in plain SQLite

Problem:

`quotex_accounts.password` is stored as plain text in SQLite.

Required action for any future credential stage:

- Do not store real passwords in SQLite.
- Prefer environment variables, OS keyring, or encrypted secret storage.
- Keep real credentials out of Git, logs, screenshots, and Telegram messages.

Acceptance criteria:

- No real credential is stored in plain local DB.

## Recommended Next Implementation Order

Do not start with Quotex integration.

Implement in this order:

1. Disable/hide Quotex credential input for Telegram-only DEMO stage.
2. Improve `/signal_chats` source diagnostics.
3. Add remove/disable signal group flow.
4. Rename or gate `Start bot` as DEMO scanner only.
5. Add super-admin restrictions for adding admins.
6. Improve Telegram delivery error messages.
7. Add small regression tests or manual QA checklist updates.

## Manual QA After Hardening

After implementing the next hardening patch, repeat:

```text
/id
/menu
/status
/signal_chats
/test_signal
/logs
/audit
```

Also repeat non-admin test:

```text
/start
/menu
```

Expected result:

- Admin works.
- Non-admin blocked.
- Test signal works.
- Quotex credentials cannot be entered during this stage.
- Signal group diagnostics clearly show the active source.
- Git remains clean.

## Final Judgment

The current Telegram runtime is a valid local DEMO foundation.

It is not yet ready for the next feature stage until the Telegram-only boundaries are made clearer and the Quotex credential path is disabled or gated.
