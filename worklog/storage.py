"""Plain-text storage: one file per day, one log entry per line.

Layout:  <data_dir>/logs/YYYY/YYYY-MM-DD.txt
"""

import datetime as dt
import os
from pathlib import Path


def data_dir():
    override = os.environ.get("WORKLOG_HOME")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "worklog"


def config_dir():
    override = os.environ.get("WORKLOG_HOME")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "worklog"


def day_file(d):
    return data_dir() / "logs" / f"{d.year:04d}" / f"{d.isoformat()}.txt"


def read_day(d):
    p = day_file(d)
    if not p.exists():
        return []
    return [ln.rstrip("\n") for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def write_day(d, lines):
    lines = [ln.strip() for ln in lines if ln.strip()]
    p = day_file(d)
    if not lines:
        if p.exists():
            p.unlink()
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_lines(d, new_lines):
    new_lines = [ln.strip() for ln in new_lines if ln.strip()]
    if not new_lines:
        return 0
    write_day(d, read_day(d) + new_lines)
    return len(new_lines)


def days_with_logs(year, month=None):
    """Return {date: entry_count} for every logged day in a month.

    With month=None, scan the whole year instead.
    """
    folder = data_dir() / "logs" / f"{year:04d}"
    out = {}
    if not folder.exists():
        return out
    prefix = f"{year:04d}-" if month is None else f"{year:04d}-{month:02d}-"
    for f in folder.glob(f"{prefix}*.txt"):
        try:
            d = dt.date.fromisoformat(f.stem)
        except ValueError:
            continue
        n = len(read_day(d))
        if n:
            out[d] = n
    return out


def entries_between(start, end):
    """Return {date: [lines]} for days that have entries, sorted by date."""
    out = {}
    d = start
    while d <= end:
        lines = read_day(d)
        if lines:
            out[d] = lines
        d += dt.timedelta(days=1)
    return out


def format_entries(entries):
    """Render {date: lines} as plain text suitable for humans and AI prompts."""
    chunks = []
    for d, lines in entries.items():
        chunks.append(f"{d:%Y-%m-%d (%A)}")
        chunks.extend(f"  - {ln}" for ln in lines)
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n" if chunks else ""
