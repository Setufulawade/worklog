<<<<<<< HEAD
automate worklog
=======
# worklog

A daily work journal for the Linux terminal, with AI-written reports and PowerPoint export.

## Install

```sh
sudo apt install ./worklog_0.1.0_all.deb     # or, once published: sudo apt install worklog
sudo apt install python3-pptx                # only needed for PPT export (installed automatically if "Recommends" are on)
```

## Everyday use

```sh
worklog                          # add today's logs, one line at a time (empty line = done)
worklog add "Fixed login bug"    # add a single entry
worklog add -d yesterday         # add logs for another day (interactive)
worklog add -d 2026-11-03 "Sprint planning"
worklog view -d 2026-11-03       # show a day
worklog edit -d 2026-11-03       # edit a day in $EDITOR
worklog calendar                 # browse a month, pick a day to view / edit / add
```

Dates accept `YYYY-MM-DD`, `DD-MM-YYYY`, `today`, `yesterday`, or an offset like `-3`.

### Calendar keys

| Key | Action |
|---|---|
| arrows / `h j k l` | move between days |
| `n` / `p` (or PgDn / PgUp) | next / previous month |
| `t` | jump to today |
| `Enter` / `v` | view the day full screen |
| `e` | edit the day in `$EDITOR` |
| `a` | add log lines to the day |
| `q` / `Esc` | quit |

Days that have entries are marked with `*`.

## AI reports and slides

```sh
worklog config set api_key YOUR_KEY          # stored in ~/.config/worklog/config.json (mode 600)
# or:  export WORKLOG_API_KEY=YOUR_KEY       # also reads ANTHROPIC_API_KEY / OPENAI_API_KEY

worklog report weekly                        # this week
worklog report monthly -p last               # last month
worklog report yearly  -p 2026 -o 2026.md    # a whole year

worklog ppt weekly                           # worklog-weekly-<period>.pptx in the current folder
worklog ppt monthly -p 2026-10 -o oct.pptx
worklog ppt yearly --no-ai                   # build slides straight from your logs, no API call
```

Periods: weekly `this | last | YYYY-Www | any date`, monthly `this | last | YYYY-MM`, yearly `this | last | YYYY`.

Yearly reports condense each month first, so large years still fit in one request.

### Providers

```sh
worklog config set provider anthropic        # default (model claude-sonnet-5-5)
worklog config set provider openai           # any OpenAI-compatible API
worklog config set base_url http://localhost:11434/v1   # e.g. a local Ollama server
worklog config set model <model-name>
worklog config show
```

**Privacy:** `report` and AI-built `ppt` send the log text for the chosen period to your AI provider.
Use `ppt --no-ai` to keep everything local.

## Where data lives

- Logs: `~/.local/share/worklog/logs/YYYY/YYYY-MM-DD.txt` (plain text, one entry per line)
- Reports: `~/.local/share/worklog/reports/`
- Config: `~/.config/worklog/config.json`

Back up or sync the `worklog` data folder with anything you like (git, Syncthing, rsync).

## Building the package

```sh
./build-deb.sh            # -> dist/worklog_0.1.0_all.deb  (needs only dpkg-deb)
```

Set your name first: `DEB_MAINTAINER="Jane Doe <jane@example.com>" ./build-deb.sh`
and edit `packaging/copyright` and `debian/*`.

## Publishing so anyone can `apt install worklog`

A `.deb` alone is not "in apt". Pick one:

1. **Launchpad PPA (easiest for Ubuntu users).** Users run
   `sudo add-apt-repository ppa:YOURNAME/worklog && sudo apt install worklog`.
   Uses the `debian/` folder: `dpkg-buildpackage -S`, sign, `dput ppa:YOURNAME/worklog ...`.
2. **Your own apt repository** (works for any Debian/Ubuntu). Host the `.deb` with
   `reprepro` or `aptly` on any static web host (GitHub Pages, S3, your server), sign the
   repo with a GPG key, and give users two commands: add your key + one `sources.list.d` line.
3. **Official Debian archive** (reaches every Debian/Ubuntu user by default, slowest):
   file an ITP bug and find a sponsor via mentors.debian.net.

## License

MIT
>>>>>>> 994d6f3 (feat: add interactive month calendar and CLI for worklog management)
