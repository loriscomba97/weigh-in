# Checklists

## At kickoff

- [ ] Read project instructions and memory, the register, earlier analyses, the claims register and your own site
- [ ] Wrote down today's date and the snapshot (commit and date) of every repository analyzed
- [ ] Listed every source of the competitor: main site, product sites, docs, repositories, release channels, registries
- [ ] Checked the versions of the key third-party components they ship against upstream
- [ ] Collected the real state of your product: license, signing, CI, telemetry, next release
- [ ] Tried the tools: web, public APIs and tokens, browser, publishing connector, helpers
- [ ] Asked the open questions in one message, each with a default
- [ ] Chose the variant, the tracks and the deep dives, and sent the kickoff agreement

## Per track

**Business, traction, market**

- [ ] Company, people, funding, marks, governance, with sources
- [ ] Pricing page captured the same day; price history from archives
- [ ] Traction measured with dates: stars and pace, issues and pull requests apart, downloads by type, registries, community
- [ ] Declared numbers quoted as declared, next to measurements
- [ ] Showcased partners checked against the code
- [ ] What changed since the baseline, if there is one

**Architecture and engineering**

- [ ] Snapshot recorded; size and growth at three or more dates; vendored and generated code excluded
- [ ] History: authors, bus factor, identities grouped, cadence, fixes, releases, hotspots, agent signals
- [ ] The map: processes, boundaries, ports, data, keys, updates, signing
- [ ] Every integration on their site checked in the code; the paid layer and its license
- [ ] Telemetry confirmed on the code path: default state, consent, payload, identity, host
- [ ] Security signals read in context; secrets masked
- [ ] Docs checked against code

**The technical core**

- [ ] The axes still describe your product; each cell has evidence and a level
- [ ] The headline capability traced step by step in the code
- [ ] Ideas to take, each with its license path; what not to copy, with the reason

**Licenses and dependencies**

- [ ] Every license file read in full where not standard; folders mapped
- [ ] License history and contribution terms (CLA or DCO); trademark policy
- [ ] Shipped versions of key components, with their licenses
- [ ] "Can we do this?" table, obligations, risks, questions for counsel

## Before delivery

- [ ] Every fact has a source and a date; every piece of reasoning is marked "(inference)"
- [ ] The decisive points were re-checked at the source and marked "verified"
- [ ] Numbers, dates and names match across documents; reconciliations are noted
- [ ] Every document has "0. In short" and "What I could not verify"
- [ ] The summary answers the ten questions
- [ ] "What not to say", the concessions and the uncomfortable truths are there
- [ ] Public drafts (FAQ, positioning lines) passed `scripts/claims_lint.py` and the forbidden phrases
- [ ] Decisions, actions and ideas are in the register, with sources
- [ ] No commit and no publication happened without approval
- [ ] Work files stayed in the scratch workspace

## After approval, when publishing

- [ ] Pages created first; structure as in [publishing.md](publishing.md), with the general summary in place of the decision maker's summary
- [ ] Converted, chunked at headings, uploaded in order
- [ ] Every page read back: start, joins, end, tables, links
- [ ] Page addresses saved in memory and in the register
