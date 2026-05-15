import json
import re
from collections import defaultdict
from pathlib import Path

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import database


TRADER_LOG_PATH = Path(__file__).resolve().parent / "logs" / "trader.log"
DECISION_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}),\d+ INFO "
    r"Decision asset=(?P<asset>\S+) direction=(?P<direction>\S+) "
    r"confidence=(?P<confidence>\d+) reason=(?P<reason>.*)$"
)
TRADE_SCHEDULED_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}),\d+ INFO "
    r"Trade scheduled id=(?P<id>\d+) asset=(?P<asset>\S+) direction=(?P<direction>\S+) "
    r"confidence=(?P<confidence>\d+) entry=(?P<entry>\S+)"
)
TRADE_OPENED_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}),\d+ INFO "
    r"DEMO trade opened id=(?P<id>\d+).*entry_price=(?P<entry_price>\S+)"
)
TRADE_CLOSED_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2}),\d+ INFO "
    r"DEMO trade closed id=(?P<id>\d+).*result=(?P<result>\S+).*profit=(?P<profit>\S+)"
)


INPUT_PROMPTS = {
    "trade_amount": {
        "text": "💵 اكتب مبلغ الصفقة\n\nمثال: 1 أو 2 أو 12.5",
        "return_menu": "settings",
    },
    "min_payout": {
        "text": "💰 اكتب أقل نسبة ربح مسموحة\n\nمثال: 70 أو 75 أو 80\nاكتب 0 إذا بدك بدون فلتر.",
        "return_menu": "settings",
    },
    "daily_loss_limit": {
        "text": "📉 اكتب حد الخسارة اليومي\n\nمثال: 30\nاكتب 0 إذا بدك بدون حد.",
        "return_menu": "risk",
    },
    "max_daily_trades": {
        "text": "🔢 اكتب أقصى عدد صفقات باليوم\n\nمثال: 20\nاكتب 0 إذا بدك بدون حد.",
        "return_menu": "risk",
    },
    "stop_after_losses": {
        "text": "⛔ اكتب عدد الخسائر المتتالية للإيقاف\n\nمثال: 3\nاكتب 0 إذا بدك بدون حد.",
        "return_menu": "risk",
    },
    "add_group": {
        "text": "➕ إضافة مجموعة\n\nاكتب chat_id للمجموعة.\nمثال: -1001234567890\n\nملاحظة: لازم البوت يكون داخل المجموعة.",
        "return_menu": "admin",
    },
    "add_admin": {
        "text": "➕ إضافة أدمن\n\nاكتب Telegram user ID للأدمن الجديد.\nمثال: 8497188657",
        "return_menu": "admin",
    },
    "quotex_email": {
        "text": "✉️ تغيير إيميل Quotex\n\nاكتب الإيميل الجديد.",
        "return_menu": "quotex",
    },
    "quotex_password": {
        "text": "🔑 تغيير كلمة سر Quotex\n\nاكتب كلمة السر الجديدة.",
        "return_menu": "quotex",
    },
    "signal_interval_minutes": {
        "text": "⏳ وقت إرسال الصفقة\n\nاكتب عدد الدقائق بين الصفقات.\nمثال: 10 أو 12 أو 15\n\nاكتب 0 إذا بدك الوضع مفتوح.",
        "return_menu": "settings",
    },
}


def render_menu(db_path: str, menu_key: str) -> dict:
    if menu_key == "assets":
        return render_assets_menu(db_path)

    return {
        "text": menu_text(db_path, menu_key),
        "reply_markup": buttons_to_keyboard(database.get_buttons(db_path, menu_key)),
    }


def handle_callback(db_path: str, callback_data: str) -> dict:
    if callback_data.startswith("asset:toggle:"):
        asset_id = int(callback_data.split(":")[-1])
        database.toggle_asset(db_path, asset_id)
        result = render_assets_menu(db_path)
        result["answer"] = "تم تحديث الزوج"
        return result

    if callback_data.startswith("btn:"):
        button_key = callback_data[4:]
        button = database.get_button(db_path, button_key)
        if not button:
            return {
                "text": "الزر غير موجود أو غير مفعل.",
                "reply_markup": back_keyboard("main"),
                "answer": "زر غير متاح",
            }
        return handle_button(db_path, button)

    return {
        "text": "أمر غير معروف.",
        "reply_markup": back_keyboard("main"),
        "answer": "أمر غير معروف",
    }


def handle_button(db_path: str, button) -> dict:
    action_type = button["action_type"]
    action_value = button["action_value"] or ""
    payload = safe_json(button["payload_json"])

    if action_type == "open_menu":
        result = render_menu(db_path, action_value)
        result["answer"] = ""
        return result

    if action_type == "set_setting":
        key, value = action_value.split("=", 1)
        database.set_setting(db_path, key, value)
        return_menu = payload.get("return_menu", "main")
        result = render_menu(db_path, return_menu)
        result["answer"] = "تم حفظ الإعداد"
        return result

    if action_type == "set_signal_timing":
        mode, seconds = action_value.split(":", 1)
        database.set_setting(db_path, "signal_mode", mode)
        database.set_setting(db_path, "signal_interval_seconds", seconds)
        return_menu = payload.get("return_menu", "settings")
        result = render_menu(db_path, return_menu)
        result["answer"] = "تم حفظ وقت الإرسال"
        return result

    if action_type == "request_input":
        prompt = INPUT_PROMPTS.get(action_value)
        if not prompt:
            return {
                "text": "هذا الإدخال غير مدعوم.",
                "reply_markup": back_keyboard("main"),
                "answer": "غير مدعوم",
            }
        return {
            "text": prompt["text"],
            "reply_markup": back_keyboard(prompt["return_menu"]),
            "answer": "",
            "input_key": action_value,
            "return_menu": prompt["return_menu"],
        }

    if action_type == "run_command":
        return run_command(db_path, action_value, payload)

    return {
        "text": "نوع الزر غير مدعوم.",
        "reply_markup": back_keyboard("main"),
        "answer": "غير مدعوم",
    }


def run_command(db_path: str, command: str, payload: dict) -> dict:
    return_menu = payload.get("return_menu", "main")

    if command == "status":
        return {
            "text": status_text(db_path),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "today_report":
        return {
            "text": today_report_text(db_path),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "full_report":
        return {
            "text": full_report_text(db_path),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "best_pairs":
        return {
            "text": pair_report_text(db_path, worst=False),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "worst_pairs":
        return {
            "text": pair_report_text(db_path, worst=True),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "last_trades":
        return {
            "text": last_trades_text(db_path),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "entry_errors":
        return {
            "text": entry_errors_text(db_path),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "risk_status":
        return {
            "text": risk_text(db_path),
            "reply_markup": back_keyboard("risk"),
            "answer": "",
        }

    if command == "test_signal":
        return {
            "text": "سيتم إرسال إشارة تجريبية للمجموعة.",
            "reply_markup": back_keyboard(return_menu),
            "answer": "test_signal",
            "command": "test_signal",
        }

    if command == "signal_chats":
        return {
            "text": signal_chats_text(db_path),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "connection_status":
        return {
            "text": connection_text(),
            "reply_markup": back_keyboard(return_menu),
            "answer": "",
        }

    if command == "logs_status":
        return {
            "text": logs_text(),
            "reply_markup": logs_keyboard(return_menu),
            "answer": "",
        }

    if command == "clear_quotex_account":
        database.clear_quotex_account(db_path)
        result = render_menu(db_path, return_menu)
        result["answer"] = "تم حذف بيانات Quotex"
        return result

    if command == "enable_all_assets":
        database.set_all_assets(db_path, True)
        result = render_assets_menu(db_path)
        result["answer"] = "تم تفعيل كل الأزواج"
        return result

    if command == "disable_all_assets":
        database.set_all_assets(db_path, False)
        result = render_assets_menu(db_path)
        result["answer"] = "تم تعطيل كل الأزواج"
        return result

    return {
        "text": "الأمر غير معروف.",
        "reply_markup": back_keyboard("main"),
        "answer": "أمر غير معروف",
    }


def buttons_to_keyboard(buttons) -> InlineKeyboardMarkup:
    rows = defaultdict(list)
    for button in buttons:
        rows[button["row_index"]].append(
            {
                "text": button["label"],
                "callback_data": f"btn:{button['button_key']}",
                "col_index": button["col_index"],
            }
        )

    inline_keyboard = []
    for row_index in sorted(rows):
        row = sorted(rows[row_index], key=lambda item: item["col_index"])
        inline_keyboard.append(
            [InlineKeyboardButton(text=item["text"], callback_data=item["callback_data"]) for item in row]
        )
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def render_assets_menu(db_path: str) -> dict:
    assets = database.get_assets(db_path)
    inline_keyboard = []
    row = []
    for asset in assets:
        marker = "✅" if asset["enabled"] else "⬜"
        row.append(
            InlineKeyboardButton(
                text=f"{marker} {asset['display_name']}",
                callback_data=f"asset:toggle:{asset['id']}",
            )
        )
        if len(row) == 2:
            inline_keyboard.append(row)
            row = []
    if row:
        inline_keyboard.append(row)

    footer = buttons_to_keyboard(database.get_buttons(db_path, "assets")).inline_keyboard
    inline_keyboard.extend(footer)
    return {
        "text": assets_text(db_path),
        "reply_markup": InlineKeyboardMarkup(inline_keyboard=inline_keyboard),
    }


def menu_text(db_path: str, menu_key: str) -> str:
    if menu_key == "main":
        return status_text(db_path, title="لوحة التحكم")
    if menu_key == "trading":
        return trading_text(db_path)
    if menu_key == "reports":
        return reports_text(db_path)
    if menu_key == "settings":
        return settings_text(db_path)
    if menu_key == "duration":
        return "⏱️ اختر مدة الصفقة"
    if menu_key == "confidence":
        return "🎯 اختر أقل ثقة لإرسال الصفقة"
    if menu_key == "amount":
        return "💵 اختر مبلغ الصفقة"
    if menu_key == "payout":
        return payout_text(db_path)
    if menu_key == "account_type":
        return "🧪 اختر نوع الحساب\n\nملاحظة: التنفيذ الحقيقي لاحقًا يحتاج تأكيد إضافي قبل ربطه بالتداول."
    if menu_key == "signal_timing":
        return signal_timing_text(db_path)
    if menu_key == "quotex":
        return quotex_text(db_path)
    if menu_key == "risk":
        return risk_text(db_path)
    if menu_key == "ai":
        return ai_text(db_path)
    if menu_key == "system":
        return system_text()
    if menu_key == "admin":
        return admin_text(db_path)
    if menu_key == "daily_loss_limit":
        return "📉 اختر حد الخسارة اليومي\n\nقيمة 0 تعني بدون حد."
    if menu_key == "max_daily_trades":
        return "🔢 اختر أقصى عدد صفقات باليوم\n\nقيمة 0 تعني بدون حد."
    if menu_key == "stop_after_losses":
        return "⛔ اختر الإيقاف بعد خسائر متتالية\n\nقيمة 0 تعني بدون حد."
    return "لوحة التحكم"


def status_text(db_path: str, title: str = "🔄 حالة البوت") -> str:
    settings = database.get_settings(db_path)
    enabled_assets = database.get_enabled_assets(db_path)
    enabled = settings.get("bot_enabled", "false") == "true"
    ai_enabled = settings.get("ai_enabled", "false") == "true"
    duration = int(settings.get("trade_duration_seconds", "180")) // 60
    return (
        f"{title}\n\n"
        f"الحالة: {'يعمل' if enabled else 'متوقف'}\n"
        f"الوضع: {settings.get('account_type', 'DEMO')}\n"
        f"AI: {'يعمل' if ai_enabled else 'متوقف'}\n"
        f"الأزواج المفعلة: {len(enabled_assets)}\n"
        f"مدة الصفقة: {duration} دقائق\n"
        f"أقل ثقة: {settings.get('min_confidence', '80')}/100\n\n"
        "الأقسام:\n"
        "📊 التداول | 📈 التقارير | ⚙️ الإعدادات | 🤖 AI\n"
        "🛡️ المخاطر | 📡 النظام | 👥 الإدارة"
    )


def trading_text(db_path: str) -> str:
    stats = database.get_today_stats(db_path)
    enabled_assets = database.get_enabled_assets(db_path)
    return (
        "📊 التداول\n\n"
        f"الأزواج المفعلة: {len(enabled_assets)}\n"
        f"صفقات اليوم: {stats['total']} | فوز: {stats['win_rate']}%\n"
        f"الصافي اليوم: {format_money(stats['profit_loss'])}\n\n"
        "من هنا تختار الأزواج، تشوف التقارير، أو ترسل إشارة تجربة."
    )


def reports_text(db_path: str) -> str:
    today = database.get_today_stats(db_path)
    overall = database.get_overall_stats(db_path)
    return (
        "📊 التقارير\n\n"
        f"اليوم: {today['total']} صفقة | {today['win_rate']}% | {format_money(today['profit_loss'])}\n"
        f"الشامل: {overall['total']} صفقة | {overall['win_rate']}% | {format_money(overall['profit_loss'])}\n\n"
        "اختر التقرير المطلوب."
    )


def settings_text(db_path: str) -> str:
    settings = database.get_settings(db_path)
    duration = int(settings.get("trade_duration_seconds", "180")) // 60
    return (
        "⚙️ الإعدادات\n\n"
        f"⏱️ مدة الصفقة: {duration} دقائق\n"
        f"🎯 أقل ثقة: {settings.get('min_confidence', '80')}/100\n"
        f"💵 مبلغ الصفقة: ${settings.get('trade_amount', '10')}\n"
        f"💰 أقل ربح: {format_payout_filter(settings.get('min_payout', '0'))}\n"
        f"🧪 الوضع: {settings.get('account_type', 'DEMO')}\n"
        f"⏳ وقت الإرسال: {signal_timing_label(settings)}\n"
        f"🔔 التنبيهات: صفقة + نتيجة\n"
        f"🔐 حساب Quotex: {quotex_status_label(db_path)}"
    )


def payout_text(db_path: str) -> str:
    settings = database.get_settings(db_path)
    return (
        "💰 أقل ربح payout\n\n"
        f"الحالي: {format_payout_filter(settings.get('min_payout', '0'))}\n\n"
        "إذا كانت النسبة أقل من الرقم المحدد، البوت يتجاهل الصفقة قبل الدخول."
    )


def assets_text(db_path: str) -> str:
    assets = database.get_assets(db_path)
    enabled_count = sum(1 for asset in assets if asset["enabled"])
    return f"💱 الأزواج\n\nالمفعلة: {enabled_count} من {len(assets)}"


def risk_text(db_path: str) -> str:
    settings = database.get_settings(db_path)
    return (
        "🛡️ إدارة المخاطر\n\n"
        f"📉 حد خسارة يومي: {format_money_limit(settings.get('daily_loss_limit', '30'))}\n"
        f"🔢 أقصى صفقات يوميًا: {format_count_limit(settings.get('max_daily_trades', '20'))}\n"
        f"⛔ إيقاف بعد خسائر: {format_count_limit(settings.get('stop_after_losses', '3'))}"
    )


def quotex_text(db_path: str) -> str:
    account = database.get_quotex_account(db_path)
    email = account["email"] if account and account["email"] else "غير محدد"
    password_status = "موجودة" if account and account["password"] else "غير محددة"
    enabled = account["enabled"] if account else 0
    return (
        "🔐 حساب Quotex\n\n"
        f"الإيميل: {email}\n"
        f"كلمة السر: {password_status}\n"
        f"الحالة: {'مفعل' if enabled else 'غير مفعل'}\n\n"
        "هذه البيانات مخزنة في قاعدة البيانات لاستخدام ربط Quotex لاحقًا."
    )


def signal_timing_text(db_path: str) -> str:
    settings = database.get_settings(db_path)
    return (
        "⏳ وقت إرسال الصفقة\n\n"
        f"الحالي: {signal_timing_label(settings)}\n\n"
        "اختر فاصل ثابت أو مفتوح حسب قوة الفرص."
    )


def signal_timing_label(settings: dict) -> str:
    mode = settings.get("signal_mode", "interval")
    seconds = safe_int(settings.get("signal_interval_seconds"), 600)
    if mode == "open" or seconds <= 0:
        return "مفتوح"
    minutes = seconds / 60
    if minutes.is_integer():
        return f"كل {int(minutes)} دقائق"
    return f"كل {minutes:.1f} دقيقة"


def quotex_status_label(db_path: str) -> str:
    account = database.get_quotex_account(db_path)
    if account and account["email"] and account["password"] and account["enabled"]:
        return "مضبوط"
    return "غير مكتمل"


def ai_text(db_path: str) -> str:
    settings = database.get_settings(db_path)
    enabled = settings.get("ai_enabled", "false") == "true"
    return (
        "🤖 الذكاء الاصطناعي\n\n"
        f"الحالة: {'يعمل' if enabled else 'متوقف'}\n\n"
        "حاليًا هذا الزر يحفظ حالة AI فقط. التحليل الفعلي سيتم ربطه لاحقًا."
    )


def connection_text() -> str:
    return (
        "📡 الاتصال\n\n"
        "Telegram: يعمل\n"
        "Quotex: غير مربوط بعد\n"
        "pyquotex: غير مفعل بعد\n"
        "آخر تحديث سعر: غير متاح"
    )


def logs_text() -> str:
    lines = read_recent_log_lines(TRADER_LOG_PATH)
    if not lines:
        return (
            "📝 السجل المباشر\n\n"
            "لا يوجد سجل مباشر متاح حالياً."
        )

    decisions = []
    opportunities = []
    trades_by_id = {}
    last_trade_event = None

    for line in lines:
        decision = parse_decision_line(line)
        if decision:
            decisions.append(decision)
            if decision["direction"] != "NO_TRADE":
                opportunities.append(decision)
            continue

        scheduled = TRADE_SCHEDULED_RE.match(line)
        if scheduled:
            trade = scheduled.groupdict()
            trades_by_id[trade["id"]] = trade
            last_trade_event = {
                "time": trade["time"],
                "asset": trade["asset"],
                "direction": trade["direction"],
                "confidence": trade["confidence"],
                "status": "تمت الجدولة",
            }
            continue

        opened = TRADE_OPENED_RE.match(line)
        if opened:
            event = opened.groupdict()
            trade = trades_by_id.get(event["id"], {})
            last_trade_event = {
                "time": event["time"],
                "asset": trade.get("asset", f"ID {event['id']}"),
                "direction": trade.get("direction", ""),
                "confidence": trade.get("confidence", ""),
                "status": "تم فتح الصفقة",
            }
            continue

        closed = TRADE_CLOSED_RE.match(line)
        if closed:
            event = closed.groupdict()
            trade = trades_by_id.get(event["id"], {})
            result = format_result(event["result"])
            last_trade_event = {
                "time": event["time"],
                "asset": trade.get("asset", f"ID {event['id']}"),
                "direction": trade.get("direction", ""),
                "confidence": trade.get("confidence", ""),
                "status": f"{result} | الربح: {event['profit']}",
            }

    text_lines = ["📝 السجل المباشر"]

    recent_opportunities = opportunities[-3:][::-1]
    text_lines.append("")
    text_lines.append("🔥 فرص ممكنة:")
    if recent_opportunities:
        for index, item in enumerate(recent_opportunities, 1):
            text_lines.append(
                f"{index}. {item['asset']} | {format_direction(item['direction'])} | {item['confidence']}/100"
            )
    else:
        text_lines.append("لا توجد فرص فوق الثقة حالياً.")

    text_lines.append("")
    text_lines.append("🔍 آخر 4 تحليلات:")
    recent_decisions = decisions[-4:][::-1]
    if recent_decisions:
        for index, item in enumerate(recent_decisions, 1):
            status = "✅ فرصة ممكنة" if item["direction"] != "NO_TRADE" else "❌ مرفوضة"
            text_lines.append("")
            text_lines.append(
                f"{index}. {item['time']} | {item['asset']} | {format_direction(item['direction'])} | {item['confidence']}/100"
            )
            text_lines.append(status)
            text_lines.append(f"السبب: {short_text(item['reason'], 120)}")
    else:
        text_lines.append("لا توجد تحليلات مسجلة حالياً.")

    if last_trade_event:
        text_lines.append("")
        text_lines.append("📌 آخر تنفيذ:")
        trade_label = " | ".join(
            part for part in [
                last_trade_event["time"],
                last_trade_event["asset"],
                format_direction(last_trade_event["direction"]) if last_trade_event["direction"] else "",
                f"{last_trade_event['confidence']}/100" if last_trade_event["confidence"] else "",
            ] if part
        )
        text_lines.append(trade_label)
        text_lines.append(last_trade_event["status"])

    return "\n".join(text_lines)


def read_recent_log_lines(path: Path, max_bytes: int = 120_000) -> list[str]:
    try:
        with path.open("rb") as file:
            file.seek(0, 2)
            size = file.tell()
            file.seek(max(0, size - max_bytes))
            data = file.read()
    except OSError:
        return []
    return data.decode("utf-8", "replace").splitlines()


def parse_decision_line(line: str) -> dict | None:
    match = DECISION_RE.match(line)
    if not match:
        return None
    return match.groupdict()


def format_direction(direction: str) -> str:
    if direction == "CALL":
        return "CALL"
    if direction == "PUT":
        return "PUT"
    return "مرفوض"


def format_result(result: str) -> str:
    result = result.upper()
    if result == "WIN":
        return "✅ ربح"
    if result == "LOSS":
        return "❌ خسارة"
    if result == "DRAW":
        return "🔄 تعادل"
    return result


def short_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def system_text() -> str:
    return (
        "📡 النظام\n\n"
        "هنا تتابع حالة الاتصال والسجل وحالة تشغيل الخدمة."
    )


def admin_text(db_path: str) -> str:
    chat_count = len(database.get_signal_chat_ids(db_path))
    return (
        "👥 الإدارة\n\n"
        f"مجموعات الإشارات: {chat_count}\n\n"
        "أضف مجموعة جديدة أو أدمن جديد من هنا."
    )


def signal_chats_text(db_path: str) -> str:
    chat_ids = database.get_signal_chat_ids(db_path)
    if not chat_ids:
        return (
            "📡 مجموعات الإشارات\n\n"
            "لا توجد مجموعة إشارات محفوظة في قاعدة البيانات.\n\n"
            "أضف مجموعة من لوحة التحكم: 👥 الإدارة ← ➕ إضافة مجموعة، "
            "أو اضبط SIGNALS_CHAT_ID في bot/.env كخيار احتياطي."
        )

    lines = ["📡 مجموعات الإشارات", "", f"العدد: {len(chat_ids)}", ""]
    for index, chat_id in enumerate(chat_ids, start=1):
        lines.append(f"{index}. {chat_id}")
    lines.extend(["", "استخدم /test_signal لتجربة الإرسال لهذه المجموعات."])
    return "\n".join(lines)


def today_report_text(db_path: str) -> str:
    stats = database.get_today_stats(db_path)
    return (
        "📅 تقرير اليوم\n\n"
        f"📌 إجمالي الصفقات: {stats['total']}\n"
        f"✅ رابحة: {stats['wins']}\n"
        f"❌ خاسرة: {stats['losses']}\n"
        f"➖ تعادل: {stats['draws']}\n\n"
        f"📈 نسبة الفوز: {format_percent(stats['win_rate'])}\n"
        f"💰 الصافي: {format_money(stats['profit_loss'])}"
    )


def full_report_text(db_path: str) -> str:
    stats = database.get_overall_stats(db_path)
    best = database.get_pair_stats(db_path, limit=1, worst=False)
    worst = database.get_pair_stats(db_path, limit=1, worst=True)
    last = database.get_last_closed_trade(db_path)

    best_label = pair_summary_label(best[0]) if best else "لا يوجد"
    worst_label = pair_summary_label(worst[0]) if worst else "لا يوجد"
    last_label = last_trade_label(last) if last else "لا يوجد"

    return (
        "🧾 التقرير الشامل\n\n"
        f"📌 إجمالي الصفقات: {stats['total']}\n"
        f"✅ رابحة: {stats['wins']}\n"
        f"❌ خاسرة: {stats['losses']}\n"
        f"➖ تعادل: {stats['draws']}\n\n"
        f"📈 نسبة الفوز: {format_percent(stats['win_rate'])}\n"
        f"💰 الصافي: {format_money(stats['profit_loss'])}\n\n"
        f"🏆 أفضل زوج: {best_label}\n"
        f"📉 أسوأ زوج: {worst_label}\n"
        f"🕯️ آخر صفقة: {last_label}"
    )


def pair_report_text(db_path: str, worst: bool = False) -> str:
    pairs = database.get_pair_stats(db_path, limit=10, worst=worst)
    title = "📉 أسوأ الأزواج" if worst else "🏆 أفضل الأزواج"
    if not pairs:
        return f"{title}\n\nلا توجد صفقات مغلقة كافية بعد."

    lines = [title, ""]
    for index, pair in enumerate(pairs, start=1):
        lines.extend(
            [
                f"{index}. {pair['asset']}",
                f"📌 الصفقات: {pair['total']}",
                f"✅ ربح: {pair['wins']} | ❌ خسارة: {pair['losses']} | ➖ تعادل: {pair['draws']}",
                f"📈 نسبة الفوز: {format_percent(pair['win_rate'])}",
                f"💰 الصافي: {format_money(pair['profit_loss'])}",
                "",
            ]
        )
    return "\n".join(lines)


def last_trades_text(db_path: str) -> str:
    trades = database.get_last_trades(db_path, limit=10)
    if not trades:
        return "📈 آخر الصفقات\n\nلا توجد صفقات مغلقة بعد."

    lines = ["📈 آخر الصفقات", ""]
    for trade in trades:
        result = result_icon(trade["result"])
        lines.append(
            f"{result} {trade['asset']} | {trade['direction']} | "
            f"{trade['confidence']}/100 | {format_money(trade['profit_loss'])}"
        )
    return "\n".join(lines)


def entry_errors_text(db_path: str) -> str:
    errors = database.get_entry_errors(db_path, limit=10)
    if not errors:
        return "⚠️ أخطاء الدخول\n\nلا توجد أخطاء دخول مسجلة."

    lines = ["⚠️ أخطاء الدخول", ""]
    for trade in errors:
        message = trade["error_message"] or "خطأ غير معروف"
        if len(message) > 55:
            message = message[:52] + "..."
        lines.append(f"#{trade['id']} {trade['asset']} | {trade['status']} | {message}")
    return "\n".join(lines)


def pair_summary_label(pair: dict) -> str:
    return f"{pair['asset']} | {format_percent(pair['win_rate'])} | {format_money(pair['profit_loss'])}"


def last_trade_label(trade) -> str:
    return (
        f"{trade['asset']} | {trade['direction']} | "
        f"{result_icon(trade['result'])} | {format_money(trade['profit_loss'])}"
    )


def result_icon(result: str) -> str:
    return {"WIN": "✅", "LOSS": "❌", "DRAW": "🔄", "PENDING": "⏳"}.get(result, "⏳")


def format_percent(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0
    if number.is_integer():
        return f"{int(number)}%"
    return f"{number:.2f}%"


def format_money(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0
    if number > 0:
        return f"+${number:.2f}"
    if number < 0:
        return f"-${abs(number):.2f}"
    return "$0.00"


def format_payout_filter(value) -> str:
    number = safe_int(value, 0)
    if number <= 0:
        return "بدون فلتر"
    return f"{number}%"


def back_keyboard(menu_key: str) -> InlineKeyboardMarkup:
    button_key_by_menu = {
        "main": "back_from_assets",
        "settings": "settings_menu",
        "payout": "payout_menu",
        "risk": "risk_menu",
        "assets": "assets_menu",
        "ai": "ai_menu",
        "trading": "trading_menu",
        "reports": "reports_menu",
        "system": "system_menu",
        "admin": "admin_menu",
        "quotex": "quotex_menu",
    }
    button_key = button_key_by_menu.get(menu_key, "back_from_assets")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ رجوع", callback_data=f"btn:{button_key}")]
        ]
    )


def logs_keyboard(menu_key: str) -> InlineKeyboardMarkup:
    button_key_by_menu = {
        "main": "back_from_assets",
        "settings": "settings_menu",
        "payout": "payout_menu",
        "risk": "risk_menu",
        "assets": "assets_menu",
        "ai": "ai_menu",
        "trading": "trading_menu",
        "reports": "reports_menu",
        "system": "system_menu",
        "admin": "admin_menu",
        "quotex": "quotex_menu",
    }
    button_key = button_key_by_menu.get(menu_key, "system_menu")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 تحديث", callback_data="btn:logs_status")],
            [InlineKeyboardButton(text="⬅️ رجوع", callback_data=f"btn:{button_key}")],
        ]
    )


def safe_json(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def format_money_limit(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0
    if number <= 0:
        return "بدون حد"
    if number.is_integer():
        return f"${int(number)}"
    return f"${number}"


def format_count_limit(value) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    if number <= 0:
        return "بدون حد"
    return str(number)


def safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_signal(asset: str, direction: str, entry_time: str, duration_minutes: int, confidence: int) -> str:
    asset_label = database.asset_markdown_label(asset)
    if direction == "CALL":
        header = "🟢📈 دخول صعود | CALL"
    else:
        header = "🔴📉 دخول هبوط | PUT"

    return (
        f"{header}\n\n"
        f"📌 الزوج: {asset_label}\n"
        f"🕯️ وقت الدخول: {entry_time}\n"
        f"⏱️ مدة الصفقة: {duration_minutes} دقائق\n"
        f"🎯 الثقة: {confidence}/100"
    )
