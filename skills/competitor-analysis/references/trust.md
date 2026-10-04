# Trust: telemetry, network, privacy, security

Trust is often where a smaller product beats a bigger one, so it deserves evidence, not adjectives. Everything here is read from the code; running the product is a closed-source technique that needs the user's approval ([closed-source.md](closed-source.md)).

## 1. Telemetry

```bash
python3 scripts/telemetry_scan.py <repo>
python3 scripts/telemetry_scan.py <repo> --include-tests --include-docs
python3 scripts/telemetry_scan.py <repo> --at release/1.0 --max-hosts 0   # another branch, every host
```

The scan reports analytics and error-reporting SDKs, lines that look like consent or opt-out switches, and every external host the code mentions, with known telemetry hosts flagged. Signatures live in `scripts/telemetry_signatures.json`; add one when you meet a new SDK.

Each SDK has a `strength`. "usage" means a line imports, initializes or loads it. "mention only" means the code just names the vendor's domain, as an integration catalog, a settings list or a docs link does: a product that lets users connect their own error tracker is not sending its telemetry there.

Each SDK found is a lead. Confirm it by reading the code path and answering, with `file:line`:

1. **Does it run by default?** Find the call that initializes it and what guards it.
2. **Before or after consent?** Is there a consent screen, and does the SDK start before it?
3. **What does it send?** Event names, properties, screen recordings, crash dumps, file paths, prompts.
4. **With which identity?** An anonymous id, a device id, an account id, an email.
5. **To whom?** The host, the vendor, the region.
6. **Can the user turn it off,** and does off really mean off (no init, no queue, no flush)?
7. **Is it in every build,** or only in development or nightly builds?

## 2. Network contacts

- Static view: the host list from `telemetry_scan.py`, grouped by purpose: updates, telemetry, model or API providers, the vendor's own backend, documentation links.
- Contacts at startup, before the user has turned anything on: follow the startup code path.
- A dynamic view (a network capture of the running app) is a hands-on test: only with approval, on a test machine.

## 3. The privacy policy against the code

- Capture the policy the same day: `scripts/capture_page.py <policy url> --out-dir <evidence>`.
- Line by line, compare what it says is collected, why, for how long and shared with whom, with what the code does.
- Note the gaps both ways: collected but not declared, declared but not collected.
- Check the subprocessor list, if they publish one, against the hosts in the code.
- Report gaps as dated facts with both citations. Leave legal conclusions to counsel.

## 4. App security

```bash
python3 scripts/app_security_scan.py <repo>
```

Signals by area, each with `file:line`:

- **macOS:** entitlements, and the risky ones: library validation disabled, dyld environment variables allowed, unsigned executable memory, JIT, get-task-allow; the app sandbox; the hardened runtime; update keys for the updater; notarization steps in the release workflow (`notarytool`, `stapler`). An Xcode project that never sets the hardened runtime or an entitlements file is reported as such: "not configured" is a finding, not a clean result.
- **Electron:** fuses configured or not; `BrowserWindow` web preferences (`nodeIntegration`, `contextIsolation`, `sandbox`, `webSecurity`); signing, notarization and update-signature settings in the build configuration. `notarize: false` there often means notarization runs as a separate step: look for the notarization step signal before you write "not notarized".
- **Tauri:** the updater public key; the content security policy.
- **Android and iOS:** cleartext traffic, debuggable builds, App Transport Security exceptions, privacy manifests.
- **Web:** Content-Security-Policy, permissive CORS, servers bound to every network interface (`0.0.0.0`), which other machines on the network can reach.
- **Secrets:** tokens and keys that look real, shown masked, and files that should never be committed. Placeholders and test fixtures are filtered, but check each hit.

A signal is a lead. Read the configuration in context before you report it: a debug-only setting is not a shipped one, and an entitlement may be required by a feature the product really needs. When you report a risky setting, say what it enables and why the product may need it.

Also check, by reading:

- **Local servers:** does a local HTTP or websocket server authenticate its callers? Does it check the `Origin` header? Can a web page in the user's browser reach it?
- **Update integrity:** are update payloads signed, and is the signature verified before install?
- **Credential storage:** system keychain or plain files?
- **The security contact:** a `SECURITY.md`, a disclosure policy, past advisories and how fast they were fixed.

## 5. How to write it

- Every trust statement is a dated fact with `file:line` at the snapshot, never an adjective.
- Never print a secret's value, not even partly beyond the mask the scripts use.
- If you find something that looks like a live credential or a serious vulnerability, stop and tell the user; do not test it, and do not put details in shared documents. Responsible disclosure to the vendor is the user's decision.
- Run the same scans on your own product ([mirror.md](mirror.md)). A trust comparison you have not run on yourself is a claim, not evidence.
