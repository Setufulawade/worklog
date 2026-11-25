# Architecture

`worklog` is a single-user, offline-first command line application. It has no server, no
database, and no background process. Everything it knows lives in plain text files under the
user's XDG directories.

This document describes how the code is organised, how data moves through it, and why the
significant decisions were made.

- Version described: `0.2.0`
- Python: 3.9+
- Runtime dependencies: none. `python-pptx` is imported lazily and only for `worklog ppt`.

---

## 1. Design goals

| Goal | Consequence in the code |
|---|---|
| Your notes must outlive the tool | Logs are plain UTF-8 text, one file per day, one entry per line. No database, no proprietary format, no migration logic. |
| Zero install friction | Standard library only. `urllib` instead of an SDK, `argparse` instead of a CLI framework, `unittest` instead of pytest. |
| AI is optional | Logging, viewing, editing, the calendar and `ppt --no-ai` are fully local. Only `report` and AI-built `ppt` touch the network. |
| Composable with Unix tools | `add` reads stdin when it is not a TTY, `report` writes Markdown to stdout, everything else is line-oriented text. |
| Degrade with a clear message | Each optional capability (PPT export, AI, interactive calendar) checks for its own prerequisite and prints an actionable error instead of a traceback. |

## 2. Layered view

```
                        ┌─────────────────────────────────────────┐
   user / shell ───────▶│  cli.py        argparse + dispatch      │
                        └───────┬─────────────┬─────────────┬─────┘
                                │             │             │
                    ┌───────────▼──┐   ┌──────▼──────┐  ┌───▼──────────┐
                    │ calendar_ui  │   │  reports    │  │   config     │
                    │  (curses)    │   │ stats+prompt│  │ json + XDG   │
                    └───────┬──────┘   └──┬───────┬──┘  └───┬──────────┘
                            │             │       │         │
                            │        ┌────▼───┐ ┌─▼─────────▼──┐
                            │        │  ai.py │ │  storage.py  │
                            │        │ urllib │ │  plain text  │
                            │        └────┬───┘ └──────┬───────┘
                            │             │            │
                            └─────────────┴────────────┤
                                                       ▼
                                        ┌──────────────────────────┐
                                        │ pptx_gen.py (lazy import)│
                                        │ python-pptx rendering    │
                                        └──────────────────────────┘
                                                       │
                                        ┌──────────────▼───────────┐
                                        │ $XDG_DATA_HOME / $XDG_…  │
                                        │ ~/.local/share/worklog   │
                                        │ ~/.config/worklog        │
                                        └──────────────────────────┘
```

Two rules keep the layering clean:

1. **`storage.py` is the only module that touches the filesystem for logs.** Everything else
   asks it for `{date: [entries]}` mappings. This is what makes the test suite able to
   redirect all I/O with a single environment variable.
2. **`ai.py` is the only module that opens a socket.** `reports.py` builds prompts and parses
   responses but never performs I/O itself; `config.py` never talks to a provider.

## 3. Module responsibilities

| Module | Lines | Responsibility |
|---|---|---|
| `worklog/__init__.py` | 3 | Package metadata; the single source of truth for `__version__`, which `build-deb.sh` parses with `sed`. |
| `worklog/__main__.py` | 5 | Enables `python -m worklog`. Five lines that call `cli.main()`. |
| `worklog/cli.py` | 297 | `argparse` surface, subcommand dispatch, interactive `add` loop, stdin pipelining, the day/year views, the `year` shortcut, exit codes, output paths. |
| `worklog/dates.py` | 94 | `parse_date` for human date input; `week_range` / `month_range` / `year_range` returning `(start, end, label)`; `RANGES` dispatch table; `daterange` generator. |
| `worklog/storage.py` | 99 | Day-file path resolution, read/write/append, month/year scanning, range collection, prompt formatting. |
| `worklog/config.py` | 60 | `config.json` load/save (mode 600), XDG path resolution, env-var key precedence, key masking. |
| `worklog/calendar_ui.py` | 216 | `curses` month grid, day preview panel, full-screen viewer, multi-line add prompt, `$EDITOR` handoff. |
| `worklog/reports.py` | 224 | Period stats, system/user prompt construction, yearly month digests, Markdown report assembly, JSON deck extraction, no-AI deck builder. |
| `worklog/ai.py` | 80 | One function, `complete(system, prompt, cfg)`, over `urllib.request` for the Anthropic Messages API and the OpenAI Chat Completions API. |
| `worklog/pptx_gen.py` | 159 | Builds the `.pptx`: title slide, stats slide, content slides, auto-sized bullets, speaker notes. All `python-pptx` imports are inside `_import()`. |

## 4. Request flows

### 4.1 Logging an entry (`worklog`, `worklog add`)

```
argv ──▶ build_parser ──▶ cmd_add
                            │
                    args.text? ──yes──▶ append_lines(d, [" ".join(text)])
                            │no
                    stdin is a TTY? ──no──▶ append_lines(d, stdin lines)
                            │yes
                    _interactive_add(d): loop input(), one append per line
                            │
                     write_day(d, existing + new)   # full rewrite
```

`append_lines` is implemented as read-all-then-write-all rather than an `O_APPEND` write. That
keeps blank-line normalisation and file creation in one place (`write_day`), at the cost of
re-reading the day file for each line typed interactively — irrelevant at human typing speed,
and it is what guarantees the "file is deleted when it has no entries" invariant.

### 4.2 Browsing the calendar

```
cmd_calendar ──▶ isatty check ──▶ curses.wrapper(_main, start)
                                        │
                                   _draw(year, month, cursor)
                                        ├── storage.days_with_logs(y, m)   # {date: count}
                                        ├── calendar.Calendar(firstweekday=0)
                                        └── storage.read_day(cursor)       # preview panel
                                        │
                                   getch() ──▶ move / shift month / view / edit / add
```

The calendar holds no state beyond the cursor date. Every redraw re-reads the month's file
counts and the cursor day's entries, so an edit made in `$EDITOR` is visible immediately on
return.

### 4.3 Generating a report

```
cmd_report ──▶ reports.generate_report(kind, period)
                     │
                     ├── RANGES[kind](spec) ──▶ (start, end, label)
                     ├── storage.entries_between(start, end)   # {date: [lines]}
                     │        └── empty? ──▶ ValueError("No log entries found for …")
                     ├── compute_stats(entries, start, end)
                     ├── context:
                     │     weekly/monthly → storage.format_entries(entries)
                     │     yearly           → _month_digests(): one ai.complete() per
                     │                        non-empty month, then those digests
                     │                        become the context
                     ├── ai.complete(REPORT_SYSTEM, prompt, cfg)
                     └── header (title + stats line) + model Markdown
                     │
               write to --output or data_dir()/reports/<kind>-<slug>.md, print to stdout
```

The yearly path is the only multi-call flow: up to 12 condensation requests followed by the
final synthesis. Its purpose is context-window management — a full year of daily entries can
exceed the model's limit, whereas 12 digests of 8–15 bullets will not.

### 4.4 Generating a deck

```
cmd_ppt ──▶ --no-ai? ──yes──▶ reports.raw_deck()  (deterministic, local)
                │no
        reports.generate_deck_content()
                ├── same period + context + stats as a report
                ├── ai.complete(DECK_SYSTEM, prompt) → JSON
                ├── _extract_json(): slice from first "{" to last "}"
                ├── normalise: drop non-dict slides and slides without bullets
                └── empty result → AIError
                │
        pptx_gen.build(path, label, stats, deck, kind)
                └── title slide, stats slide, N content slides → prs.save()
```

`raw_deck` exists so the export works without an API key: weekly becomes one slide per logged
day, monthly groups by ISO week, yearly groups by month. Long lists are chunked 7 bullets per
slide with a `(cont.)` title suffix.

Both commands are thin wrappers: `cmd_report` delegates to `_write_report` and `cmd_ppt` to
`_build_ppt`, and the `year` shortcut calls the same two helpers after printing the year view.
That keeps one default output location and one save/print policy per artifact regardless of
which command asked for it.

## 5. Data model

Full detail is in [data-model.md](data-model.md). In brief:

- A **day** is a file: `logs/YYYY/YYYY-MM-DD.txt`.
- An **entry** is a non-blank line in that file. Entries have no ID, timestamp, tag or
  metadata. Ordering is file order.
- The in-memory currency between modules is `Dict[date, List[str]]`, always containing only
  days that have at least one entry.

Consequences worth knowing: you cannot have an intentionally blank entry, you cannot reorder
entries except by editing the file, and a day "exists" only while it has content.

## 6. Error handling and exit codes

| Situation | Behaviour |
|---|---|
| Bad date / unknown period / no entries | `ValueError` in the layer that detects it, caught in `main()`, printed as `worklog: <message>`, exit **1** |
| AI failure (no key, HTTP error, unreachable, empty or unparseable response) | `AIError` (a `RuntimeError`), same path, exit **1** |
| Ctrl-C | Caught in `main()`, exit **130** |
| Missing `python-pptx` | `_import()` raises `SystemExit` with install instructions |
| Calendar with stdout redirected | `SystemExit("The calendar needs an interactive terminal.")` |
| Corrupt `config.json` | Silently ignored (`json.JSONDecodeError` / `OSError`), defaults used |
| Unparseable filename in the logs folder | Skipped by `days_with_logs` via `ValueError` on `date.fromisoformat` |
| Chronically short terminal or narrow window | `_safe_add` swallows `curses.error` and truncates, rather than crashing the UI |

The CLI never leaks a traceback for expected failures. Anything else is a bug and is allowed
to propagate.

## 7. Extension points

| To add… | Touch |
|---|---|
| A new subcommand | `cli.build_parser()` (subparser + `set_defaults(func=…)`), plus a `cmd_*` function — `cmd_year` is a compact example of a shortcut that reuses existing handlers |
| A new date/period format | `dates.parse_date`, or one of the three `*_range` functions |
| A new period kind (e.g. quarterly) | A range function, an entry in `dates.RANGES`, entries in `reports.REPORT_GUIDE`, `reports.DECK_GUIDE`, plus the `choices=[…]` in the two subparsers |
| A new AI provider | `config.PROVIDER_DEFAULT_MODEL`, `config.ENV_KEYS`, a branch in `ai.complete`, and the validation string in `cmd_config` |
| A new slide layout | `pptx_gen.build` after the stats-slide block |
| A new stats metric | `reports.compute_stats` and `reports.stats_text` (the deck stats slide reads `stats` directly, so extend its `cards` list too) |

## 8. Known limitations

These are deliberate trade-offs, not oversights. See [decisions.md](decisions.md).

1. **No file locking.** Two concurrent `worklog add` processes on the same day will lose one
   write. Single-user, interactive usage makes this acceptable; a lock file would add a
   cross-platform dependency or platform-specific `fcntl`/`msvcrt` code.
2. **Writes are not atomic.** `Path.write_text` is not `write`+`rename`, so a crash mid-write
   could truncate a day file. The blast radius is one day's entries.
3. **`entries_between` is O(days in range).** It performs one file existence check and read per
   day. A 10-year yearly report is ~3,650 `stat` calls — negligible locally, but it means the
   storage layer does not scale to decades without a directory listing optimisation.
4. **The whole period is sent to the model.** There is no chunking for very dense weekly or
   monthly logs; only the yearly path is condensed.
5. **Stats stop at counts.** No hours, no categories, no tags — the format has no place to put
   them.
6. **`pptx_gen` reaches into OOXML.** Real bullet glyphs require `lxml` and `pptx.oxml`, which
   are transitive dependencies of `python-pptx` rather than documented public API.
7. **Interactive paths assume a POSIX terminal** (`curses`, `$VISUAL`, `man` pages, `dpkg-deb`).
   The plain commands work anywhere Python does.
8. **No i18n.** Weekday and month names come from the system locale through `strftime`, but
   all messages are English.
