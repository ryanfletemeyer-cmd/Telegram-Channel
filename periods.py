from datetime import date, timedelta

ANCHOR_DATE = date(2026, 5, 18)
PAY_PERIOD_LENGTH = 14


def get_pay_period(d):
    """Returns (period_start, period_end) for the pay period containing date d."""
    days_since = (d - ANCHOR_DATE).days
    period_num = days_since // PAY_PERIOD_LENGTH
    start = ANCHOR_DATE + timedelta(days=period_num * PAY_PERIOD_LENGTH)
    end = start + timedelta(days=PAY_PERIOD_LENGTH - 1)
    return start, end


def get_day_of_period(d):
    """Returns 1-based day number within the pay period (1–14)."""
    start, _ = get_pay_period(d)
    return (d - start).days + 1


def is_period_end(d):
    """Returns True if d is the last day (Sunday) of a pay period."""
    _, end = get_pay_period(d)
    return d == end


def get_week_range(d):
    """Returns (monday, sunday) for the ISO week containing date d."""
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def fmt_date(d):
    """Formats a date as 'May 18' (no leading zero on day)."""
    return f"{d:%b} {d.day}"
