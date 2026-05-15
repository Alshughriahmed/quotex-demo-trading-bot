import argparse
import asyncio
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

import database
import menu
from audit_log import audit_summary_text
from config import ConfigError, load_config, startup_summary
from demo_guardrails import DEMO_ONLY_NOTICE, enforce_demo_only
from states import INPUTS, INPUTS_BY_STATE, AdminInput
from trading.trader import TradingRunner


CONFIG = {}
router = Router()


def is_admin(user_id) -> bool:
    return database.is_admin(CONFIG["db_path"], user_id)


async def send_admin_menu(message: Message, menu_key: str = "main") -> None:
    rendered = menu.render_menu(CONFIG["db_path"], menu_key)
    await message.answer(rendered["text"], reply_markup=rendered["reply_markup"])


async def edit_admin_menu(callback: CallbackQuery, rendered: dict) -> None:
    try:
        await callback.message.edit_text(rendered["text"], reply_markup=rendered.get("reply_markup"))
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


def configured_signal_chat_ids() -> list[str]:
    chat_ids = database.get_signal_chat_ids(CONFIG["db_path"])
    if not chat_ids and CONFIG.get("signals_chat_id"):
        chat_ids = [CONFIG["signals_chat_id"]]
    return chat_ids


async def send_test_signal(bot: Bot) -> dict:
    chat_ids = configured_signal_chat_ids()
    if not chat_ids:
        raise RuntimeError("لا توجد مجموعة إشارات مضبوطة. أضف المجموعة من لوحة التحكم أو اضبط SIGNALS_CHAT_ID.")

    sent: list[int] = []
    failed: list[tuple[int, str]] = []
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, "تيست")
            sent.append(chat_id)
        except Exception as exc:
            failed.append((chat_id, str(exc)))

    if not sent and failed:
        raise RuntimeError(format_test_signal_failures(failed))
    return {"sent": sent, "failed": failed}


def format_test_signal_failures(failures: list[tuple[int, str]], limit: int = 5) -> str:
    lines = ["فشل إرسال الإشارة التجريبية لكل المجموعات.", "", "الأخطاء:"]
    for chat_id, error in failures[:limit]:
        lines.append(f"- {chat_id}: {error}")
    if len(failures) > limit:
        lines.append(f"... ومجموعات أخرى فاشلة: {len(failures) - limit}")
    return "\n".join(lines)


def format_test_signal_result(result: dict) -> str:
    sent = result.get("sent", [])
    failed = result.get("failed", [])
    if not failed:
        return f"تم إرسال إشارة تجريبية إلى {len(sent)} مجموعة."

    lines = [
        f"تم إرسال الإشارة التجريبية إلى {len(sent)} مجموعة.",
        f"فشل الإرسال إلى {len(failed)} مجموعة.",
        "",
        "المجموعات التي فشل الإرسال إليها:",
    ]
    for chat_id, error in failed[:5]:
        lines.append(f"- {chat_id}: {error}")
    if len(failed) > 5:
        lines.append(f"... ومجموعات أخرى فاشلة: {len(failed) - 5}")
    return "\n".join(lines)


def signal_chats_text() -> str:
    chat_ids = configured_signal_chat_ids()
    if not chat_ids:
        return (
            "📡 مجموعات الإشارات\n\n"
            "لا توجد مجموعة إشارات مضبوطة.\n\n"
            "أضف مجموعة من لوحة التحكم: 👥 الإدارة ← ➕ إضافة مجموعة، "
            "أو اضبط SIGNALS_CHAT_ID في bot/.env."
        )

    lines = ["📡 مجموعات الإشارات", "", f"العدد: {len(chat_ids)}", ""]
    for index, chat_id in enumerate(chat_ids, start=1):
        lines.append(f"{index}. {chat_id}")
    lines.extend(["", "استخدم /test_signal لتجربة الإرسال لهذه المجموعات."])
    return "\n".join(lines)


@router.message(Command("id"))
async def command_id(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else ""
    await message.answer(f"chat_id: {message.chat.id}\nuser_id: {user_id}")


@router.message(Command("start", "menu"))
async def command_menu(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        await message.answer("غير مصرح لك باستخدام لوحة التحكم.")
        return

    await state.clear()
    await send_admin_menu(message, "main")


@router.message(Command("status"))
async def command_status(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        return
    await message.answer(menu.status_text(CONFIG["db_path"]), reply_markup=menu.back_keyboard("main"))


@router.message(Command("logs", "live_logs"))
async def command_live_logs(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        return
    await message.answer(menu.logs_text(), reply_markup=menu.logs_keyboard("system"))


@router.message(Command("audit", "audit_log"))
async def command_audit_log(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        return
    await message.answer(audit_summary_text(menu.TRADER_LOG_PATH), reply_markup=menu.logs_keyboard("system"))


@router.message(Command("cancel"))
async def command_cancel(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        return
    await state.clear()
    await message.answer("تم إلغاء الإدخال.", reply_markup=menu.render_menu(CONFIG["db_path"], "main")["reply_markup"])


@router.message(Command("test_signal"))
async def command_test_signal(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        return

    try:
        result = await send_test_signal(message.bot)
    except Exception as exc:
        await message.answer(f"فشل إرسال الإشارة التجريبية:\n{exc}")
        return

    await message.answer(format_test_signal_result(result))


@router.message(Command("signal_chats", "groups"))
async def command_signal_chats(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        return
    await message.answer(signal_chats_text(), reply_markup=menu.back_keyboard("admin"))


@router.callback_query(F.data)
async def callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    if not is_admin(user_id):
        await callback.answer("غير مصرح", show_alert=True)
        return

    if callback.data == "btn:logs_status":
        result = {
            "text": audit_summary_text(menu.TRADER_LOG_PATH),
            "reply_markup": menu.logs_keyboard("system"),
        }
        await state.clear()
        await callback.answer("تم تحديث سجل القرارات")
        await edit_admin_menu(callback, result)
        return

    result = menu.handle_callback(CONFIG["db_path"], callback.data or "")
    if result.get("command") == "test_signal":
        try:
            delivery_result = await send_test_signal(callback.bot)
            result["text"] = "🧪 تجربة إشارة\n\n" + format_test_signal_result(delivery_result)
        except Exception as exc:
            result["text"] = f"🧪 تجربة إشارة\n\nفشل إرسال الإشارة التجريبية:\n{exc}"
        await state.clear()
        await callback.answer("تم تنفيذ التجربة")
        await edit_admin_menu(callback, result)
        return

    input_key = result.get("input_key")
    if input_key:
        input_config = INPUTS.get(input_key)
        if not input_config:
            await callback.answer("إدخال غير مدعوم", show_alert=True)
            return
        await state.set_state(input_config["state"])
        await callback.answer(result.get("answer", ""))
        await edit_admin_menu(callback, result)
        return

    await state.clear()
    await callback.answer(result.get("answer", ""))
    await edit_admin_menu(callback, result)


@router.message(
    StateFilter(
        AdminInput.trade_amount,
        AdminInput.min_payout,
        AdminInput.daily_loss_limit,
        AdminInput.max_daily_trades,
        AdminInput.stop_after_losses,
        AdminInput.add_group,
        AdminInput.add_admin,
        AdminInput.quotex_email,
        AdminInput.quotex_password,
        AdminInput.signal_interval_minutes,
    )
)
async def input_handler(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        await state.clear()
        return

    current_state = await state.get_state()
    input_config = INPUTS_BY_STATE.get(current_state)
    if not input_config:
        await state.clear()
        await message.answer("حالة غير معروفة. اكتب /menu للرجوع.")
        return

    if input_config["kind"] == "chat_id":
        await save_group_input(message, state, input_config)
        return

    if input_config["kind"] == "admin_id":
        await save_admin_input(message, state, input_config)
        return

    if input_config["kind"] == "email":
        await save_quotex_email_input(message, state, input_config)
        return

    if input_config["kind"] == "password":
        await save_quotex_password_input(message, state, input_config)
        return

    if input_config["kind"] == "minutes":
        await save_signal_interval_input(message, state, input_config)
        return

    try:
        value = parse_input_value(message.text or "", input_config)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    database.set_setting(CONFIG["db_path"], input_config["setting_key"], value)
    await state.clear()
    rendered = menu.render_menu(CONFIG["db_path"], input_config["return_menu"])
    await message.answer(input_config["saved_text"], reply_markup=rendered["reply_markup"])


async def save_group_input(message: Message, state: FSMContext, input_config: dict) -> None:
    raw = (message.text or "").strip()
    try:
        chat_id = int(raw)
    except ValueError:
        await message.answer("اكتب chat_id صالح. مثال: -1001234567890")
        return

    try:
        chat = await message.bot.get_chat(chat_id)
    except Exception as exc:
        await message.answer(
            "لم أستطع الوصول لهذه المجموعة.\n"
            "تأكد أن البوت مضاف داخل المجموعة وأن الرقم صحيح.\n\n"
            f"الخطأ: {exc}"
        )
        return

    database.add_telegram_chat(
        CONFIG["db_path"],
        chat_id,
        title=chat.title or chat.full_name,
        chat_type=chat.type,
        purpose="signals",
    )
    await state.clear()
    rendered = menu.render_menu(CONFIG["db_path"], input_config["return_menu"])
    await message.answer(f"{input_config['saved_text']}\n\nالمجموعة: {chat.title or chat_id}", reply_markup=rendered["reply_markup"])


async def save_admin_input(message: Message, state: FSMContext, input_config: dict) -> None:
    raw = (message.text or "").strip()
    try:
        admin_id = int(raw)
    except ValueError:
        await message.answer("اكتب Telegram user ID صالح. مثال: 8497188657")
        return

    if admin_id <= 0:
        await message.answer("معرف الأدمن لازم يكون رقم موجب.")
        return

    database.add_admin_user(CONFIG["db_path"], admin_id)
    await state.clear()
    rendered = menu.render_menu(CONFIG["db_path"], input_config["return_menu"])
    await message.answer(f"{input_config['saved_text']}\n\nالأدمن: {admin_id}", reply_markup=rendered["reply_markup"])


async def save_quotex_email_input(message: Message, state: FSMContext, input_config: dict) -> None:
    email = (message.text or "").strip()
    if "@" not in email or "." not in email:
        await message.answer("اكتب إيميل صالح.")
        return

    database.upsert_quotex_account(CONFIG["db_path"], email=email, account_type="DEMO", enabled=True)
    await state.clear()
    rendered = menu.render_menu(CONFIG["db_path"], input_config["return_menu"])
    await message.answer(f"{input_config['saved_text']}\n\nالإيميل: {email}", reply_markup=rendered["reply_markup"])


async def save_quotex_password_input(message: Message, state: FSMContext, input_config: dict) -> None:
    password = (message.text or "").strip()
    if len(password) < 4:
        await message.answer("كلمة السر قصيرة جدًا.")
        return

    database.upsert_quotex_account(CONFIG["db_path"], password=password, account_type="DEMO", enabled=True)
    await state.clear()
    rendered = menu.render_menu(CONFIG["db_path"], input_config["return_menu"])
    await message.answer(input_config["saved_text"], reply_markup=rendered["reply_markup"])


async def save_signal_interval_input(message: Message, state: FSMContext, input_config: dict) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        minutes = float(raw)
    except ValueError:
        await message.answer("اكتب رقم دقائق صالح. مثال: 10 أو 12.5")
        return

    if minutes < 0:
        await message.answer("المدة لا يمكن أن تكون أقل من 0.")
        return

    if minutes == 0:
        database.set_setting(CONFIG["db_path"], "signal_mode", "open")
        database.set_setting(CONFIG["db_path"], "signal_interval_seconds", "0")
        saved = "تم ضبط الوضع: مفتوح"
    else:
        seconds = int(minutes * 60)
        if seconds < 60:
            await message.answer("أقل مدة مسموحة دقيقة واحدة، أو اكتب 0 للوضع المفتوح.")
            return
        database.set_setting(CONFIG["db_path"], "signal_mode", "interval")
        database.set_setting(CONFIG["db_path"], "signal_interval_seconds", str(seconds))
        saved = f"{input_config['saved_text']}\n\nكل {minutes:g} دقائق"

    await state.clear()
    rendered = menu.render_menu(CONFIG["db_path"], input_config["return_menu"])
    await message.answer(saved, reply_markup=rendered["reply_markup"])


@router.message()
async def fallback_message(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        return
    await message.answer(
        "اكتب /menu لفتح لوحة التحكم.\n\n"
        "أوامر مفيدة:\n"
        "/logs للسجل المباشر\n"
        "/audit لسجل قرارات البوت\n"
        "/signal_chats لعرض مجموعات الإشارات"
    )


def parse_input_value(raw: str, input_config: dict):
    value = raw.strip().replace(",", ".")
    if not value:
        raise ValueError("اكتب رقم صالح.")

    if input_config["kind"] == "int":
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError("اكتب رقم صحيح مثل 0 أو 3 أو 20.") from exc
        if number < 0:
            raise ValueError("الرقم لا يمكن أن يكون أقل من 0.")
        if number == 0 and not input_config.get("allow_zero"):
            raise ValueError("هذه القيمة لا تقبل 0.")
        return str(number)

    if input_config["kind"] == "percent":
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError("اكتب نسبة صحيحة مثل 70 أو 75 أو 80.") from exc
        if number < 0 or number > 100:
            raise ValueError("النسبة لازم تكون بين 0 و 100.")
        if number == 0 and not input_config.get("allow_zero"):
            raise ValueError("هذه القيمة لا تقبل 0.")
        return str(number)

    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError("اكتب رقم صالح مثل 1 أو 12.5.") from exc

    if number < 0:
        raise ValueError("الرقم لا يمكن أن يكون أقل من 0.")
    if number == 0 and not input_config.get("allow_zero"):
        raise ValueError("هذه القيمة لا تقبل 0.")
    if number.is_integer():
        return str(int(number))
    return str(number)


async def run_bot(config: dict) -> None:
    bot = Bot(token=config["token"])
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    runner = TradingRunner(bot, config["db_path"])
    runner_task = asyncio.create_task(runner.run(), name="trading-runner")
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        print("Aiogram bot polling started.")
        await dp.start_polling(bot)
    finally:
        await runner.stop()
        runner_task.cancel()
        await asyncio.gather(runner_task, return_exceptions=True)
        await bot.session.close()


async def async_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init-db", action="store_true", help="Create data.db and seed defaults")
    parser.add_argument("--check", action="store_true", help="Check Telegram token")
    parser.add_argument("--check-config", action="store_true", help="Validate local configuration without starting the bot")
    args = parser.parse_args()

    require_token = not args.init_db
    app_config = load_config(require_token=require_token)
    config = app_config.as_dict()
    CONFIG.update(config)

    database.init_db(
        config["db_path"],
        admin_ids=config["admin_ids"],
        signals_chat_id=config["signals_chat_id"],
    )
    enforce_demo_only(config["db_path"])

    if args.init_db:
        print(f"Database ready: {config['db_path']}")
        print(DEMO_ONLY_NOTICE)
        print(startup_summary(app_config))
        return

    if args.check_config:
        print(DEMO_ONLY_NOTICE)
        print(startup_summary(app_config))
        return

    if args.check:
        bot = Bot(token=config["token"])
        try:
            me = await bot.get_me()
            print(f"Connected to Telegram bot: @{me.username} (id={me.id})")
            print(DEMO_ONLY_NOTICE)
            print(startup_summary(app_config))
        finally:
            await bot.session.close()
        return

    print(DEMO_ONLY_NOTICE)
    print(startup_summary(app_config))
    await run_bot(config)


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("Bot stopped.")
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        print("Create bot/.env from .env.example and fill your local private values.", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        raise
