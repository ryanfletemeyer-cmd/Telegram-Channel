import logging
import re
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

import db
import periods
from config import TIMEZONE, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

_pending = {}

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}


def _today():
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def _fh(h):
    return f"{round(h, 2):g}"


def get_status_text():
    """Build the status summary block."""
    today = _today()
    day_total = db.get_day_total(today.isoformat())
    mon, sun = periods.get_week_range(today)
    week_total = db.get_total_in_range(mon.isoformat(), sun.isoformat())
    ps, pe = periods.get_pay_period(today)
    day_of = periods.get_day_of_period(today)
    period_total = db.get_total_in_range(ps.isoformat(), pe.isoformat())
    summer = db.get_summer_total()
    today_str = f"{_fh(day_total)} hrs" if db.has_entries(today.isoformat()) else "not yet logged"
    return (
        f"\U0001f4ca Status\n"
        f"Today: {today_str}\n"
        f"This week (Mon–Sun): {_fh(week_total)} hrs\n"
        f"This pay period (day {day_of} of 14): {_fh(period_total)} hrs\n"
        f"All summer total: {_fh(summer)} hrs"
    )


def _is_auth(update: Update) -> bool:
    return update.effective_chat.id == TELEGRAM_CHAT_ID


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all plain-text (non-command) messages."""
    logger.info("Message from chat_id=%s: %s", update.effective_chat.id, update.message.text)
    if not _is_auth(update):
        logger.warning("Unauthorized chat_id=%s (expected %s)", update.effective_chat.id, TELEGRAM_CHAT_ID)
        return

    text = update.message.text.strip()
    lower = text.lower()
    chat_id = update.effective_chat.id

    if chat_id in _pending:
        pending = _pending.pop(chat_id)
        if lower == "yes":
            db.add_hours(pending["date"], pending["hours"], pending["source"])
            day_total = db.get_day_total(pending["date"])
            d = date.fromisoformat(pending["date"])
            await update.message.reply_text(
                f"✅ Logged {_fh(pending['hours'])} hrs for {d.strftime('%a %b')} {d.day}. "
                f"Day total: {_fh(day_total)} hrs."
            )
            return

    try:
        hours = float(lower)
        today = _today()
        if today.weekday() < 5:
            target = today
        else:
            target = _most_recent_unlogged_weekday(today)
        await _log_hours(update, target, hours, "daily_prompt")
        return
    except ValueError:
        pass

    if lower == "undo":
        await _cmd_undo(update)
    elif lower == "total":
        await _cmd_total(update)
    elif lower == "week":
        await _cmd_week(update)
    elif lower == "period":
        await _cmd_period(update)
    elif lower == "help":
        await _cmd_help(update)
    elif lower == "status":
        await update.message.reply_text(get_status_text())
    elif lower.startswith("add "):
        await _cmd_add(update, lower)
    else:
        await update.message.reply_text(
            "Didn't understand that. Send `help` to see commands.",
            parse_mode="Markdown",
        )


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("/start from chat_id=%s", update.effective_chat.id)
    if not _is_auth(update):
        logger.warning("Unauthorized /start from chat_id=%s", update.effective_chat.id)
        return
    await update.message.reply_text(
        "\U0001f44b Hours tracker bot is running! Send `help` to see available commands.",
        parse_mode="Markdown",
    )


async def handle_help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_auth(update):
        return
    await _cmd_help(update)


async def handle_testprompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_auth(update):
        return
    from scheduler import send_daily_prompt
    await send_daily_prompt()


async def handle_testemail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_auth(update):
        return
    from scheduler import send_biweekly_email
    await send_biweekly_email(test_mode=True)


def _most_recent_unlogged_weekday(from_date):
    d = from_date
    for _ in range(7):
        d -= timedelta(days=1)
        if d.weekday() < 5 and not db.has_entries(d.isoformat()):
            return d
    return from_date - timedelta(days=(from_date.weekday() - 4) % 7 or 7)


async def _log_hours(update, target, hours, source):
    if hours < 0:
        await update.message.reply_text("❌ Hours can't be negative.")
        return

    if hours > 24:
        _pending[update.effective_chat.id] = {
            "date": target.isoformat(),
            "hours": hours,
            "source": source,
        }
        await update.message.reply_text(
            f"That's a lot — {_fh(hours)} hours. Reply `yes` to confirm or send a corrected number.",
            parse_mode="Markdown",
        )
        return

    db.add_hours(target.isoformat(), hours, source)
    day_total = db.get_day_total(target.isoformat())
    await update.message.reply_text(
        f"✅ Logged {_fh(hours)} hrs for {target.strftime('%a %b')} {target.day}. "
        f"Day total: {_fh(day_total)} hrs."
    )


async def _cmd_add(update, text):
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text("Usage: `add <hours> [date]`", parse_mode="Markdown")
        return

    try:
        hours = float(parts[1])
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Usage: `add <hours> [date]`", parse_mode="Markdown"
        )
        return

    today = _today()

    if len(parts) == 2:
        await _log_hours(update, today, hours, "add_command")
    elif len(parts) == 3:
        target_str = parts[2]
        if target_str == "yesterday":
            await _log_hours(update, today - timedelta(days=1), hours, "add_yesterday")
        elif target_str in WEEKDAYS:
            weekday_num = WEEKDAYS[target_str]
            d = today
            while d.weekday() != weekday_num:
                d -= timedelta(days=1)
            ps, _ = periods.get_pay_period(today)
            if d < ps:
                await update.message.reply_text(
                    f"❌ {target_str.capitalize()} ({periods.fmt_date(d)}) is before "
                    f"the current pay period."
                )
                return
            await _log_hours(update, d, hours, "add_weekday")
        else:
            try:
                d = date.fromisoformat(target_str)
                await _log_hours(update, d, hours, "add_date")
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid date. Use `yesterday`, a weekday name, or `YYYY-MM-DD`.",
                    parse_mode="Markdown",
                )
    else:
        await update.message.reply_text(
            "Usage: `add <hours> [yesterday|weekday|YYYY-MM-DD]`", parse_mode="Markdown"
        )


async def _cmd_undo(update):
    row = db.undo_last()
    if row:
        await update.message.reply_text(
            f"↩️ Removed {_fh(row['hours'])} hrs from {row['date']} "
            f"(source: {row['source']})."
        )
    else:
        await update.message.reply_text("Nothing to undo.")


async def _cmd_total(update):
    total = db.get_summer_total()
    await update.message.reply_text(f"☀️ All summer total: {_fh(total)} hrs")


async def _cmd_week(update):
    today = _today()
    mon, sun = periods.get_week_range(today)
    entries = dict(db.get_hours_in_range(mon.isoformat(), sun.isoformat()))

    lines = [f"\U0001f4c5 This week ({periods.fmt_date(mon)} – {periods.fmt_date(sun)}):"]
    week_total = 0.0
    for i in range(7):
        d = mon + timedelta(days=i)
        h = entries.get(d.isoformat(), 0.0)
        week_total += h
        marker = "  ←" if d == today else ""
        if h > 0 or d.weekday() < 5:
            lines.append(f"  {d.strftime('%a')} {periods.fmt_date(d)}: {_fh(h)} hrs{marker}")
    lines.append(f"\nWeek total: {_fh(week_total)} hrs")
    await update.message.reply_text("\n".join(lines))


async def _cmd_period(update):
    today = _today()
    ps, pe = periods.get_pay_period(today)
    day_of = periods.get_day_of_period(today)
    entries = dict(db.get_hours_in_range(ps.isoformat(), pe.isoformat()))

    lines = [
        f"\U0001f4cb Pay period ({periods.fmt_date(ps)} – {periods.fmt_date(pe)}), "
        f"day {day_of} of 14:"
    ]
    period_total = 0.0
    for i in range(14):
        d = ps + timedelta(days=i)
        h = entries.get(d.isoformat(), 0.0)
        period_total += h
        marker = "  ←" if d == today else ""
        if h > 0 or d.weekday() < 5:
            lines.append(f"  {d.strftime('%a')} {periods.fmt_date(d)}: {_fh(h)} hrs{marker}")
    lines.append(f"\nPeriod total: {_fh(period_total)} hrs")
    await update.message.reply_text("\n".join(lines))


async def _cmd_help(update):
    await update.message.reply_text(
        "\U0001f4d6 Commands:\n"
        "• `8` or `7.5` — log hours for today\n"
        "• `add X` — add X hours to today\n"
        "• `add X yesterday` — add X hours to yesterday\n"
        "• `add X monday` — add to most recent Monday (etc.)\n"
        "• `add X 2026-05-22` — add to a specific date\n"
        "• `undo` — remove the last entry\n"
        "• `total` — all-summer total\n"
        "• `week` — this week's breakdown\n"
        "• `period` — this pay period's breakdown\n"
        "• `status` — current status summary\n"
        "• `help` — this message\n"
        "\nTest commands:\n"
        "• `/testprompt` — trigger a daily prompt now\n"
        "• `/testemail` — send a test email to yourself",
        parse_mode="Markdown",
    )
