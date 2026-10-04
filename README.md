# weigh-in

**Put your product and your rival on the same scale.**

weigh-in is an [Agent Skill](https://agentskills.io) for competitor analysis, for agents that can run shell commands. Point it at a competitor, ideally an open-source one. It guides your agent through a kickoff, four research tracks and a set of documents that end with decisions you can defend. At a boxing weigh-in both fighters step on the same scale: weigh-in measures your own product with the same scripts and the same rules.

[Example](docs/example.md) · [Get started](#get-started) · [How it works](#how-it-works) · [Install options](docs/install.md) · [Issues](https://github.com/loriscomba97/weigh-in/issues)

[![CI](https://github.com/loriscomba97/weigh-in/actions/workflows/ci.yml/badge.svg)](https://github.com/loriscomba97/weigh-in/actions/workflows/ci.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## What you get

- **A summary for the decision maker** that answers ten questions, from "who are they really?" to "which decisions are needed now?"
- **Seven documents:** business, architecture, the technical core, licenses, your product side by side, a technical plan, strategy.
- **A register** of decisions, actions and ideas, each with its source and a proposed default.
- **Public words you can defend:** a claims ledger, a "what not to say" list, FAQ answers within 40 words and a comparison page structure.

## See it in action

The [example](docs/example.md) runs the scripts on Acme Notes, a fictional competitor built with planted problems, and shows the analysis they lead to. In about a minute, with no network or accounts, they find a README that promises "No tracking, ever" next to analytics that start at launch, an open core in three licenses, risky Electron settings and downloads that are 97% update checks.

## Get started

Use an agent that supports Agent Skills and runs shell commands, such as Claude Code or Codex. The scripts need git and Python 3.9 or later, with no packages.

```bash
npx skills add loriscomba97/weigh-in
```

Then ask your agent:

```text
Analyze https://github.com/acme/acme against our product and tell me what to decide.
```

The agent reads what you already have, runs the kickoff checks and asks its open questions once, each with a default. Nothing is committed or published without your yes. See [install options](docs/install.md) for agents and scopes.

## How it works

Three principles run through every step:

1. **Every fact has a source and a date.** Code facts cite `file:line` at a pinned commit; web facts cite the URL and the day it was read; reasoning is marked "(inference)".
2. **The mirror.** Your product is read with the same scripts and the same evidence levels as the competitor, and every analysis has a section of uncomfortable truths about you.
3. **Read only.** The agent never installs or runs the competitor's software, creates no accounts and never writes to a repository it analyzes.

Fourteen Python scripts collect the evidence and print JSON:

| Script | What it measures |
|---|---|
| `snapshot`, `loc_count`, `git_stats` | The pinned commit, size and growth, authors and bus factor, cadence, fixes, releases, hotspots, signs of agent-assisted development |
| `dependency_versions` | The versions they ship against the latest upstream |
| `license_scan` | Licenses per folder, SPDX headers, relicensing history, CLA or DCO |
| `telemetry_scan`, `app_security_scan` | Analytics SDKs, opt-out switches, external hosts, entitlements, Electron and Tauri settings, committed secrets |
| `github_traction`, `public_counts` | Stars and their pace, issues and pull requests apart, release downloads decoded, registry and community counts |
| `capture_page`, `wayback` | Dated copies of pages, and how they looked before |
| `claims_lint`, `md_to_notion`, `chunk_markdown` | Wording checks for public copy, and publishing to Notion |

A script finds signals. The agent confirms each one in the code or at the source before it becomes a finding.

## What it checks

Four research tracks (business and traction; architecture and engineering; the technical core against you; licenses and dependencies) and eleven lenses, from "what they own and what they integrate" to "if they..." scenarios. Comparison axes come with example sets for several product categories. Closed-source competitors get a variant built on public sources, with an evidence level on every fact.

## Limits

- **Read only.** Testing a closed product by hand needs your approval and a test machine.
- **Signals are not findings.** Keyword matches and download counts need reading in context.
- **Estimates stay estimates,** labeled and with their formula.
- **Not legal advice.** License readings and advertising rules are a starting point for counsel.
- **Rate limits.** The GitHub API allows 60 calls an hour without a token; sampled star history needs `GITHUB_TOKEN`.

## License and contributing

[MIT](LICENSE) © Loris Comba. Report false alarms, missing signatures or outdated rules through [CONTRIBUTING.md](CONTRIBUTING.md). Follow [SECURITY.md](SECURITY.md) to report vulnerabilities privately.
