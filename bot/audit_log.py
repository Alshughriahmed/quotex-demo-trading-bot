from __future__ import annotations

from collections import Counter
from pathlib import Path


AUDIT_MARKER = " AUDIT event="

EVENT_LABELS = {
    "risk_check": "🛡️ فحص المخاطر",
    "asset_analyzed": "🔍 تحليل زوج",
    "asset_rejected": "🚫 رفض زوج",
    "scan_completed": "✅ انتهاء الفحص",
    "trade_selected": "🎯 اختيار صفقة",
    "timing_check": "⏳ فحص الوقت",
    "timing_allowed": "⏳ الوقت مسموح",
    "blocked": "⛔ إيقاف/منع",
    "trade_scheduled": "📌 جدولة صفقة",
    "trade_opened": "🟢 فتح صفقة",
    "trade_closed": "🏁 إغلاق صفقة",
    "trade_error": "⚠️ خطأ صفقة",
    "connection": "📡 اتصال",
    "telegram_send": "✉️ إرسال Telegram",
}

FIELD_LABELS = {
    "reason": "السبب",
    "asset": "الزوج",
    "direction": "الاتجاه",
    "confidence": "الثقة",
    "payout": "العائد",
    "min_payout": "أقل عائد",
    "allowed": "مسموح",
    "rule": "القاعدة",
    "current": "الحالي",
    "limit": "الحد",
    "result": "النتيجة",
    "profit": "الربح",
    "trade_id": "رقم الصفقة",
    "status": "الحالة",
}


def parse_audit_line(line: str) -> dict | None:
    if AUDIT_MARKER not in line:
        return None

    prefix, payload = line.split(AUDIT_MARKER, 1)
    parts = payload.split()
    if not parts:
        return None

    event = parts[0]
    fields = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key] = value.replace("_", " ")

    time_label = prefix.split()[1] if len(prefix.split()) > 1 else ""
    return {"time": time_label, "event": event, "fields": fields}


def read_audit_events(log_path: Path, max_bytes: int = 120_000) -> list[dict]:
    try:
        with log_path.open("rb") as file:
            file.seek(0, 2)
            size = file.tell()
            file.seek(max(0, size - max_bytes))
            data = file.read()
    except OSError:
        return []

    events = []
    for line in data.decode("utf-8", "replace").splitlines():
        event = parse_audit_line(line)
        if event:
            events.append(event)
    return events


def audit_summary_text(log_path: Path, limit: int = 8) -> str:
    events = read_audit_events(log_path)
    if not events:
        return "📋 سجل القرارات\n\nلا توجد قرارات AUDIT مسجلة بعد."

    recent = events[-limit:][::-1]
    counts = Counter(event["event"] for event in events[-80:])

    lines = ["📋 سجل قرارات البوت", ""]
    lines.append("📊 آخر 80 حدث:")
    for event, count in counts.most_common(6):
        lines.append(f"- {event_label(event)}: {count}")

    lines.append("")
    lines.append(f"🕘 آخر {len(recent)} قرارات:")
    for item in recent:
        lines.append("")
        lines.append(f"{item['time']} | {event_label(item['event'])}")
        for key in ("reason", "asset", "direction", "confidence", "payout", "allowed", "rule", "result", "profit"):
            if key in item["fields"]:
                lines.append(f"{FIELD_LABELS.get(key, key)}: {short(item['fields'][key], 70)}")

    return "\n".join(lines)


def event_label(event: str) -> str:
    return EVENT_LABELS.get(event, event)


def short(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
