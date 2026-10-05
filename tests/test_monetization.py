"""Tests for monetization_scan.py: the paid layer in a codebase, and what a pricing page offers."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCRIPTS, run_script, write

PRICING_TEXT = """Pricing
Free $0 Forever · open source
Pro $49 USD / month · Cancel any time
Team $169 /mo $135/mo billed yearly
Up to 5 people
Each extra person $25 a month
Your logo, name and domain +$99 a month
Extra cloud hours are $0.05 each.
Enterprise Custom
Talk to us
Get Pro · $49/month
Launch price for the first 100 users, then $89/month
Équipe 4,99 € par mois
"""


def fake_product(root: Path) -> None:
    write(root, "package.json", '{"name": "acme", "dependencies": {"stripe": "^14.0.0", "@lemonsqueezy/lemonsqueezy.js": "^3.0.0"}}\n')
    write(root, "src/billing.ts", 'import Stripe from "stripe";\nexport const stripe = new Stripe(process.env.STRIPE_KEY!);\n')
    write(root, "server/license.ts", "const key = process.env.ACME_LICENSE_KEY;\n"
                                     "export function verifyLicense(token: string) { return token.length > 0; }\n"
                                     'if (!entitled("admin")) throw new Error("admin needs a license");\n')
    write(root, "src/plan.ts", 'export function canInvite(plan: string) {\n  if (plan === "team") return true;\n  return isPro;\n}\n')
    write(root, "src/offer.tsx", 'export const PRICING_URL = "https://acme.example/pricing";\n'
                                 'export const DOCS_PRICES = "https://models.example.org/pricing";\n'
                                 'export const PRO_PRICE = "$49";\n'
                                 'export const NOTE = "Launch price for the first 100 users";\n'
                                 'export const BUTTON = "Upgrade to Pro";\n'
                                 'run("$1");\n')
    write(root, "src/analytics.ts", "export function remember(email: string) {\n  posthog.identify(email, { email });\n}\n")
    write(root, "server/cloud.ts", "const relay = process.env.ACME_CLOUD_RELAY_URL;\nconst broker = process.env.ACME_BROKER_TOKEN;\n"
                                   "const api = process.env.CLOUDFLARE_API_TOKEN;\n")
    write(root, "enterprise/LICENSE", "Acme Enterprise License\n\nAll rights reserved.\n")
    write(root, "enterprise/license.ts", "export const LICENSE_HEADER = 'not a license file';\n")
    write(root, "enterprise/index.ts", "export const enabled = true;\n")
    write(root, "tests/billing.test.ts", 'import Stripe from "stripe";\nconst key = process.env.ACME_LICENSE_KEY;\n')
    write(root, "docs/pricing.md", "Set your license key to unlock the team plan.\n")
    write(root, "package-lock.json", '{"packages": {"node_modules/stripe": {"version": "14.0.0"}}}\n')


class CodeTest(unittest.TestCase):
    def test_billing_gates_offers_leads_seams_and_folders(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fake_product(root)
            out = run_script("monetization_scan.py", "code", str(root), "--own-domain", "acme.example")

            billing = {b["name"]: b for b in out["billing"]}
            self.assertEqual(set(billing), {"Stripe", "Lemon Squeezy"})
            self.assertEqual(billing["Stripe"]["files"], ["package.json", "src/billing.ts"])

            gates = {(h["file"], h["line"]) for h in out["license_gates"]}
            self.assertEqual(gates, {("server/license.ts", 1), ("server/license.ts", 2), ("server/license.ts", 3)})
            self.assertEqual(out["strong_counts"]["license_gates"], 3)

            plans = [(h["file"], h["line"], h["strength"]) for h in out["plan_gates"]]
            self.assertEqual(plans, [("src/plan.ts", 2, "strong"), ("src/plan.ts", 3, "weak")])

            offers = [h["match"] for h in out["offers"]]
            self.assertIn("https://acme.example/pricing", offers)
            self.assertIn('"$49"', offers)
            self.assertIn("Launch price", offers)
            self.assertIn('"Upgrade to Pro"', offers)
            self.assertFalse(any("models.example.org" in o or "$1" in o for o in offers))

            self.assertEqual([(h["file"], h["line"]) for h in out["lead_capture"]], [("src/analytics.ts", 2)])
            self.assertEqual(sorted(s["name"] for s in out["hosted_seams"]), ["ACME_BROKER_TOKEN", "ACME_CLOUD_RELAY_URL"])
            self.assertEqual(out["paid_folders"], [{"path": "enterprise", "reason": "name and own license",
                                                   "license_file": "enterprise/LICENSE",
                                                   "license_first_line": "Acme Enterprise License"}])
            self.assertEqual(out["hits_in_tests"], {"billing": 1, "license_gates": 1})

            with_docs = run_script("monetization_scan.py", "code", str(root), "--include-docs", "--include-tests")
            self.assertIn("docs/pricing.md", {h["file"] for h in with_docs["license_gates"]})
            self.assertIn("tests/billing.test.ts", {f for b in with_docs["billing"] for f in b["files"]})
            self.assertIn("https://models.example.org/pricing", {h["match"] for h in with_docs["offers"]})

    def test_not_a_folder(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / "monetization_scan.py"), "code", "/no/such/folder"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)


class PageTest(unittest.TestCase):
    def test_prices_units_and_groups(self):
        with tempfile.TemporaryDirectory() as folder:
            page = write(Path(folder), "pricing.txt", PRICING_TEXT)
            out = run_script("monetization_scan.py", "page", str(page))["pages"][0]
            self.assertEqual(out["price_range"]["USD"], {"min": 0.0, "max": 169.0, "count": 9})
            self.assertEqual(out["price_range"]["EUR"], {"min": 4.99, "max": 4.99, "count": 1})
            units = {p["text"]: p["units"] for p in out["prices"]}
            self.assertEqual(units["Pro $49 USD / month · Cancel any time"], ["month"])
            self.assertEqual(units["Each extra person $25 a month"], ["month"])
            texts = {key: [x["text"] for x in out[key]] for key in ("free", "ctas", "limits", "terms", "add_ons", "contact")}
            self.assertEqual(texts["free"], ["Free $0 Forever · open source"])
            self.assertEqual(texts["ctas"], ["Talk to us", "Get Pro · $49/month"])
            self.assertEqual(texts["limits"], ["Up to 5 people", "Launch price for the first 100 users, then $89/month"])
            self.assertIn("Team $169 /mo $135/mo billed yearly", texts["terms"])
            self.assertIn("Launch price for the first 100 users, then $89/month", texts["terms"])
            self.assertEqual(texts["add_ons"], ["Each extra person $25 a month", "Your logo, name and domain +$99 a month",
                                                "Extra cloud hours are $0.05 each."])
            self.assertEqual(texts["contact"], ["Enterprise Custom", "Talk to us"])

    def test_html_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            page = write(Path(folder), "pricing.html", "<html><head><title>Plans $1</title><script>var p = '$5';</script></head>"
                                                       "<body><h2>Pro</h2><p>$12 per seat a month</p></body></html>")
            out = run_script("monetization_scan.py", "page", str(page))["pages"][0]
            self.assertEqual(out["price_range"], {"USD": {"min": 12.0, "max": 12.0, "count": 1}})
            self.assertEqual(out["prices"][0]["units"], ["month", "seat"])


if __name__ == "__main__":
    unittest.main()
