"""worklog command line interface."""

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from . import __version__, config, storage
from .ai import AIError
from .dates import parse_date

try:  # nicer line editing (arrow keys, history) in the interactive prompt
    import readline  # noqa: F401
except ImportError:
    pass


def _slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()


def _progress(msg):
    print(f"  {msg}", file=sys.stderr)


# ------------------------------------------------------------ log commands

def _interactive_add(d):
    existing = storage.read_day(d)
    print(f"Logging for {d:%A, %d %B %Y}" + (f"  ({len(existing)} existing entr{'y' if len(existing) == 1 else 'ies'})" if existing else ""))
    print("Type one log per line. Press Enter on an empty line (or Ctrl-D) to finish.\n")
    added = 0
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            break
        added += storage.append_lines(d, [line])
    print(f"Saved {added} entr{'y' if added == 1 else 'ies'} to {d:%Y-%m-%d}." if added else "Nothing added.")


def cmd_add(args):
    d = parse_date(args.date)
    if args.text:
        n = storage.append_lines(d, [" ".join(args.text)])
        print(f"Added to {d:%Y-%m-%d}." if n else "Nothing added.")
    elif not sys.stdin.isatty():
        n = storage.append_lines(d, sys.stdin.read().splitlines())
        print(f"Added {n} entr{'y' if n == 1 else 'ies'} to {d:%Y-%m-%d}.")
    else:
        _interactive_add(d)


def cmd_view(args):
    d = parse_date(args.date)
    lines = storage.read_day(d)
    print(f"{d:%A, %d %B %Y}")
    if not lines:
        print("  (no entries)")
        return
    for i, ln in enumerate(lines, 1):
        print(f"  {i:>2}. {ln}")


def cmd_edit(args):
    from .calendar_ui import edit_in_editor

    d = parse_date(args.date)
    edit_in_editor(d)
    print(f"Saved {d:%Y-%m-%d}.")


def cmd_calendar(args):
    from .calendar_ui import run

    if not sys.stdout.isatty():
        raise SystemExit("The calendar needs an interactive terminal.")
    start = dt.date.today()
    if args.month:
        m = re.fullmatch(r"(\d{4})-(\d{1,2})", args.month)
        start = dt.date(int(m.group(1)), int(m.group(2)), 1) if m else parse_date(args.month)
    run(start)


# --------------------------------------------------------- report / ppt

def cmd_report(args):
    from . import reports

    label, md = reports.generate_report(args.kind, args.period, progress=_progress)
    if args.output:
        out = Path(args.output)
    else:
        out = storage.data_dir() / "reports" / f"{args.kind}-{_slug(label)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(md)
    print(f"[saved to {out}]", file=sys.stderr)


def cmd_ppt(args):
    from . import pptx_gen, reports

    if args.no_ai:
        label, stats, _entries, deck = reports.raw_deck(args.kind, args.period)
    else:
        label, stats, _entries, deck = reports.generate_deck_content(args.kind, args.period, progress=_progress)
    out = Path(args.output) if args.output else Path.cwd() / f"worklog-{args.kind}-{_slug(label)}.pptx"
    out.parent.mkdir(parents=True, exist_ok=True)
    count = pptx_gen.build(out, label, stats, deck, args.kind)
    print(f"Created {out}  ({count} slides)")


# --------------------------------------------------------------- config

def cmd_config(args):
    cfg = config.load()
    if args.action == "show":
        shown = dict(cfg)
        shown["api_key"] = config.mask(config.get_api_key(cfg))
        print(f"Config file: {config.config_path()}")
        for k, v in shown.items():
            print(f"  {k:<11} {v}")
        return
    if args.action == "path":
        print(config.config_path())
        return
    # set
    if not args.key or args.value is None:
        raise SystemExit("Usage: worklog config set <key> <value>   (keys: provider, model, api_key, base_url, max_tokens)")
    if args.key not in config.DEFAULTS:
        raise SystemExit(f"Unknown key '{args.key}'. Valid keys: {', '.join(config.DEFAULTS)}")
    val = args.value
    if args.key == "max_tokens":
        val = int(val)
    if args.key == "provider":
        if val not in config.PROVIDER_DEFAULT_MODEL:
            raise SystemExit("provider must be 'anthropic' or 'openai'")
        old = cfg["provider"]
        if cfg["model"] == config.PROVIDER_DEFAULT_MODEL.get(old):
            cfg["model"] = config.PROVIDER_DEFAULT_MODEL[val]
    cfg[args.key] = val
    config.save(cfg)
    print(f"Set {args.key}." + (" (stored in a private file, mode 600)" if args.key == "api_key" else ""))


# ----------------------------------------------------------------- main

def build_parser():
    p = argparse.ArgumentParser(
        prog="worklog",
        description="A daily work journal for the terminal, with AI reports and PowerPoint export.",
        epilog="Run 'worklog' with no arguments to add today's logs interactively.",
    )
    p.add_argument("--version", action="version", version=f"worklog {__version__}")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="add log entries (today by default)")
    a.add_argument("-d", "--date", default="today", help="date: YYYY-MM-DD, DD-MM-YYYY, yesterday, -2 ...")
    a.add_argument("text", nargs="*", help="a single entry; omit for interactive mode")
    a.set_defaults(func=cmd_add)

    v = sub.add_parser("view", help="show the entries of a day")
    v.add_argument("-d", "--date", default="today")
    v.set_defaults(func=cmd_view)

    e = sub.add_parser("edit", help="edit a day in $EDITOR")
    e.add_argument("-d", "--date", default="today")
    e.set_defaults(func=cmd_edit)

    c = sub.add_parser("calendar", aliases=["cal"], help="browse months, pick a day to view or edit")
    c.add_argument("month", nargs="?", help="start month YYYY-MM (default: this month)")
    c.set_defaults(func=cmd_calendar)

    r = sub.add_parser("report", help="AI report: weekly, monthly or yearly")
    r.add_argument("kind", choices=["weekly", "monthly", "yearly"])
    r.add_argument("-p", "--period", help="weekly: this|last|YYYY-Www|date   monthly: this|last|YYYY-MM   yearly: this|last|YYYY")
    r.add_argument("-o", "--output", help="save the Markdown report here")
    r.set_defaults(func=cmd_report)

    s = sub.add_parser("ppt", help="PowerPoint: weekly, monthly or yearly")
    s.add_argument("kind", choices=["weekly", "monthly", "yearly"])
    s.add_argument("-p", "--period", help="same values as 'report --period'")
    s.add_argument("-o", "--output", help="output .pptx path")
    s.add_argument("--no-ai", action="store_true", help="build slides directly from your logs, no API call")
    s.set_defaults(func=cmd_ppt)

    g = sub.add_parser("config", help="show or change settings (AI provider, model, API key)")
    g.add_argument("action", choices=["show", "set", "path"])
    g.add_argument("key", nargs="?")
    g.add_argument("value", nargs="?")
    g.set_defaults(func=cmd_config)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not args.cmd:
            _interactive_add(dt.date.today())
            return 0
        args.func(args)
        return 0
    except (ValueError, AIError) as e:
        print(f"worklog: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
