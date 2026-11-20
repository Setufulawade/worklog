# Development guide

How to work on `worklog`: run it from a checkout, follow the project conventions, add a
feature without fighting the architecture, and build the Debian package.

Related: [architecture.md](architecture.md) · [testing.md](testing.md) ·
[../TESTS.md](../TESTS.md) · [decisions.md](decisions.md)

---

## 1. Prerequisites

| Need | For |
|---|---|
| Python 3.9 or newer | everything |
| `git` | the checkout |
| `python3-pptx` (or `pip install python-pptx`) | only `worklog ppt` |
| `dpkg-deb` | only `./build-deb.sh` |
| `debhelper`, `dh-python`, `pybuild-plugin-pyproject` | only the `debian/rules` package path |

Nothing is required to run, test or develop the core tool. `pyproject.toml` declares
`dependencies = []`; `python-pptx` lives in the optional `ppt` extra so that a plain
`pip install .` stays dependency-free.

## 2. Run from a checkout

There is no build step and no install step for development:

```sh
git clone <repo> worklog && cd worklog
python3 -m worklog                      # interactive add for today
python3 -m worklog view -d yesterday
python3 -m worklog report weekly -p last
```

`python3 -m worklog` goes through `worklog/__main__.py` → `worklog.cli.main`, exactly like the
installed `worklog` script. Use a throwaway data directory so experiments never touch your real
journal:

```sh
WORKLOG_HOME=/tmp/worklog-dev python3 -m worklog add "test entry"
WORKLOG_HOME=/tmp/worklog-dev python3 -m worklog view
```

`WORKLOG_HOME` relocates both the logs and `config.json` into that one folder, which makes it
easy to test reports against fixture logs:

```sh
mkdir -p /tmp/worklog-dev/logs/2026
printf 'Shipped the importer\nFixed the retry loop\n' > /tmp/worklog-dev/logs/2026/2026-11-18.txt
WORKLOG_HOME=/tmp/worklog-dev python3 -m worklog report weekly -p 2026-W47 --output /tmp/w47.md
```

If you prefer an installed entry point, use an editable install in a virtualenv:

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[ppt]'
worklog --version
```

## 3. Layout

```
worklog/
├── worklog/            the package (10 modules, ~1,150 lines)
├── tests/              unittest suite (dates, storage)
├── docs/               this documentation set
├── packaging/          worklog.1 man page, copyright for the .deb
├── debian/             packaging for dpkg-buildpackage / PPA
├── build-deb.sh        single-file build using only dpkg-deb
├── pyproject.toml      PEP 621 metadata, console script, optional extra
├── README.md           user-facing overview
├── TESTS.md            how to run the tests
└── LICENSE             MIT
```

## 4. Conventions

The codebase is small and deliberately uniform. Match it.

**Standard library only.** Adding a runtime dependency is a breaking change for the packaging
story (a `.deb` that installs on a bare system) and needs a decision record. Extend an existing
stdlib tool rather than reaching for a framework: `argparse`, `urllib.request`, `json`,
`pathlib`, `curses`, `unittest`.

**Lazy imports for optional capabilities.** `python-pptx` is imported inside
`pptx_gen._import()`, and `calendar_ui` and `reports` are imported inside the `cmd_*` functions
that need them. This keeps `worklog --version` and plain logging fast and importable on a system
with no optional packages and no terminal.

**Storage is the only place that knows paths.** New features ask `storage` for
`{date: [lines]}`. Do not build paths with `/` or `Path.home()` in a command handler — that
would bypass `WORKLOG_HOME` and break the tests.

**Errors are messages, not tracebacks.** Raise `ValueError` for bad user input and `AIError`
for provider problems; `cli.main` already catches both, prefixes `worklog: ` and returns 1.
Reserve other exceptions for genuine bugs.

**Progress goes to stderr, results to stdout.** `cli._progress` prints to stderr. Reports are
printed to stdout so they can be redirected. Keep that split: it is what makes
`worklog report weekly > week.md` and `worklog report weekly | pbcopy` work.

**Naming.** Module-private helpers are `_prefixed`. Public functions are plain verbs
(`read_day`, `write_day`, `compute_stats`, `build`). Constants are `UPPER_CASE`
(`RANGES`, `DEFAULTS`, `REPORT_SYSTEM`, the `pptx_gen` palette).

**Formatting.** Four-space indents, double-quoted strings, lines capped near 100 columns, no
type annotations (the project is untyped and stays that way), no `__all__`. There is no
formatter or linter configuration committed; keep diffs minimal and let the existing style
guide you.

**Docstrings.** One line for short functions, describing behaviour rather than mechanics. The
`cli.py` file uses section banners:

```python
# ------------------------------------------------------------ log commands
```

**Version.** `worklog/__init__.py.__version__` is the single source of truth: `pyproject.toml`,
`build-deb.sh` (via `sed`) and the man page all describe the same version. Bump it once, in that
file, and update `debian/changelog` when packaging.

**User-facing text.** Sentence case, present tense, no exclamation marks:
`Added to 2026-11-20.`, `Nothing added.`, `No log entries found for November 2026.` Singular
and plural are both handled (`entr{'y' if n == 1 else 'ies'}`).

## 5. Recipes

### Add a subcommand

1. Write `cmd_<name>(args)` in `cli.py` under the appropriate banner.
2. In `build_parser()`, add `p = sub.add_parser("<name>", help="…")`, its arguments, and
   `p.set_defaults(func=cmd_<name>)`.
3. Keep the body thin: resolve input, call into `storage` / `reports`, print. Import heavy or
   optional modules inside the function.
4. Document it in `docs/cli-reference.md`, `README.md`, and `packaging/worklog.1`.
5. Add tests if the logic is non-trivial; parsing and printing alone usually are not worth a
   test.

### Add a period kind (example: quarterly)

1. `dates.py`: `quarter_range(spec=None, today=None) -> (start, end, label)`; register it as
   `RANGES["quarterly"]`.
2. `reports.py`: add entries to `REPORT_GUIDE` and `DECK_GUIDE`; extend the branches in
   `raw_deck` if the no-AI path should support it (currently `weekly` / `monthly` / else-yearly).
3. `cli.py`: add `"quarterly"` to both `choices=[…]` lists and to the `--period` help text.
4. Docs: `README.md` periods line, `docs/data-model.md` label table, man page.

### Add an AI provider

1. `config.py`: `PROVIDER_DEFAULT_MODEL["<name>"] = "<default-model>"` and
   `ENV_KEYS["<name>"] = ["WORKLOG_API_KEY", "<VENDOR>_API_KEY"]`.
2. `ai.py`: add a branch to `complete()` that builds the request, reads the reply and raises
   `AIError` on anything unexpected. Keep the "empty response" check at the end shared.
3. `cli.py`: extend the validation tuple in `cmd_config` and its error string.
4. If the provider needs a non-Bearer auth header, follow the Anthropic branch's pattern of
   passing the header dict to `_post`.
5. Providers that are OpenAI-compatible usually need **no code** — set
   `provider openai` plus `base_url`.

### Change the look of the deck

`pptx_gen.py` is intentionally a single `build()` plus small helpers. The palette is the
module-level constants; slide geometry is in inches against a 13.333 × 7.5 (16:9) canvas. Bullet
glyphs are set through OOXML (`_bullet`), because `python-pptx` has no public bullet API; that
function needs `lxml` and stays isolated for that reason. Font size is chosen by `_font_size`
from bullet count and total character length — if you change thresholds, check a 3-bullet slide
and a 9-bullet slide before committing.

## 6. Packaging

Two independent paths exist.

### `./build-deb.sh` — quick, no debhelper

```sh
./build-deb.sh
# -> dist/worklog_0.1.0_all.deb
```

The script is a single POSIX `sh` file with `set -eu`. It:

1. Reads the version from `worklog/__init__.py` with `sed`.
2. Builds a tree in `build/worklog_<version>_all/`.
3. Copies `worklog/*.py` into `/usr/lib/python3/dist-packages/worklog/`.
4. Writes an executable `/usr/bin/worklog` shim that imports `worklog.cli.main`.
5. Gzips `packaging/worklog.1`, installs the copyright and README into
   `/usr/share/doc/worklog/`, and generates `changelog.Debian.gz` from the current date and
   `$DEB_MAINTAINER`.
6. Normalises permissions (755 dirs, 644 files), computes `Installed-Size`, writes
   `DEBIAN/control` and a `postrm` that removes `__pycache__`, then calls
   `dpkg-deb --build --root-owner-group`.

Set the maintainer before building:

```sh
DEB_MAINTAINER="Jane Doe <jane@example.com>" ./build-deb.sh
dpkg-deb -I dist/worklog_0.1.0_all.deb     # inspect control
dpkg-deb -c dist/worklog_0.1.0_all.deb     # inspect contents
```

`Recommends: python3-pptx` is a recommend rather than a dependency on purpose: PPT export is
optional, and a hard dependency would pull a heavier package onto systems that only journal.

Placeholders to replace before publishing: `Homepage` in `DEBIAN/control`, `debian/control`,
`packaging/copyright`, `debian/copyright`, and the maintainer fields in `debian/changelog` /
`debian/control`.

### `debian/rules` — debhelper / pybuild (for a PPA)

`debian/` drives `dpkg-buildpackage` with `dh $@ --buildsystem=pybuild` and
`Build-Depends: debhelper-compat (= 13), dh-python, pybuild-plugin-pyproject, python3-all,
python3-setuptools`. Format is `3.0 (native)`.

```sh
dpkg-buildpackage -S -us -uc       # source package for a PPA
dput ppa:<user>/worklog ../worklog_0.1.0-1_source.changes
```

Keep `debian/changelog` and `__version__` in step; `debian/changelog` uses the
`0.1.0-1`-style Debian revision while the Python package uses the bare `0.1.0`.

## 7. Release checklist

1. `python3 -m unittest discover -s tests -v` — all green.
2. Bump `__version__`; add a `debian/changelog` entry if packaging.
3. Update `README.md`, `docs/cli-reference.md` and `packaging/worklog.1` for any CLI change.
4. `./build-deb.sh`, then smoke-test the built package in a container or VM:
   `dpkg -i`, `worklog --version`, `worklog add`, `worklog view`, `worklog calendar`.
5. Verify `python3-pptx`-absent behaviour if you touched the deck code: `worklog ppt weekly`
   should print instructions, not a traceback.
6. Tag the commit.

## 8. Debugging notes

| Symptom | Likely cause |
|---|---|
| `No module named worklog` | Running from outside the project root without installing |
| Tests create `__pycache__` | Normal; delete with `find . -name __pycache__ -exec rm -rf {} +` |
| Calendar looks garbled | Terminal smaller than the grid, or `TERM` unset; `_safe_add` truncates instead of crashing |
| `curl`-style network errors | `ai._post` wraps `URLError` as `AIError`; check `base_url`, proxy env vars, and connectivity |
| `API returned HTTP 401` | Key missing/expired, or an env var overriding the stored key — `worklog config show` shows the masked source value |
| `API returned HTTP 404` with a custom `base_url` | The OpenAI branch appends `/chat/completions` to `base_url`; the URL should already end in `/v1` |
| Slide text overflows | `_font_size` thresholds in `pptx_gen.py`; the AI sometimes returns long bullets despite the 18-word rule |
