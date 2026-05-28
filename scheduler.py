from datetime import timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import db
import periods
from config import TIMEZONE, TELEGRAM_CHAT_ID, EMPLOYER_EMAIL, GMAIL_ADDRESS
from email_sender import send_email
from handlers import get_status_text, _today, _fh

_bot = None


def setup_scheduler(bot):
    """Register all scheduled jobs and start the scheduler."""
    global _bot
    _bot = bot

    tz = ZoneInfo(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        send_daily_prompt,
        CronTrigger(day_of_week="mon-fri", hour=17, minute=0, timezone=tz),
        id="daily_prompt",
    )
    scheduler.add_job(
        send_evening_reminder,
        CronTrigger(day_of_week="mon-fri", hour=19, minute=0, timezone=tz),
        id="evening_reminder",
    )
    scheduler.add_job(
        send_morning_reminder,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=0, timezone=tz),
        id="morning_reminder",
    )
    scheduler.add_job(
        _check_biweekly_email,
        CronTrigger(day_of_week="sun", hour=17, minute=0, timezone=tz),
        id="biweekly_email",
    )

    scheduler.start()
    return scheduler


async def send_daily_prompt():
    """Send the 5pm daily hours prompt with status summary."""
    prompt = "How many hours did you work today? Reply with a number (e.g. `8` or `7.5`)."
    status = get_status_text()
    await _bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=f"{prompt}\n\n{status}",
        parse_mode="Markdown",
    )


async def send_evening_reminder():
    """7pm reminder if today's hours haven't been logged."""
    today = _today()
    if not db.has_entries(today.isoformat()):
        await _bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="Hey, still need your hours for today.",
        )


async def send_morning_reminder():
    """8am next-day reminder if the previous weekday's hours are missing."""
    today = _today()
    if today.weekday() == 0:
        check_date = today - timedelta(days=3)
        label = "Friday"
        cmd_hint = "`add X friday`"
    else:
        check_date = today - timedelta(days=1)
        label = "yesterday"
        cmd_hint = "`add X yesterday` or just `X` if today is the same"

    if not db.has_entries(check_date.isoformat()):
        await _bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"Don't forget to log {label}'s hours. Reply with {cmd_hint}.",
            parse_mode="Markdown",
        )


async def _check_biweekly_email():
    """Scheduled Sunday check — sends the email only on period-end Sundays."""
    today = _today()
    if not periods.is_period_end(today):
        return
    await send_biweekly_email(test_mode=False)


async def send_biweekly_email(test_mode=False):
    """Build and send the biweekly hours email."""
    today = _today()
    ps, pe = periods.get_pay_period(today)

    if not test_mode and db.is_email_sent(ps.isoformat()):
        await _bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"ℹ️ Biweekly email for {periods.fmt_date(ps)}–{periods.fmt_date(pe)} was already sent.",
        )
        return

    entries = dict(db.get_hours_in_range(ps.isoformat(), pe.isoformat()))
    total = sum(entries.values()) if entries else 0.0

    start_str = periods.fmt_date(ps)
    end_str = periods.fmt_date(pe)

    breakdown_lines = []
    for i in range(14):
        d = ps + timedelta(days=i)
        h = entries.get(d.isoformat(), 0.0)
        if d.weekday() >= 5 and h == 0:
            continue
        breakdown_lines.append(f"  {d.strftime('%a')} {periods.fmt_date(d)}: {_fh(h)} hrs")

    HOURLY_RATE = 25
    amount_owed = total * HOURLY_RATE

    body = (
        f"Hi Marc,\n\n"
        f"Here are my hours for the pay period {start_str} – {end_str}:\n\n"
        f"Total hours: {_fh(total)}\n"
        f"Amount owed: ${amount_owed:,.2f} ({_fh(total)} hrs × ${HOURLY_RATE}/hr)\n\n"
        f"Daily breakdown:\n"
        + "\n".join(breakdown_lines)
        + "\n\nThanks,\nRyan"
    )

    subject = f"Hours worked — {start_str} to {end_str}"
    to_addr = GMAIL_ADDRESS if test_mode else EMPLOYER_EMAIL

    try:
        send_email(to_addr, subject, body)
        if not test_mode:
            db.mark_email_sent(ps.isoformat(), pe.isoformat())
        dest = "yourself (test)" if test_mode else "Marc"
        await _bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"✅ Biweekly email sent to {dest} — {_fh(total)} total hours for {start_str}–{end_str}.",
        )
    except Exception as e:
        await _bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"❌ Failed to send biweekly email: {e}",
        )
