# Business model and pricing: what is free, what is paid, and where they convert

Two open-source products can give away the same code and still fight a pricing war. The battle is over what each side charges for, why, and where it turns a free user into a customer. This is track 5 and document 08. Run it in every full analysis, and run it again whenever the competitor's pricing, partner or enterprise pages change.

## 1. The questions

1. **The offer.** Every plan, price, unit and allowance, as published today, and how it changed.
2. **Free and paid.** For each capability, the plan that gets it. For each paywall: why it sits there.
3. **Open and closed.** For each component: its license, where its code lives, who runs it. How the paid layer is switched on, in the code.
4. **Integrations and partners.** What they build, what they plug in, who pays whom, and which placements they sell.
5. **Where they earn and where they convert.** The revenue streams by likely weight, the path from first visit to paying customer, what they give away and what that costs them.
6. **Against yours.** Your own model on the same rows: your free and paid lines, your levers, the levers you cannot use, your conversion moments, your price anchors.

## 2. Evidence, and where it lives

| Source | What it gives | How |
|---|---|---|
| Pricing, cloud, enterprise or white-label, partner and download pages of the main site, captured the same day | Plans, prices, units, allowances, add-ons, discounts, "contact us" tiers, partner prices, license claims | `scripts/capture_page.py <url> --out-dir evidence/`, then `scripts/monetization_scan.py page <capture>` |
| Terms, refund policy, `llms.txt`, the checkout link (read the link, never open a checkout) | The payment provider, the billing entity, refund rules, the prices they feed to search and answer engines | Capture; read |
| The history of those pages | When a plan appeared, when a promise left the free tier | `scripts/wayback.py list <url> --per day`, `fetch --text`, then `scripts/removals.py pages <old> <new>` |
| The repository | Where the paid layer lives and how it is gated: license folders and keys, entitlement checks, billing SDKs, hosted-service seams, in-app offers and their triggers, prices written in the app, analytics and lead capture | `scripts/monetization_scan.py code <repo>`, then read every strong signal in the code; `scripts/license_scan.py` for the license per folder |
| Their docs on hosting, self-hosting, enterprise and partners | What a self-hoster gets for free, what the hosted plan adds, the contract with private services | Read the docs in the repository and on the site |
| References to repositories you cannot see | Closed services: control planes, billing, relays | Names in docs and code; the public API answers 404 for a private repository |
| Your own pricing data, plans and decisions | The mirror | Your site's pricing page or data files, your register, your FAQ; read only |

Prices change weekly at young companies. Date every price, keep the capture, and quote the plan name exactly.

## 3. Free and paid

Build one table: rows are capabilities, columns are plans. Capabilities to cover, when they apply: number of agents, bots or projects; providers and models; platforms; usage of models (included or brought by the user); always-on hosting; compute, storage and other metered resources; people and seats; administration; single sign-on; audit; budgets and spend limits; branding; support levels; deployment (hosted, self-hosted, on-premises); integrations and connectors; the API.

Then, for each paywall, write why it sits there (inference), from these usual reasons:

- **It costs them money:** machines, metered third-party services, storage, bandwidth. Limits then come in hours, minutes or gigabytes, not features.
- **Only organizations need it:** administration, single sign-on, audit, budgets, roles. Their own rule is often written down, for example "what an open-source user would want goes in the core".
- **It is scarce:** support, onboarding, people's time.
- **It is distribution:** branding, white-label, reselling.

Also list what they give away that costs them money: hosted brokers, tunnels, free credits, build infrastructure. Free users then raise their costs, which shapes their next moves (inference).

## 4. Open and closed

| Component | License | Where the code lives | Who runs it | Evidence |
|---|---|---|---|---|

Read the gate in the code. Open core usually works one of these ways:

- **A folder under its own license,** source-available, switched on by a license key: find the key format, how it is verified (signature, offline or online), the entitlement identifiers, the grace period and what happens when the key lapses. `license_scan.py` finds the folder license; `monetization_scan.py code` finds the key and entitlement checks.
- **A separate private repository or binary** for the paid layer or the hosted control plane. The public code shows its seams: environment variables naming a relay, a broker or a cloud service, with a URL and a token.
- **Hosted-only services:** the code is open, but it runs with their keys on their accounts, so self-hosters must bring their own.
- **No gate in the code at all:** everything is open and they sell hosting, support or services.

Compare their public words with the code: "the whole app is open source" next to a source-available folder, or a free plan that "has every feature" while the paid layer grows.

## 5. Integrations and partners

For each area (models, compute, voice, connectors, plugin catalogs, templates): what they build, what they plug in, who pays whom, and whether the user brings a key. Then the partner program: categories, price per placement, what the partner gets (a spot in the product, a launch post, a listing, a tracked link), how many spots, and the audience numbers they declare. Placements usually sit exactly where the product looks neutral, in the pickers for models, computers and tools. Quote declared audience numbers as declared, never as measured.

## 6. Where they earn and where they convert

**The revenue streams,** ranked by likely weight (inference): enterprise and white-label contracts, subscriptions, usage, services, placements, donations. Give the reasons: contract size, margin, effort to sell.

**The path,** step by step, each with evidence:

| Step | What to find | Where |
|---|---|---|
| Arrival | Content, search, answer engines (`llms.txt`), stars, community, launch tactics | Site, blog, repository |
| First run | Account or not; email capture; analytics on or off by default; who receives the identity | Onboarding code, analytics setup, privacy policy |
| Offer | In-app offers: when they appear, how often, whether they can be dismissed for good, what price they show. Prices in the app can differ from the site | `monetization_scan.py code` (offers, prices in code); read the component and its conditions |
| Reasons to pay | The pain the paid plan removes: a machine that must stay on, keys to set up, limits, team needs | Pricing pages, docs |
| Expansion | Seats, add-ons, larger tiers, annual billing | Pricing pages |
| Other businesses | White-label, OEM, API, reseller terms, contract length, setup fees | Enterprise pages |

**The economics,** always "(inference)": cost anchors from public list prices (a machine, a metered service, a payment provider's fee), the margin at full use, what the free tier costs them.

**Pricing techniques worth naming:** fair-use allowances, add-ons, annual discounts, launch prices for the first customers, "every plan starts with a call", self-hosted plans cheaper than hosted ones.

## 7. Against yours

Run the mirror on the same rows ([mirror.md](mirror.md)):

- **Your free and paid map,** from your pricing data or your decisions. A placeholder is still a fact about your intentions: quote its file and line.
- **Your open and closed map.** If everything you ship is under one permissive license, nothing in your code can be sold: a limit in the code is a limit anyone can remove. Your paid side then has to be services, content or guarantees that need you: maintained data, hosted services that cost you, support, compliance, validated releases, training.
- **The levers you cannot use,** because of your license, your architecture or decisions already taken, such as "runs only on the user's machine" or "no account".
- **Your conversion moments.** Without telemetry, conversion has to be designed into the product: the moment a user meets the limit your paid offer removes.
- **Price anchors,** per person and per unit, from their published prices, never copied as targets.

Write the comparison as a table: lever, theirs, yours today, judgment. Close with proposals, each with a default for the register ([register.md](register.md)).

## 8. Traps

- **Taking a license claim on a download page for the whole story.** Read the license files per folder and the build that ships.
- **Comparing list prices without units and allowances.** Per person, per seat, per workspace and per machine are different things; so are monthly and annual prices.
- **Calling a bring-your-own-key plan free.** The user still pays the provider; say so.
- **Quoting a partner page's audience numbers as measured.**
- **Treating an in-app offer as the price list,** or the reverse. Quote each with its place and date.
- **Opening a checkout to find the payment provider.** It can create a payment session on their side; read the link and the policies instead.
- **Recommending prices for your product from theirs alone.** Their prices change, and their costs are not yours. Use them as anchors, then test with your own customers.
