# FinServ Events Bot

Finds upcoming **financial services events** — networking mixers, panels,
meetups, summits — in **Washington DC, NYC, Philadelphia, and Boston**, and
filters out the expensive ones (default: minimum ticket ≤ $150; free events
are highlighted).

## How it works

`finserv_events_bot.py` (Python 3.11+, stdlib only — nothing to install):

1. **Fetches** public listings from three sources, per city:
   - **Eventbrite** search pages (parses the JSON payload embedded in the page)
   - **10times.com** banking-finance city listings (parses schema.org JSON-LD)
   - **Gary's Guide** (NYC tech/finance calendar)
2. **Scores** each event for finserv relevance using weighted keywords
   (fintech, banking, capital markets, payments, …) with negative weights
   that weed out personal-finance / get-rich-quick seminar spam.
3. **Filters** to in-person events in the next 75 days at or under the price
   cap, dedupes, and sorts by date.
4. **Writes** to `events/`:
   - `index.html` — browsable page, live at <https://ddalgin.github.io/events/>
   - `events.json` — machine-readable results
   - `latest.md` — plain digest readable on GitHub

Every source is best-effort: if one errors or bot-blocks the run, the others
still work and the failure is listed in the page footer and the run log.

## Schedule

`.github/workflows/finserv-events.yml` runs the bot **Mondays and Thursdays
at 12:00 UTC** and commits any changes. You can also run it on demand from
the **Actions tab → FinServ Events Bot → Run workflow**, optionally
overriding the price cap and date window.

> Note: the scheduled trigger only activates once the workflow is on the
> default branch (`main`).

## Run locally

```bash
python bot/finserv_events_bot.py                    # defaults: $150, 75 days
python bot/finserv_events_bot.py --max-price 50 --days 45
python bot/test_parsers.py                          # offline tests
```

## Tuning

- **Cities/sources**: edit `CITIES` in `finserv_events_bot.py`.
- **Search terms**: edit `SEARCH_TERMS`.
- **Relevance**: edit `KEYWORD_WEIGHTS` / `NEGATIVE_WEIGHTS`, or raise
  `--min-score` (default 2) if too much noise gets through.
- **Price cap**: `--max-price` (default 150).

## Known limitations / ideas

- Eventbrite sometimes bot-blocks datacenter IPs; when that happens the run
  falls back to the other sources and reports it. If it becomes chronic,
  good next sources: Luma (lu.ma) city pages, Meetup, and the CFA Society
  calendars for each of the four cities.
- Prices reflect the *minimum* listed ticket at scan time.
