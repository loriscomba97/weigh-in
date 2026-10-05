# Changelog

## 0.2.0 (5 October 2026)

- **Business model and pricing, a fifth standard track and an eighth document.** What the competitor gives away and what it charges for, and why each paywall sits where it does; what is open and what is closed, and how the paid layer is switched on in the code; integrations and partner placements; where they earn and where a free user becomes a customer; and your own model on the same rows, with the levers your license and architecture leave you. The method is in `references/business-model.md`; lens 6, the kickoff, the mirror, the templates, the checklists and the pitfalls follow.
- **A new script, `monetization_scan.py`.** `code` finds the paid layer in a codebase: license keys and entitlement checks, plan gates, in-app offers and prices, billing and licensing SDKs, hosted services the vendor runs, and folders with a license of their own. `page` reads captured pricing, cloud, enterprise and partner pages: prices with currency and unit, free-tier markers, calls to action, allowances, billing terms, add-ons and "contact us" tiers. Signatures live in `monetization_signatures.json`.
- **The example shows it.** `make_acme.py --raw` also saves a fictional pricing page, and `docs/example.md` reads the business model of Acme Notes.
- **Sixteen scripts and 70 tests,** on Python 3.9 and 3.14.

## 0.1.1 (5 October 2026)

- **What they removed.** A new script, `removals.py`, lists what disappeared between two snapshots. Between two commits: the folders that are gone (moves set apart, with where the files went), the deleted files by kind, and the headings that left README and docs files. Between two captures of a page: the lines that are gone, with reworded lines, such as a changed price, set apart. The update variant now looks for removals on purpose, and confirmed ones get their own rows in "What changed". The idea came from a reply to the launch article.
- **Fifteen scripts and 65 tests,** with five for the new script, on Python 3.9 and 3.14.

## 0.1.0 (4 October 2026)

First public release.

- **One skill, `weigh-in`.** A kickoff with checks and questions that carry defaults, eight phases, four research tracks with deep dives, eleven lenses, comparison axes with example sets by product category, and two evidence scales.
- **Eighteen references.** Kickoff, process, tracks, lenses, axes, code, trust, numbers, licensing, the mirror, closed-source competitors, deliverables, public words and comparative advertising law, the register, publishing, pitfalls, checklists and templates.
- **Fourteen scripts.** Python 3.9 or later, standard library only. Eleven read repositories, history, licenses, telemetry, app hardening, dependency versions, GitHub traction, registry and community counts, and web pages, and print JSON; two convert and split documents for Notion; one checks the wording of public copy.
- **Repository tooling.** A validator for the Agent Skills format and the house style, a public-safety scan for commits and pushes, and CI on Python 3.9 and 3.14.
- **An example you can run in a minute.** `docs/example/make_acme.py` builds Acme Notes, a fictional competitor with planted problems, and `docs/example.md` shows what the scripts find and the analysis they lead to.
- **Tested end to end before release.** An agent ran the skill on a real open-source project, blind to an earlier analysis of it. The problems it found (in dates, identities, release windows, license recognition, archived pages, dependency coverage and the quick variant) are fixed, and each one has a regression test.
- **Tests.** Throwaway git repositories, fixtures and saved API responses; no network. The example's numbers are tested too.
