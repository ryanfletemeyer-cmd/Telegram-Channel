from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pymysql

from config import MYSQL_URL, TIMEZONE


def _conn():
    p = urlparse(MYSQL_URL)
    return pymysql.connect(
        host=p.hostname,
        port=p.port or 3306,
        user=p.username,
        password=p.password,
        database=p.path.lstrip("/"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def init_db():
    """Create tables if they don't exist."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hours_log (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    date VARCHAR(10) NOT NULL,
                    hours DOUBLE NOT NULL,
                    logged_at VARCHAR(32) NOT NULL,
                    source VARCHAR(20) NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sent_emails (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    period_start VARCHAR(10) NOT NULL,
                    period_end VARCHAR(10) NOT NULL,
                    sent_at VARCHAR(32) NOT NULL,
                    UNIQUE(period_start)
                )
            """)
        conn.commit()
    finally:
        conn.close()


def add_hours(date_str, hours, source):
    """Insert a new hours entry."""
    conn = _conn()
    try:
        now = datetime.now(ZoneInfo(TIMEZONE)).isoformat()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO hours_log (date, hours, logged_at, source) VALUES (%s, %s, %s, %s)",
                (date_str, hours, now, source),
            )
        conn.commit()
    finally:
        conn.close()


def undo_last():
    """Remove and return the most recent entry, or None."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM hours_log ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM hours_log WHERE id = %s", (row["id"],))
        conn.commit()
        return row
    finally:
        conn.close()


def get_day_total(date_str):
    """Sum of hours for a single date."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(hours), 0) AS total FROM hours_log WHERE date = %s",
                (date_str,),
            )
            return cur.fetchone()["total"]
    finally:
        conn.close()


def has_entries(date_str):
    """True if at least one row exists for this date."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM hours_log WHERE date = %s", (date_str,)
            )
            return cur.fetchone()["cnt"] > 0
    finally:
        conn.close()


def get_hours_in_range(start_iso, end_iso):
    """Returns [(date_str, total_hours), ...] for days with entries in the range."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT date, SUM(hours) AS total FROM hours_log "
                "WHERE date >= %s AND date <= %s GROUP BY date ORDER BY date",
                (start_iso, end_iso),
            )
            return [(r["date"], r["total"]) for r in cur.fetchall()]
    finally:
        conn.close()


def get_total_in_range(start_iso, end_iso):
    """Sum of all hours in a date range."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(hours), 0) AS total FROM hours_log "
                "WHERE date >= %s AND date <= %s",
                (start_iso, end_iso),
            )
            return cur.fetchone()["total"]
    finally:
        conn.close()


def get_summer_total():
    """Sum of all hours ever logged."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(hours), 0) AS total FROM hours_log")
            return cur.fetchone()["total"]
    finally:
        conn.close()


def is_email_sent(period_start_iso):
    """True if a biweekly email was already sent for this period."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM sent_emails WHERE period_start = %s",
                (period_start_iso,),
            )
            return cur.fetchone()["cnt"] > 0
    finally:
        conn.close()


def mark_email_sent(period_start_iso, period_end_iso):
    """Record that the biweekly email for this period was sent."""
    conn = _conn()
    try:
        now = datetime.now(ZoneInfo(TIMEZONE)).isoformat()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO sent_emails (period_start, period_end, sent_at) "
                "VALUES (%s, %s, %s)",
                (period_start_iso, period_end_iso, now),
            )
        conn.commit()
    finally:
        conn.close()
