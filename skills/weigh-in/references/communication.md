# Public words: claims, comparisons and the law

Internal documents can say anything that is true and sourced. Public words need more: proof that holds up when the competitor reads them, and a frame that keeps you within comparative advertising law. This page is a working guide, not legal advice.

## 1. Every public claim has its proof

Keep a claims ledger in document 07: one row per claim you want to make.

| Claim | Proof required | Proof today, with level | Status | Owner |
|---|---|---|---|---|
| "Works with X in the background" | A recorded run on the build users have | Measured on a test app only | Not yet | Product |

- **Status** is one of: ready, needs proof, needs counsel, never.
- A claim moves to "ready" only when its proof exists at the level the claim implies, and your claims register (if you keep one) has cleared it.
- Run the drafts through the lint:

```bash
python3 scripts/claims_lint.py drafts/*.md --forbidden phrases.txt --competitor "Acme" --superlatives
```

It flags forbidden phrases (one per line in the file, `re:` for patterns), blockquote answers over 40 words, superlatives and absolutes, comparisons such as "unlike Acme", and lines that name a competitor next to a number without a date (versions, `file:line` citations and inline code do not count). Forbidden phrases and long answers fail the run; the rest are warnings unless you pass `--strict`. Wrap phrases you quote on purpose, as in a "What not to say" list, between `<!-- claims-lint: off -->` and `<!-- claims-lint: on -->`. It checks wording only; it cannot make a claim true.

## 2. What not to say: a fixed section

Document 05 and document 07 each have a "What not to say" section. It holds:

- false or unprovable statements about the competitor;
- unverified firsts and onlys: "the first", "the only", "the fastest";
- unmeasured numbers next to the competitor's name;
- quality judgments: "buggy", "slow", "insecure", "toy";
- any wording that presents your product as an imitation or replica of theirs: "clone", "copy", "the open-source <their product>";
- phrases your claims register forbids;
- confidential information the user shared at kickoff.

## 3. Concede in public

Where the competitor is ahead, say so, on the comparison page and in the FAQ. A comparison that concedes nothing reads as marketing and invites a challenge. "What they still do better" is a mandatory section of the comparison page.

## 4. Comparison FAQ

- One question per entry, phrased the way a user would search it.
- The answer within 40 words, plain, without forbidden phrases.
- Sources with dates under each answer.
- A condition: what must be true before the entry is published, for example "only after the signed build ships".

Template in [templates.md](templates.md).

## 5. The comparison page

In this order:

1. a title written like the search query ("X vs Y", "Y alternative for Z");
2. the author and the date the facts were checked;
3. one line on non-affiliation and trademarks ("X is a trademark of its owner; we are not affiliated");
4. a short answer: who should pick which;
5. a table with a source on every cell about the competitor;
6. "What they still do better", mandatory;
7. "Which one to choose", by use case;
8. the FAQ;
9. the sources, dated.

Recheck every fact before each update of the page, and change the "checked on" date only when you did.

## 6. The legal frame

Comparative advertising is lawful in the main markets when it is truthful, verifiable and fair. Before a public comparison ships, counsel reads it. The texts below were checked at the linked sources on 4 October 2026; laws change and vary by country.

**European Union.** [Directive 2006/114/EC](https://eur-lex.europa.eu/eli/dir/2006/114/oj) on misleading and comparative advertising, Article 4, allows comparative advertising when it:

- is not misleading;
- compares goods or services meeting the same needs or intended for the same purpose;
- objectively compares one or more material, relevant, verifiable and representative features, which may include price;
- does not discredit or denigrate the competitor's marks, trade names, goods, services, activities or circumstances;
- does not take unfair advantage of the reputation of a competitor's mark or name;
- does not present goods or services as imitations or replicas of goods or services bearing a protected mark or trade name;
- does not create confusion between the advertiser and a competitor.

For consumers, the Unfair Commercial Practices Directive 2005/29/EC also applies. Each member state implements both in its own law.

**United Kingdom.** [Regulation 4](https://www.legislation.gov.uk/uksi/2008/1276/regulation/4) of the Business Protection from Misleading Marketing Regulations 2008 sets similar conditions, and the CAP Code has its own rules on comparisons.

**United States.** Section 43(a) of the Lanham Act ([15 U.S.C. 1125(a)](https://www.law.cornell.edu/uscode/text/15/1125)) lets a competitor sue over false or misleading statements about your or their goods. The FTC's statement on comparative advertising ([16 CFR 14.15](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-14/section-14.15)) encourages truthful comparisons that name competitors, and its [Policy Statement Regarding Advertising Substantiation](https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation) (1984) expects a reasonable basis for claims before they are made. Competitors often challenge claims through the National Advertising Division of BBB National Programs.

**Trademarks.** Using a competitor's name to identify them in a fair comparison is generally allowed. Their logos, colors and visual style are not needed and add risk: do not use them.

**Everywhere:** keep the evidence for every claim, dated, for as long as the claim is public.

## 7. Positioning

- Build positioning on a principle of yours, never on a competitor's defect: defects get fixed.
- Positioning statements go through the technical review of claims your project uses. Ask at kickoff what it is and who does it.
- Settled communication decisions stay settled ([kickoff.md](kickoff.md), question 13).
