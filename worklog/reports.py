"""Build AI reports and slide content from the log files."""

import datetime as dt
import json

from . import ai, config, storage
from .dates import RANGES, month_range

REPORT_SYSTEM = (
    "You are an assistant that turns a person's raw daily work log into a clear, "
    "accurate, professional report. Only use facts present in the log; never invent "
    "projects, numbers, people or outcomes. If something is unclear, describe it "
    "neutrally. Write in Markdown."
)

REPORT_GUIDE = {
    "weekly": (
        "Write a detailed WEEKLY report with these sections: "
        "## Summary (3-5 sentences), ## Day-by-day (what happened each logged day), "
        "## Key accomplishments, ## Themes & focus areas, ## Challenges / blockers (only if "
        "the log suggests any), ## Carry-over & suggested next steps."
    ),
    "monthly": (
        "Write a detailed MONTHLY report with these sections: "
        "## Executive summary, ## Major accomplishments, ## Work by theme or project "
        "(group related entries together), ## Week-by-week progress, ## Challenges / blockers "
        "(only if the log suggests any), ## Patterns & observations (consistency, focus), "
        "## Goals for next month (derived from open items in the log)."
    ),
    "yearly": (
        "Write a detailed YEARLY report with these sections: "
        "## Year in review (executive summary), ## Biggest accomplishments, "
        "## Month-by-month timeline, ## Major themes & projects across the year, "
        "## Skills & growth shown, ## Challenges & lessons, ## Patterns & observations, "
        "## Priorities for next year (derived from the log)."
    ),
}

DECK_GUIDE = {
    "weekly": "6-8 slides covering: overview, highlights per day or theme, accomplishments, challenges, next steps.",
    "monthly": "8-10 slides covering: overview, major accomplishments, work by theme, week-by-week progress, challenges, patterns, next month goals.",
    "yearly": "10-12 slides covering: year overview, biggest accomplishments, a timeline by quarter or month, themes, growth, challenges, next year priorities.",
}


# ---------------------------------------------------------------- stats ----

def compute_stats(entries, start, end):
    days_logged = len(entries)
    total = sum(len(v) for v in entries.values())
    span = (end - start).days + 1
    busiest = max(entries.items(), key=lambda kv: len(kv[1]), default=None)

    # longest streak of consecutive logged days
    best = cur = 0
    prev = None
    for d in sorted(entries):
        cur = cur + 1 if prev and (d - prev).days == 1 else 1
        best = max(best, cur)
        prev = d

    return {
        "days_logged": days_logged,
        "days_in_period": span,
        "entries": total,
        "busiest_day": busiest[0] if busiest else None,
        "busiest_count": len(busiest[1]) if busiest else 0,
        "longest_streak": best,
    }


def stats_text(stats):
    b = f"{stats['busiest_day']:%d %b %Y} ({stats['busiest_count']} entries)" if stats["busiest_day"] else "n/a"
    return (
        f"Days logged: {stats['days_logged']} of {stats['days_in_period']}; "
        f"total entries: {stats['entries']}; busiest day: {b}; "
        f"longest streak: {stats['longest_streak']} day(s)."
    )


# ----------------------------------------------------------- AI context ----

def _say(progress, msg):
    if progress:
        progress(msg)


def _month_digests(start, end, cfg, progress):
    """For a year: ask the AI to condense each month, so long logs fit in one prompt."""
    digests = []
    for m in range(1, 13):
        s, e, label = month_range(f"{start.year}-{m:02d}")
        entries = storage.entries_between(s, e)
        if not entries:
            continue
        _say(progress, f"Condensing {label} ({sum(len(v) for v in entries.values())} entries)...")
        text = ai.complete(
            REPORT_SYSTEM,
            "Condense this month of work-log entries into 8-15 concrete bullet points "
            "(keep specific names, tasks and outcomes). Plain Markdown bullets only.\n\n"
            + storage.format_entries(entries),
            cfg,
        )
        digests.append(f"### {label}\n{text}")
    return "\n\n".join(digests)


def _context(kind, start, end, cfg, progress):
    entries = storage.entries_between(start, end)
    if not entries:
        return entries, ""
    if kind == "yearly":
        return entries, _month_digests(start, end, cfg, progress)
    return entries, storage.format_entries(entries)


# ------------------------------------------------------------- reports ----

def generate_report(kind, spec=None, cfg=None, progress=None):
    """Return (label, markdown). Raises ValueError if the period has no entries."""
    cfg = cfg or config.load()
    start, end, label = RANGES[kind](spec)
    entries, context = _context(kind, start, end, cfg, progress)
    if not entries:
        raise ValueError(f"No log entries found for {label}.")
    stats = compute_stats(entries, start, end)
    note = "(condensed month by month)" if kind == "yearly" else "(raw daily entries)"
    prompt = (
        f"Period: {label}\n"
        f"Stats: {stats_text(stats)}\n\n"
        f"{REPORT_GUIDE[kind]}\n\n"
        f"Work log {note}:\n\n{context}"
    )
    _say(progress, f"Writing {kind} report for {label}...")
    body = ai.complete(REPORT_SYSTEM, prompt, cfg)
    header = f"# {kind.capitalize()} Work Report - {label}\n\n_{stats_text(stats)}_\n\n"
    return label, header + body + "\n"


# ---------------------------------------------------------------- decks ----

DECK_SYSTEM = (
    "You turn a person's work log into presentation content. Use only facts from the log. "
    "Respond with ONE JSON object and nothing else (no code fences)."
)


def _extract_json(text):
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ai.AIError("The AI did not return slide content in the expected format.")
    try:
        return json.loads(text[a : b + 1])
    except json.JSONDecodeError as e:
        raise ai.AIError(f"Could not parse the AI's slide content: {e}") from None


def generate_deck_content(kind, spec=None, cfg=None, progress=None):
    """Return (label, stats, entries, deck_dict) with deck_dict = {title, subtitle, slides:[{title,bullets,notes}]}."""
    cfg = cfg or config.load()
    start, end, label = RANGES[kind](spec)
    entries, context = _context(kind, start, end, cfg, progress)
    if not entries:
        raise ValueError(f"No log entries found for {label}.")
    stats = compute_stats(entries, start, end)
    prompt = (
        f"Create slide content for a {kind} work presentation. Period: {label}.\n"
        f"Stats: {stats_text(stats)}\n"
        f"Plan: {DECK_GUIDE[kind]}\n\n"
        "Rules: each slide has a short title (max 8 words) and 3-5 bullets, each bullet "
        "max 18 words and specific. Do NOT include a title slide or a stats slide (those are "
        "added automatically). Optional 'notes' = 1-3 sentences of speaker notes.\n\n"
        'JSON shape: {"title": str, "subtitle": str, "slides": [{"title": str, "bullets": [str], "notes": str}]}\n\n'
        f"Work log:\n\n{context}"
    )
    _say(progress, f"Planning {kind} slides for {label}...")
    deck = _extract_json(ai.complete(DECK_SYSTEM, prompt, cfg))
    deck.setdefault("title", f"{kind.capitalize()} Work Review")
    deck.setdefault("subtitle", label)
    deck["slides"] = [
        s for s in deck.get("slides", []) if isinstance(s, dict) and s.get("bullets")
    ]
    if not deck["slides"]:
        raise ai.AIError("The AI returned no usable slides.")
    return label, stats, entries, deck


def raw_deck(kind, spec=None):
    """Build slides straight from the log, with no AI. Returns (label, stats, entries, deck)."""
    start, end, label = RANGES[kind](spec)
    entries = storage.entries_between(start, end)
    if not entries:
        raise ValueError(f"No log entries found for {label}.")
    stats = compute_stats(entries, start, end)
    slides = []

    def add(title, bullets):
        for i in range(0, len(bullets), 7):
            t = title if i == 0 else f"{title} (cont.)"
            slides.append({"title": t, "bullets": bullets[i : i + 7]})

    if kind == "weekly":
        for d, lines in entries.items():
            add(f"{d:%A, %d %b}", lines)
    elif kind == "monthly":
        weeks = {}
        for d, lines in entries.items():
            iso = d.isocalendar()
            weeks.setdefault((iso[0], iso[1]), []).append((d, lines))
        for (_, wk), items in weeks.items():
            add(f"Week {wk}", [f"{d:%d %b}: {ln}" for d, lines in items for ln in lines])
    else:
        months = {}
        for d, lines in entries.items():
            months.setdefault(d.month, []).extend(f"{d:%d %b}: {ln}" for ln in lines)
        for m, bullets in months.items():
            add(f"{dt.date(2000, m, 1):%B}", bullets[:6] + ([f"...and {len(bullets) - 6} more entries"] if len(bullets) > 6 else []))

    deck = {
        "title": f"{kind.capitalize()} Work Review",
        "subtitle": label,
        "slides": slides,
    }
    return label, stats, entries, deck
