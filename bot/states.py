from aiogram.fsm.state import State, StatesGroup


class AdminInput(StatesGroup):
    trade_amount = State()
    min_payout = State()
    daily_loss_limit = State()
    max_daily_trades = State()
    stop_after_losses = State()
    add_group = State()
    add_admin = State()
    quotex_email = State()
    quotex_password = State()
    signal_interval_minutes = State()


INPUTS = {
    "trade_amount": {
        "state": AdminInput.trade_amount,
        "setting_key": "trade_amount",
        "return_menu": "settings",
        "kind": "money",
        "allow_zero": False,
        "saved_text": "تم حفظ مبلغ الصفقة.",
    },
    "min_payout": {
        "state": AdminInput.min_payout,
        "setting_key": "min_payout",
        "return_menu": "settings",
        "kind": "percent",
        "allow_zero": True,
        "saved_text": "تم حفظ أقل نسبة ربح.",
    },
    "daily_loss_limit": {
        "state": AdminInput.daily_loss_limit,
        "setting_key": "daily_loss_limit",
        "return_menu": "risk",
        "kind": "money",
        "allow_zero": True,
        "saved_text": "تم حفظ حد الخسارة اليومي.",
    },
    "max_daily_trades": {
        "state": AdminInput.max_daily_trades,
        "setting_key": "max_daily_trades",
        "return_menu": "risk",
        "kind": "int",
        "allow_zero": True,
        "saved_text": "تم حفظ أقصى عدد صفقات.",
    },
    "stop_after_losses": {
        "state": AdminInput.stop_after_losses,
        "setting_key": "stop_after_losses",
        "return_menu": "risk",
        "kind": "int",
        "allow_zero": True,
        "saved_text": "تم حفظ إيقاف الخسائر المتتالية.",
    },
    "add_group": {
        "state": AdminInput.add_group,
        "return_menu": "main",
        "kind": "chat_id",
        "saved_text": "تمت إضافة المجموعة.",
    },
    "add_admin": {
        "state": AdminInput.add_admin,
        "return_menu": "main",
        "kind": "admin_id",
        "saved_text": "تمت إضافة الأدمن.",
    },
    "quotex_email": {
        "state": AdminInput.quotex_email,
        "return_menu": "quotex",
        "kind": "email",
        "saved_text": "تم حفظ إيميل Quotex.",
    },
    "quotex_password": {
        "state": AdminInput.quotex_password,
        "return_menu": "quotex",
        "kind": "password",
        "saved_text": "تم حفظ كلمة سر Quotex.",
    },
    "signal_interval_minutes": {
        "state": AdminInput.signal_interval_minutes,
        "return_menu": "settings",
        "kind": "minutes",
        "saved_text": "تم حفظ وقت إرسال الصفقة.",
    },
}


INPUTS_BY_STATE = {config["state"].state: config for config in INPUTS.values()}
