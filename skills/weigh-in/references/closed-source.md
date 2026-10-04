# Closed-source competitors

Without a repository the method stays the same. What changes is the sources and the strength of the evidence, so every fact carries its evidence level and "What I could not verify" grows. That is honest, not a failure.

## 1. Sources

- The site, the docs, release notes and changelogs, status pages and their incident history.
- Public SDKs, examples and packages: package registries, the company's public repositories. SDKs reveal API shapes, endpoints and telemetry: run `scripts/telemetry_scan.py`, `scripts/license_scan.py` and `scripts/dependency_versions.py` on them.
- Terms of service, privacy policy, data processing agreement, subprocessor list, security or trust pages.
- Store listings: privacy labels, permissions, ratings and reviews, version history.
- Official videos, webinars and conference talks: they often show what the docs do not.
- Archives: `scripts/wayback.py` for the history of prices, claims and pages.
- Patents, job posts (the stack they hire for), company registries, funding databases.
- Public discussions on forums and social sites: leads, never proof.
- Their public web pages, captured with `scripts/capture_page.py`: the HTML lists the analytics and tag scripts the site loads. `scripts/telemetry_scan.py` on the evidence folder finds them.

## 2. Evidence levels

Mark every fact with one of:

| Level | Meaning |
|---|---|
| Stated | The company says so, on a dated page |
| Observed | You saw it in a recorded test (below) |
| Verified | Confirmed on several independent sources |
| Inference | Your reasoning, with the steps written down |

## 3. The hands-on test

Installing and using the product is a test, and it happens only with the user's explicit approval, under these rules:

- On a test machine or a disposable virtual machine, never on a work machine, and with no real data.
- With an account created by a person on the team. The agent never creates accounts or enters payment details.
- Within the terms of use and the license: no disassembly or reverse engineering where they forbid it. Reading what the system shows (version, signature, requested permissions) is not disassembly; still, check the terms.
- With a network capture to see what leaves the machine, and video for behavior comparisons. Keep both as evidence with dates.
- With the build version and the machine recorded, as for your own measurements.

Useful reads on a test machine, after approval: the app's signing identity and entitlements (`codesign -dv --entitlements - <App.app>` on macOS), its notarization status (`spctl -a -vv <App.app>`), its bundled frameworks and their versions, its update feed URL and the permissions it asks for, and when.

## 4. The documents adapt

- **02** becomes "Architecture, stated and observable": what they say, what the SDKs, pages and tests show.
- **03** and **05** rest on recorded tests and documented behavior, not on code.
- **04** becomes "Terms, licenses of known components, public SDKs": the terms of service, the licenses of their open-source parts and SDKs, third-party notices visible in the app.
- "What I could not verify" is longer, and that is right.

## 5. Positioning changes

- Against a closed product, your openness becomes an argument of its own: code anyone can read, and claims such as "no telemetry" that anyone can verify. Make sure they are true first ([mirror.md](mirror.md)).
- Against an open product, openness is level, and quality decides.
