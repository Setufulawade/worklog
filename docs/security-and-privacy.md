# Security and privacy

`worklog` is a local-first tool, but it is not a private tool by default: two of its commands
send your journal to a third-party API. This document states exactly what leaves the machine,
what is stored, and which risks are accepted.

---

## 1. Data egress

| Command | Network activity | What is sent |
|---|---|---|
| `worklog`, `add`, `view`, `edit`, `calendar` | none | — |
| `worklog config show/path/set` | none | — |
| `worklog ppt --no-ai` | none | — |
| `worklog report weekly\|monthly\|yearly` | one POST per report (yearly: one per non-empty month, then one final POST) | The full text of the period's entries, plus computed stats and the period label |
| `worklog ppt` (without `--no-ai`) | one POST | The same period text and stats |

The destination is `cfg["base_url"]` if set, otherwise:

- `anthropic` → `https://api.anthropic.com/v1/messages`
- `openai` → `https://api.openai.com/v1/chat/completions`

There is no other outbound traffic. No telemetry, no analytics, no update check, no crash
reporting, no timezone or hostname collection.

**Practical consequence:** a `base_url` pointed at `http://localhost:11434/v1` (Ollama) or a
self-hosted gateway keeps all log text on your machine. This is the supported way to use the AI
features privately, and it needs `provider openai` plus `base_url`; an empty API key is accepted
in that configuration.

## 2. What is stored, and how protected

| Data | Location | Permissions |
|---|---|---|
| Log entries | `<data_dir>/logs/YYYY/YYYY-MM-DD.txt` | Created with the process umask (typically `0644` — **readable by other local users** on a shared machine) |
| Reports | `<data_dir>/reports/*.md` | Same |
| API key, config | `<config_dir>/config.json` | Explicitly `0600` (`os.chmod` right after write) |

The config file is deliberately locked down because it may hold a secret. The **logs are not**:
they are ordinary text files, by design, so that they can be grepped, backed up and synced. On a
multi-user host, either tighten the umask before first use (`umask 077`) or keep the data
directory on encrypted storage.

Nothing is encrypted at rest. Anyone who can read the files — or a backup, or a synced folder's
other devices — can read the journal.

## 3. API key handling

Resolution order (`config.get_api_key`): `WORKLOG_API_KEY`, then the provider-specific variable
(`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`), then `api_key` in `config.json`.

- Environment variables win, so a key can be supplied per-session without being written to disk.
- The file is written with mode `0600`; the containing directory is left at default permissions.
- `worklog config show` masks the key: `abcd...wxyz` for keys over 10 characters, `****`
  otherwise. It never prints the full value, which makes the output safe to paste into an issue.
- The key is sent only to the configured endpoint, in the header (`x-api-key` for Anthropic,
  `Authorization: Bearer` for OpenAI-compatible APIs). It is never written into reports, decks,
  log files, or error messages.
- On an HTTP error, `ai._post` includes the **first 500 characters of the response body** in the
  `AIError` message. Provider error bodies normally echo the endpoint and a message, not the
  key — but if you are pasting an error into a public issue, scan it first.
- There is no key rotation, validation, or expiry handling. `config set api_key` does not test
  the key; the first failure appears when you run `report` or `ppt`.

## 4. Threat model

Assumed: a single-user workstation; the user trusts their own shell, their editor and their
package manager. Not defended against: a compromised local account, a malicious AI provider, or
physical access.

| Risk | Assessment | Mitigation |
|---|---|---|
| Log content exposed to the AI provider | **Inherent to `report` and `ppt`.** Provider retention and training policies apply. | Use `ppt --no-ai`, or point `base_url` at a local server; keep sensitive entries out of logged periods you report on |
| Fabricated facts in a report | Model output is generative. The system prompt forbids inventing projects, numbers or people, but this is an instruction, not a guarantee. | Treat reports as drafts; the deterministic header stats are the only verified numbers |
| Prompt injection from log content | Log text is untrusted input to the model. A pasted line like "ignore previous instructions" could alter output. Impact is limited to a wrong report — the tool executes nothing the model says. | Nothing automated; review generated files before sharing |
| Key committed to a repo | `.gitignore` does not cover `config.json`, but it lives outside the project at `~/.config/worklog/`. | Keep it there; never copy it into the checkout |
| Malicious `$EDITOR` value | `edit_in_editor` runs `subprocess.call(f'{editor} "{path}"', shell=True)`. A hostile `EDITOR` value executes arbitrary code — but it would already be running as your user, so this is only a risk if the variable comes from an untrusted source. | Do not export `EDITOR` from untrusted config; a value containing `"` also breaks the command |
| Symlink attack on the data directory | Writes follow symlinks (`Path.write_text`). A local attacker who can write inside your data directory can redirect a day file. | Keep `~/.local/share/worklog` owned by you with normal permissions; the config file's `0600` protects the key, not the logs |
| Concurrent writes / crash mid-write | Not security issues, but they can truncate a day file | Documented limitation; see [architecture.md](architecture.md#8-known-limitations) |
| Terminal escape sequences in entries | A log line containing escape codes is printed by `view` and drawn by curses; a malicious entry could manipulate the display (no execution). | Only paste content you trust; `view` output is line-oriented and adds a numeric prefix |
| Supply chain | Zero runtime dependencies; `python-pptx` only for PPT export, installed from your distro or PyPI. | Keep it optional; prefer the distro package |

## 5. Privacy checklist before sharing output

Before pasting a report, deck or log into a ticket or chat:

1. Reports and decks contain **verbatim details** from your entries — names, ticket IDs, host
   names, sometimes customer data. The model copies what you wrote.
2. `worklog config show` masks the key but reveals `provider`, `model` and `base_url`. A `base_url`
   can leak internal hostnames.
3. Error messages may contain up to 500 characters of provider response.
4. The `.pptx` file embeds speaker notes, which are model-generated text derived from the log.

## 6. Reporting a vulnerability

There is no security contact configured in this repository. Until one exists, report issues
privately to the maintainer listed in `debian/control` / `packaging/copyright`, and avoid opening
a public issue for anything that could expose another user's log data.
