# DC Happy Hour Bot

Ranks the best **happy-hour bars, rooftops, and restaurants in Washington DC**
by **walking distance** from a chosen starting point (default: the office at
**1001 G St NW**, on top of Metro Center) plus **rooftop / view / deal
quality**.

Built for the "where should we go after work?" question — especially _"best
rooftop near Metro Center."_

## How it works

`happy_hour_bot.py` (Python 3.11+, stdlib only — nothing to install):

1. **Curated dataset** — a hand-vetted list of ~31 spots across DC (downtown,
   Penn Quarter, Chinatown, Wharf, Dupont, Shaw, U Street, H Street, Capitol
   Hill, Adams Morgan, Brookland) with coordinates, happy-hour windows, deals,
   ratings, price, feature tags, and 🏆 **"Best of DC" awards** from
   [@theblaguard](https://www.instagram.com/theblaguard/)'s Food & Drink poll
   (Best Bar, Best Happy Hour, Best Burger, Best Wings, Best Sports Bar, Best
   Dive Bar, Best Irish Pub, Best Bar Food). Unlike a live scrape, it never
   breaks when a venue site blocks bots.
2. **Distance** — computes crow-flies distance (haversine) from the chosen
   origin, applies a 1.35× street factor, and estimates walking minutes.
3. **Ranks** with a transparent composite score. Two modes:
   - `quality` (default) — city-wide: venue rating + 🏆 award weight
     (winner 5 pts, runner-up 3 pts, stacking) + feature desirability +
     requested-feature boost + a nudge for a standing happy hour, with walk
     time as a light tiebreak.
   - `proximity` — walk time from the origin dominates (the original
     "closest good happy hour" behavior).
4. **Writes** to `happyhour/`:
   - `index.html` — browsable ranked page, live at
     <https://ddalgin.github.io/happyhour/>
   - `happyhour.json` — machine-readable results
   - `latest.md` — plain digest readable on GitHub

## Run locally

```bash
python bot/happy_hour_bot.py                          # city-wide, best by rating + awards
python bot/happy_hour_bot.py --awards-only            # only "Best of DC" award venues
python bot/happy_hour_bot.py --rank-by proximity      # closest good happy hours to the office
python bot/happy_hour_bot.py --category rooftop       # rooftops only
python bot/happy_hour_bot.py --features view,outdoor  # prioritize views + patios
python bot/happy_hour_bot.py --happy-hour-only --max-walk 10 --rank-by proximity
python bot/happy_hour_bot.py --origin the_wharf --top 5
python bot/test_happy_hour.py                         # offline tests
```

### Options

| Flag | Purpose |
|------|---------|
| `--origin` | Start point: `office` (default), `metro_center`, `white_house`, `chinatown`, `the_wharf`, `union_station` |
| `--rank-by` | `quality` (default, city-wide by rating/awards) or `proximity` (by walk time) |
| `--category` | `all` (default), `rooftop`, `bar`, `restaurant` |
| `--features` | Comma-separated features to prioritize, e.g. `rooftop,view,outdoor` |
| `--require-features` | Hard-filter to spots that have ALL `--features` (default: features only boost ranking) |
| `--max-walk` | Drop spots farther than N minutes on foot |
| `--happy-hour-only` | Only spots with a standing happy hour |
| `--awards-only` | Only spots that won a "Best of DC" award |
| `--top` | Keep only the top N results |

## Schedule

`.github/workflows/happy-hour.yml` runs the bot **Fridays at 15:00 UTC** and
commits any changes. You can also run it on demand from the **Actions tab →
Happy Hour Bot → Run workflow**, overriding origin / category / features.

> The scheduled trigger only activates once the workflow is on the default
> branch (`main`).

## Tuning / adding spots

Add or edit entries in the `SPOTS` list in `happy_hour_bot.py` (name, lat/lng,
neighborhood, category, url, happy-hour window, deals, features, rating,
price, notes). Adjust `FEATURE_BONUS` to change how much rooftops/views/etc.
weigh in the score. `python bot/test_happy_hour.py` guards the data shape and
ranking logic.

> Happy-hour times and deals change often — the bot links each venue's page;
> always confirm before you go.
