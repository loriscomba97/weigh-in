# Contributing

Useful contributions include signatures for SDKs, assistants and payment or licensing providers the scripts miss, reproducible false alarms, rules for new release file types, license phrases, and mistakes worth adding to the pitfalls. Include a small example that shows the issue: a file, a repository layout, an API response.

## How the repository is built

| Folder | What it holds |
|---|---|
| `skills/weigh-in/` | The installable skill: `SKILL.md`, `references/` and `scripts/` |
| `skills/weigh-in/scripts/` | Python scripts, standard library only, and their data files |
| `tests/` | Unit tests with throwaway git repositories and saved API responses |
| `scripts/` | Repository tooling: the skill validator and the public-safety scan |
| `docs/` | Installation, and the example with `docs/example/make_acme.py`, which builds a fictional competitor |

## Before you open a pull request

Run these from the repository root:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
python3 scripts/check_public_safety.py
```

The validator checks the skill against the Agent Skills format, compiles every script, checks that each one is documented and named in the skill, and enforces the house style. The safety scan looks for credentials, keys and email addresses. A passing scan does not replace reading your diff for private information.

- **Test script changes.** Add or extend a test in `tests/`. Tests never touch the network: test parsers directly, and network paths through saved responses (`--offline`).
- **Keep false alarms reproducible.** Add the case that triggered one to a test, so it stays fixed.
- **Keep outputs stable.** Agents and documents read the JSON keys. Add keys; rename or remove one only with a changelog entry.

## Adding a signature

- **Telemetry SDKs:** add an entry to `telemetry_signatures.json` with the name, kind, import or package patterns, keywords and hosts. Prefer patterns with word boundaries; "rollbar" must not match "scrollbar".
- **Assistants:** add an entry to `ai_signals.json` with a label, patterns and an example co-author line that uses `noreply@example.com`. A test checks that every example matches its own label.
- **License phrases:** add the key phrases that identify the license text, not its name alone.

## Writing references

- Plain US English, short sentences with active verbs, no long dashes.
- Rules that come from a law or a vendor name their source; the rest are the method's own rules.
- Every example uses neutral names (Acme, example.com) and no real competitor.

## Propose a new check

Open an issue with:

1. The question the check answers, and why it matters for a decision.
2. Where the evidence comes from: code, history, a public API, a page.
3. A small example where it fires, and one where it must not.

Follow [SECURITY.md](SECURITY.md) for vulnerabilities rather than opening a public issue.

## Maintainers

Enable the hooks with `git config core.hooksPath .githooks`. They require GitHub noreply commit identities and run the safety scan before commits and pushes, including the maintainer's private denylist, which lives outside the repository.
