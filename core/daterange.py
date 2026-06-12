"""Date-period presets and date parsing/formatting for list filters and storage.

Dates are **stored as ISO ``YYYY-MM-DD``** so SQL range/sort is chronological
(``to_iso`` normalises on write; ``migrate_dates`` converts existing rows), but
are **displayed as ``DD/MM/YY``** (see DESIGN.md) via ``format``/``format_stored``.
``parse`` accepts both forms so a database mid-migration (or any stray legacy row)
still reads correctly. This module also turns a named period (Today, This week, …)
into an inclusive ``(start, end)`` pair of ``datetime.date`` objects.
"""
import datetime

# Order matters: this is the order shown in the period dropdowns.
PERIODS = (
    "All", "Today", "Yesterday", "This week", "Last week",
    "This month", "Last month", "This year", "Last year", "Custom",
)


def parse(text):
    """Parse a stored date string to a date, or None.

    Accepts ISO ``YYYY-MM-DD`` (the current stored form) and the legacy
    ``DD/MM/YY`` / ``DD/MM/YYYY`` so a part-migrated database still reads.
    """
    if not text:
        return None
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def format(value):
    """Format a date as ``DD/MM/YY`` (the app's display form)."""
    return value.strftime("%d/%m/%y") if value else ""


def format_stored(text):
    """Format a stored date string (ISO or legacy) as ``DD/MM/YY`` for display.

    Unparseable text is returned unchanged so nothing unexpected is hidden.
    """
    parsed = parse(text)
    return parsed.strftime("%d/%m/%y") if parsed else (text or "")


def to_iso(value):
    """Normalise a date or date string to ISO ``YYYY-MM-DD`` for storage.

    Accepts a ``datetime.date``, an ISO string, or a legacy ``DD/MM/YY(YY)``
    string. An empty/None value passes through; an unparseable string is returned
    unchanged (so a bad value is never silently turned into a wrong date).
    """
    if value is None or value == "":
        return value
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    parsed = parse(value)
    return parsed.strftime("%Y-%m-%d") if parsed else value


def iso_today(today=None):
    """Today's date as an ISO ``YYYY-MM-DD`` string."""
    return (today or datetime.date.today()).strftime("%Y-%m-%d")


def in_range_sql(start, end, column="date"):
    """Return an ``(sql_clause, params)`` filtering an ISO date column to [start, end].

    ``start``/``end`` are ``datetime.date`` objects or None (open bound). Safe for
    SQL because ISO text compares chronologically. Use as::

        clause, params = daterange.in_range_sql(s, e, "jr.date")
        conn.execute(f"... WHERE {clause}", (*other, *params))
    """
    clauses, params = [], []
    if start is not None:
        clauses.append(f"{column} >= ?")
        params.append(start.strftime("%Y-%m-%d"))
    if end is not None:
        clauses.append(f"{column} <= ?")
        params.append(end.strftime("%Y-%m-%d"))
    return (" AND ".join(clauses) if clauses else "1=1"), params


def period_range(period, today=None):
    """Return an inclusive ``(start, end)`` date pair for a named period.

    ``All`` and ``Custom`` return ``(None, None)`` — the caller supplies the range
    for Custom from its own start/end fields. Either bound may be None (open).
    """
    today = today or datetime.date.today()
    if period in ("All", "Custom"):
        return (None, None)
    if period == "Today":
        return (today, today)
    if period == "Yesterday":
        d = today - datetime.timedelta(days=1)
        return (d, d)
    if period == "This week":
        start = today - datetime.timedelta(days=today.weekday())  # Monday
        return (start, start + datetime.timedelta(days=6))
    if period == "Last week":
        this_mon = today - datetime.timedelta(days=today.weekday())
        last_mon = this_mon - datetime.timedelta(days=7)
        return (last_mon, last_mon + datetime.timedelta(days=6))
    if period == "This month":
        start = today.replace(day=1)
        return (start, _month_end(start))
    if period == "Last month":
        first_this = today.replace(day=1)
        last_month_end = first_this - datetime.timedelta(days=1)
        return (last_month_end.replace(day=1), last_month_end)
    if period == "This year":
        return (today.replace(month=1, day=1), today.replace(month=12, day=31))
    if period == "Last year":
        y = today.year - 1
        return (datetime.date(y, 1, 1), datetime.date(y, 12, 31))
    return (None, None)


def in_range(text, start, end):
    """True if the ``DD/MM/YY`` string falls within [start, end] (open bounds OK).

    Rows whose date can't be parsed pass only when both bounds are open.
    """
    value = parse(text)
    if value is None:
        return start is None and end is None
    if start is not None and value < start:
        return False
    if end is not None and value > end:
        return False
    return True


def _month_end(first_of_month):
    if first_of_month.month == 12:
        nxt = first_of_month.replace(year=first_of_month.year + 1, month=1)
    else:
        nxt = first_of_month.replace(month=first_of_month.month + 1)
    return nxt - datetime.timedelta(days=1)
