"""Date parsing and period helpers."""

import datetime as dt
import re


def parse_date(text, today=None):
    """Parse 'today', 'yesterday', '-3', '+1', 'YYYY-MM-DD', 'DD-MM-YYYY', 'DD/MM/YYYY'."""
    today = today or dt.date.today()
    t = (text or "today").strip().lower()
    if t in ("today", "t", ""):
        return today
    if t in ("yesterday", "y"):
        return today - dt.timedelta(days=1)
    if t == "tomorrow":
        return today + dt.timedelta(days=1)
    if re.fullmatch(r"[+-]\d+", t):
        return today + dt.timedelta(days=int(t))
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    raise ValueError(
        f"Could not understand date '{text}'. Use YYYY-MM-DD, DD-MM-YYYY, "
        "'today', 'yesterday' or an offset like -2."
    )


def week_range(spec=None, today=None):
    """ISO week. spec: None/'this', 'last', 'YYYY-Www', or any date inside the week."""
    today = today or dt.date.today()
    s = (spec or "this").strip().lower()
    if s == "this":
        ref = today
    elif s == "last":
        ref = today - dt.timedelta(days=7)
    else:
        m = re.fullmatch(r"(\d{4})-?w(\d{1,2})", s)
        if m:
            ref = dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
        else:
            ref = parse_date(s, today)
    start = ref - dt.timedelta(days=ref.weekday())
    end = start + dt.timedelta(days=6)
    iso = start.isocalendar()
    label = f"Week {iso[1]}, {iso[0]} ({start:%d %b} - {end:%d %b %Y})"
    return start, end, label


def month_range(spec=None, today=None):
    """spec: None/'this', 'last', 'YYYY-MM'."""
    today = today or dt.date.today()
    s = (spec or "this").strip().lower()
    if s == "this":
        y, m = today.year, today.month
    elif s == "last":
        first = today.replace(day=1)
        prev = first - dt.timedelta(days=1)
        y, m = prev.year, prev.month
    else:
        mm = re.fullmatch(r"(\d{4})-(\d{1,2})", s)
        if not mm:
            raise ValueError("Month must be 'this', 'last' or YYYY-MM.")
        y, m = int(mm.group(1)), int(mm.group(2))
    start = dt.date(y, m, 1)
    nxt = dt.date(y + (m == 12), (m % 12) + 1, 1)
    end = nxt - dt.timedelta(days=1)
    return start, end, f"{start:%B %Y}"


def year_range(spec=None, today=None):
    """spec: None/'this', 'last', 'YYYY'."""
    today = today or dt.date.today()
    s = (spec or "this").strip().lower()
    if s == "this":
        y = today.year
    elif s == "last":
        y = today.year - 1
    elif re.fullmatch(r"\d{4}", s):
        y = int(s)
    else:
        raise ValueError("Year must be 'this', 'last' or YYYY.")
    return dt.date(y, 1, 1), dt.date(y, 12, 31), str(y)


RANGES = {"weekly": week_range, "monthly": month_range, "yearly": year_range}


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)
