# Data model and on-disk formats

`worklog` has no schema, no migrations and no database. This document specifies exactly what
it writes, where, and what invariants hold, so that other tools can read or generate the data
safely.

See [architecture.md](architecture.md) for how the modules use this model.

---

## 1. Directory layout

All paths are derived in `worklog/storage.py` (`data_dir`, `config_dir`, `day_file`).

```
$XDG_DATA_HOME/worklog/            # defaults to ~/.local/share/worklog
├── logs/
│   ├── 2025/
│   │   ├── 2025-12-31.txt
│   │   └── ...
│   └── 2026/
│       ├── 2026-01-02.txt
│       └── 2026-11-20.txt
└── reports/
    ├── weekly-week-47-2026-16-nov-22-nov-2026.md
    └── monthly-november-2026.md

$XDG_CONFIG_HOME/worklog/          # defaults to ~/.config/worklog
└── config.json                    # mode 0600
```

Resolution rules:

1. If `$WORKLOG_HOME` is set, **both** `data_dir()` and `config_dir()` return it verbatim —
   the subdirectory is not appended. Consequences: logs land in `$WORKLOG_HOME/logs/…` and the
   config in `$WORKLOG_HOME/config.json`. This is the test hook, and a convenient way to keep a
   self-contained instance on a USB stick.
2. Otherwise `data_dir()` = `${XDG_DATA_HOME:-~/.local/share}/worklog` and `config_dir()` =
   `${XDG_CONFIG_HOME:-~/.config}/worklog`. An empty `XDG_DATA_HOME` is treated as unset, which
   matches the XDG spec.

Directories are created lazily. Nothing exists after a fresh install until the first write.

## 2. Day files — the canonical store

**Path:** `<data_dir>/logs/<YYYY>/<YYYY-MM-DD>.txt`

- The folder is the 4-digit year, derived from the date (not from the filename string).
- The filename is the ISO date, `date.isoformat()`.
- Encoding is UTF-8, newline is `\n`.
- **One entry per line.** An entry is any line that is non-blank after stripping whitespace.

Example, `logs/2026/2026-11-20.txt`:

```
Fixed the login timeout bug
Reviewed Priya's PR for the export job
Wrote up the incident notes
```

### Invariants

| Invariant | Enforced by | Notes |
|---|---|---|
| A file contains only non-blank lines | `write_day` strips and filters | Blank lines are never persisted |
| A file always ends with exactly one `\n` | `"\n".join(lines) + "\n"` | Except the empty case, where the file does not exist |
| A day file exists **iff** it has at least one entry | `write_day` unlinks when `lines` is empty | `edit` relies on this: clearing the file in `$EDITOR` deletes the day |
| The date in the filename is the only date associated with an entry | Format has no date field | Moving an entry between days means editing two files |
| Entries keep insertion order | Append is read-all + rewrite | Manual reordering is possible, and is preserved |

### Reading and writing

`read_day(d)` returns `[]` for a missing file, otherwise the non-blank lines with trailing
newlines removed. `write_day(d, lines)` is a whole-file rewrite; `append_lines` is
`write_day(d, read_day(d) + new)`. There is no partial update, no seek, and no lock — see the
limitations in [architecture.md](architecture.md#8-known-limitations).

### Month scanning

`days_with_logs(year, month)` globs `logs/<YYYY>/<YYYY-MM-*.txt>`, parses each stem with
`date.fromisoformat`, and returns `{date: entry_count}`. Files whose stem is not a valid ISO
date are silently skipped, so stray files (`.DS_Store`, editor backups, `notes.txt`) do not
break the calendar. With `month=None` it globs the whole `logs/<YYYY>/` folder instead, which
gives a year summary (logged days and entry counts) without probing every day of the year.

`entries_between(start, end)` walks the range one day at a time with `dates.daterange` and
returns `{date: [lines]}` for days that have entries, in ascending date order (dict insertion
order, guaranteed from Python 3.7).

## 3. Report files

**Path:** `<data_dir>/reports/<kind>-<slug>.md`, unless `--output` is given.

`<kind>` is `weekly`, `monthly` or `yearly`. `<slug>` is the human label lowercased with every
run of non-alphanumeric characters collapsed to a single `-` and trimmed
(`cli._slug`). Examples:

| Period label | File |
|---|---|
| `Week 47, 2026 (16 Nov - 22 Nov 2026)` | `weekly-week-47-2026-16-nov-22-nov-2026.md` |
| `November 2026` | `monthly-november-2026.md` |
| `2026` | `yearly-2026.md` |

The slug is therefore not reversible and not stable across label changes. Generating the same
period twice overwrites the file. The report body is model-generated Markdown behind a
deterministic header:

```markdown
# Weekly Work Report - Week 47, 2026 (16 Nov - 22 Nov 2026)

_Days logged: 5 of 7; total entries: 23; busiest day: 18 Nov 2026 (7 entries); longest streak: 5 day(s)._

## Summary
...
```

The header is the only part of a report that `worklog` itself asserts as fact; everything below
it is the model's summary of the log and is subject to the accuracy caveats in
[security-and-privacy.md](security-and-privacy.md).

## 4. `config.json`

**Path:** `<config_dir>/config.json`, written with mode `0600` (`os.chmod` after write).

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-5-5",
  "base_url": "",
  "api_key": "",
  "max_tokens": 8000
}
```

| Key | Type | Meaning |
|---|---|---|
| `provider` | `"anthropic"` \| `"openai"` | Selects the API shape in `ai.complete` |
| `model` | string | Sent verbatim as `model` in the request body |
| `base_url` | string | Empty means the provider default. Used for proxies, gateways, or a local OpenAI-compatible server |
| `api_key` | string | Fallback only; environment variables win |
| `max_tokens` | int | Sent as `max_tokens`; not validated against the model's limit |

Behavioural details that are easy to miss:

- `load()` starts from `DEFAULTS` and `dict.update`s whatever is on disk, so a partial or
  older config file is valid: missing keys keep their defaults, unknown keys are preserved
  (and printed by `config show`).
- A malformed file is ignored entirely rather than reported; the user sees defaults.
- `config set provider X` also resets `model` to that provider's default **only if** the
  current model is still the old provider's default. A custom model is never silently replaced.
- `providers` are limited to the two names in `PROVIDER_DEFAULT_MODEL`; there is no plugin
  mechanism.
- `set api_key` prints a hint that the file is private, but does not verify the key.

### API key precedence

`config.get_api_key(cfg)` checks, in order:

1. `WORKLOG_API_KEY`
2. `ANTHROPIC_API_KEY` (provider `anthropic`) or `OPENAI_API_KEY` (provider `openai`)
3. `cfg["api_key"]` from the file

Consequence: an exported environment variable always overrides the stored key, and rotating a
key for one session does not require touching the config file. For `provider: openai` with a
non-empty `base_url`, an empty key is permitted — this is what makes a local Ollama or
llama.cpp server usable.

`config.mask()` shows `abcd...wxyz` for keys longer than 10 characters and `****` otherwise, so
`config show` can be pasted into a bug report without leaking a full secret.

## 5. In-memory structures

The storage layer hands out one shape, which `reports.py` and `calendar_ui.py` both consume:

```python
{datetime.date(2026, 11, 20): ["Fixed the login bug", "Reviewed the PR"]}
```

- Keys are always `date` objects, never strings.
- Days with no entries are absent, never present with an empty list. Callers test truthiness
  to decide whether there is work to do (`if not entries: raise ValueError(...)`).
- Ordering is ascending by date because `entries_between` walks the range forwards.

Other structures:

```python
# reports.compute_stats
{"days_logged": 5, "days_in_period": 7, "entries": 23,
 "busiest_day": date(2026, 11, 18), "busiest_count": 7, "longest_streak": 5}

# deck dict (from AI JSON, or from reports.raw_deck)
{"title": "Weekly Work Review",
 "subtitle": "Week 47, 2026 (…)",           # optional for AI decks; defaulted
 "slides": [{"title": "…", "bullets": ["…"], "notes": "…"}]}   # notes optional
```

`pptx_gen.build` requires `deck["slides"]` and each slide's `bullets`; `notes` is optional and
becomes the speaker notes. The title and stats slides are generated from `label` and `stats`,
never from the deck dict, which is why the prompt explicitly forbids the model from producing
them.

## 6. Period labels

Every range function returns `(start, end, label)` with inclusive endpoints. Labels are user
facing and are reused as the report title, the deck subtitle, and the filename slug.

| Function | Inputs | `start` / `end` | Label |
|---|---|---|---|
| `week_range` | `None`, `this` | Monday / Sunday of the current ISO week | `Week 47, 2026 (16 Nov - 22 Nov 2026)` |
| | `last` | the same, one week earlier | — |
| | `YYYY-Www` | that ISO week (`fromisocalendar`) | — |
| | any date | the week containing it | — |
| `month_range` | `None`, `this` | 1st / last day of the current month | `November 2026` |
| | `last` | previous calendar month | — |
| | `YYYY-MM` | that month | — |
| `year_range` | `None`, `this` | 1 Jan / 31 Dec of the current year | `2026` |
| | `last` | previous year | — |
| | `YYYY` | that year | — |

Weeks are ISO-8601: Monday first, and week 1 is the week containing the first Thursday. This
means a January date can belong to week 52/53 of the previous year, and that a "weekly" report
can legitimately span two calendar months or two calendar years.

## 7. Interoperating

Because the store is plain text, other tools need only follow the path and line rules:

```sh
# Import from another tool (one entry per line)
some-exporter | worklog add -d yesterday

# Grep across all history
grep -rn "incident" ~/.local/share/worklog/logs/

# Back up / sync (any tool works)
rsync -a ~/.local/share/worklog/ backup/worklog/
cd ~/.local/share/worklog && git init && git add -A && git commit -m "journal"

# Machine-readable dump of one day
cat ~/.local/share/worklog/logs/2026/2026-11-20.txt
```

When writing files yourself, keep the invariants in §2: UTF-8, one entry per line, no blank
lines, no files for empty days. Anything else is tolerated by the reader but will be
normalised the next time `worklog` rewrites that day.
