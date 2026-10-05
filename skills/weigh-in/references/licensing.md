# Licenses and what you may reuse

Licenses decide what you may take from a competitor: with notices, only as an idea, or never. This page is a working guide for the analysis, not legal advice. Confirm every reuse decision with counsel.

## 1. Map the licenses

```bash
python3 scripts/license_scan.py <repo>
```

The scan lists every LICENSE, COPYING, NOTICE, LICENSING and PATENTS file with the license family recognized from its text, SPDX headers by identifier and folder, the license each package manifest declares, lockfiles, the history of the top-level license files, contribution terms, and flags: copyleft, source-available or custom terms, more than one family, a missing root license.

Recognition is by key phrases. Then:

- **Read the full text** of every license that is not a well-known one, and of every license in a subfolder.
- **One repository, several licenses** is common: an open core under a permissive license, an `enterprise/` or `ee/` folder under a commercial one, a component under copyleft. Map each folder. How the paid layer is switched on, and what it sells, is track 5 ([business-model.md](business-model.md)).
- **Manifests can disagree** with the license files. The license file usually governs; note the mismatch.
- **Relicensing shows in history:** the commits that changed the license files, and the announcement. Note whether old releases keep the old license, which they usually do.
- **Third-party components** have their own licenses. `vendored_license_files` lists the license files in vendored folders (`third_party/`, `vendor/`), which the rest of the scan skips; `--include-vendored` scans them in full. For components installed by a package manager, find the shipped version with `scripts/dependency_versions.py` and read the license at that version.
- **Recognition starts from the title.** Some license texts name others: the MPL names the GPL family among its secondary licenses. The scan trusts the title on the first line first; when a file has no title, read it.
- **Models and datasets** they ship or download at run time have licenses too, often with use restrictions.

## 2. License families

| Family | Examples | In short |
|---|---|---|
| Permissive | MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, Zlib | Reuse almost freely, keeping the copyright and license notices. Apache-2.0 adds an explicit patent grant, the NOTICE file and a duty to mark changed files |
| Public-domain-like | 0BSD, Unlicense, CC0 | No conditions in practice; check the jurisdiction for CC0 fallbacks |
| Weak copyleft | MPL-2.0, LGPL-2.1, LGPL-3.0, EPL-2.0 | Changes to the covered files or library stay under the same license; the larger work can have another license. MPL works file by file; LGPL needs the library to stay replaceable |
| Strong copyleft | GPL-2.0, GPL-3.0 | If you distribute a work based on it, the whole work goes under the GPL with its source. GPL-2.0-only and Apache-2.0 are incompatible; GPL-3.0 and Apache-2.0 are compatible one way |
| Network copyleft | AGPL-3.0 | The GPL, plus: users who interact with a modified version over a network must be offered its source |
| Source-available | BSL 1.1, FSL, Elastic License 2.0, SSPL, Commons Clause, PolyForm | Readable, not open source. Each forbids some uses, usually a competing product or a hosted service. BSL and FSL convert to an open license after a set time |
| Custom or proprietary | "All rights reserved", enterprise licenses | No rights without a contract. Reading is allowed when the code is public; reuse is not |
| Documentation and media | CC BY, CC BY-SA, CC BY-NC, CC BY-ND | NC forbids commercial use, ND forbids derivatives, SA passes the license on |
| Fonts | SIL OFL 1.1 | Bundling allowed; selling the font alone is not; reserved font names restrict renamed forks |
| Model weights | Permissive licenses, responsible-AI licenses, vendor community licenses | Often add an acceptable-use policy or limits by size of user base. Read each one |

Source-available terms in more detail:

- **BSL 1.1 (Business Source License):** production use is limited by an "Additional Use Grant"; each version converts to a named open-source license on its change date, at most four years after release.
- **FSL (Functional Source License):** any use except a competing one; each version converts to Apache-2.0 or MIT two years after release.
- **Elastic License 2.0:** no offering the software as a managed service, no circumventing license keys, no removing notices.
- **SSPL:** like the AGPL, but offering the software as a service obliges you to release the source of the whole service stack.
- **Commons Clause:** a rider that forbids selling a product or service whose value comes substantially from the software.
- **PolyForm:** a family of plain-language licenses (Noncommercial, Small Business, Shield, Internal Use and others), each with its own limit.

## 3. Can we do this?

A first reading for the analysis. Every "yes" carries conditions; every row needs counsel before you act.

| What you want | Permissive | Weak copyleft | GPL | AGPL | Source-available | Custom |
|---|---|---|---|---|---|---|
| Use it as a dependency of your product | Yes, with notices | Yes, keeping its files or library under its license | Only if your distributed product can go under the GPL | As the GPL, plus the network source offer | Read the grant; usually no for a competing product | No, without a contract |
| Copy code into your codebase | Yes, with notices and changes marked | Yes; copied files keep their license | Only into code you distribute under the GPL | As the GPL, plus the network clause | Usually no for competing use | No |
| Fork it and distribute the fork | Yes | Yes | Yes, under the GPL | Yes, under the AGPL | Per terms; often not as a competing product | No |
| Offer it as a hosted service | Yes | Yes | Yes; the GPL has no network clause | Yes, offering the source of your changes to users | Often forbidden outright | No |
| Learn from it and rebuild it in a clean room | Yes | Yes | Yes | Yes | Usually yes: copyright covers expression, not ideas; check patents and terms | Ideas yes, but check terms of use and patents |
| Use their name or logo | Only to refer to them, within their trademark policy | Same | Same | Same | Same | Same |

## 4. Obligations when you reuse

- Keep the copyright notices and the license text.
- For Apache-2.0: carry the NOTICE file's contents, and mark the files you changed.
- Ship third-party notices with your binaries: an "open-source licenses" screen or file.
- For copyleft: the source offer, in the form the license requires.
- Record what you took, from where, at which commit, under which license. An SBOM makes this durable.

## 5. Clean room

When the license forbids taking code but the idea is worth having:

1. One person or agent session reads the competitor's code and writes a functional specification: what it does, inputs, outputs, behavior. No code, no identifiers, no structure copied.
2. A different person or a fresh agent session, without access to the competitor's code, implements from the specification only.
3. Keep the specification and a short log of who did what and when.

This is a practice that lowers risk, not a guarantee. Patents can cover ideas that copyright does not: for a core mechanism, ask counsel whether a patent search is worth it.

## 6. Contribution terms and relicensing risk

- **A CLA** (Contributor License Agreement) often grants the company broad rights, including relicensing. A company that owns all the rights can move future versions to a source-available license. Treat a CLA as a signal of that option.
- **A DCO** (Developer Certificate of Origin, the `Signed-off-by` line) certifies the contribution only; relicensing then needs every contributor's consent.
- **Trademarks:** a trademark policy usually lets forks exist but not under the original name.

## 7. Questions for counsel

Write them so a lawyer can answer each one with a yes, a no or a condition:

- May we use component X, under license Y at version Z, as a dependency of our product, distributed as we distribute it?
- May we copy file X into our codebase, and what notices and markings are needed?
- Does license X's restriction on "competing use" cover our product as described in one paragraph?
- Is our planned clean-room process adequate for feature X?
- May we name competitor X, and show its prices and limits, on a public comparison page in market Y?
- Does contribution agreement X let the company relicense, and what would that mean for us if we depend on it?

## 8. In the documents

- Document 04 holds the map, the clauses, the history, the "can we do this?" table, the obligations, the risks and the questions for counsel.
- Document 06 says, item by item, which path each idea takes: dependency, copy with notices, clean room, or not at all.
- Never write "we can use this" without the license, the version and the condition.
