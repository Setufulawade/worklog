# Architecture decision records

Short records of the choices that shaped `worklog`, in the order they matter. Each entry states
the context, the decision, the consequences accepted, and what was rejected.

Status: all accepted as of 0.1.0.

---

## ADR-001 — Standard library only

**Context.** `worklog` is distributed as a Debian package (`Depends: python3 (>= 3.9)`) and must
install and run on a bare system. Every runtime dependency becomes a packaging obligation and a
potential version conflict on the user's machine.

**Decision.** No runtime dependencies. `argparse` for the CLI, `urllib.request` for HTTP, `json`
for config and deck content, `pathlib` for paths, `curses` for the calendar, `unittest` for
tests. `pyproject.toml` declares `dependencies = []`.

**Consequences.** Anthropic and OpenAI calls are written by hand (~80 lines) instead of using
their SDKs; we must keep the request/response shapes correct ourselves and cannot use SDK
features such as automatic retries, streaming or token counting. Installing on a minimal Debian
image needs nothing beyond `python3`.

**Rejected.** `requests` (nicer API, but a dependency for one function), `click`/`typer`
(duplicate of `argparse`'s job), `pytest` (test-only dependency, no functional gain).

## ADR-002 — One plain-text file per day, one entry per line

**Context.** The journal is the user's data and must remain readable, greppable and portable for
years, across versions of this tool and without it.

**Decision.** Store each day as UTF-8 text at `logs/YYYY/YYYY-MM-DD.txt`, one entry per line, and
delete the file when the day has no entries. No headers, no metadata, no escaping.

**Consequences.** Trivial interop (`cat`, `grep`, `rsync`, `git`), trivial backup, no migration
code ever. In exchange the format cannot express per-entry timestamps, tags, categories or
editing history — a day is an ordered list of strings, full stop. Blank lines are not
representable as entries; entry order is file order.

**Rejected.** SQLite (opaque, needs a migration story, breaks `grep`), JSON/TOML per day
(unreadable in an editor, merge-hostile), one file per entry (thousands of inodes, no natural
day boundary).

## ADR-003 — Year folders, and derived paths as the only index

**Context.** `entries_between` must find a range of days, and `days_with_logs` must light up a
month in the calendar. A database index would be the conventional answer.

**Decision.** Derive paths from dates (`logs/<year>/<iso-date>.txt`) and scan the year folder when
a month or range is needed. `days_with_logs` tolerates unparseable filenames instead of
maintaining an index file.

**Consequences.** There is nothing to keep in sync, nothing to rebuild, and hand-placed or
rsync-restored files are picked up immediately. Range reads cost one `stat` per day
(`entries_between`), and month scans cost one `glob` plus a read per hit — fine for years of a
single user's journal, not designed for decades or for thousands of entries per day.

**Rejected.** A manifest/index file (can drift from truth; every write becomes two writes),
SQLite (see ADR-002), a directory watcher or cache (needs invalidation, outlives its value here).

## ADR-004 — Facts in the header, prose from the model

**Context.** An LLM asked to summarise can invent numbers. Users may paste reports into status
meetings.

**Decision.** `reports.generate_report` writes the deterministic part itself — the title and the
stats line (`Days logged: 5 of 7; total entries: 23; …`) — and appends the model's Markdown below
it. The system prompt forbids inventing facts, but the tool does not rely on that for the
numbers it can compute. The deck follows the same split: `worklog` renders the title and stats
slides; the model only supplies content slides.

**Consequences.** Every report has at least one trustworthy section, and users can tell them
apart. The model's content is still unverified prose, and the tool does not detect or flag
fabrication inside it.

**Rejected.** Letting the model produce the whole document including statistics (unverifiable),
and post-hoc fact-checking (needs a second model call and still unreliable).

## ADR-005 — Yearly reports condense month by month

**Context.** A year of daily entries can exceed a model's context window, and a single huge prompt
degrades output quality even when it fits.

**Decision.** For `yearly`, `_month_digests` asks the model to turn each non-empty month into
8–15 concrete bullets, then sends the twelve digests (plus stats and period) as the context for
the final report. Weekly and monthly reports send the raw entries.

**Consequences.** Up to 13 API calls per yearly report — slower and more expensive — and detail
lost in each condensation cannot be recovered later. In return the final prompt is bounded
regardless of how much was logged, and each call is small enough to produce a focused summary.
Months with no entries are skipped, so a partial year costs proportionally less.

**Rejected.** Truncating the log to the last N entries (silently drops the start of the year),
summarising only quarterly (still too large), chunked map-reduce into a single file (more moving
parts, same call count).

## ADR-006 — `python-pptx` is optional and lazily imported

**Context.** PPT export is a minority use, but it needs a third-party library with
`lxml` underneath.

**Decision.** Declare it as the optional extra `ppt` and import it inside `pptx_gen._import()`,
which also carries the install instructions. The `.deb` lists it as `Recommends`, not `Depends`.

**Consequences.** `worklog --version`, logging and reports work on a system without it; `ppt`
fails with a two-line fix instead of an `ImportError`. The deck code cannot use a hard import at
module top level, so `build()` receives the imported symbols through a tuple — slightly awkward,
contained to one function.

**Rejected.** Hard dependency (heavier install for everyone), hand-writing OOXML (large, fragile,
and worse than the library).

## ADR-007 — `WORKLOG_HOME` overrides both XDG roots

**Context.** Tests and developer experiments need isolated storage; tests otherwise have to mock
`Path.home()` or patch module functions.

**Decision.** A single environment variable replaces both the data root and the config root,
without appending `worklog` to it. `storage.data_dir()` and `storage.config_dir()` are the only
readers; everything else goes through them.

**Consequences.** The whole suite isolates with two lines in `setUp`/`tearDown`, and a portable
copy of the journal is one env var away. Downside: it is a process-global variable, so tests are
serial, and a user who sets it gets logs *directly* in that folder, which is not obvious from the
name — documented in [data-model.md](data-model.md#1-directory-layout).

**Rejected.** Per-command `--data-dir` flag (pollutes the CLI surface and every handler),
`unittest.mock.patch` on `Path.home` (fragile, and would not cover config).

## ADR-008 — `curses` for the calendar

**Context.** Browsing months is the one place where a list of prompts is a poor fit; users want to
see which days have entries and jump around.

**Decision.** A `curses` month grid (`calendar_ui.py`) with a preview panel, plus a plain
`$EDITOR` handoff for real editing. All drawing goes through `_safe_add`, which truncates and
swallows `curses.error`; the editor launches with curses suspended and restored.

**Consequences.** No mouse, no colour theme, no Windows support, and layout must survive small
terminals (preview moves below the grid when there is no room). In exchange: no dependency, it
works over SSH, and it starts instantly. The command refuses to run when stdout is not a TTY
rather than corrupting a pipe.

**Rejected.** A TUI framework (a dependency for one screen), a web UI (a server, a port, a
browser — a different product), arrow-key prompts in a loop (cannot show a month at a glance).

## ADR-009 — Config as JSON at mode 0600, environment variables first

**Context.** The tool needs a provider, model and key, and keys must not leak into the repo or
into `ps` output.

**Decision.** `config.json` under the XDG config dir, `chmod 0600` immediately after write.
`WORKLOG_API_KEY` and the provider-specific variables take precedence over the file. Output is
masked. Unknown keys in the file are preserved.

**Consequences.** Secrets can stay entirely off disk (env vars) or in one clearly-permissioned
file. JSON is not human-friendly to hand-edit, and there is no schema validation beyond
`cmd_config`'s checks — an invalid `provider` written by hand surfaces as an `AIError` at call
time.

**Rejected.** A TOML/INI config (would need a parser pre-3.11), a keyring integration (platform
dependency; also gets in the way of headless use), storing keys only in the environment
(inconvenient for desktop users).

## ADR-010 — Human labels double as filenames, via a lossy slug

**Context.** Reports and decks need names users recognise, on a filesystem with restricted
characters.

**Decision.** `cli._slug` lowercases the period label and replaces every run of non-alphanumerics
with `-`. `weekly-week-47-2026-16-nov-22-nov-2026.md`.

**Consequences.** Recognisable and portable, and collisions are practically impossible for date
ranges. The mapping is lossy and not reversible, so code must never parse a filename to recover a
period; regenerate from `RANGES` instead. Re-running a period overwrites its report, which is the
intended behaviour.

**Rejected.** Raw labels as filenames (spaces, commas, parentheses), timestamps in the name
(unstable, clutters the folder), hashes (unreadable).

## ADR-011 — No formatter, linter or CI configuration

**Context.** The project is ~1,100 lines with one maintainer and no build server.

**Decision.** No `black`/`ruff`/`flake8` config, no `.github/workflows`. Style is maintained by
consistency with the existing files; the only automated check is the `unittest` suite.

**Consequences.** No toolchain to install or version, and no churn from formatting rules. Review
depends on the contributor matching the house style (4 spaces, double quotes, `_private`
helpers). Adding CI later is a three-line job — see
[testing.md](testing.md#7-continuous-integration).

**Rejected.** Adopting a formatter now (would reformat every file in one commit, obscuring real
change history for a cosmetic gain).

## ADR-012 — Two packaging paths, one authoritative version

**Context.** Users want a `.deb` they can install now; a PPA needs debhelper metadata.

**Decision.** Keep both: `build-deb.sh` (POSIX `sh`, `dpkg-deb` only, works on any Debian-ish
host) and `debian/` (`debhelper-compat 13`, `pybuild`) for `dpkg-buildpackage`. `__version__` in
`worklog/__init__.py` is the source of truth: `build-deb.sh` parses it with `sed`, while
`pyproject.toml` repeats it statically and `debian/changelog` carries the `0.1.0-1` revision.

**Consequences.** Some duplication — the package description appears in `build-deb.sh`,
`debian/control` and `pyproject.toml` — and a release must update `debian/changelog` separately.
In exchange, a contributor can produce an installable `.deb` with no debhelper installed, and a
maintainer can still upload to a PPA with the standard tooling.

**Rejected.** Only `build-deb.sh` (no PPA path), only `debian/` (requires debhelper just to try
the tool), a single templated control file (extra generation step for two files).
