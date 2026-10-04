# Numbers without being fooled

Shop-window numbers are easy to collect and easy to misread. For each number, say what it measures, what it does not, its source and its date. Quote the competitor's declared numbers as declared, next to your measurement.

## 1. GitHub

```bash
python3 scripts/github_traction.py owner/repo --save <scratch>/raw
python3 scripts/github_traction.py owner/repo --check-interval-hours 4 --star-history 12
python3 scripts/github_traction.py owner/repo --offline <scratch>/raw     # re-read a saved run
```

- **Stars** measure attention, not use. Their pace matters more than their total: a launch spike and a steady climb are different businesses. `--star-history N` samples N pages of the stargazer list to date star milestones and compute stars per day between them. GitHub lists stargazers to signed-in callers only, so it needs `GITHUB_TOKEN`. Without it, date the counts that archived pages show: the repository page, or the rounded count many projects display on their own site (`scripts/wayback.py`).
- **Watchers:** the real count is `subscribers_count`. The API field called `watchers_count` repeats the stars. The script reports the real one.
- **Forks** include one-click forks that never change anything. Active forks, with commits ahead, are a better signal.
- **Issues and pull requests:** the repository's `open_issues_count` adds the two together. The script counts them apart through the search API.
- **Contributors:** GitHub lists linked accounts, not people. One person can be several accounts, and commits with unlinked emails are missing. Cross-check with `scripts/git_stats.py`.
- **Release downloads** are lifetime totals per file, bots and retries included. Classify them by file type, as the script does:
  - **installers** are first installs. A stable file name (`App-setup.exe`) is the cleanest count of new installs; a name with the version in it can also be fetched by an updater;
  - **update checks** (`latest-mac.yml`, `appcast.xml`, `latest.json`) are downloaded by running copies, often at launch and then on a timer. They measure activity, not people;
  - **update deltas, checksums and signatures** follow installs and updates;
  - **archives** on macOS are often update payloads.
- **Running copies at once:** update checks per day multiplied by the check interval in hours, divided by 24. Read the interval from the product's code. It is an estimate: say so wherever you quote it, and give the formula. Two biases to name: an app that also checks at every launch adds checks for short sessions, which pushes the estimate up; copies that never update are missed, which pushes it down. When one repository releases several products (desktop, mobile, helpers), keep to the releases that carry the desktop update files, as the script does.
- **Mirrored releases:** when the same tag is published in two repositories, count it once (`--releases-repo` merges by tag).
- **Releases elsewhere:** `releases_elsewhere` lists the owner's other public repositories whose names suggest releases, and warns when the first release read comes long after the repository was created. Older versions often live in such a repository; add it with `--releases-repo`, or your totals will be too low.
- **Mobile and desktop:** release windows count only releases that carry update-check files, so a mobile-only release in between does not cut a desktop window short.
- **The rate limit:** 60 calls an hour without a token. Set `GITHUB_TOKEN` in the environment; the script sends it to the API only and never prints it.

## 2. Registries and communities

```bash
python3 scripts/public_counts.py --npm <package> --pypi <package> --crate <crate>
python3 scripts/public_counts.py --brew <formula> --cask <token> --docker <namespace/repo>
python3 scripts/public_counts.py --open-vsx <namespace/name> --discord <invite code or URL> --save <scratch>/raw
```

| Source | What it counts | What it does not |
|---|---|---|
| npm downloads | Package fetches in the last day, week, month | People. CI runs, mirrors and caches inflate it; one install of a big app can pull a package many times |
| PyPI downloads (pypistats.org) | Package fetches, as that service reports them | People, for the same reasons |
| crates.io | All-time and last-90-days downloads | People; build systems fetch crates on every clean build |
| Homebrew | Installs in the last 30, 90 and 365 days | Users who turned Homebrew analytics off |
| Docker Hub | All-time pulls | People or deployments; automated pulls dominate |
| Open VSX | All-time downloads of an editor extension | Active users. The other main extension marketplace shows installs on its listing page |
| Discord invite | Approximate members and members online | Engaged users. Online is one moment; check it at the same hour on several days |

Compare like with like: the same source, the same period, the same date. For npm, PyPI and crates.io the output carries the repository each package declares: check that it is the competitor's before you quote its numbers.

## 3. Other public signals

- **App stores:** rating, number of ratings and reviews, by country, with the date. Read the most recent reviews for recurring problems.
- **Web traffic and search interest:** third-party estimates. Quote them as estimates, with the tool's name and date, and never next to a measured number as if they were one.
- **Job posts:** headcount growth and the stack they hire for.
- **Funding and revenue:** from filings and press. Revenue that a company announces is a claim.

## 4. Prices and price lists

- Read the pricing page of the main site, the same day, and capture it: `scripts/capture_page.py`.
- The history comes from archives: `scripts/wayback.py list <url> --per month`, then `fetch` the snapshots around each change.
- Note the currency, taxes, billing period, seat or usage basis, and what each plan includes.
- If the page renders in the browser, the captured HTML may be nearly empty: the capture's metadata warns you. Use a browser tool for those pages.

## 5. Estimates

- Estimated economics (margins, infrastructure cost per user, burn) are always inference.
- Write the calculation and the source and date of every list price you used.
- Give a range, not a point, when the inputs are uncertain.
- Never put an estimate in a public claim.

## 6. Writing numbers

- Every number has a date: "1,234 stars on 4 October 2026", not "about 1k stars".
- Use the same number, with the same date, in every document.
- When two sources disagree, reconcile them (definition, date, scope) and note the reconciliation in the appendix header.
