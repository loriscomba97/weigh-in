# The documents

## 1. The folder

- Default name: `analyses/<competitor>-<YYYY-MM-DD>/`, wherever the user keeps analyses. It stays untracked unless the user decides otherwise.
- Inside: the numbered documents, and `appendices/` with the working reports of the tracks (A, B, C...).
- Nothing else: clones, raw API responses, drafts and superseded versions stay in the scratch workspace.

```text
analyses/acme-2026-10-04/
  00-summary.md
  01-company-product-business.md
  02-architecture-and-stack.md
  03-technical-core.md
  04-licenses-and-dependencies.md
  05-side-by-side.md
  06-technical-plan.md
  07-strategy-and-moves.md
  appendices/
    A-architecture.md
    B-technical-core.md
    C-licenses.md
    D-business-and-market.md
```

Deep dives become extra documents numbered after 03; renumber the rest. The summary is always 00.

## 2. The skeleton of every document

1. **A numbered, plain title.**
2. **The header:** date; audience; basis (the snapshot of each repository with commit and date, the sources, the state of your product used); method (read only, what was not done, what you re-checked yourself); the evidence scale if the document compares; the pointer to the appendix with the detail.
3. **"0. In short":** 5 to 10 points, the ones needed to decide.
4. **The sections** of the document.
5. **"What I could not verify"** at the end: each item with the reason and what would settle it.

Templates for the header and for the appendix note are in [templates.md](templates.md).

## 3. The standard set

| # | Document | Holds |
|---|---|---|
| 00 | **Summary for the decision maker** | Readable in five minutes. The answer in three lines; who they are, in numbers; their technology and where it comes from; licenses; where they beat you and where you beat them; uncomfortable truths about you; what to do before the next deadline, in the weeks after and later; decisions, each with a default; where to read the rest. It answers the ten questions in SKILL.md |
| 01 | **Company, product, business** | Company and people; public numbers; product and editions; price list and revenue model; measured traction; reception; market and positioning; what changed and corrections to the earlier analysis |
| 02 | **Architecture and stack** | The map; size and growth; data, keys, updates, signing; the product in the code; how they work (CI, tests, cadence, people, agent-assisted development); the paid layer; telemetry; security; quality; strengths and weaknesses against you |
| 03 | **The technical core** | The layer where you collide, on your axes; the head-to-head with evidence levels; how they achieve their headline capability; ideas to take; what not to copy |
| 04 | **Licenses and dependencies** | The map; clauses of non-standard licenses; license changes; contribution terms; third-party components; the "can we do this?" table; obligations; positions compared; risks; questions for counsel |
| 05 | **Your product side by side** | The answers to the same need; technology and business row by row; platform or framework by framework when it matters; the balance; what not to say; uncomfortable truths; scenarios |
| 06 | **Technical plan** | The principle; work packages before the deadline, at 30 days, at 90 days and later, each with owner and effort; what to take, item by item, with its license path; what not to copy; quick experiments, each with its success criterion |
| 07 | **Strategy and moves** | The picture in five sentences; positioning; what to say and with which proof; the FAQ; the comparison page; coexistence; pricing; what to watch; risks; decisions |

## 4. The appendices

- They are the working reports of the tracks, with every `file:line` and URL citation.
- Each opens with a note, in the documents' language, that holds:
  - what the report is, and the snapshot;
  - the user's constraints valid for the analysis;
  - number reconciliations;
  - later updates, each with its date.
- When a document and an appendix disagree, the document prevails. Say so in the note.

## 5. Language

- Documents in the language the user chose at kickoff; working reports in English unless the team reads another language better. Record the choice in the headers.
- Keep product names, file names, commands and quotes in their original language.

## 6. Style

- **Plain language:** short sentences, one idea per sentence. Explain each technical term the first time it appears.
- **Form:** bold for the key sentences, numbered lists for sequences, tables for comparisons.
- **Numbers:** always with their date; thousands separators and decimal marks as the document's language writes them; currencies written out in the text.
- **No value judgments** about competitors: facts, sources and declared inferences.
- **For the decision maker:** what it means, what changes for us, what to decide. Technical detail goes to the appendices.
- **Citations:** `file:line` at the snapshot for code; URL and access date for the web; who and when for people.
- **Reliability marks:** "(inference)" on reasoning, "verified" on points re-checked at the source.

## 7. The quick variant

One document, `00-quick-analysis.md`, and no appendices: working data stays in the scratch folder. Same header and rules, plus a line naming the tracks you ran. The sections:

1. **In short:** 5 to 10 points.
2. **Who they are:** company, people, size, pace, traction, with dates.
3. **What they do and for whom:** promise, how it works, business model, trust facts.
4. **License:** the reuse table for the parts that matter.
5. **Where they stand against you:** a head-to-head of 6 to 10 rows with evidence levels, their strengths, your possible leads, uncomfortable truths about you, "if they..." scenarios and what not to say.
6. **What to do:** decisions with defaults, actions before the next deadline and after, and the ten questions in one line each.
7. **What I could not verify.**

## 8. The update variant

Every document adds two sections after "0. In short":

- **What changed:** a table with the item, the value before (with date), the value now (with date), and why it matters.
- **Corrections to the earlier analysis:** what was wrong or is no longer true, and why.
