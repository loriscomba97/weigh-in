# The register of decisions, actions and ideas

Analyses produce more than documents: decisions to take, things to do, ideas worth weighing. Keep them in one register for all analyses, so nothing is lost between them.

## 1. One file

- A single Markdown file, in the place the user chooses at kickoff (default: `analyses/REGISTER.md`).
- Three kinds of entry, each with its own code:

| Kind | Code | Holds |
|---|---|---|
| Decision | D-01, D-02... | A question for the decision maker, in one sentence, with the proposed default and the deadline if there is one |
| Action | A-01, A-02... | Something to do, with the owner and the date |
| Idea | I-01, I-02... | Something to weigh, with a rough effort and the expected gain |

- Codes never change and are never reused, so documents and messages can cite them.

## 2. Every entry cites its source

Use a short reference to the analysis and the item, for example `ACME-06 P3`: document 06 of the Acme analysis, item P3. An entry without a source cannot be checked later.

## 3. The layout

```markdown
# Register of decisions, actions and ideas

## 1. Open decisions
| Code | Decision | Default | Deadline | Source |
|---|---|---|---|---|

## 2. Actions
| Code | Action | Owner | Due | Status | Source |
|---|---|---|---|---|---|

## 3. Ideas
| Code | Idea | Effort | Gain | Source |
|---|---|---|---|---|

## 4. Closed
| Code | What | Closed on | Outcome |
|---|---|---|---|
```

- Closed entries move to the bottom with the date and the outcome: the decision taken, the action done or dropped, the idea adopted or parked.
- Group by theme inside each section when the register grows: product, technology, communication, legal, method.

## 4. The running list

If the user wants it, end every reply with a short "Open items" section drawn from the register: first the open decisions, then the nearest actions. Work them down a little at a time. Keep it short: codes, one line each, and the default for each decision.

## 5. After each analysis

- Add the new decisions, actions and ideas, each with its source.
- Turn what to watch (a competitor's release, a license change date, a price change) into actions with a date.
- Close the entries the analysis settled, with the date.
- Update the entries an update analysis changed, and note why.
