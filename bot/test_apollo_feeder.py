#!/usr/bin/env python3
"""Offline tests for apollo_feeder_bot (no network, no API key).

Run:  python bot/test_apollo_feeder.py
"""
import json
import unittest

import apollo_feeder_bot as bot


# A minimal mixed_companies/search response shape.
ORG_SEARCH_FIXTURE = {
    "organizations": [
        {
            "id": "org1",
            "name": "Goliath Asset Management",
            "primary_domain": "goliatham.com",
            "website_url": "https://goliatham.com",
            "industry": "asset management",
            "keywords": ["asset management", "capital markets"],
            "estimated_num_employees": 60000,
            "annual_revenue": "12500000000",
            "total_funding": 0,
            "city": "New York",
            "country": "United States",
        },
        {
            "id": "org2",
            "name": "Tiny Fintech Startup",
            "primary_domain": "tinyfintech.io",
            "industry": "fintech",
            "keywords": ["fintech"],
            "estimated_num_employees": 40,
            "annual_revenue": "3000000",
            "city": "Austin",
            "country": "United States",
        },
    ],
    "pagination": {"page": 1, "total_pages": 1},
}

PEOPLE_SEARCH_FIXTURE = {
    "people": [
        {
            "id": "p1",
            "first_name": "Dana",
            "last_name": "Cho",
            "title": "Chief Investment Officer",
            "seniority": "c_suite",
            "email": "email_not_unlocked@domain.com",
            "email_status": "locked",
            "linkedin_url": "https://linkedin.com/in/danacho",
            "organization": {"id": "org1", "name": "Goliath Asset Management",
                             "primary_domain": "goliatham.com"},
            "city": "New York", "country": "United States",
        }
    ],
    "pagination": {"page": 1, "total_pages": 1},
}


class FakeClient:
    """Stands in for ApolloClient; returns canned responses by path."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def post(self, path, body):
        self.calls.append((path, body))
        resp = self.responses.get(path)
        if isinstance(resp, Exception):
            raise resp
        return resp or {}


class NumberParseTest(unittest.TestCase):
    def test_units(self):
        self.assertEqual(bot.to_number("$1.2B"), 1_200_000_000)
        self.assertEqual(bot.to_number("450M"), 450_000_000)
        self.assertEqual(bot.to_number("1,234"), 1234)
        self.assertEqual(bot.to_number("45%"), 45)
        self.assertEqual(bot.to_number(0.45), 0.45)
        self.assertIsNone(bot.to_number(""))
        self.assertIsNone(bot.to_number(None))


class ScoreAccountTest(unittest.TestCase):
    def test_whale_scores_high(self):
        a = bot.Account(apollo_id="x", name="Big Bank", industry="investment banking",
                        keywords=["investment banking"], employees=60000,
                        revenue=12e9, funding=0)
        score, tier, reasons = bot.score_account(a)
        self.assertEqual(tier, "Whale")
        self.assertGreaterEqual(score, 12)
        self.assertIn("revenue $10B+", reasons)

    def test_small_firm_is_standard(self):
        a = bot.Account(apollo_id="y", name="Tiny", industry="fintech",
                        keywords=["fintech"], employees=40, revenue=3e6)
        _, tier, _ = bot.score_account(a)
        self.assertEqual(tier, "Standard")


class AccountSearchTest(unittest.TestCase):
    def test_parses_scores_and_dedupes(self):
        client = FakeClient({"/api/v1/mixed_companies/search": ORG_SEARCH_FIXTURE})
        accts, statuses = bot.search_accounts(
            client, ["New York, US"], bot.FINSERV_KEYWORDS, 5e8, pages=1)
        self.assertTrue(all(s.ok for s in statuses))
        accts = bot.dedupe_accounts(accts)
        self.assertEqual(len(accts), 2)
        # sorted by score desc -> whale first
        self.assertEqual(accts[0].name, "Goliath Asset Management")
        self.assertEqual(accts[0].tier, "Whale")
        self.assertEqual(accts[0].revenue, 12.5e9)

    def test_api_error_is_reported_not_fatal(self):
        client = FakeClient({"/api/v1/mixed_companies/search": RuntimeError("429 rate limit")})
        accts, statuses = bot.search_accounts(
            client, ["X"], bot.FINSERV_KEYWORDS, 5e8, pages=2)
        self.assertEqual(accts, [])
        self.assertFalse(statuses[0].ok)
        self.assertIn("429", statuses[0].detail)


class PeopleSearchTest(unittest.TestCase):
    def test_locked_email_becomes_blank(self):
        client = FakeClient({"/api/v1/mixed_people/search": PEOPLE_SEARCH_FIXTURE})
        contacts, statuses = bot.search_people(
            client, ["org1"], bot.PERSONA_TITLES, bot.PERSONA_SENIORITIES, pages=1)
        self.assertTrue(all(s.ok for s in statuses))
        self.assertEqual(len(contacts), 1)
        c = contacts[0]
        self.assertEqual(c.email, "")               # locked placeholder stripped
        self.assertEqual(c.company, "Goliath Asset Management")
        self.assertEqual(c.account_id, "org1")

    def test_no_accounts_reports_status(self):
        client = FakeClient({})
        contacts, statuses = bot.search_people(
            client, [], bot.PERSONA_TITLES, bot.PERSONA_SENIORITIES, pages=1)
        self.assertEqual(contacts, [])
        self.assertFalse(statuses[0].ok)


class CsvTest(unittest.TestCase):
    def test_csv_headers_and_tier(self):
        import tempfile
        from pathlib import Path
        acct = bot.Account(apollo_id="org1", name="Goliath", tier="Whale")
        c = bot.Contact(apollo_id="p1", first_name="Dana", last_name="Cho",
                        title="CIO", company="Goliath", domain="goliatham.com",
                        account_id="org1")
        with tempfile.TemporaryDirectory() as d:
            bot.write_csv([c], [acct], Path(d))
            text = (Path(d) / "apollo_import.csv").read_text()
        self.assertIn("First Name", text.splitlines()[0])
        self.assertIn("Dana", text)
        self.assertIn("Whale", text)                # tier joined via account_id
        self.assertIn("https://goliatham.com", text)


class SequenceAnalysisTest(unittest.TestCase):
    CSV = (
        "Step,Subject,Sent,Opened,Replied,Bounced\n"
        "1,Quick question about your data stack,1000,520,45,8\n"
        "2,Following up,1000,180,3,55\n"    # low open, high bounce, low reply
    )

    def test_parse_and_derive_rates(self):
        steps = bot.parse_sequence_rows(self.CSV)
        self.assertEqual(len(steps), 2)
        self.assertAlmostEqual(steps[0]["open_rate"], 0.52, places=3)
        self.assertAlmostEqual(steps[0]["reply_rate"], 0.045, places=3)
        self.assertAlmostEqual(steps[1]["bounce_rate"], 0.055, places=3)

    def test_findings_and_recs(self):
        analysis = bot.analyze_sequence(bot.parse_sequence_rows(self.CSV))
        blob = " ".join(analysis["findings"] + analysis["recommendations"]).lower()
        self.assertIn("bounce", blob)               # step 2 flagged
        self.assertIn("open rate", blob)            # step 2 low open flagged
        self.assertEqual(analysis["summary"]["num_steps"], 2)
        self.assertTrue(analysis["summary"]["total_sent"] == 2000)

    def test_percent_columns_accepted(self):
        csv_pct = ("Step,Open Rate,Reply Rate\n"
                   "1,52%,4.5%\n2,18%,0.3%\n")
        steps = bot.parse_sequence_rows(csv_pct)
        self.assertAlmostEqual(steps[0]["open_rate"], 0.52, places=3)
        self.assertAlmostEqual(steps[1]["reply_rate"], 0.003, places=4)

    def test_empty_csv(self):
        analysis = bot.analyze_sequence(bot.parse_sequence_rows(""))
        self.assertEqual(analysis["steps"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
