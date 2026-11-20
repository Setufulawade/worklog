# Testing strategy

The suite exists to protect the two things everything else depends on: **date/period
arithmetic** and **the on-disk format**. Those are pure functions with sharp edge cases
(year boundaries, ISO week numbering, blank lines, empty days), so they are cheap to test and
expensive to get wrong.

For the commands themselves, see [../TESTS.md](../TESTS.md). This document covers the
reasoning, the current state and the gaps.

- Framework: `unittest` (standard library)
- Location: `tests/`
- Current suite: **29 tests**, ~0.01 s, no network, no terminal, no optional packages

---

## 1. Why `unittest` and not `pytest`

`worklog` ships with `dependencies = []` and is installable from a bare Debian system. A test
dependency would mean CI and contributors need an extra install for no functional gain — the
suite uses only assertions and temporary directories. `unittest` also gives `discover`,
`-k` filtering and `-f` for free. See [decisions.md](decisions.md#adr-001--standard-library-only).

## 2. Test inventory

### `tests/test_dates.py` — 16 tests

Every test calls the range functions with an explicit `today=`, so results are independent of
the day the suite runs.

| Class | Tests | What it pins down |
|---|---|---|
| `ParseDateTest` (4) | `test_named_days`, `test_offsets`, `test_explicit_formats`, `test_rejects_garbage` | `today`/`t`/empty, `yesterday`/`y`, `tomorrow`, `±N`, the four numeric formats, and that an unparseable string raises instead of silently returning today |
| `WeekRangeTest` (4) | `test_this_week_starts_monday`, `test_last_week`, `test_explicit_iso_week`, `test_any_date_inside_the_week` | Monday-first weeks, `last` = −7 days, `YYYY-Www` via `date.fromisocalendar`, arbitrary date → containing week |
| `MonthRangeTest` (4) | `test_this_month`, `test_last_month_crosses_year`, `test_december_rollover`, `test_rejects_bad_spec` | First/last day inclusive; January's `last` is December of the previous year; month arithmetic for December; rejection of `"banana"` |
| `YearRangeTest` (2) | `test_full_year`, `test_rejects_bad_spec` | 1 Jan – 31 Dec, `this`/`last`/`YYYY`, bad input |
| `DaterangeTest` (2) | `test_inclusive_range`, `test_single_day` | `daterange` yields both endpoints; a one-day range yields one day |

The fixed reference date in the file is `TODAY = dt.date(2026, 11, 20)`, chosen so the `last`
cases exercise a year boundary (January) and a month boundary at the same time.

### `tests/test_storage.py` — 13 tests

| Test | Pins down |
|---|---|
| `test_day_file_layout` | `day_file()` = `<root>/logs/YYYY/YYYY-MM-DD.txt` |
| `test_empty_day_reads_as_empty_list` | Missing file → `[]`, not `None` and no exception |
| `test_append_and_read` | Round-trip preserves order and content |
| `test_blank_lines_are_ignored` | `"a\n\n  \nb\n"` → `["a", "b"]` |
| `test_write_day_replaces_contents` | Whole-file semantics, no leftover lines |
| `test_writing_nothing_deletes_the_file` | `write_day(d, [])` unlinks — the "day exists iff it has entries" invariant |
| `test_days_with_logs_scoped_to_month` | Only the requested month, with correct entry counts |
| `test_days_with_logs_ignores_stray_files` | `notes.txt` and bad stems are skipped, not crashed on |
| `test_days_with_logs_missing_year` | Missing year folder → `{}` |
| `test_entries_between_skips_empty_days_and_sorts` | Empty days absent; keys ascending |
| `test_format_entries` | Header format `YYYY-MM-DD (Weekday)` and `  - entry` bullets |
| `test_format_entries_empty` | `{}` → `""` (so the prompt builder never emits a dangling header) |
| `test_config_dir_follows_home_override` | `WORKLOG_HOME` relocates the config dir too, not just the data dir |

## 3. Isolation

The suite never touches `~/.local/share/worklog`. `StorageTest.setUp` saves the current
`WORKLOG_HOME`, points it at a fresh `tempfile.TemporaryDirectory`, and `tearDown` restores the
previous value (or deletes it) and removes the directory:

```python
def setUp(self):
    self._old = os.environ.get("WORKLOG_HOME")
    self._tmp = tempfile.TemporaryDirectory()
    os.environ["WORKLOG_HOME"] = self._tmp.name

def tearDown(self):
    if self._old is None:
        os.environ.pop("WORKLOG_HOME", None)
    else:
        os.environ["WORKLOG_HOME"] = self._old
    self._tmp.cleanup()
```

This works because of the architectural rule that only `storage.py` resolves paths — no test
ever needs to patch a function or mock a module. Anything newly written must respect
`data_dir()` / `config_dir()`, or it becomes untestable this way.

Caveat: because the env var is process-global, these tests are not safe to run in parallel
threads. The suite is serial by design; do not add concurrency to the runner.

## 4. What is not tested, and why

| Area | Reason | Risk if it breaks | Cheap mitigation |
|---|---|---|---|
| `cli.py` argument parsing and dispatch | Mostly declarative `argparse` wiring; testing it would assert on help strings | A renamed flag or wrong default | `worklog <cmd> --help` in a smoke test |
| `cli.py` output formatting (`view` numbering, confirmation text) | Cosmetic | Cosmetic | Manual check |
| `calendar_ui.py` | Requires a curses terminal and keystrokes; `curses.wrapper` cannot run in a pipe | Broken keybinding, garbled layout | Manual matrix in §6 |
| `reports.compute_stats` | Pure, but currently untested | Wrong streak or busiest day in every report | **Best next test to add** — see §5 |
| `reports._extract_json` / deck normalisation | Pure string → dict, but coupled to `ai.complete` | Crash on a model that wraps JSON in prose | Easy: test with fixture strings |
| `ai.py` | Needs a socket and a key | Provider contract drift | Test `_post` error mapping against a local HTTP server, or skip |
| `pptx_gen.py` | Needs `python-pptx`; asserting on OOXML is brittle | Deck fails to open | Smoke test: build a deck in a temp dir, assert slide count |
| `config.py` load/save/masking | Needs `WORKLOG_HOME`; straightforward | Key precedence bug, world-readable file | Easy to add alongside the storage tests |

The gaps are deliberate scoping, not an endorsement. `compute_stats` and the config precedence
are the two highest-value additions because they are pure logic with silent failure modes.

## 5. Adding a test

1. Put unit tests next to the module under test: `tests/test_<module>.py`.
2. Follow the existing shape — a `unittest.TestCase` per behaviour group, a fixed `TODAY`
   constant for anything date-related, `subTest` only if a case table genuinely helps.
3. If the code touches the filesystem, use the `WORKLOG_HOME`/`TemporaryDirectory` pattern from
   `StorageTest`; do not mock `storage` functions.
4. Assert values, not printed text. If a message matters, assert on the exception type and a
   substring, e.g. `with self.assertRaises(ValueError): …`.
5. Run it: `python3 -m unittest discover -s tests -v`. Keep `tests/__init__.py` in place — the
   dotted module paths in the docs depend on it.

Sketch of the missing `compute_stats` test:

```python
import datetime as dt
from worklog.reports import compute_stats, stats_text

def test_streak_and_busiest_day(self):
    entries = {
        dt.date(2026, 11, 16): ["a"],
        dt.date(2026, 11, 17): ["b", "c", "d"],
        dt.date(2026, 11, 19): ["e"],       # gap breaks the streak
    }
    stats = compute_stats(entries, dt.date(2026, 11, 16), dt.date(2026, 11, 22))
    self.assertEqual(stats["days_logged"], 3)
    self.assertEqual(stats["days_in_period"], 7)
    self.assertEqual(stats["entries"], 5)
    self.assertEqual(stats["busiest_day"], dt.date(2026, 11, 17))
    self.assertEqual(stats["longest_streak"], 2)
    self.assertIn("3 of 7", stats_text(stats))
```

## 6. Manual test matrix

Run this after changes to the CLI, the calendar or the deck, where automation is disproportionate
to the risk.

| Scenario | Command | Expected |
|---|---|---|
| Fresh install, first entry | `WORKLOG_HOME=$(mktemp -d) worklog add "hello"` | `Added to <today>.`; one file created |
| Interactive add | `worklog` (TTY) | Prompt per line; empty line ends; `Saved N entries` |
| Stdin import | `printf 'a\nb\n' \| worklog add` | `Added 2 entries` |
| Bad date | `worklog view -d banana` | `worklog: Could not understand date 'banana'.` exit 1 |
| Empty period | `worklog report weekly -p 1999-W01` | `worklog: No log entries found for …` exit 1, no file |
| No API key | `env -u WORKLOG_API_KEY -u ANTHROPIC_API_KEY -u OPENAI_API_KEY worklog report weekly` | Instructions to set a key, exit 1 |
| Calendar without TTY | `worklog calendar \| cat` | `The calendar needs an interactive terminal.` |
| Calendar keys | arrows, `n`/`p`/`t`/Enter/`e`/`a`/`q` | Cursor moves, months shift, edits persist |
| Editor round-trip | `EDITOR="sed -i 's/^/x /'" worklog edit` | File lines prefixed, `Saved` printed |
| Deck without AI | `worklog ppt weekly --no-ai` | Deck opens with title, stats, one slide per logged day |
| Deck without `python-pptx` | uninstall/observe without the extra | Install instructions, no traceback |
| Narrow terminal | calendar in a 40×12 window | No crash; preview moves below the grid |

## 7. Continuous integration

There is no CI configuration in the repository yet. If one is added, the whole job is:

```sh
python3 -m unittest discover -s tests -v
```

on any Python 3.9+ image, with no secrets and no services. Optionally add a lint step once the
project decides on a linter; see [decisions.md](decisions.md#adr-011--no-formatter-linter-or-ci-configuration).
