# Research tracks: every question

Each track below lists the questions its helper answers. Not every question applies to every competitor: mark the ones that do not as "not applicable" with a reason, never skip them silently. Every answer carries its source and date, and every piece of reasoning is marked "(inference)".

## Track 1. Business, traction, market

**Company and people**

- The legal entity, its country and its founding date. Registries, the site's legal pages, the terms of service.
- Founders and key people, with their public background. Who left recently.
- Headcount: the team page, job posts, professional networks. Mark estimates as estimates.
- Funding: rounds, amounts, investors, dates. Press releases, filings, funding databases.
- Who owns the trademarks and the domains. Trademark databases, the trademark policy in the repository.
- Governance of the open-source project: company-controlled or foundation; maintainers who are employees; who can merge.

**Product**

- Product lines and editions: open source, hosted, enterprise, add-ons. What each includes.
- Platforms and system requirements.
- What is free and what is paid, and where the line is drawn in the code (cross-check with track 2).
- Roadmap signals: public roadmaps, milestone and label names in the issue tracker, changelogs, job posts, conference talks.

**Price list and revenue model**

- The pricing page of the main site, captured the same day: `scripts/capture_page.py`. Plans, prices, currencies, taxes, seats or usage, free tier limits, trials, "contact us" tiers.
- The price history: `scripts/wayback.py list <pricing url> --per month`, then fetch the snapshots around each change.
- How they really earn: subscriptions, usage, services, support, a marketplace cut, hardware, hosting, licensing to enterprises. License key checks in the code are evidence.
- Estimated economics, always marked "(inference)" with the calculation and the list prices used: cost per user, margin, burn.

**Traction** (methods and traps in [numbers.md](numbers.md))

- Stars, their history and pace; forks; watchers; contributors; open issues and open pull requests counted apart: `scripts/github_traction.py`.
- Release downloads by type: installers, update checks, packages. The running-copies estimate, with its formula.
- Package downloads, Homebrew installs, container pulls, extension installs, community members: `scripts/public_counts.py`.
- App store ratings and review counts, with the date.
- Web traffic and search interest from third-party tools, marked as estimates.
- Their declared numbers ("10,000 teams"), quoted as declared, next to your measurement.

**Reception**

- Launch threads and posts (developer forums, social sites, launch platforms), reviews, notable endorsements, press.
- Recurring praise and recurring complaints in issues, forums and reviews, quoted with links and dates.
- Churn signals: "moving away from" posts, migration guides others wrote.

**Market and positioning**

- The category they claim, their tagline and headline claims, the words they want to own.
- Who they name as competitors, and the comparison pages they publish.
- The target customer and use cases, from the site, the docs and the sales pages.
- The keywords they target: titles, descriptions, docs headings, blog topics.
- Showcased partners and integrations against the ones that exist in the code (track 2). A logo is not an integration.

**Distribution**

- Channels: repository, package registries, app stores, Homebrew, marketplaces, plugins for other tools, cloud marketplaces, resellers, enterprise sales.
- Search and docs: how they rank for the category's main queries (a sample, dated).
- Install friction: one-line install, signing and notarization, permissions asked and when, account required or not.
- Community: chat servers, forums, events, ambassadors, contributor programs.

**What changed** (update variant): each item above, before and now, with dates.

## Track 2. Architecture and engineering

Methods and scripts are in [code.md](code.md) and [trust.md](trust.md).

- **Processes and boundaries:** apps, services, daemons, helpers, extensions; the language of each part; how they talk (local HTTP, sockets, pipes, platform IPC); the ports they open; what runs with elevated rights; what talks to the network.
- **Size and growth:** source, test and generated lines at the snapshot and at two to four earlier dates; the largest files; where the code concentrates.
- **Data, keys, updates, signing:** where user data lives and whether it is encrypted; how API keys and tokens are stored; how the app updates and whether updates are signed and verified; code signing and notarization in the release pipeline.
- **The product in the code:** the data model; the engines, models or providers it supports and how it drives them; approvals and permissions; memory and state; schedules and automations; integrations, each one checked against the marketing list.
- **CI, tests, evaluations:** what runs on each pull request; test share and kinds; end-to-end suites; benchmarks and evaluations, with their method; release automation.
- **Cadence and people:** commits per week; authors and their shares; the bus factor; the share of fix commits; release gaps; one person with several identities; bots.
- **Agent-assisted development:** co-author trailers, assistant branches, agent instruction files. A lower bound, never a quality verdict.
- **The paid layer:** enterprise folders, license key checks, feature flags, cloud-only features, and the license that covers them.
- **Telemetry and network contacts:** SDKs, default state, consent, identity, hosts; the privacy policy against the code.
- **Security:** entitlements and hardening, update signing, local servers and their authentication, content security policy, committed secrets, the security contact.
- **Quality and debt:** hotspots; TODO, FIXME and HACK counts; very large files; open bug issues and their age; skipped or flaky tests; outdated dependencies.
- **Docs against code:** where the docs say one thing and the code does another; where they are honest about their limits, which is worth imitating.

## Track 3. The technical core against you

- **Name the layer** where you really collide. It is rarely the whole product.
- **The axes:** build or reuse them as [axes.md](axes.md) explains, and check at kickoff that they still describe your product.
- **For each axis:** their answer, with evidence and its level; your answer, with evidence and its level.
- **The head-to-head table:** where each side wins, by how much, and for how long (copyable in weeks, or durable).
- **How they achieve their headline capability,** step by step in the code, with `file:line`.
- **Ideas to take,** each with its path: as a dependency, copied with notices, or as an idea in a clean room ([licensing.md](licensing.md)).
- **What not to copy,** and why: license, an architecture that conflicts with yours, a principle you hold, a known defect.
- **Their likely next moves on this layer,** from the roadmap signals in track 1 (inference).

## Track 4. Licenses and dependencies

Methods are in [licensing.md](licensing.md).

- **The license map:** the root license, licenses per folder, SPDX headers, package manifests, mismatches between them: `scripts/license_scan.py`.
- **Non-standard clauses:** read the full text of every custom or source-available license. Field-of-use limits, competing-use bans, change dates, user thresholds.
- **License history:** the commits that changed license files, announcements, the old and new terms, and whether old releases keep the old license.
- **Contribution terms:** a CLA, which can let the company relicense, or a DCO, which does not.
- **Trademarks:** a trademark policy, rules for forks, registered marks.
- **Third-party components:** the important ones and their licenses; copyleft inside the shipped product; third-party notices shipped in the binaries; an SBOM if they publish one; pinned versions against upstream: `scripts/dependency_versions.py`.
- **Models and data:** the licenses of model weights and datasets they ship or download at run time.
- **The "can we do this?" table** for their code: dependency, copy, fork, hosted service, clean-room idea, name and logo.
- **Obligations** if you reuse anything, and the **risks:** relicensing, copyleft reaching your code, patent clauses, trademark.
- **Questions for counsel,** written so a lawyer can answer them.

## Deep dives

Run one only when it pays off, with the same brief and output rules.

| Deep dive | When | Questions |
|---|---|---|
| Audit of your own product | Your state changed a lot or is unclear | [mirror.md](mirror.md), all of it |
| Platform or framework by framework | Compatibility is the battleground | For each platform or framework: does it work, how, with which proof, at which evidence level ([axes.md](axes.md)) |
| One key feature | They launched something new | What it does, how it works in the code, what it costs, who it is for, what it means for you |
| Models and perception | They depend on models | Which models, how they are called, what data reaches them, cost per task (inference), licenses of the weights, privacy effects |
| The mechanisms | You need the how and why of one behavior | The code path step by step, the platform features it relies on, its limits, how robust it is |
| Security | Trust is the battleground | [trust.md](trust.md), all of it, plus their security history: advisories, CVEs, disclosed incidents |
| Pricing and packaging | You are setting prices | Their plans over time, what moves between tiers, discounts, the value metric, the reactions to price changes |
| Go-to-market | Distribution is the battleground | Channels, launches and their results, search positions, community programs, partnerships that exist in code or contracts |
