# worklog documentation

Everything about how `worklog` works, written for people who need to understand, maintain or
extend it. For everyday usage, start with the top-level [README](../README.md); for running the
tests, [TESTS.md](../TESTS.md) is the short version and [testing.md](testing.md) explains the
reasoning.

## Contents

| Document | Read it to… |
|---|---|
| [architecture.md](architecture.md) | Understand the module layering, the request flows for logging / calendar / reports / decks, the error model, and the known limitations |
| [data-model.md](data-model.md) | Know exactly what is on disk: paths, XDG rules, the day-file format and its invariants, report filenames, `config.json`, in-memory shapes, period labels |
| [cli-reference.md](cli-reference.md) | Look up a command, flag, date format, environment variable or exit code |
| [development.md](development.md) | Set up a checkout, follow the coding conventions, add a command / period / provider, and build the `.deb` |
| [testing.md](testing.md) | Understand what the 45 tests cover, how isolation works, what is untested and why, and how to add a test |
| [security-and-privacy.md](security-and-privacy.md) | See precisely what leaves the machine, how the API key is protected, and which risks are accepted |
| [decisions.md](decisions.md) | Read the rationale behind the twelve significant design decisions (stdlib-only, plain text, no index, optional `python-pptx`, …) |

## Reading paths

**"I want to use it."** [../README.md](../README.md) → [cli-reference.md](cli-reference.md).

**"I want to change a command."** [architecture.md §3–4](architecture.md#3-module-responsibilities)
→ [development.md §5](development.md#5-recipes) → [cli-reference.md](cli-reference.md).

**"I want to know where my data is."** [data-model.md §1–2](data-model.md#1-directory-layout).

**"I want to know what the AI is sent."** [security-and-privacy.md §1](security-and-privacy.md#1-data-egress).

**"I want to add tests."** [testing.md §5](testing.md#5-adding-a-test).

**"I want to package a release."** [development.md §6–7](development.md#6-packaging).

## At a glance

```
worklog (0.2.0) — a daily work journal for the terminal
├── 10 modules, ~1,240 lines, Python 3.9+, zero runtime dependencies
├── storage: one UTF-8 text file per day, one entry per line, under XDG dirs
├── optional: AI reports and decks (your key, your provider) and python-pptx export
├── tests: 45 unittest cases over dates, storage, CLI output and yearly reports
└── packaging: build-deb.sh (dpkg-deb) and debian/ (debhelper/pybuild)
```

| Aspect | Where it is defined |
|---|---|
| Version | `worklog/__init__.py` |
| Entry points | `worklog = worklog.cli:main` (`pyproject.toml`), `python -m worklog` |
| Commands | `worklog/cli.py:build_parser` |
| Storage root | `worklog/storage.py:data_dir` |
| Period arithmetic | `worklog/dates.py` |
| Prompt wording | `worklog/reports.py` (`REPORT_SYSTEM`, `REPORT_GUIDE`, `DECK_GUIDE`) |
| HTTP contract | `worklog/ai.py:complete` |
| Slide design | `worklog/pptx_gen.py` |
| Package metadata | `pyproject.toml`, `debian/control`, `build-deb.sh` |

## Conventions in this folder

- Documents describe the code as it is in `0.2.0`, not an aspirational design. Where the code has
  a limitation, it is stated as a limitation.
- File and function names are given exactly as they appear in the source, so they can be searched.
- Cross-links use relative paths, so the folder works when read on GitHub, in an editor, or after
  converting with pandoc.
- Diagrams are ASCII rather than Mermaid, to render identically everywhere including a plain
  terminal pager.
