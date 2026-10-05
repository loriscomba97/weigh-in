# The process, phase by phase

Eight phases follow the kickoff ([kickoff.md](kickoff.md)). A quick analysis runs the same phases with less material; an update starts from the earlier analysis and writes what changed.

## Phase 1. Prepare

- **A scratch workspace** for clones, raw API responses, notes, working reports and drafts. Only what you deliver goes in the analysis folder.
- **The competitor's clone,** with full history, at today's commit: `scripts/snapshot.py <url> --dest <scratch>/<name>`. Record the commit and the date.
- **Your own snapshot:** the commit of your main branch and of the branches going into the next release, read only.
- **The measuring scripts,** run once at the start, so every track works from the same numbers: `loc_count.py`, `git_stats.py`, `license_scan.py`, `telemetry_scan.py`, `app_security_scan.py`, `dependency_versions.py`, `github_traction.py --save <scratch>/raw`. Save their JSON in the scratch folder and cite it.
- **The baseline:** the earlier analysis of the same competitor, if any, and the state of your product collected at kickoff.

## Phase 2. Research in parallel

Five standard tracks, each given to a helper with the same base brief ([templates.md](templates.md)):

| Track | Covers |
|---|---|
| Business, traction, market | Company and people; product and editions; measured traction; reception; market and positioning; showcased partners against real integrations; distribution and search; what changed |
| Architecture and engineering | Processes and boundaries; size and growth; data, keys, updates, signing; the product in the code; CI, tests, evaluations; cadence and people; agent-assisted development; the paid layer; telemetry and network contacts; security; quality and debt |
| The technical core against you | The layer where you collide, on your axes ([axes.md](axes.md)); the head-to-head; ideas to take; what not to copy |
| Licenses and dependencies | License map; clauses of non-standard licenses; license changes over time; contribution terms; trademarks; third-party components and shipped notices; what you may do with their code; obligations; risks; questions for counsel |
| Business model and pricing | The offer and its history; free and paid; open and closed, and the gate; integrations and partners; where they earn and convert; your model on the same rows ([business-model.md](business-model.md)) |

The full question list for each track is in [tracks.md](tracks.md).

**Deep dives, only when they pay off:**

- **an audit of your own product,** when your state changed a lot or is unclear;
- **platform by platform or framework by framework,** when the core of the competition is compatibility;
- **one key feature of the competitor,** when they launch something new;
- **models and perception,** when they rely on models with special licenses, costs or privacy effects;
- **the mechanisms,** when you need to understand how and why they do one thing;
- **security,** when trust is the battleground;
- **pricing and packaging for your own product,** when you are about to set or change prices: interviews, willingness to pay, packaging options;
- **go-to-market,** when distribution is the battleground: channels, search, launches, community.

**How many tracks:**

- five for a full analysis;
- up to eight for a main competitor on the day of their launch;
- one or two for a quick analysis.

Each helper writes one working report in the scratch folder, with every claim cited, and replies with a short summary and what it could not verify. If your agent cannot run helpers, run the tracks yourself, one after another, with the same brief.

## Phase 3. Verify

- **Re-check the decisive points of every report yourself:** versions, prices, licenses, telemetry, traction numbers, and everything that reaches the summary. Mark them "verified" only after that.
- **Reconcile numbers that disagree** between two reports. The definition or the date usually changed. Note the reconciliation in the appendix header.
- **Check strategy-changing claims twice, on different sources:** a product withdrawn, a license changed, a feature that "does not exist", a company that pivoted.
- **Read a sample of the cited lines.** A helper can cite the right file and the wrong line.
- **Move what you cannot verify** to "What I could not verify".

## Phase 4. Write

- **The order:**
  1. the documents built on the strongest reports;
  2. the comparison, the plan and the strategy;
  3. **the summary for the decision maker, last.**
- Follow the skeletons and the style in [deliverables.md](deliverables.md).
- **Coherence:** the same numbers, dates and names in every document; every cross-reference checked.
- **Write the documents yourself.** Helpers research; the author owns the argument.

## Phase 5. Deliver

- A short, critical message: the three things to know, the answers to the ten questions, links to the files.
- The summary also sent as a file, if your environment can send files.
- Close in the format the user's working rules ask for. If they keep a running list of open items, end with it ([register.md](register.md)).

## Phase 6. Review

- **The user's corrections apply to every document,** appendices included. Add a dated note at the top of each appendix that changed ("Update of <date>: ...").
- Superseded versions stay in the scratch workspace, never in the delivered folder.
- Corrections that will hold in the future become memory: working rules and stable facts, in whatever memory the project keeps.
- Deliver the revised set together, with a list of what changed.

## Phase 7. Publish

Only after the user's approval, and only where they say. For Notion and other workspaces, see [publishing.md](publishing.md). Public pages also need [communication.md](communication.md) and, for any comparison that names a competitor, counsel.

## Phase 8. Register and memory

- Decisions, actions and ideas go into the single register, each with its source ([register.md](register.md)).
- What to watch after the analysis becomes an action in the register. If the user asks, schedule a periodic check.
- Save a project memory for the analysis: where it lives, the facts that matter beyond the documents, the addresses of published pages.

## Variants

**Quick.** One or two tracks and one document, `00-quick-analysis.md`, with the sections in [deliverables.md](deliverables.md) (section 7). Pick the tracks that answer the question that triggered the analysis; when nothing is specific, take business and traction plus the technical core, and add the license and trust facts the scripts produce. Register entries as usual. When an earlier analysis exists and the user asks for something quick, run a **quick update**: the same document, plus a "What changed" table.

**Update.** Start from the earlier analysis. Re-run the scripts at the new snapshot and diff the numbers. Every document gets a "What changed" section (a table: item, before with date, now with date, why it matters) and a "Corrections to the earlier analysis" section. Update the register entries that the changes touch.

Look for what they removed, on purpose: additions announce themselves, removals do not. `scripts/removals.py commits <clone> <baseline commit> HEAD` lists the folders, files and documentation headings that disappeared since the commit the earlier analysis pinned, with renames and moves set apart. `scripts/removals.py pages <old capture> <new capture>` lists the lines gone from a page between two captures, with reworded lines (a changed price, a renamed plan) apart: compare the pricing, features, integrations, docs and changelog pages, using the captures of the earlier analysis or `scripts/wayback.py fetch --text` for its date. Each removal is a lead until you confirm it: a folder can move to another package, a heading can be reworded, a feature can live on behind a flag. A confirmed one gets its own "What changed" row.

**Several competitors at once.** Run the kickoff once, then one full or quick analysis per competitor with the same axes, so their rows line up in a final landscape table. Write the landscape last.
