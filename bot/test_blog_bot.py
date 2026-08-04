#!/usr/bin/env python3
"""Offline tests for finserv_blog_bot.

Run:  python bot/test_blog_bot.py
"""
import datetime as dt
import json
import re
import tempfile
import unittest
from pathlib import Path

import finserv_blog_bot as bot

RSS_FIXTURE = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Capital One leans on MLB loyalty push for credit card growth</title>
    <link>https://example.com/capital-one-mlb</link>
    <pubDate>Mon, 03 Aug 2026 10:00:00 +0000</pubDate>
    <description>The bank's baseball sponsorship and rewards strategy.</description>
  </item>
  <item>
    <title>Unrelated quarterly earnings roundup</title>
    <link>https://example.com/earnings</link>
    <pubDate>Mon, 03 Aug 2026 09:00:00 +0000</pubDate>
    <description>Nothing to do with the topic.</description>
  </item>
</channel></rss>"""

ATOM_FIXTURE = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>AI machine translation and compliance in banking</title>
    <link href="https://example.com/ai-banking"/>
    <updated>2026-08-02T12:00:00Z</updated>
    <summary>Governance for LLM translation in regulated finance.</summary>
  </entry>
</feed>"""


class StatLibraryTest(unittest.TestCase):
    def test_every_stat_has_source_and_date(self):
        self.assertTrue(bot.STAT_LIBRARY)
        for sid, s in bot.STAT_LIBRARY.items():
            self.assertTrue(s.url.startswith("http"), f"{sid} missing url")
            self.assertTrue(s.claim.strip(), f"{sid} missing claim")
            self.assertTrue(str(s.as_of).strip(), f"{sid} missing as_of")
            for extra in s.also:
                self.assertIn("|", extra, f"{sid} malformed corroborating source")
                self.assertTrue(extra.split("|", 1)[1].startswith("http"))

    def test_angles_reference_real_stats(self):
        for key, angle in bot.ANGLES.items():
            for sid in angle.stat_ids:
                self.assertIn(sid, bot.STAT_LIBRARY,
                              f"angle {key} references unknown stat {sid}")
            self.assertIn(angle.renderer, bot.RENDERERS)


class FeedParseTest(unittest.TestCase):
    def test_parses_rss(self):
        items = bot.parse_feed(RSS_FIXTURE, "example.com")
        self.assertEqual(len(items), 2)
        top = items[0]
        self.assertIn("Capital One", top.title)
        self.assertEqual(top.url, "https://example.com/capital-one-mlb")
        self.assertEqual(top.published, dt.date(2026, 8, 3))

    def test_parses_atom_with_href_link(self):
        items = bot.parse_feed(ATOM_FIXTURE, "example.com")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://example.com/ai-banking")
        self.assertEqual(items[0].published, dt.date(2026, 8, 2))

    def test_bad_xml_returns_empty(self):
        self.assertEqual(bot.parse_feed(b"not xml", "x"), [])


class PegSelectionTest(unittest.TestCase):
    def test_picks_most_relevant_item(self):
        items = bot.parse_feed(RSS_FIXTURE, "example.com")
        peg = bot.pick_peg(items, bot.ANGLES["multicultural-loyalty"])
        self.assertIsNotNone(peg)
        self.assertIn("Capital One", peg.title)

    def test_no_match_returns_none(self):
        items = [bot.NewsItem("Weather report", "https://x/y", "x", None)]
        self.assertIsNone(
            bot.pick_peg(items, bot.ANGLES["multicultural-loyalty"]))


class DraftTest(unittest.TestCase):
    def test_flagship_draft_has_sources_and_no_unsourced_stats(self):
        angle = bot.ANGLES["multicultural-loyalty"]
        slug, md = bot.build_draft(angle, bot.FIXTURE_PEG)
        self.assertTrue(slug.startswith(dt.date.today().isoformat()))
        self.assertIn("## Sources", md)
        self.assertIn("DRAFT — human review required", md)
        self.assertIn("111,616", md)          # verified stat surfaced
        self.assertIn("$125 million", md)

        # Every [^n] marker used in the body must have a matching definition.
        used = set(re.findall(r"\[\^(\d+)\]", md.split("## Sources")[0]))
        defined = set(re.findall(r"\[\^(\d+)\]:", md))
        self.assertTrue(used)
        self.assertTrue(used.issubset(defined),
                        f"unsourced citation markers: {used - defined}")

    def test_generic_renderer_produces_sourced_draft(self):
        angle = bot.ANGLES["ai-governance"]
        _, md = bot.build_draft(angle, bot.FIXTURE_PEG)
        self.assertIn("## Sources", md)
        used = set(re.findall(r"\[\^(\d+)\]", md.split("## Sources")[0]))
        defined = set(re.findall(r"\[\^(\d+)\]:", md))
        self.assertTrue(used.issubset(defined))


class CitationsTest(unittest.TestCase):
    def test_dedupes_and_numbers_in_order(self):
        c = bot.Citations()
        self.assertEqual(c.cite_stat("co_mlb_deal"), "[^1]")
        self.assertEqual(c.cite_stat("loyalty_wars"), "[^2]")
        self.assertEqual(c.cite_stat("co_mlb_deal"), "[^1]")  # reused, same num
        self.assertEqual(c.count(), 2)
        rendered = c.render()
        self.assertIn("[^1]:", rendered)
        self.assertIn("[^2]:", rendered)


class OutputTest(unittest.TestCase):
    def test_writes_all_outputs_offline(self):
        with tempfile.TemporaryDirectory() as d:
            rc = bot.main(["--offline", "--out-dir", d,
                           "--angle", "multicultural-loyalty"])
            self.assertEqual(rc, 0)
            out = Path(d)
            self.assertTrue((out / "latest.md").exists())
            self.assertTrue((out / "index.html").exists())
            meta = json.loads((out / "drafts.json").read_text())
            self.assertEqual(meta["angle"], "multicultural-loyalty")
            self.assertEqual(meta["peg"]["source"], "fortune.com")
            self.assertTrue(any(f.name.endswith(".md") and f.name != "latest.md"
                                for f in out.iterdir()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
