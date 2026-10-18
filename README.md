# Matt Pocock Skills for Agent Zero

Agent Zero plugin that installs [mattpocock/skills](https://github.com/mattpocock/skills)
— *Skills for Real Engineers* — into your Agent Zero skill library, and registers a
slash command for every skill.

## What you get

| | |
|---|---|
| **25 skills** | Engineering (`tdd`, `code-review`, `diagnosing-bugs`, `to-spec`, `to-tickets`, `wayfinder`, `wizard`, …) and productivity (`grilling`, `teach`, `handoff`, …) |
| **25 slash commands** | Same names as upstream: `/tdd`, `/to-spec`, `/grilling`, `/handoff`, … |
| **Zero-maintenance updates** | Upstream changes arrive on the next plugin update — no manual sync |

Two upstream skills are intentionally excluded: `setup-matt-pocock-skills`
(installs a Claude Code harness that does not exist here) and `ask-matt`
(points at external paid content).

## Install

Install from this repository's URL via **Plugins → Install from Git**. The
installer clones this repo, then runs the plugin's `install()` hook, which:

1. `git clone --depth 1` of upstream at the ref in `upstream.yaml`
2. verifies the clone contains usable skills (refuses to swap otherwise)
3. atomically swaps it into the plugin's `vendor/` cache
4. copies each skill into `/a0/usr/skills/`, tagged with an ownership marker
5. regenerates the matching slash commands in `/a0/usr/plugins/_commands/commands/`
6. records the resolved upstream commit in `upstream.yaml`

**Requirements:** network access to GitHub during install and update, plus `git`
(already present in Agent Zero).

## Updates

Click **Update** on the plugin. The framework pulls this repository and then
re-runs `install()`, which re-fetches upstream and re-syncs everything. If
upstream itself has not changed, you get the same skills with a fresh commit
record. There is nothing to bump by hand.

To follow a different ref (e.g. a tag) or a fork, edit `upstream.yaml`:

```yaml
repo: https://github.com/mattpocock/skills.git
ref: main
```

## Failure behaviour

Nothing is deleted until a new clone has been fetched and verified. If the
fetch fails and a previous cache exists, that cache is reused and the recorded
`resolved_commit` is left at the last known-good value. If there is no cache
either, the install fails loudly rather than leaving you with missing skills.

Your own skills are never touched: a skill directory without a
`.mattpocock_skills.json` marker is treated as user-owned and skipped.

## Uninstall

Removes exactly what it created — the 25 skills (by marker), the 25 slash
commands (by marker), and the `vendor/` cache. Skills of yours that happen to
share a name are left alone.

## Files

| File | Purpose |
|---|---|
| `plugin.yaml` | Manifest |
| `hooks.py` | `install()` / `pre_update()` / `uninstall()` lifecycle |
| `helpers/upstream.py` | Fetch, verify, swap, sync, remove |
| `helpers/commands_sync.py` | Slash-command generation and removal |
| `upstream.yaml` | Which repo/ref to follow, and the last resolved commit |

## License

Plugin code: MIT (see `LICENSE`). The skills fetched at install time are
MIT © Matt Pocock; their notice is preserved in `LICENSE`.