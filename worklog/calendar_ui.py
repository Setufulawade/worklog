"""Interactive month calendar in the terminal (curses).

Keys
  arrows / h j k l   move between days
  n / PgDn           next month        p / PgUp   previous month
  t                  jump to today
  Enter / v          view the day full screen
  e                  edit the day in $EDITOR
  a                  add log lines to the day
  q / Esc            quit
"""

import calendar
import curses
import datetime as dt
import os
import shutil
import subprocess

from . import storage

WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _editor():
    return os.environ.get("VISUAL") or os.environ.get("EDITOR") or shutil.which("nano") or "vi"


def edit_in_editor(d):
    """Open the day's file in $EDITOR. Works with or without curses active."""
    p = storage.day_file(d)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("", encoding="utf-8")
    subprocess.call(f'{_editor()} "{p}"', shell=True)
    # normalise (drop blank lines, delete empty file)
    storage.write_day(d, storage.read_day(d))


def _safe_add(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    try:
        win.addstr(y, x, text[: max(0, w - x - 1)], attr)
    except curses.error:
        pass


def _prompt(stdscr, label):
    h, w = stdscr.getmaxyx()
    stdscr.move(h - 1, 0)
    stdscr.clrtoeol()
    _safe_add(stdscr, h - 1, 0, label, curses.A_BOLD)
    curses.echo()
    curses.curs_set(1)
    try:
        raw = stdscr.getstr(h - 1, len(label), max(1, w - len(label) - 2))
    except KeyboardInterrupt:
        raw = b""
    curses.noecho()
    curses.curs_set(0)
    return raw.decode("utf-8", "replace").strip()


def _view_full(stdscr, d):
    top = 0
    while True:
        lines = storage.read_day(d)
        h, w = stdscr.getmaxyx()
        stdscr.erase()
        _safe_add(stdscr, 0, 0, f" {d:%A, %d %B %Y} ", curses.A_REVERSE)
        body = [f"{i + 1:>3}. {ln}" for i, ln in enumerate(lines)] or ["(no entries for this day)"]
        view_h = h - 3
        top = max(0, min(top, max(0, len(body) - view_h)))
        for i, ln in enumerate(body[top : top + view_h]):
            _safe_add(stdscr, 2 + i, 1, ln)
        _safe_add(stdscr, h - 1, 0, " e edit   a add   up/down scroll   q back ", curses.A_DIM)
        stdscr.refresh()
        k = stdscr.getch()
        if k in (ord("q"), 27, ord("v"), 10, 13):
            return
        if k in (curses.KEY_DOWN, ord("j")):
            top += 1
        elif k in (curses.KEY_UP, ord("k")):
            top -= 1
        elif k == ord("e"):
            curses.def_prog_mode()
            curses.endwin()
            edit_in_editor(d)
            curses.reset_prog_mode()
            stdscr.refresh()
        elif k == ord("a"):
            _add_loop(stdscr, d)


def _add_loop(stdscr, d):
    """Keep asking for lines until an empty one is entered."""
    while True:
        text = _prompt(stdscr, f"[{d:%d %b}] log (empty to finish): ")
        if not text:
            return
        storage.append_lines(d, [text])


def _draw(stdscr, year, month, cursor):
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    logged = storage.days_with_logs(year, month)
    today = dt.date.today()

    title = f"  {calendar.month_name[month]} {year}  "
    _safe_add(stdscr, 0, 0, " worklog ", curses.A_REVERSE)
    _safe_add(stdscr, 0, 10, title, curses.A_BOLD)

    # grid
    x0, y0, cw = 2, 2, 5
    for i, name in enumerate(WEEKDAYS):
        _safe_add(stdscr, y0, x0 + i * cw, f"{name:>3}", curses.A_DIM)
    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)
    for r, week in enumerate(weeks):
        for c, day in enumerate(week):
            if not day:
                continue
            d = dt.date(year, month, day)
            mark = "*" if d in logged else " "
            cell = f"{day:>3}{mark}"
            attr = 0
            if d in logged:
                attr |= curses.A_BOLD
            if d == today:
                attr |= curses.A_UNDERLINE
            if d == cursor:
                attr = curses.A_REVERSE | curses.A_BOLD
            _safe_add(stdscr, y0 + 1 + r, x0 + c * cw, cell, attr)

    total = sum(logged.values())
    _safe_add(stdscr, y0 + 8, x0, f"{len(logged)} day(s) logged, {total} entr{'y' if total == 1 else 'ies'} this month", curses.A_DIM)
    _safe_add(stdscr, y0 + 9, x0, "* = has entries   underline = today", curses.A_DIM)

    # preview panel (right side if wide enough, otherwise below)
    lines = storage.read_day(cursor)
    px = x0 + 7 * cw + 3
    py = 2
    if px + 30 > w:
        px, py = x0, y0 + 11
    _safe_add(stdscr, py, px, f"{cursor:%A, %d %B %Y}", curses.A_BOLD)
    if not lines:
        _safe_add(stdscr, py + 2, px, "(no entries - press 'a' to add)", curses.A_DIM)
    else:
        room = max(1, h - py - 5)
        width = max(10, w - px - 2)
        for i, ln in enumerate(lines[:room]):
            text = f"- {ln}"
            if len(text) > width:
                text = text[: width - 1] + "…"
            _safe_add(stdscr, py + 2 + i, px, text)
        if len(lines) > room:
            _safe_add(stdscr, py + 2 + room, px, f"... +{len(lines) - room} more (Enter to view all)", curses.A_DIM)

    _safe_add(
        stdscr,
        h - 1,
        0,
        " arrows move  n/p month  t today  Enter view  e edit  a add  q quit ",
        curses.A_DIM,
    )
    stdscr.refresh()


def _shift_month(d, delta):
    m = d.month - 1 + delta
    y = d.year + m // 12
    m = m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    return dt.date(y, m, min(d.day, last))


def _main(stdscr, start):
    curses.curs_set(0)
    stdscr.keypad(True)
    cursor = start
    while True:
        _draw(stdscr, cursor.year, cursor.month, cursor)
        k = stdscr.getch()
        if k in (ord("q"), 27):
            return
        elif k in (curses.KEY_LEFT, ord("h")):
            cursor -= dt.timedelta(days=1)
        elif k in (curses.KEY_RIGHT, ord("l")):
            cursor += dt.timedelta(days=1)
        elif k in (curses.KEY_UP, ord("k")):
            cursor -= dt.timedelta(days=7)
        elif k in (curses.KEY_DOWN, ord("j")):
            cursor += dt.timedelta(days=7)
        elif k in (ord("n"), curses.KEY_NPAGE):
            cursor = _shift_month(cursor, 1)
        elif k in (ord("p"), curses.KEY_PPAGE):
            cursor = _shift_month(cursor, -1)
        elif k == ord("t"):
            cursor = dt.date.today()
        elif k in (10, 13, curses.KEY_ENTER, ord("v")):
            _view_full(stdscr, cursor)
        elif k == ord("e"):
            curses.def_prog_mode()
            curses.endwin()
            edit_in_editor(cursor)
            curses.reset_prog_mode()
            stdscr.refresh()
        elif k == ord("a"):
            _add_loop(stdscr, cursor)


def run(start=None):
    os.environ.setdefault("ESCDELAY", "25")  # make Esc respond instantly
    curses.wrapper(_main, start or dt.date.today())
