#!/usr/bin/env python3
"""Offline tests for finserv_report_bot's analysis engine and rendering.

These lock down the derived math (YoY, running YTD, % to goal, pace) and check
that the numbers in the data file reconcile with what the source report shows,
so a bad edit to a month file or the engine fails loudly.

Run:  python bot/test_report.py
"""
import json
import unittest
from pathlib import Path

import finserv_report_bot as bot

DATA = Path(__file__).parent / "data" / "2026-05.json"


class RevenueMathTest(unittest.TestCase):
    def setUp(self):
        self.rev = bot.compute_revenue(json.loads(DATA.read_text())["revenue"])

    def test_yoy_dollars_and_percent(self):
        jan = self.rev["months"][0]
        self.assertEqual(jan["yoy_dollar"], 410570)   # 4,159,799 - 3,749,229
        self.assertAlmostEqual(jan["yoy_pct"], 11.0, places=1)

    def test_running_ytd_accumulates(self):
        apr = self.rev["months"][3]
        self.assertEqual(apr["ytd_2026"], 15903262)   # rounds to the deck's 15,903,261.28
        self.assertEqual(apr["ytd_2025"], 16348666)

    def test_ytd_totals_and_trailing(self):
        # Full-year-to-date (incl. estimated May) matches the ~$19.49M / ~$20.41M deck.
        self.assertEqual(self.rev["ytd_2026"], 19493262)
        self.assertEqual(self.rev["ytd_2025"], 20408666)
        self.assertLess(self.rev["total_yoy_dollar"], 0)          # trailing
        self.assertAlmostEqual(self.rev["total_yoy_pct"], -4.5, places=1)

    def test_may_flagged_estimate(self):
        may = self.rev["months"][-1]
        self.assertTrue(may["estimate"])
        self.assertAlmostEqual(may["yoy_pct"], -11.6, places=1)

    def test_months_up_down_counts(self):
        self.assertEqual(self.rev["months_up"], 1)   # only January
        self.assertEqual(self.rev["months_down"], 4)


class DiscoveryMathTest(unittest.TestCase):
    def setUp(self):
        self.disc = bot.compute_discovery(
            json.loads(DATA.read_text())["discovery"], month_number=5)

    def test_category_ytd_and_pct(self):
        general = self.disc["categories"][0]
        self.assertEqual(general["ytd"], 108)         # 82 + 26
        self.assertAlmostEqual(general["pct_to_goal"], 54.0, places=1)

    def test_total_row(self):
        total = self.disc["total"]
        self.assertEqual(total["goal"], 750)
        self.assertEqual(total["ytd"], 204)           # reconciles to deck's 204
        self.assertAlmostEqual(total["pct_to_goal"], 27.2, places=1)

    def test_pace_and_laggards(self):
        # Five months into the year -> ~41.7% straight-line pace.
        self.assertAlmostEqual(self.disc["pace_pct"], 500 / 12, places=1)
        self.assertLess(self.disc["total"]["pct_to_goal"], self.disc["pace_pct"])
        weakest = self.disc["laggards"][0]
        self.assertIn("Tech/Consulting", weakest["name"])

    def test_activity_over_goal(self):
        nl = next(a for a in self.disc["activities"] if a["name"] == "Newsletter/Content")
        self.assertEqual(nl["ytd"], 29)
        self.assertGreater(nl["pct_to_goal"], 100)    # 242%


class WinsTest(unittest.TestCase):
    def test_total_booked(self):
        wins = bot.compute_wins(json.loads(DATA.read_text())["wins"])
        self.assertEqual(wins["count"], 4)
        self.assertEqual(wins["total"], 212000)
        self.assertTrue(wins["all_numeric"])


class NewsletterTest(unittest.TestCase):
    def test_benchmark_and_delta(self):
        nl = bot.analyze_newsletter(json.loads(DATA.read_text())["newsletter"])
        self.assertAlmostEqual(nl["open_delta_pts"], 36.87 - 7.53, places=2)
        self.assertGreater(nl["open_vs_benchmark_x"], 1.0)  # beats the benchmark
        self.assertAlmostEqual(nl["list_pct"], 2488 / 3000 * 100, places=1)


class FormattingTest(unittest.TestCase):
    def test_money(self):
        self.assertEqual(bot.money(212000), "$212,000")
        self.assertEqual(bot.money(3590000, approx=True), "~$3.59M")
        self.assertEqual(bot.money(None), "—")

    def test_signed_money(self):
        self.assertEqual(bot.signed_money(410570), "+$410,570")
        self.assertEqual(bot.signed_money(-470000, approx=True), "~-$470,000")

    def test_pct(self):
        self.assertEqual(bot.pct(-4.5, signed=True), "-4.5%")
        self.assertEqual(bot.pct(11.0, signed=True), "+11.0%")
        self.assertEqual(bot.pct(36.87, digits=2), "36.87%")

    def test_direction(self):
        self.assertEqual(bot.direction(5), "up")
        self.assertEqual(bot.direction(-5), "down")
        self.assertEqual(bot.direction(0), "flat")


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DATA.read_text())
        self.c = bot.compute(self.data)

    def test_analysis_nonempty_and_grounded(self):
        text = " ".join(self.c["analysis"])
        self.assertIn("trailing", text)          # revenue is down YoY
        self.assertIn("204 of 750", text)        # discovery figure surfaced
        self.assertIn("$212,000", text)          # wins total surfaced

    def test_html_renders_key_numbers(self):
        html = bot.render_html(self.data, self.c)
        self.assertIn("Financial Services", html)
        self.assertIn("36.87%", html)            # newsletter open rate
        self.assertIn("$115,000", html)          # a marquee win
        self.assertIn("<!doctype html>", html)

    def test_markdown_renders(self):
        md = bot.render_markdown(self.data, self.c)
        self.assertIn("| Month | 2025 | 2026 |", md)
        self.assertIn("Total Discovery Calls", md)

    def test_month_key(self):
        self.assertEqual(bot.month_key(self.data), "2026-05")


if __name__ == "__main__":
    unittest.main(verbosity=2)
