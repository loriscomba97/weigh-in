# Kickoff: context, checks, questions

No analysis starts without context. Work in this order:

1. read everything that already exists;
2. run the checks;
3. only then ask the user what is still open, in one message, each question with a proposed default.

The facts that change from one analysis to the next (the state of your product, decisions, dates, people) are never assumed from memory. They are collected here, every time.

## 1. Read before you ask

| Source | What it tells you |
|---|---|
| Project instructions and memory: agent instruction files, notes the user keeps | Working rules, recent decisions, preferences, who does what |
| The register of decisions, actions and ideas ([register.md](register.md)) | What is already decided and what is open |
| Earlier analyses, above all of the same competitor | The baseline for "What changed" and for corrections |
| Your claims register and list of forbidden phrases, if they exist | What you may say in public and what is blocked |
| What your own site says today about license, architecture, privacy and prices: FAQ, docs, pricing page | The public statements every comparison must agree with |
| Your own repository, read only: the main branch and the active ones, with the date of each branch's last commit | The real state of your product, not the one in memory |

Find out where these live at each kickoff. Do not assume last time's paths.

## 2. Kickoff checks

| Check | Why | How |
|---|---|---|
| Today's date | Every number in the analysis carries its date | The system clock. Write it in every header |
| Every source of the competitor: main site, product sites, docs, repositories, release channels, package registries | One secondary page never tells the whole story. When pages disagree, the main site prevails. Releases often live in a second repository too, such as an older mirror | Search; the repository's homepage field; the site footer; "edit this page" links in the docs; the organization's other repositories; the updater's feed in the code (electron-builder `publish`, Sparkle `SUFeedURL`, Tauri updater endpoints); `releases_elsewhere` in `scripts/github_traction.py` |
| The commit you analyze | The whole analysis refers to that snapshot, written at the top of every document | `scripts/snapshot.py` |
| The versions of the third-party components they really ship, and the latest upstream | A pinned version can hide a defect fixed upstream, and the reverse | `scripts/dependency_versions.py --check-latest --only <the components that matter>` |
| Whether an earlier analysis exists | You need "What changed" and the corrections | The register and the analyses folder, then the competitor's name across the workspace: `git ls-files \| grep -i <name>` and `git grep -il <name>`, because earlier work is often filed under another name |
| The real state of your product: license, signing, CI, telemetry, next release | They are the first rows of every comparison, and the most contestable | Your repository, read only, and your site. See [mirror.md](mirror.md) |
| The tools you have: web access, public APIs and tokens, a browser, a publishing connector, parallel helpers | They decide how you work and how much runs in parallel | Try each once. Note what is missing and which checks become "not verified" |

## 3. Questions for the user

Ask only what sections 1 and 2 did not answer. Give every question a default, so silence never blocks the work. Send them in one message.

**The goal**

1. Why now? A launch, a funding round, news, a customer's question. *Default: a routine check.*
2. Who will read it: only you, the technical team as well, or will it become a public comparison page? *Default: you and the team; nothing public.*
3. Full, quick or update? By when, and with which budget of time and requests? *Default: full for a direct open-source competitor, quick otherwise, update when an earlier analysis exists, quick update when both apply; no fixed budget, but bounded commands.*

**The competitor**

4. Which addresses: main site, product site, repositories, docs? *Default: the ones found in the checks.*
5. Is it open source? If not, what is public, and may a person test a build on a test machine? *Default: no hands-on test.*
6. What do you know that is not public, such as people who left, contacts or rumors? What of it must never be written? *Default: nothing non-public is written.*

**Your product today** (the facts that change most often)

7. The license of each part. Are any parts closed? *Default: what the license files in your repository say.*
8. Where does it run: only on the user's machine, in your cloud, in the customer's? *Default: what your docs say.*
9. Distribution: signing, notarization, the update channel. *Default: what your release pipeline shows.*
10. The next release: when, and which branches go in? *Default: unknown; the comparison uses the main branch.*
11. What is true today: capabilities, supported platforms and integrations, published prices or not? *Default: only what the shipped build and the site support.*
12. Who holds which role: decisions, technical lead, product, release and deploy? *Default: owners are left blank in the plan.*

**The rules of the moment**

13. Are there communication decisions not to reopen, such as homepage claims or forbidden phrases? *Default: the claims register, if there is one.*
14. Are there comparisons to exclude, for example with features of products you do not consider competitors? *Default: none.*
15. Are there strategic paths already excluded, for example an architecture you rejected? *Default: none.*
16. May competitors be named in your content, and on which conditions? *Default: named in internal documents only; public naming needs counsel.*

**The tools**

20. Is a GitHub token available? It raises the API limit and enables star history. *Default: no token; star pace from archived pages.*
21. May a person download the competitor's installer, without running it, so you can check its signature and notarization? *Default: no download.*

**The outputs**

17. Local only, or also a shared workspace such as Notion or a wiki? Where, and only after your approval? *Default: local only.*
18. Which language for the documents, and which for the working reports? *Default: documents in the language the user writes in, working reports in English.*
19. How much parallel work is acceptable, that is, how many helpers? *Default: four, one per standard track.*

## 4. The kickoff agreement

Before starting, send a short message with:

- the competitor and the snapshot (commit and date);
- the research tracks and any deep dives;
- the outputs and their destination;
- the timing;
- the defaults applied to unanswered questions.

If the user does not answer a non-blocking question, proceed with the default and write it in the document header. A template is in [templates.md](templates.md).

## When you cannot ask

In a one-shot or delegated run, do not wait. Apply the defaults above, and state every choice at the top of each document, so the reader knows what the analysis assumed.
