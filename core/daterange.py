"""Date-period presets and DD/MM/YY parsing for list filters.

Dates across the app are stored as ``DD/MM/YY`` text (see DESIGN.md). This module
turns a named period (Today, This week, …) into an inclusive ``(start, end)`` pair
of ``datetime.date`` objects and parses the stored text back into dates, so list
views can filter by a quick preset or an explicit start/end range.
"""
import datetime

# Order matters: this is the order shown in the period dropdowns.
PERIODS = (
    "All", "Today", "Yesterday", "This week", "Last week",
    "This month", "Last month", "This year", "Last year", "Custom",
)


def parse(text):
    """Parse a ``DD/MM/YY`` (or ``DD/MM/YYYY``) string to a date, or None."""
    if not text:
        return None
    text = text.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def format(value):
    """Format a date as ``DD/MM/YY`` (the app's stored form)."""
    return value.strftime("%d/%m/%y") if value else ""


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
