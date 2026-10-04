# Install weigh-in

weigh-in is one [Agent Skill](https://agentskills.io): a folder with a `SKILL.md`, references and scripts. It is written for agents that read Agent Skills and run shell commands, such as Claude Code and Codex.

## Requirements

- git.
- Python 3.9 or later for the scripts, with no packages to install. macOS ships a suitable `python3` with the command line tools.
- Network access for clones, public pages, the GitHub API and package registries.
- Optional: a `GITHUB_TOKEN` environment variable, which raises the GitHub API limit from 60 calls an hour and enables sampled star history. The scripts send it to `api.github.com` only and never print it.
- Optional: an agent that can run helpers in parallel, and a browser tool for pages that render in the browser.

## With the skills installer

Run this in the project where you want to use the skill:

```bash
npx skills add loriscomba97/weigh-in
```

Files go to `.agents/skills/`, with links for the agents you choose, such as `.claude/skills/` for Claude Code.

| Option | What it does |
|---|---|
| `-g` | Installs for your user, in `~/.agents/skills/` and `~/.claude/skills/`, instead of the project |
| `-a claude-code codex` | Selects the agents to install for |
| `-y` | Skips the questions |

The installer collects anonymous usage data. Set `DISABLE_TELEMETRY=1` to turn it off.

## Check and use the install

Run `npx skills list`, or ask your agent which skills are available. Then call the skill directly:

- **Claude Code:** `/weigh-in https://github.com/acme/acme`
- **Codex:** `$weigh-in https://github.com/acme/acme`, or `/skills` to select it.

You can also ask in plain words:

| Request | What the skill does |
|---|---|
| "Analyze Acme against our product and tell me what to decide." | A full analysis: kickoff, four tracks, eight documents, register entries |
| "Acme just launched X. What does it mean for us?" | A quick analysis focused on the new feature |
| "Update last month's Acme analysis." | An update: what changed, and corrections |
| "Can we reuse Acme's parser? Check the license." | The licenses track and the "can we do this?" table |
| "Draft a comparison FAQ against Acme." | Claims, proof, "what not to say" and the FAQ format |

## Where the analyses go

By default in `analyses/<competitor>-<YYYY-MM-DD>/` in the current project, untracked. Clones, raw API responses and drafts go to a scratch folder outside it. The agent asks at kickoff if you want another place, a shared workspace or another language.

## Update or remove

`npx skills update` updates installed skills. `npx skills remove weigh-in` removes this one.

## By hand

Copy [`skills/weigh-in/`](../skills/weigh-in) into your agent's skills folder. Keep the folder intact: its references and scripts are included.

| Agent | For one project | For your user |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.agents/skills/` | `~/.agents/skills/` |

## Run the scripts on their own

The scripts work without an agent. From the skill folder:

```bash
python3 scripts/snapshot.py https://github.com/acme/acme --dest work/acme
python3 scripts/git_stats.py work/acme
python3 scripts/github_traction.py acme/acme --save work/raw
```

Each prints JSON. Every script explains its options with `--help`. To try them without a real competitor, build the fictional one in [the example](example.md).
