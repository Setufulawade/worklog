# Running the worklog tests

The tests use only the Python standard library (`unittest`). There is nothing to install
and no network or AI access is involved, so they run anywhere `worklog` itself runs.

Run every command below from the **project root** (the folder containing `pyproject.toml`),
because the tests import `worklog` as a package.

## Run the whole suite

```sh
python3 -m unittest discover -s tests -v
```

- `discover -s tests` finds every `test_*.py` file in `tests/`.
- `-v` prints one line per test. Drop it for a compact dot-per-test summary.

Expected result:

```
Ran 45 tests in 0.009s

OK
```

One test is skipped when `python-pptx` is not installed (`--ppt` is still built and checked;
the test is the only part that needs the library).

If you see `python: command not found`, use `python3` (some systems do not provide a
`python` executable), or activate the virtualenv you installed the package into.

## Run a single file, class or test

```sh
python3 -m unittest tests.test_storage -v                        # one file
python3 -m unittest tests.test_dates.WeekRangeTest -v            # one class
python3 -m unittest tests.test_dates.ParseDateTest.test_offsets  # one test
```

Use the module path (`tests.test_storage`), not a file path (`tests/test_storage.py`).
That works because `tests/__init__.py` makes `tests` an importable package.

You can also run from inside the folder, where the prefix is unnecessary:

```sh
cd tests && python3 -m unittest discover -v
```

## Useful flags

| Flag | Effect |
|---|---|
| `-v`, `--verbose` | list every test by name |
| `-f`, `--failfast` | stop after the first failure |
| `-k PATTERN` | only run tests whose name matches (Python 3.7+) |

Examples:

```sh
python3 -m unittest discover -s tests -f      # stop after the first failure
python3 -m unittest discover -s tests -k month  # only tests with "month" in the name
```

## What is covered

| File | Tests |
|---|---|
| `tests/test_dates.py` | `parse_date` (`today`, `yesterday`, `-3`, `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`, bad input), `week_range` (ISO weeks, `last`, `YYYY-Www`, any date inside a week), `month_range` (`this`, `last` across a year boundary, December rollover, bad spec), `year_range`, `daterange` |
| `tests/test_storage.py` | day-file path layout, append/read round-trip, blank-line filtering, `write_day` replacement, empty writes deleting the file, `days_with_logs` month and year scoping, stray-file tolerance, `entries_between` ordering, `format_entries` output |
| `tests/test_cli.py` | `view` day output, `view --year` grouping and `--summary`, the `year` shortcut (view, summary, `--report`, `--ppt --no-ai`, argument guards) |
| `tests/test_reports.py` | the yearly path: one digest call per logged month, month caps in the no-AI deck, empty-year errors |

Not covered by tests: the curses calendar, live calls to an AI provider (the CLI tests stub
`reports.ai.complete`), and the default AI deck path when `python-pptx` is absent.

## How isolation works

`tests/test_storage.py` sets `WORKLOG_HOME` to a fresh `tempfile.TemporaryDirectory` in
`setUp` and restores the previous value in `tearDown`. Your real logs in
`~/.local/share/worklog/` are never read or written by the tests.

Running the suite creates `__pycache__/` folders. That is normal Python behaviour; add a
`.gitignore` entry if you do not want them showing up in `git status`.
