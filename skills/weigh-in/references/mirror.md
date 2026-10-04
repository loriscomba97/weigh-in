# The mirror: your product under the same rules

A comparison that skips your own weak points cannot support a decision. Read your product with the same rigor, the same scripts and the same evidence levels as the competitor.

## 1. Read it the same way

- **Read only,** on the main branch and on the branches going into the next release: the scanners take `--at <branch>`, so you never need a checkout. Record the commits in the document header, as you do for the competitor.
- **Run the same scripts on your repository:**
  - `scripts/loc_count.py` and `scripts/git_stats.py`: size, growth, cadence, bus factor. Your own bus factor is often the most uncomfortable number in the analysis;
  - `scripts/telemetry_scan.py`: verifies or refutes any "no telemetry" claim you make;
  - `scripts/license_scan.py`: the licenses you really ship, per folder;
  - `scripts/app_security_scan.py`: the hardening you really have;
  - `scripts/dependency_versions.py --check-latest`: your own outdated components.
- **Use the same evidence levels** ([axes.md](axes.md)): measured on a real app, measured on a test app, reported, no evidence.

## 2. Every "ahead" row needs proof

- Verify every row where you lead in the code or in a recorded test, and say on which build and which machine it holds.
- A row at "No evidence" stays internal until someone proves it.
- If your lead depends on a branch that has not shipped, say so: the comparison is with the build users have.

## 3. Uncomfortable truths: a fixed section

The summary (document 00) and the comparison (document 05) always have a section of uncomfortable truths about you. Typical areas:

- **License:** parts that are closed, unclear or about to change; a missing license file.
- **Signing and distribution:** unsigned or unnotarized builds, no update signature, permissions asked too early.
- **CI and tests:** no CI, no end-to-end tests, tests that do not run on pull requests.
- **Validation:** claims measured only on your own test app, never on the real software customers use.
- **Professional workflows:** claimed, not recorded.
- **Incidents:** outages, data issues, security reports, and how they were handled.
- **Knowledge concentration:** one person holds most of the code or of the release process.
- **Claims under review:** statements on your site that your claims register has not cleared.

## 4. Your site against your claims register

- List what your site says today about license, architecture, privacy, prices and capabilities, captured the same day.
- Check each statement against your claims register, if you keep one. Claims still under review never enter a public comparison.
- Note every statement the code contradicts. Fix the site or the code before you compare in public.

## 5. Never exaggerate

- What the competitor has and you lack (memory, automations, more platforms, a larger community) gets written, in full.
- Do not count a feature that is planned, partial or behind a flag as shipped.
- Do not compare your next release with their current one unless you label it.
- When you are unsure whether you lead, say "comparable" and explain why.
