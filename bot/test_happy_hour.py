#!/usr/bin/env python3
"""Offline tests for happy_hour_bot ranking, filtering, and distances.

Run:  python bot/test_happy_hour.py
"""
import unittest

import happy_hour_bot as bot


class DistanceTests(unittest.TestCase):
    def test_haversine_zero(self):
        self.assertEqual(bot.haversine_mi(38.9, -77.0, 38.9, -77.0), 0.0)

    def test_haversine_known_short_hop(self):
        # Office to Crimson View is a short walk — well under a mile.
        d = bot.haversine_mi(38.8983, -77.0264, 38.8996, -77.0220)
        self.assertLess(d, 0.5)
        self.assertGreater(d, 0.0)

    def test_walking_minutes_monotonic(self):
        self.assertLessEqual(bot.walking_minutes(0.1), bot.walking_minutes(1.0))
        self.assertGreaterEqual(bot.walking_minutes(0.01), 1)


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.origin = bot.ORIGINS["office"]

    def test_all_spots_returned_by_default(self):
        spots = bot.rank(self.origin, "all", set(), False, None, False)
        self.assertEqual(len(spots), len(bot.SPOTS))

    def test_sorted_by_descending_score(self):
        spots = bot.rank(self.origin, "all", set(), False, None, False)
        scores = [s.score for s in spots]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_category_filter(self):
        spots = bot.rank(self.origin, "rooftop", set(), False, None, False)
        self.assertTrue(spots)
        self.assertTrue(all(s.category == "rooftop" for s in spots))

    def test_happy_hour_only_excludes_no_hh(self):
        spots = bot.rank(self.origin, "all", set(), False, None, True)
        self.assertTrue(all(s.has_happy_hour for s in spots))
        # VUE has no standing happy hour, so it must be filtered out.
        self.assertNotIn("VUE Rooftop", [s.name for s in spots])

    def test_max_walk_filter(self):
        spots = bot.rank(self.origin, "all", set(), False, 10, False)
        self.assertTrue(all(s.walk_min <= 10 for s in spots))
        # The Wharf spots are well over 10 minutes away.
        self.assertNotIn("Moonraker at Pendry", [s.name for s in spots])

    def test_require_features_hard_filter(self):
        spots = bot.rank(self.origin, "all", {"view"}, True, None, False)
        self.assertTrue(spots)
        self.assertTrue(all("view" in s.features for s in spots))

    def test_requested_feature_boosts_score(self):
        # Asking for "rooftop,view" should push a rooftop to the top.
        spots = bot.rank(self.origin, "all", {"rooftop", "view"}, False, None,
                         False, rank_by="proximity")
        self.assertIn(spots[0].category, {"rooftop"})
        self.assertTrue(spots[0].matched)

    def test_closer_spot_scores_higher_in_proximity_mode(self):
        # Two synthetic spots, identical except distance.
        near = bot.Spot(name="Near", lat=38.8985, lng=-77.0265,
                        neighborhood="x", category="bar", url="",
                        happy_hour="Mon–Fri 4–7pm", deals="", features=["cocktails"],
                        rating=4.0, price="$$")
        far = bot.Spot(name="Far", lat=38.8790, lng=-77.0228,
                       neighborhood="x", category="bar", url="",
                       happy_hour="Mon–Fri 4–7pm", deals="", features=["cocktails"],
                       rating=4.0, price="$$")
        o_lat, o_lng, _ = self.origin
        for s in (near, far):
            s.dist_mi = bot.haversine_mi(o_lat, o_lng, s.lat, s.lng)
            s.walk_min = bot.walking_minutes(s.dist_mi)
            bot.score_spot(s, set(), rank_by="proximity")
        self.assertGreater(near.score, far.score)


class AwardTests(unittest.TestCase):
    def setUp(self):
        self.origin = bot.ORIGINS["office"]

    def test_award_points_winner_beats_runner_up(self):
        winner = bot.Spot(name="w", lat=0, lng=0, neighborhood="", category="bar",
                          url="", happy_hour="", deals="", features=[],
                          rating=4.0, price="$$", awards=["Best Bar (winner)"])
        runner = bot.Spot(name="r", lat=0, lng=0, neighborhood="", category="bar",
                          url="", happy_hour="", deals="", features=[],
                          rating=4.0, price="$$", awards=["Best Bar (runner-up)"])
        self.assertGreater(bot.award_points(winner), bot.award_points(runner))

    def test_multiple_awards_stack(self):
        two = bot.Spot(name="t", lat=0, lng=0, neighborhood="", category="bar",
                       url="", happy_hour="", deals="", features=[],
                       rating=4.0, price="$$",
                       awards=["Best Wings (winner)", "Best Sports Bar (winner)"])
        one = bot.Spot(name="o", lat=0, lng=0, neighborhood="", category="bar",
                       url="", happy_hour="", deals="", features=[],
                       rating=4.0, price="$$", awards=["Best Wings (winner)"])
        self.assertGreater(bot.award_points(two), bot.award_points(one))

    def test_awards_only_filter(self):
        spots = bot.rank(self.origin, "all", set(), False, None, False,
                         awards_only=True)
        self.assertTrue(spots)
        self.assertTrue(all(s.awards for s in spots))
        # A non-award spot from the original set must be excluded.
        self.assertNotIn("Crimson View", [s.name for s in spots])

    def test_quality_mode_surfaces_award_winners_citywide(self):
        # In quality mode a multi-award winner should outrank a plain
        # nearby spot even though it's farther from the office.
        spots = bot.rank(self.origin, "all", set(), False, None, False,
                         rank_by="quality")
        names = [s.name for s in spots]
        # Duke's Grocery (2 wins) and Union Pub (2 wins) should rank highly.
        self.assertLess(names.index("Duke's Grocery"), 8)
        self.assertLess(names.index("Union Pub"), 10)

    def test_every_award_string_is_recognized(self):
        # Guard against typos: each award must score > 0.
        for raw in bot.SPOTS:
            for a in raw.get("awards", []):
                s = bot.Spot(name="x", lat=0, lng=0, neighborhood="",
                             category="bar", url="", happy_hour="", deals="",
                             features=[], rating=4.0, price="$$", awards=[a])
                self.assertGreater(bot.award_points(s), 0, f"unrecognized: {a}")


class RunsLateTests(unittest.TestCase):
    def setUp(self):
        self.origin = bot.ORIGINS["office"]

    def test_runs_late_filter_only_late_spots(self):
        spots = bot.rank(self.origin, "all", set(), False, None, False,
                         runs_late_only=True)
        self.assertTrue(spots)
        self.assertTrue(all(s.runs_late for s in spots))

    def test_bar_charley_is_a_late_spot(self):
        names = [s.name for s in bot.rank(self.origin, "all", set(), False, None,
                                          False, runs_late_only=True)]
        self.assertIn("Bar Charley", names)

    def test_late_spots_still_count_as_happy_hour(self):
        # All-night / reverse HH spots carry a real window, so --happy-hour-only
        # must include them.
        hh_names = [s.name for s in bot.rank(self.origin, "all", set(), False,
                                             None, True)]
        self.assertIn("Bar Charley", hh_names)


class HappyHourFlagTests(unittest.TestCase):
    def test_check_listing_is_not_a_standing_hh(self):
        s = bot.Spot(name="x", lat=0, lng=0, neighborhood="", category="bar",
                     url="", happy_hour="Check listing", deals="",
                     features=[], rating=4.0, price="$$")
        self.assertFalse(s.has_happy_hour)

    def test_blank_is_not_a_standing_hh(self):
        s = bot.Spot(name="x", lat=0, lng=0, neighborhood="", category="bar",
                     url="", happy_hour="", deals="", features=[],
                     rating=4.0, price="$$")
        self.assertFalse(s.has_happy_hour)

    def test_real_window_is_a_standing_hh(self):
        s = bot.Spot(name="x", lat=0, lng=0, neighborhood="", category="bar",
                     url="", happy_hour="Mon–Fri 4–7pm", deals="", features=[],
                     rating=4.0, price="$$")
        self.assertTrue(s.has_happy_hour)


class DataIntegrityTests(unittest.TestCase):
    def test_every_spot_has_required_fields(self):
        for raw in bot.SPOTS:
            spot = bot.Spot(**raw)  # will raise if a key is missing/extra
            self.assertTrue(spot.name)
            self.assertTrue(spot.url.startswith("http"))
            self.assertIn(spot.category, {"rooftop", "bar", "restaurant"})
            self.assertIsInstance(spot.features, list)
            self.assertIsInstance(spot.awards, list)
            self.assertIsInstance(spot.runs_late, bool)
            self.assertTrue(0 <= spot.rating <= 5)

    def test_spot_names_unique(self):
        names = [s["name"] for s in bot.SPOTS]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
