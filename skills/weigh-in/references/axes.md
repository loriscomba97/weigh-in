# Comparison axes and evidence levels

An axis is a question that both products must answer, with evidence. The axes turn "who is better" into a table a decision maker can read row by row. They belong to your product, not to the competitor: a good set describes the layer where you really collide.

## Build your axes

1. **Start from the customer's need** ([lenses.md](lenses.md), lens 1), not from your feature list.
2. **Name the layer where you collide.** Two products in the same category often compete on one layer only.
3. **Write 8 to 12 axes as questions** that any product in the category can answer. "Where does the work run?" is an axis; "Has feature X" is not.
4. **Include the axes where they win.** A set built to make you look good is useless for deciding.
5. **Give every cell an evidence level** (below). A claim without a level is a guess.
6. **Check the axes at every kickoff.** Products change; an axis that no longer describes your product misleads the whole analysis. Update the set, and note the change in the register.
7. **Keep the set stable across competitors,** so their rows line up in one landscape table.

## Axes that fit almost any product

| Axis | The question |
|---|---|
| Problem and user | Which job does it do, for whom, and how well does it fit that user's day? |
| Where it runs | On the user's machine, in the vendor's cloud, in the customer's cloud, or a mix? |
| What the user gives up | Attention, control, data, time to set up, lock-in? |
| Platforms and integrations | Which systems, tools and formats does it support, and with which proof? |
| Data and privacy | What leaves the user's machine, to whom, and can it be turned off? |
| Openness | The license of each part, contribution terms, trademarks |
| Price and packaging | What is free, what is paid, the value metric, the total cost for a typical customer |
| Distribution and install | Channels, signing, permissions asked and when, account required |
| Reliability and verification | How does the product know it did the right thing, and how does the user? |
| Extensibility | APIs, plugins, automation, self-hosting |
| Support and community | Docs, response times, community size and health |
| Security posture | Hardening, update signing, disclosure policy, history of incidents |

## Example sets by category

Use them as starting points. Replace, merge or drop rows until the set describes your product.

**Agents that operate software for a user** (computer use, desktop automation, RPA)

| Axis | The question |
|---|---|
| Where the agent works | On a computer elsewhere, on the user's own desktop, or on a screen of its own on the same machine? |
| What the user undergoes | Does the agent take the focus, the cursor, the windows, the app switching? Who wins when both act at once? |
| Framework by framework | What works, and with which proof, for each UI technology: native toolkits, web engines, cross-platform frameworks, games and GPU canvases, professional apps, menus, file dialogs, text and input methods |
| Perception | What reaches the model: text, images or both? At what cost, and with which privacy risk? |
| Verification | Does the agent know whether its action took effect? |
| Parallelism | How many agents at once, and where? |
| Approvals and rules | Who decides what the agent may do, and where does the rule live? |
| Privacy | Telemetry, accounts, relays, data that leaves the machine |
| Openness | The license of each part, contributions, trademarks |
| Platforms and distribution | Supported systems, signing, permissions asked and when |
| Professional apps | Workflows tested and recorded, not only claimed |
| Learning and memory | Memory, learning from the user, demonstrations |

**Developer tools, CLIs and libraries**

Language and runtime support; install footprint and dependencies; API surface and stability (versioning, breaking changes); performance, with reproducible benchmarks; docs quality; ecosystem and plugins; governance (company or foundation); release cadence; issue response time; security process and advisories; adoption (downloads, dependents).

**SaaS and web apps**

Core jobs and their depth; pricing and packaging (free tier, seats, usage); data residency and compliance (certifications, data processing agreement); integrations and API; onboarding and time to value; performance; mobile; admin, roles and permissions; uptime history from the status page; support terms.

**Mobile and consumer apps**

Store ratings and review counts by country; privacy labels against behavior; permissions asked; offline use; parity across platforms; monetization (ads, subscriptions, purchases); onboarding; accessibility; app size; update cadence.

**AI models, APIs and agent platforms**

Access (open weights or API only); the license of the weights; context and limits; price per unit of work; latency; evaluation results with their source and conditions; tool use; data retention and training on customer data; deployment options (local, private cloud); rate limits; safety features.

**Creative and professional media software**

Formats and codecs; plugin formats and host support; latency and real-time behavior; hardware requirements; collaboration; licensing model (perpetual, subscription, offline activation); integration with the rest of the professional toolchain; file compatibility across versions.

## Evidence levels

Every cell of a comparison table carries its level. Declare the scale once, in the document header.

**For the competitor**

| Level | Meaning |
|---|---|
| Observed | Seen by you in a recorded test (closed-source variant, with approval) |
| Test matrix | A test matrix in their repository covers it, with test apps or fixtures |
| End-to-end test | An end-to-end test in their repository exercises it |
| Code or docs only | The code implements it or the docs describe it; nothing shows it working |
| Claim | Their marketing says so; nothing else does |

**For your product**

| Level | Meaning |
|---|---|
| Measured on a real app | Measured on the real software a customer uses, on a named build and machine |
| Measured on a test app | Measured on a test app of your own |
| Reported | Stated in a commit, a design decision or an issue; not measured |
| No evidence | Believed, not shown |

A row where you lead at "No evidence" is a row to prove before anyone says it in public ([mirror.md](mirror.md)).
