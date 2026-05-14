# Quotex Demo Telegram Bot

بوت Telegram لإدارة إشارات تداول وتجربة تنفيذ صفقات DEMO على Quotex.

> تنبيه: هذه نسخة تطويرية للتجربة على DEMO فقط. لا توجد أي ضمانات ربح. لا تشغل REAL قبل اختبار طويل وإدارة مخاطر صارمة.

## ما تم تنظيفه

هذه النسخة لا تحتوي على:

- `.env` الحقيقي
- `session.json`
- قواعد بيانات `*.db`
- السجلات `logs/`
- النسخ الاحتياطية `backups/`
- أي توكن أو كلمة مرور مدمجة داخل الكود

## التحسينات الأولى

- إزالة بيانات Quotex الافتراضية من `database.py`.
- إصلاح احترام الفاصل الزمني بين الصفقات في `TradingRunner.can_scan_by_schedule`.
- إضافة `.gitignore` مناسب.
- إضافة `.env.example`.
- إضافة `requirements.txt`.
- إضافة فحص أمان محلي يمنع رفع ملفات التشغيل والأسرار بالخطأ.

## التشغيل المحلي

من داخل مجلد المشروع:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example bot/.env
```

املأ `bot/.env`:

```env
TELEGRAM_BOT_TOKEN=ضع_توكن_البوت_هنا
ADMIN_TELEGRAM_IDS=ضع_user_id_الخاص_بك
SIGNALS_CHAT_ID=ضع_chat_id_للمجموعة_اختياري
DATABASE_PATH=data.db
```

ثم شغل:

```bash
cd bot
python main.py --init-db
python main.py --check-config
python main.py --check
python main.py
```

## فحص الأمان قبل الرفع

قبل أي `git add` أو `git push` شغّل من مجلد المشروع الرئيسي:

```bash
python tools/safety_check.py
```

إذا ظهر خطأ، لا ترفع الكود قبل إصلاحه. هذا الفحص يبحث عن:

- ملفات `.env` الحقيقية.
- قواعد البيانات `*.db`.
- ملفات الجلسات مثل `session.json`.
- مجلدات التشغيل مثل `logs/` و `backups/`.
- أنماط واضحة لتوكنات أو كلمات مرور مكتوبة داخل الملفات.

## أوامر Telegram

- `/id` لمعرفة `chat_id` و `user_id`.
- `/start` أو `/menu` لفتح لوحة التحكم.
- `/status` لعرض الحالة.
- `/test_signal` لتجربة إرسال رسالة للمجموعة.

## ملاحظات أمان

- لا ترفع `bot/.env` إلى GitHub.
- لا ترفع `data.db`.
- لا ترفع `session.json` أو `.quotex/`.
- استخدم حساب DEMO أولًا.
