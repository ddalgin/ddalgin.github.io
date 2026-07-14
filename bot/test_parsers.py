#!/usr/bin/env python3
"""Offline tests for finserv_events_bot parsers and filtering.

Run:  python bot/test_parsers.py
"""
import json
import unittest
from datetime import date, timedelta

import finserv_events_bot as bot

FUTURE = (date.today() + timedelta(days=14)).isoformat()
FAR_FUTURE = (date.today() + timedelta(days=200)).isoformat()

EVENTBRITE_FIXTURE = (
    "<html><head><script>\n"
    "window.__SERVER_DATA__ = "
    + json.dumps({
        "search_data": {
            "events": {
                "results": [
                    {
                        "name": "NYC Fintech Networking Mixer",
                        "url": "https://www.eventbrite.com/e/nyc-fintech-mixer-1",
                        "start_date": FUTURE,
                        "is_online_event": False,
                        "summary": "Meet founders and bankers in financial services.",
                        "primary_venue": {"name": "The Yard"},
                        "ticket_availability": {
                            "is_free": False,
                            "minimum_ticket_price": {"major_value": "25.00"},
                        },
                    },
                    {
                        "name": "Online Crypto Webinar",
                        "url": "https://www.eventbrite.com/e/online-2",
                        "start_date": FUTURE,
                        "is_online_event": True,
                        "ticket_availability": {"is_free": True},
                    },
                ]
            }
        }
    })
    + ";\nwindow.other = 1;</script></head><body></body></html>"
)

JSONLD_FIXTURE = f"""
<html><head>
<script type="application/ld+json">
{{"@context":"https://schema.org","@graph":[
  {{"@type":"Event","name":"Boston Banking &amp; Payments Summit",
    "url":"https://10times.com/boston-banking",
    "startDate":"{FUTURE}T09:00:00-05:00",
    "location":{{"@type":"Place","name":"Hynes Convention Center"}},
    "offers":{{"@type":"Offer","price":"99","priceCurrency":"USD"}},
    "description":"Annual summit for banking and capital markets leaders."}},
  {{"@type":"BusinessEvent","name":"Wealth Management Expo",
    "url":"https://10times.com/wealth-expo",
    "startDate":"{FUTURE}",
    "offers":[{{"price":"0"}}]}}
]}}
</script>
</head><body></body></html>
"""

GARYSGUIDE_FIXTURE = f"""
<html><body><table>
<tr><td><b>Mon, {(date.today() + timedelta(days=14)).strftime('%b %d').replace(' 0', ' ')}</b></td></tr>
<tr><td>
 <a href="https://www.garysguide.com/events/abc123/Fintech-Founders-Happy-Hour" class="ftitle">Fintech Founders Happy Hour</a>
 <span>FREE</span>
</td></tr>
<tr><td>
 <a href="https://www.garysguide.com/events/def456/Capital-Markets-Panel" class="ftitle">Capital Markets Panel</a>
 <span>$40</span>
</td></tr>
</table></body></html>
"""


class ServerDataTest(unittest.TestCase):
    def test_extracts_json_object(self):
        data = bot.extract_server_data(EVENTBRITE_FIXTURE)
        results = data["search_data"]["events"]["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "NYC Fintech Networking Mixer")

    def test_missing_marker_raises(self):
        with self.assertRaises(ValueError):
            bot.extract_server_data("<html>nope</html>")


class EventbriteParseTest(unittest.TestCase):
    def test_parses_and_skips_online(self):
        orig = bot.fetch
        bot.fetch = lambda url, timeout=25: EVENTBRITE_FIXTURE
        try:
            events, statuses = bot.source_eventbrite(
                "New York City", {"eventbrite_slug": "ny--new-york"}, 75)
        finally:
            bot.fetch = orig
        # one in-person event per search term (online one skipped)
        per_term = len(events) / len(bot.SEARCH_TERMS)
        self.assertEqual(per_term, 1)
        ev = events[0]
        self.assertEqual(ev.price_min, 25.0)
        self.assertEqual(ev.start, FUTURE)
        self.assertEqual(ev.venue, "The Yard")
        self.assertTrue(all(s.ok for s in statuses))


class JsonLdTest(unittest.TestCase):
    def test_extracts_events_from_graph(self):
        nodes = bot.extract_jsonld_events(JSONLD_FIXTURE)
        self.assertEqual(len(nodes), 2)
        names = {n["name"] for n in nodes}
        self.assertIn("Wealth Management Expo", names)

    def test_tentimes_source(self):
        orig = bot.fetch
        bot.fetch = lambda url, timeout=25: JSONLD_FIXTURE
        try:
            events, statuses = bot.source_tentimes(
                "Boston", {"tentimes_slug": "boston-us"}, 75)
        finally:
            bot.fetch = orig
        self.assertEqual(len(events), 2)
        summit = next(e for e in events if "Summit" in e.title)
        self.assertEqual(summit.price_min, 99.0)
        self.assertEqual(summit.start, FUTURE)
        self.assertIn("&", summit.title)  # entity unescaped
        expo = next(e for e in events if "Expo" in e.title)
        self.assertTrue(expo.is_free)


class GarysGuideTest(unittest.TestCase):
    def test_parses_titles_prices_dates(self):
        orig = bot.fetch
        bot.fetch = lambda url, timeout=25: GARYSGUIDE_FIXTURE
        try:
            events, statuses = bot.source_garysguide(
                "New York City", {"garysguide": True}, 75)
        finally:
            bot.fetch = orig
        self.assertEqual(len(events), 2)
        hh = next(e for e in events if "Happy Hour" in e.title)
        self.assertTrue(hh.is_free)
        self.assertEqual(hh.start, FUTURE)
        panel = next(e for e in events if "Panel" in e.title)
        self.assertEqual(panel.price_min, 40.0)


LUMA_FIXTURE = json.dumps({
    "slug": "nyc",
    "scope": "place",
    "has_more": False,
    "next_cursor": None,
    "events": [
        {
            "api_id": "evt-1",
            "name": "NYC Fintech & Payments Founders Mixer",
            "url": "https://lu.ma/fintech-mixer",
            "start_at": f"{FUTURE}T22:00:00.000Z",
            "location_type": "offline",
            "city": "New York, NY",
            "ticket_info": {"is_free": True},
        },
        {
            "api_id": "evt-2",
            "name": "Online AI Webinar",
            "url": "https://lu.ma/webinar",
            "start_at": f"{FUTURE}T22:00:00.000Z",
            "location_type": "online",
        },
        {
            "event": {
                "api_id": "evt-3",
                "name": "Banking Infrastructure Happy Hour",
                "url": "bank-hh",
                "start_at": f"{FUTURE}T21:00:00.000Z",
                "location_type": "offline",
                "ticket_info": {"is_free": False, "price": {"cents": 1500}},
            }
        },
    ],
})


class LumaTest(unittest.TestCase):
    def test_parses_events_skips_online(self):
        orig = bot.fetch
        bot.fetch = lambda url, timeout=25: LUMA_FIXTURE
        try:
            events, statuses = bot.source_luma(
                "New York City", {"luma_slugs": ["nyc"]}, 75)
        finally:
            bot.fetch = orig
        self.assertEqual(len(events), 2)  # online event skipped
        mixer = next(e for e in events if "Mixer" in e.title)
        self.assertTrue(mixer.is_free)
        self.assertEqual(mixer.start, FUTURE)
        hh = next(e for e in events if "Happy Hour" in e.title)
        self.assertEqual(hh.price_min, 15.0)
        self.assertEqual(hh.url, "https://lu.ma/bank-hh")
        self.assertTrue(all(s.ok for s in statuses))

    def test_bad_slug_falls_through(self):
        calls = []

        def fake_fetch(url, timeout=25):
            calls.append(url)
            if "slug=bad" in url:
                raise ValueError("HTTP 404")
            return LUMA_FIXTURE

        orig = bot.fetch
        bot.fetch = fake_fetch
        try:
            events, statuses = bot.source_luma(
                "Washington DC", {"luma_slugs": ["bad", "dc"]}, 75)
        finally:
            bot.fetch = orig
        self.assertEqual(len(events), 2)
        self.assertEqual(len(statuses), 2)  # one failure, one success
        self.assertTrue(statuses[1].ok)


class ScoringFilterTest(unittest.TestCase):
    def test_finserv_event_scores_high(self):
        score, matched = bot.score_event(
            "Fintech & Banking Leaders Summit", "capital markets networking")
        self.assertGreaterEqual(score, 4)
        self.assertIn("fintech", matched)

    def test_spam_scores_low(self):
        score, _ = bot.score_event(
            "Financial Freedom: Get Rich with Passive Income", "")
        self.assertLess(score, 2)

    def test_filter_price_date_dedupe(self):
        mk = lambda **kw: bot.Event(  # noqa: E731
            title=kw.get("title", "Fintech Banking Summit"),
            url="https://x.example/e", start=kw.get("start", FUTURE),
            city="Boston", source="test",
            price_min=kw.get("price"), description="financial services")
        events = [
            mk(),                                   # keep
            mk(),                                   # duplicate -> drop
            mk(price=999.0),                        # too expensive -> drop
            mk(start=FAR_FUTURE, title="Fintech Later"),   # beyond window -> drop
            mk(start="2020-01-01", title="Fintech Past"),  # past -> drop
        ]
        kept = bot.filter_events(events, max_price=150, days=75, min_score=2)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].title, "Fintech Banking Summit")


class DateParseTest(unittest.TestCase):
    def test_various_formats(self):
        self.assertEqual(bot.parse_date_any("2026-08-01T09:00:00"), "2026-08-01")
        self.assertEqual(bot.parse_date_any("Aug 1, 2026"), "2026-08-01")
        self.assertEqual(bot.parse_date_any(""), "")
        # month-day with no year resolves to a real upcoming date
        d = bot.parse_date_any("Jul 20")
        self.assertRegex(d, r"\d{4}-07-20")


if __name__ == "__main__":
    unittest.main(verbosity=2)
