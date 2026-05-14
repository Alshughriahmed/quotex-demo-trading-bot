import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ASSETS = [
    "GBP/USD",
    "EUR/USD",
    "USD/JPY",
    "EUR/JPY",
    "AUD/USD",
    "USD/CAD",
    "GBP/JPY",
    "EUR/GBP",
    "AUD/JPY",
    "NZD/USD",
    "USD/CHF",
    "CAD/JPY",
    "GBP/CAD",
    "GBP/AUD",
    "EUR/AUD",
    "EUR/CAD",
    "AUD/CAD",
    "CHF/JPY",
    "NZD/JPY",
    "GBP/CHF",
    "EUR/CHF",
    "EUR/NZD",
    "GBP/NZD",
    "AUD/CHF",
    "AUD/NZD",
    "CAD/CHF",
    "NZD/CAD",
    "NZD/CHF",
    "USD/MXN",
    "USD/ARS",
    "USD/BRL",
    "USD/COP",
    "USD/DZD",
    "USD/IDR",
    "USD/INR",
    "USD/NGN",
    "USD/PHP",
    "USD/BDT",
    "USD/PKR",
    "USD/EGP",
]


DEFAULT_QUOTEX_SYMBOLS = {
    "AUD/NZD": "AUDNZD_otc",
    "CAD/CHF": "CADCHF_otc",
    "EUR/NZD": "EURNZD_otc",
    "GBP/NZD": "GBPNZD_otc",
    "NZD/CAD": "NZDCAD_otc",
    "NZD/CHF": "NZDCHF_otc",
    "NZD/JPY": "NZDJPY_otc",
    "NZD/USD": "NZDUSD_otc",
    "USD/ARS": "USDARS_otc",
    "USD/BDT": "USDBDT_otc",
    "USD/BRL": "USDBRL_otc",
    "USD/COP": "USDCOP_otc",
    "USD/DZD": "USDDZD_otc",
    "USD/EGP": "USDEGP_otc",
    "USD/IDR": "USDIDR_otc",
    "USD/INR": "USDINR_otc",
    "USD/MXN": "USDMXN_otc",
    "USD/NGN": "USDNGN_otc",
    "USD/PHP": "USDPHP_otc",
    "USD/PKR": "USDPKR_otc",
}


ASSET_FLAGS = {
    "AUD": "🇦🇺",
    "ARS": "🇦🇷",
    "BDT": "🇧🇩",
    "BRL": "🇧🇷",
    "CAD": "🇨🇦",
    "CHF": "🇨🇭",
    "COP": "🇨🇴",
    "DZD": "🇩🇿",
    "EGP": "🇪🇬",
    "EUR": "🇪🇺",
    "GBP": "🇬🇧",
    "IDR": "🇮🇩",
    "INR": "🇮🇳",
    "JPY": "🇯🇵",
    "MXN": "🇲🇽",
    "NGN": "🇳🇬",
    "NZD": "🇳🇿",
    "PHP": "🇵🇭",
    "PKR": "🇵🇰",
    "TRY": "🇹🇷",
    "USD": "🇺🇸",
    "XAU": "🥇",
    "ZAR": "🇿🇦",
}


DEFAULT_SETTINGS = {
    "bot_enabled": ("false", "bool", "تشغيل أو إيقاف البوت"),
    "ai_enabled": ("false", "bool", "تشغيل أو إيقاف الذكاء الاصطناعي"),
    "trade_duration_seconds": ("180", "int", "مدة الصفقة بالثواني"),
    "min_confidence": ("80", "int", "أقل ثقة لإرسال الصفقة"),
    "trade_amount": ("10", "number", "مبلغ الصفقة التجريبي"),
    "min_payout": ("0", "int", "أقل نسبة ربح مسموحة للدخول، 0 يعني بدون فلتر"),
    "account_type": ("DEMO", "text", "نوع الحساب"),
    "notifications": ("trade_and_result", "text", "نوع التنبيهات"),
    "timezone": ("Asia/Damascus", "text", "المنطقة الزمنية"),
    "signal_mode": ("interval", "text", "نظام إرسال الصفقات: interval أو open"),
    "signal_interval_seconds": ("600", "int", "الفاصل التقريبي بين الصفقات بالثواني"),
    "pre_signal_seconds": ("60", "int", "إرسال الإشارة قبل الدخول بهذا العدد من الثواني"),
    "scan_interval_seconds": ("5", "int", "الفاصل بين دورات تحليل السوق بالثواني"),
    "single_open_trade": ("true", "bool", "منع أكثر من صفقة مفتوحة بنفس الوقت"),
    "auto_entry_timing_enabled": ("true", "bool", "تعديل توقيت الدخول تلقائيا"),
    "auto_entry_default_offset_ms": ("150", "int", "تقديم أمر الدخول الابتدائي بالميلي ثانية"),
    "max_daily_trades": ("20", "int", "أقصى عدد صفقات باليوم"),
    "daily_loss_limit": ("30", "number", "حد الخسارة اليومي"),
    "stop_after_losses": ("3", "int", "إيقاف بعد خسائر متتالية"),
}

DEFAULT_QUOTEX_EMAIL = None
DEFAULT_QUOTEX_PASSWORD = None


DEFAULT_BUTTONS = [
    ("main", "start_bot", "▶️ تشغيل البوت", "set_setting", "bot_enabled=true", 1, 1, {"return_menu": "main"}),
    ("main", "stop_bot", "⏸️ إيقاف البوت", "set_setting", "bot_enabled=false", 1, 2, {"return_menu": "main"}),
    ("main", "trading_menu", "📊 التداول", "open_menu", "trading", 2, 1, {}),
    ("main", "settings_menu", "⚙️ الإعدادات", "open_menu", "settings", 2, 2, {}),
    ("main", "ai_menu", "🤖 AI", "open_menu", "ai", 3, 1, {}),
    ("main", "risk_menu", "🛡️ المخاطر", "open_menu", "risk", 3, 2, {}),
    ("main", "system_menu", "📡 النظام", "open_menu", "system", 4, 1, {}),
    ("main", "admin_menu", "👥 الإدارة", "open_menu", "admin", 4, 2, {}),
    ("trading", "assets_menu", "💱 الأزواج", "open_menu", "assets", 1, 1, {}),
    ("trading", "reports_menu", "📊 التقارير", "open_menu", "reports", 1, 2, {}),
    ("trading", "test_signal", "🧪 تجربة إشارة", "run_command", "test_signal", 2, 1, {"return_menu": "trading"}),
    ("trading", "back_from_trading", "⬅️ رجوع", "open_menu", "main", 99, 1, {}),
    ("reports", "today_report", "📅 تقرير اليوم", "run_command", "today_report", 1, 1, {"return_menu": "reports"}),
    ("reports", "full_report", "🧾 تقرير شامل", "run_command", "full_report", 1, 2, {"return_menu": "reports"}),
    ("reports", "best_pairs", "🏆 أفضل الأزواج", "run_command", "best_pairs", 2, 1, {"return_menu": "reports"}),
    ("reports", "worst_pairs", "📉 أسوأ الأزواج", "run_command", "worst_pairs", 2, 2, {"return_menu": "reports"}),
    ("reports", "last_trades", "📈 آخر الصفقات", "run_command", "last_trades", 3, 1, {"return_menu": "reports"}),
    ("reports", "entry_errors", "⚠️ أخطاء الدخول", "run_command", "entry_errors", 3, 2, {"return_menu": "reports"}),
    ("reports", "back_from_reports", "⬅️ رجوع", "open_menu", "trading", 99, 1, {}),
    ("system", "connection_status", "📡 الاتصال", "run_command", "connection_status", 1, 1, {"return_menu": "system"}),
    ("system", "logs_status", "📝 السجل", "run_command", "logs_status", 1, 2, {"return_menu": "system"}),
    ("system", "bot_status", "🔄 حالة البوت", "run_command", "status", 2, 1, {"return_menu": "system"}),
    ("system", "back_from_system", "⬅️ رجوع", "open_menu", "main", 99, 1, {}),
    ("admin", "add_group", "➕ إضافة مجموعة", "request_input", "add_group", 1, 1, {"return_menu": "admin"}),
    ("admin", "add_admin", "➕ إضافة أدمن", "request_input", "add_admin", 1, 2, {"return_menu": "admin"}),
    ("admin", "back_from_admin", "⬅️ رجوع", "open_menu", "main", 99, 1, {}),
    ("ai", "ai_enable", "▶️ تشغيل AI", "set_setting", "ai_enabled=true", 1, 1, {"return_menu": "ai"}),
    ("ai", "ai_disable", "⏸️ إيقاف AI", "set_setting", "ai_enabled=false", 1, 2, {"return_menu": "ai"}),
    ("ai", "back_from_ai", "⬅️ رجوع", "open_menu", "main", 99, 1, {}),
    ("assets", "enable_all_assets", "✅ تفعيل الكل", "run_command", "enable_all_assets", 50, 1, {"return_menu": "assets"}),
    ("assets", "disable_all_assets", "🚫 تعطيل الكل", "run_command", "disable_all_assets", 50, 2, {"return_menu": "assets"}),
    ("assets", "back_from_assets", "⬅️ رجوع", "open_menu", "main", 99, 1, {}),
    ("settings", "duration_menu", "⏱️ مدة الصفقة", "open_menu", "duration", 1, 1, {}),
    ("settings", "confidence_menu", "🎯 أقل ثقة", "open_menu", "confidence", 1, 2, {}),
    ("settings", "amount_menu", "💵 مبلغ الصفقة", "open_menu", "amount", 2, 1, {}),
    ("settings", "account_type_menu", "🧪 نوع الحساب", "open_menu", "account_type", 2, 2, {}),
    ("settings", "signal_timing_menu", "⏳ وقت إرسال الصفقة", "open_menu", "signal_timing", 3, 1, {}),
    ("settings", "payout_menu", "💰 أقل ربح", "open_menu", "payout", 3, 2, {}),
    ("settings", "quotex_menu", "🔐 حساب Quotex", "open_menu", "quotex", 4, 1, {}),
    ("settings", "back_from_settings", "⬅️ رجوع", "open_menu", "main", 99, 1, {}),
    ("payout", "payout_0", "بدون فلتر", "set_setting", "min_payout=0", 1, 1, {"return_menu": "settings"}),
    ("payout", "payout_70", "70%", "set_setting", "min_payout=70", 1, 2, {"return_menu": "settings"}),
    ("payout", "payout_75", "75%", "set_setting", "min_payout=75", 2, 1, {"return_menu": "settings"}),
    ("payout", "payout_80", "80%", "set_setting", "min_payout=80", 2, 2, {"return_menu": "settings"}),
    ("payout", "payout_85", "85%", "set_setting", "min_payout=85", 3, 1, {"return_menu": "settings"}),
    ("payout", "payout_manual", "✍️ إدخال يدوي", "request_input", "min_payout", 3, 2, {"return_menu": "settings"}),
    ("payout", "back_from_payout", "⬅️ رجوع", "open_menu", "settings", 99, 1, {}),
    ("signal_timing", "signal_interval_5", "كل 5 دقائق", "set_signal_timing", "interval:300", 1, 1, {"return_menu": "settings"}),
    ("signal_timing", "signal_interval_10", "كل 10 دقائق", "set_signal_timing", "interval:600", 1, 2, {"return_menu": "settings"}),
    ("signal_timing", "signal_interval_15", "كل 15 دقيقة", "set_signal_timing", "interval:900", 2, 1, {"return_menu": "settings"}),
    ("signal_timing", "signal_open", "مفتوح", "set_signal_timing", "open:0", 2, 2, {"return_menu": "settings"}),
    ("signal_timing", "signal_interval_manual", "✍️ إدخال يدوي", "request_input", "signal_interval_minutes", 3, 1, {"return_menu": "settings"}),
    ("signal_timing", "back_from_signal_timing", "⬅️ رجوع", "open_menu", "settings", 99, 1, {}),
    ("quotex", "change_quotex_email", "✉️ تغيير الإيميل", "request_input", "quotex_email", 1, 1, {"return_menu": "quotex"}),
    ("quotex", "change_quotex_password", "🔑 تغيير كلمة السر", "request_input", "quotex_password", 1, 2, {"return_menu": "quotex"}),
    ("quotex", "clear_quotex_account", "🧹 حذف بيانات الحساب", "run_command", "clear_quotex_account", 2, 1, {"return_menu": "quotex"}),
    ("quotex", "back_from_quotex", "⬅️ رجوع", "open_menu", "settings", 99, 1, {}),
    ("duration", "duration_60", "1 دقيقة", "set_setting", "trade_duration_seconds=60", 1, 1, {"return_menu": "settings"}),
    ("duration", "duration_120", "2 دقيقة", "set_setting", "trade_duration_seconds=120", 1, 2, {"return_menu": "settings"}),
    ("duration", "duration_180", "3 دقائق", "set_setting", "trade_duration_seconds=180", 2, 1, {"return_menu": "settings"}),
    ("duration", "duration_300", "5 دقائق", "set_setting", "trade_duration_seconds=300", 2, 2, {"return_menu": "settings"}),
    ("duration", "duration_900", "15 دقيقة", "set_setting", "trade_duration_seconds=900", 3, 1, {"return_menu": "settings"}),
    ("duration", "back_from_duration", "⬅️ رجوع", "open_menu", "settings", 99, 1, {}),
    ("confidence", "confidence_70", "70/100", "set_setting", "min_confidence=70", 1, 1, {"return_menu": "settings"}),
    ("confidence", "confidence_75", "75/100", "set_setting", "min_confidence=75", 1, 2, {"return_menu": "settings"}),
    ("confidence", "confidence_80", "80/100", "set_setting", "min_confidence=80", 2, 1, {"return_menu": "settings"}),
    ("confidence", "confidence_85", "85/100", "set_setting", "min_confidence=85", 2, 2, {"return_menu": "settings"}),
    ("confidence", "confidence_90", "90/100", "set_setting", "min_confidence=90", 3, 1, {"return_menu": "settings"}),
    ("confidence", "back_from_confidence", "⬅️ رجوع", "open_menu", "settings", 99, 1, {}),
    ("amount", "amount_1", "$1", "set_setting", "trade_amount=1", 1, 1, {"return_menu": "settings"}),
    ("amount", "amount_2", "$2", "set_setting", "trade_amount=2", 1, 2, {"return_menu": "settings"}),
    ("amount", "amount_3", "$3", "set_setting", "trade_amount=3", 2, 1, {"return_menu": "settings"}),
    ("amount", "amount_4", "$4", "set_setting", "trade_amount=4", 2, 2, {"return_menu": "settings"}),
    ("amount", "amount_5", "$5", "set_setting", "trade_amount=5", 3, 1, {"return_menu": "settings"}),
    ("amount", "amount_10", "$10", "set_setting", "trade_amount=10", 3, 2, {"return_menu": "settings"}),
    ("amount", "amount_20", "$20", "set_setting", "trade_amount=20", 4, 1, {"return_menu": "settings"}),
    ("amount", "amount_50", "$50", "set_setting", "trade_amount=50", 4, 2, {"return_menu": "settings"}),
    ("amount", "amount_manual", "✍️ إدخال يدوي", "request_input", "trade_amount", 5, 1, {"return_menu": "settings"}),
    ("amount", "back_from_amount", "⬅️ رجوع", "open_menu", "settings", 99, 1, {}),
    ("account_type", "account_demo", "🧪 DEMO", "set_setting", "account_type=DEMO", 1, 1, {"return_menu": "settings"}),
    ("account_type", "account_real", "💰 REAL", "set_setting", "account_type=REAL", 1, 2, {"return_menu": "settings"}),
    ("account_type", "back_from_account_type", "⬅️ رجوع", "open_menu", "settings", 99, 1, {}),
    ("risk", "daily_loss_limit_menu", "📉 حد خسارة يومي", "open_menu", "daily_loss_limit", 1, 1, {}),
    ("risk", "max_daily_trades_menu", "🔢 أقصى صفقات", "open_menu", "max_daily_trades", 1, 2, {}),
    ("risk", "stop_after_losses_menu", "⛔ إيقاف بعد خسائر", "open_menu", "stop_after_losses", 2, 1, {}),
    ("risk", "risk_status", "📋 عرض المخاطر", "run_command", "risk_status", 2, 2, {}),
    ("risk", "back_from_risk", "⬅️ رجوع", "open_menu", "main", 99, 1, {}),
    ("daily_loss_limit", "daily_loss_0", "بدون حد", "set_setting", "daily_loss_limit=0", 1, 1, {"return_menu": "risk"}),
    ("daily_loss_limit", "daily_loss_10", "$10", "set_setting", "daily_loss_limit=10", 1, 2, {"return_menu": "risk"}),
    ("daily_loss_limit", "daily_loss_20", "$20", "set_setting", "daily_loss_limit=20", 2, 1, {"return_menu": "risk"}),
    ("daily_loss_limit", "daily_loss_30", "$30", "set_setting", "daily_loss_limit=30", 2, 2, {"return_menu": "risk"}),
    ("daily_loss_limit", "daily_loss_50", "$50", "set_setting", "daily_loss_limit=50", 3, 1, {"return_menu": "risk"}),
    ("daily_loss_limit", "daily_loss_100", "$100", "set_setting", "daily_loss_limit=100", 3, 2, {"return_menu": "risk"}),
    ("daily_loss_limit", "daily_loss_manual", "✍️ إدخال يدوي", "request_input", "daily_loss_limit", 4, 1, {"return_menu": "risk"}),
    ("daily_loss_limit", "back_from_daily_loss", "⬅️ رجوع", "open_menu", "risk", 99, 1, {}),
    ("max_daily_trades", "max_trades_0", "بدون حد", "set_setting", "max_daily_trades=0", 1, 1, {"return_menu": "risk"}),
    ("max_daily_trades", "max_trades_5", "5", "set_setting", "max_daily_trades=5", 1, 2, {"return_menu": "risk"}),
    ("max_daily_trades", "max_trades_10", "10", "set_setting", "max_daily_trades=10", 2, 1, {"return_menu": "risk"}),
    ("max_daily_trades", "max_trades_20", "20", "set_setting", "max_daily_trades=20", 2, 2, {"return_menu": "risk"}),
    ("max_daily_trades", "max_trades_50", "50", "set_setting", "max_daily_trades=50", 3, 1, {"return_menu": "risk"}),
    ("max_daily_trades", "max_trades_manual", "✍️ إدخال يدوي", "request_input", "max_daily_trades", 3, 2, {"return_menu": "risk"}),
    ("max_daily_trades", "back_from_max_trades", "⬅️ رجوع", "open_menu", "risk", 99, 1, {}),
    ("stop_after_losses", "stop_losses_0", "بدون حد", "set_setting", "stop_after_losses=0", 1, 1, {"return_menu": "risk"}),
    ("stop_after_losses", "stop_losses_1", "1", "set_setting", "stop_after_losses=1", 1, 2, {"return_menu": "risk"}),
    ("stop_after_losses", "stop_losses_2", "2", "set_setting", "stop_after_losses=2", 2, 1, {"return_menu": "risk"}),
    ("stop_after_losses", "stop_losses_3", "3", "set_setting", "stop_after_losses=3", 2, 2, {"return_menu": "risk"}),
    ("stop_after_losses", "stop_losses_5", "5", "set_setting", "stop_after_losses=5", 3, 1, {"return_menu": "risk"}),
    ("stop_after_losses", "stop_losses_manual", "✍️ إدخال يدوي", "request_input", "stop_after_losses", 3, 2, {"return_menu": "risk"}),
    ("stop_after_losses", "back_from_stop_losses", "⬅️ رجوع", "open_menu", "risk", 99, 1, {}),
]


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str, admin_ids=None, signals_chat_id=None) -> None:
    with connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT NOT NULL UNIQUE,
                username TEXT,
                full_name TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS telegram_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL UNIQUE,
                title TEXT,
                chat_type TEXT,
                purpose TEXT NOT NULL DEFAULT 'signals',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS telegram_admin_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                menu_key TEXT NOT NULL,
                button_key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_value TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                row_index INTEGER NOT NULL DEFAULT 1,
                col_index INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                admin_only INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                value_type TEXT NOT NULL DEFAULT 'text',
                description TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                quotex_symbol TEXT,
                enabled INTEGER NOT NULL DEFAULT 0,
                payout_min INTEGER NOT NULL DEFAULT 70,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('CALL', 'PUT')),
                signal_time TEXT,
                entry_time TEXT,
                expiry_time TEXT,
                duration_seconds INTEGER NOT NULL DEFAULT 180,
                confidence INTEGER NOT NULL DEFAULT 0,
                amount REAL NOT NULL DEFAULT 0,
                account_type TEXT NOT NULL DEFAULT 'DEMO',
                entry_price REAL,
                exit_price REAL,
                result TEXT NOT NULL DEFAULT 'PENDING' CHECK(result IN ('PENDING', 'WIN', 'LOSS', 'DRAW')),
                profit_loss REAL NOT NULL DEFAULT 0,
                rsi REAL,
                ema_fast REAL,
                ema_slow REAL,
                ema_gap REAL,
                adx REAL,
                atr REAL,
                payout REAL,
                market_session TEXT,
                entry_delay_ms REAL,
                buy_latency_ms REAL,
                loss_streak INTEGER,
                candle_body_ratio REAL,
                price_slippage REAL,
                websocket_latency REAL,
                broker_open_delay_ms REAL,
                execution_offset_ms REAL,
                trend TEXT,
                volatility REAL,
                strategy_name TEXT,
                decision_reason TEXT,
                quotex_order_id TEXT,
                quotex_buy_info TEXT,
                telegram_signal_message_id TEXT,
                telegram_result_message_id TEXT,
                status TEXT NOT NULL DEFAULT 'SCHEDULED',
                error_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quotex_accounts (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                email TEXT,
                password TEXT,
                account_type TEXT NOT NULL DEFAULT 'DEMO',
                enabled INTEGER NOT NULL DEFAULT 1,
                last_login_status TEXT,
                last_login_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
            CREATE INDEX IF NOT EXISTS idx_trades_result ON trades(result);
            CREATE INDEX IF NOT EXISTS idx_assets_enabled ON assets(enabled);
            """
        )
        _seed_settings(db)
        _ensure_schema(db)
        _seed_quotex_account(db)
        _seed_buttons(db)
        _disable_stale_buttons(db)
        _seed_assets(db)
        _seed_admins(db, admin_ids or [])
        if signals_chat_id:
            upsert_chat(db, signals_chat_id, title="Signals Group", chat_type="group", purpose="signals")
        db.commit()


def _seed_settings(db: sqlite3.Connection) -> None:
    for key, (value, value_type, description) in DEFAULT_SETTINGS.items():
        db.execute(
            """
            INSERT OR IGNORE INTO bot_settings(key, value, value_type, description)
            VALUES (?, ?, ?, ?)
            """,
            (key, value, value_type, description),
        )


def _ensure_schema(db: sqlite3.Connection) -> None:
    ensure_column(db, "trades", "quotex_order_id", "TEXT")
    ensure_column(db, "trades", "quotex_buy_info", "TEXT")
    ensure_column(db, "trades", "ema_gap", "REAL")
    ensure_column(db, "trades", "adx", "REAL")
    ensure_column(db, "trades", "atr", "REAL")
    ensure_column(db, "trades", "payout", "REAL")
    ensure_column(db, "trades", "market_session", "TEXT")
    ensure_column(db, "trades", "entry_delay_ms", "REAL")
    ensure_column(db, "trades", "buy_latency_ms", "REAL")
    ensure_column(db, "trades", "loss_streak", "INTEGER")
    ensure_column(db, "trades", "candle_body_ratio", "REAL")
    ensure_column(db, "trades", "price_slippage", "REAL")
    ensure_column(db, "trades", "websocket_latency", "REAL")
    ensure_column(db, "trades", "broker_open_delay_ms", "REAL")
    ensure_column(db, "trades", "execution_offset_ms", "REAL")


def ensure_column(db: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _seed_quotex_account(db: sqlite3.Connection) -> None:
    # Do not seed real credentials. Fill them later from the Telegram admin panel.
    db.execute(
        """
        INSERT OR IGNORE INTO quotex_accounts(id, email, password, account_type, enabled)
        VALUES (1, NULL, NULL, 'DEMO', 0)
        """
    )


def _seed_buttons(db: sqlite3.Connection) -> None:
    for index, button in enumerate(DEFAULT_BUTTONS, start=1):
        menu_key, button_key, label, action_type, action_value, row_index, col_index, payload = button
        db.execute(
            """
            INSERT INTO telegram_admin_buttons(
                menu_key, button_key, label, action_type, action_value, payload_json,
                row_index, col_index, sort_order
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(button_key) DO UPDATE SET
                menu_key = excluded.menu_key,
                label = excluded.label,
                action_type = excluded.action_type,
                action_value = excluded.action_value,
                payload_json = excluded.payload_json,
                row_index = excluded.row_index,
                col_index = excluded.col_index,
                sort_order = excluded.sort_order,
                enabled = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                menu_key,
                button_key,
                label,
                action_type,
                action_value,
                json.dumps(payload, ensure_ascii=False),
                row_index,
                col_index,
                index,
            ),
        )


def _disable_stale_buttons(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE telegram_admin_buttons
        SET enabled = 0, updated_at = CURRENT_TIMESTAMP
        WHERE button_key IN (
            'demo_mode',
            'amount_100'
        )
        """
    )


def _seed_assets(db: sqlite3.Connection) -> None:
    for index, symbol in enumerate(DEFAULT_ASSETS, start=1):
        display_name = asset_display_name(symbol)
        quotex_symbol = DEFAULT_QUOTEX_SYMBOLS.get(symbol, symbol.replace("/", ""))
        db.execute(
            """
            INSERT INTO assets(symbol, display_name, quotex_symbol, enabled, sort_order)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                display_name = excluded.display_name,
                quotex_symbol = excluded.quotex_symbol,
                sort_order = excluded.sort_order,
                updated_at = CURRENT_TIMESTAMP
            """,
            (symbol, display_name, quotex_symbol, 1 if index <= 3 else 0, index),
        )


def asset_flags(symbol: str) -> tuple[str, str]:
    parts = symbol.split("/")
    if len(parts) != 2:
        return "", ""
    return ASSET_FLAGS.get(parts[0].upper(), ""), ASSET_FLAGS.get(parts[1].upper(), "")


def asset_display_name(symbol: str) -> str:
    left_flag, right_flag = asset_flags(symbol)
    return " ".join(part for part in (left_flag, symbol, right_flag) if part)


def asset_markdown_label(symbol: str) -> str:
    left_flag, right_flag = asset_flags(symbol)
    return " ".join(part for part in (left_flag, f"`{symbol}`", right_flag) if part)


def _seed_admins(db: sqlite3.Connection, admin_ids) -> None:
    for telegram_id in admin_ids:
        telegram_id = str(telegram_id).strip()
        if not telegram_id:
            continue
        db.execute(
            """
            INSERT OR IGNORE INTO admin_users(telegram_id)
            VALUES (?)
            """,
            (telegram_id,),
        )


def add_admin_user(db_path: str, telegram_id: int | str, username=None, full_name=None) -> None:
    with connect(db_path) as db:
        db.execute(
            """
            INSERT INTO admin_users(telegram_id, username, full_name, enabled)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = COALESCE(excluded.username, admin_users.username),
                full_name = COALESCE(excluded.full_name, admin_users.full_name),
                enabled = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (str(telegram_id), username, full_name),
        )
        db.commit()


def is_admin(db_path: str, telegram_id: int | str) -> bool:
    with connect(db_path) as db:
        row = db.execute(
            "SELECT id FROM admin_users WHERE telegram_id = ? AND enabled = 1",
            (str(telegram_id),),
        ).fetchone()
        return row is not None


def upsert_chat(db: sqlite3.Connection, chat_id, title=None, chat_type=None, purpose="signals") -> None:
    db.execute(
        """
        INSERT INTO telegram_chats(chat_id, title, chat_type, purpose)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            title = COALESCE(excluded.title, telegram_chats.title),
            chat_type = COALESCE(excluded.chat_type, telegram_chats.chat_type),
            purpose = excluded.purpose,
            updated_at = CURRENT_TIMESTAMP
        """,
        (str(chat_id), title, chat_type, purpose),
    )


def add_telegram_chat(db_path: str, chat_id, title=None, chat_type=None, purpose="signals") -> None:
    with connect(db_path) as db:
        upsert_chat(db, chat_id, title=title, chat_type=chat_type, purpose=purpose)
        db.commit()


def get_signal_chat_ids(db_path: str) -> list[str]:
    with connect(db_path) as db:
        rows = db.execute(
            """
            SELECT chat_id FROM telegram_chats
            WHERE enabled = 1 AND purpose = 'signals'
            ORDER BY id
            """
        ).fetchall()
        return [row["chat_id"] for row in rows]


def get_quotex_account(db_path: str):
    with connect(db_path) as db:
        return db.execute("SELECT * FROM quotex_accounts WHERE id = 1").fetchone()


def upsert_quotex_account(db_path: str, email=None, password=None, account_type=None, enabled=True) -> None:
    current = get_quotex_account(db_path)
    values = {
        "email": email if email is not None else (current["email"] if current else None),
        "password": password if password is not None else (current["password"] if current else None),
        "account_type": account_type if account_type is not None else (current["account_type"] if current else "DEMO"),
        "enabled": 1 if enabled else 0,
    }
    with connect(db_path) as db:
        db.execute(
            """
            INSERT INTO quotex_accounts(id, email, password, account_type, enabled)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                email = excluded.email,
                password = excluded.password,
                account_type = excluded.account_type,
                enabled = excluded.enabled,
                updated_at = CURRENT_TIMESTAMP
            """,
            (values["email"], values["password"], values["account_type"], values["enabled"]),
        )
        db.commit()


def clear_quotex_account(db_path: str) -> None:
    with connect(db_path) as db:
        db.execute(
            """
            UPDATE quotex_accounts
            SET email = NULL,
                password = NULL,
                enabled = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """
        )
        db.commit()


def get_setting(db_path: str, key: str, default=None):
    with connect(db_path) as db:
        row = db.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(db_path: str, key: str, value) -> None:
    with connect(db_path) as db:
        db.execute(
            """
            INSERT INTO bot_settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, str(value)),
        )
        db.commit()


def get_settings(db_path: str) -> dict:
    with connect(db_path) as db:
        rows = db.execute("SELECT key, value FROM bot_settings").fetchall()
        return {row["key"]: row["value"] for row in rows}


def get_signal_schedule(db_path: str) -> dict:
    settings = get_settings(db_path)
    mode = settings.get("signal_mode", "interval").strip().lower()
    if mode not in {"interval", "open"}:
        mode = "interval"
    return {
        "mode": mode,
        "signal_interval_seconds": _safe_int(settings.get("signal_interval_seconds"), 600),
        "pre_signal_seconds": _safe_int(settings.get("pre_signal_seconds"), 60),
        "scan_interval_seconds": max(1, _safe_int(settings.get("scan_interval_seconds"), 5)),
        "single_open_trade": settings.get("single_open_trade", "true").lower() == "true",
    }


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_buttons(db_path: str, menu_key: str):
    with connect(db_path) as db:
        return db.execute(
            """
            SELECT * FROM telegram_admin_buttons
            WHERE menu_key = ? AND enabled = 1
            ORDER BY row_index, col_index, sort_order
            """,
            (menu_key,),
        ).fetchall()


def get_button(db_path: str, button_key: str):
    with connect(db_path) as db:
        return db.execute(
            "SELECT * FROM telegram_admin_buttons WHERE button_key = ? AND enabled = 1",
            (button_key,),
        ).fetchone()


def get_assets(db_path: str):
    with connect(db_path) as db:
        return db.execute(
            "SELECT * FROM assets ORDER BY sort_order, symbol"
        ).fetchall()


def get_enabled_assets(db_path: str):
    with connect(db_path) as db:
        return db.execute(
            "SELECT * FROM assets WHERE enabled = 1 ORDER BY sort_order, symbol"
        ).fetchall()


def toggle_asset(db_path: str, asset_id: int) -> None:
    with connect(db_path) as db:
        db.execute(
            """
            UPDATE assets
            SET enabled = CASE enabled WHEN 1 THEN 0 ELSE 1 END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (asset_id,),
        )
        db.commit()


def set_all_assets(db_path: str, enabled: bool) -> None:
    with connect(db_path) as db:
        db.execute(
            "UPDATE assets SET enabled = ?, updated_at = CURRENT_TIMESTAMP",
            (1 if enabled else 0,),
        )
        db.commit()


def get_today_stats(db_path: str) -> dict:
    with connect(db_path) as db:
        row = db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN result = 'DRAW' THEN 1 ELSE 0 END) AS draws,
                SUM(profit_loss) AS profit_loss
            FROM trades
            WHERE status = 'CLOSED'
              AND result IN ('WIN', 'LOSS', 'DRAW')
              AND DATE(COALESCE(entry_time, created_at), '+3 hours') = DATE('now', '+3 hours')
            """
        ).fetchone()
        return stats_from_row(row)


def get_overall_stats(db_path: str) -> dict:
    with connect(db_path) as db:
        row = db.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN result = 'DRAW' THEN 1 ELSE 0 END) AS draws,
                SUM(profit_loss) AS profit_loss
            FROM trades
            WHERE status = 'CLOSED'
              AND result IN ('WIN', 'LOSS', 'DRAW')
            """
        ).fetchone()
        return stats_from_row(row)


def stats_from_row(row) -> dict:
    total = row["total"] or 0
    wins = row["wins"] or 0
    win_rate = round((wins / total) * 100, 2) if total else 0
    return {
        "total": total,
        "wins": wins,
        "losses": row["losses"] or 0,
        "draws": row["draws"] or 0,
        "profit_loss": row["profit_loss"] or 0,
        "win_rate": win_rate,
    }


def get_pair_stats(db_path: str, limit: int = 10, worst: bool = False) -> list[dict]:
    with connect(db_path) as db:
        rows = db.execute(
            """
            SELECT
                asset,
                COUNT(*) AS total,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN result = 'DRAW' THEN 1 ELSE 0 END) AS draws,
                SUM(profit_loss) AS profit_loss,
                AVG(payout) AS avg_payout
            FROM trades
            WHERE status = 'CLOSED'
              AND result IN ('WIN', 'LOSS', 'DRAW')
            GROUP BY asset
            HAVING total > 0
            """
        ).fetchall()

    stats = []
    for row in rows:
        total = row["total"] or 0
        wins = row["wins"] or 0
        stats.append(
            {
                "asset": row["asset"],
                "total": total,
                "wins": wins,
                "losses": row["losses"] or 0,
                "draws": row["draws"] or 0,
                "profit_loss": row["profit_loss"] or 0,
                "avg_payout": row["avg_payout"],
                "win_rate": round((wins / total) * 100, 2) if total else 0,
            }
        )

    if worst:
        stats.sort(key=lambda item: (item["win_rate"], item["profit_loss"], -item["losses"], -item["total"]))
    else:
        stats.sort(key=lambda item: (-item["win_rate"], -item["profit_loss"], -item["total"]))
    return stats[:limit]


def get_last_closed_trade(db_path: str):
    with connect(db_path) as db:
        return db.execute(
            """
            SELECT * FROM trades
            WHERE status = 'CLOSED'
              AND result IN ('WIN', 'LOSS', 'DRAW')
            ORDER BY COALESCE(entry_time, created_at) DESC
            LIMIT 1
            """
        ).fetchone()


def get_last_trades(db_path: str, limit: int = 10):
    with connect(db_path) as db:
        return db.execute(
            """
            SELECT * FROM trades
            WHERE status = 'CLOSED'
              AND result IN ('WIN', 'LOSS', 'DRAW')
            ORDER BY COALESCE(entry_time, created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def get_entry_errors(db_path: str, limit: int = 10):
    with connect(db_path) as db:
        return db.execute(
            """
            SELECT * FROM trades
            WHERE status = 'ERROR'
               OR error_message IS NOT NULL
            ORDER BY COALESCE(entry_time, created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def create_trade(db_path: str, trade: dict) -> int:
    fields = [
        "asset",
        "direction",
        "signal_time",
        "entry_time",
        "expiry_time",
        "duration_seconds",
        "confidence",
        "amount",
        "account_type",
        "entry_price",
        "exit_price",
        "result",
        "profit_loss",
        "rsi",
        "ema_fast",
        "ema_slow",
        "ema_gap",
        "adx",
        "atr",
        "payout",
        "market_session",
        "entry_delay_ms",
        "buy_latency_ms",
        "loss_streak",
        "candle_body_ratio",
        "price_slippage",
        "websocket_latency",
        "broker_open_delay_ms",
        "execution_offset_ms",
        "trend",
        "volatility",
        "strategy_name",
        "decision_reason",
        "quotex_order_id",
        "quotex_buy_info",
        "telegram_signal_message_id",
        "telegram_result_message_id",
        "status",
        "error_message",
    ]
    values = [trade.get(field) for field in fields]
    placeholders = ", ".join("?" for _ in fields)
    with connect(db_path) as db:
        cursor = db.execute(
            f"""
            INSERT INTO trades({", ".join(fields)})
            VALUES ({placeholders})
            """,
            values,
        )
        db.commit()
        return int(cursor.lastrowid)


def update_trade(db_path: str, trade_id: int, **updates) -> None:
    if not updates:
        return
    updates["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [trade_id]
    with connect(db_path) as db:
        db.execute(f"UPDATE trades SET {assignments} WHERE id = ?", values)
        db.commit()


def get_trade(db_path: str, trade_id: int):
    with connect(db_path) as db:
        return db.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()


def get_active_trade(db_path: str):
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(db_path) as db:
        return db.execute(
            """
            SELECT * FROM trades
            WHERE result = 'PENDING'
              AND status IN ('SCHEDULED', 'OPEN')
              AND COALESCE(expiry_time, entry_time, created_at) > ?
            ORDER BY COALESCE(entry_time, created_at) DESC
            LIMIT 1
            """,
            (now_iso,),
        ).fetchone()


def get_last_trade_time(db_path: str):
    with connect(db_path) as db:
        row = db.execute(
            """
            SELECT COALESCE(entry_time, signal_time, created_at) AS trade_time
            FROM trades
            WHERE status NOT IN ('ERROR', 'SKIPPED')
            ORDER BY COALESCE(entry_time, signal_time, created_at) DESC
            LIMIT 1
            """
        ).fetchone()
        return row["trade_time"] if row else None


def count_consecutive_losses(db_path: str, limit: int = 20) -> int:
    losses = 0
    with connect(db_path) as db:
        rows = db.execute(
            """
            SELECT result FROM trades
            WHERE result IN ('WIN', 'LOSS', 'DRAW')
            ORDER BY COALESCE(entry_time, created_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    for row in rows:
        if row["result"] == "LOSS":
            losses += 1
            continue
        break
    return losses
