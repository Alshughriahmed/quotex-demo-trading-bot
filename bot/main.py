import argparse
import asyncio
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

import database
import menu
from states import INPUTS, INPUTS_BY_STATE, AdminInput
from trading.trader import TradingRunner


ENV_PATH = Path(".env")
CONFIG = {}
router = Router()


def load_env(path: Path = ENV_PATH) -> dict:
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return {**values, **os.environ}


def parse_list(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def config_from_env(env: dict) -> dict:
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    db_path = env.get("DATABASE_PATH", "data.db").strip() or "data.db"
    admin_ids = parse_list(env.get("ADMIN_TELEGRAM_IDS", ""))
    signals_chat_id = env.get("SIGNALS_CHAT_ID", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing in .env")
    return {
        "token": token,
        "db_path": db_path,
        "admin_ids": admin_ids,
        "signals_chat_id": signals_chat_id,
    }


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


async def send_test_signal(bot: Bot) -> None:
    chat_ids = database.get_signal_chat_ids(CONFIG["db_path"])
    if not chat_ids and CONFIG.get("signals_chat_id"):
        chat_ids = [CONFIG["signals_chat_id"]]
    if not chat_ids:
        raise RuntimeError("SIGNALS_CHAT_ID غير مضبوط.")
    for chat_id in chat_ids:
        await bot.send_message(chat_id, "تيست")


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

    signals_chat_id = CONFIG.get("signals_chat_id")
    if not signals_chat_id:
        await message.answer("SIGNALS_CHAT_ID غير مضبوط.")
        return

    await send_test_signal(message.bot)
    await message.answer("تم إرسال إشارة تجريبية للمجموعة.")


@router.callback_query(F.data)
async def callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id if callback.from_user else None
    if not is_admin(user_id):
        await callback.answer("غير مصرح", show_alert=True)
        return

    result = menu.handle_callback(CONFIG["db_path"], callback.data or "")
    if result.get("command") == "test_signal":
        try:
            await send_test_signal(callback.bot)
            result["text"] = "🧪 تجربة إشارة\n\nتم إرسال إشارة تجريبية للمجموعة."
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

    database.upsert_quotex_account(CONFIG["db_path"], email=email, enabled=True)
    await state.clear()
    rendered = menu.render_menu(CONFIG["db_path"], input_config["return_menu"])
    await message.answer(f"{input_config['saved_text']}\n\nالإيميل: {email}", reply_markup=rendered["reply_markup"])


async def save_quotex_password_input(message: Message, state: FSMContext, input_config: dict) -> None:
    password = (message.text or "").strip()
    if len(password) < 4:
        await message.answer("كلمة السر قصيرة جدًا.")
        return

    database.upsert_quotex_account(CONFIG["db_path"], password=password, enabled=True)
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
    await message.answer("اكتب /menu لفتح لوحة التحكم.")


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
    args = parser.parse_args()

    config = config_from_env(load_env())
    CONFIG.update(config)
    database.init_db(
        config["db_path"],
        admin_ids=config["admin_ids"],
        signals_chat_id=config["signals_chat_id"],
    )

    if args.init_db:
        print(f"Database ready: {config['db_path']}")
        return

    if args.check:
        bot = Bot(token=config["token"])
        try:
            me = await bot.get_me()
            print(f"Connected to Telegram bot: @{me.username} (id={me.id})")
        finally:
            await bot.session.close()
        return

    await run_bot(config)


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("Bot stopped.")
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        raise
