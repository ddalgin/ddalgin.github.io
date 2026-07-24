# FinServ Bots

Two stdlib-only Python bots for the Financial Services team:

- **[Monthly Report Bot](#finserv-monthly-report-bot)** — turns a month of
  raw sales numbers into a polished, analyzed report (revenue, discovery,
  wins, pipeline, newsletter).
- **[Events Bot](#finserv-events-bot)** — scans public listings for
  upcoming finserv events in DC / NYC / Philly / Boston.

---

# FinServ Monthly Report Bot

The **"semi design, semi analysis"** bot. It takes one data file per month
and produces the team's monthly report — deriving every downstream figure
from the raw actuals and writing a short narrative that flags what's trailing
and what's winning, so the numbers and the story can't drift apart.

## How it works

`finserv_report_bot.py` (Python 3.11+, stdlib only):

1. **Reads** a month data file — `bot/data/<YYYY-MM>.json` (see
   `bot/data/2026-05.json` for the full shape): revenue actuals, discovery
   calls, wins, deals, newsletter metrics, the leadership note, and upcoming
   events.
2. **Analyzes** — recomputes YoY dollars/percent, running YTD, discovery
   % to goal, a straight-line pace benchmark, and newsletter lift vs.
   benchmark. It never trusts a pre-computed total in the data file; the math
   is reproducible from the inputs. It then stitches a plain-English
   *At a Glance* narrative from those computed numbers.
3. **Designs** — renders a branded, self-contained report page (dark-forest
   masthead, YoY color coding, progress meters, stat cards) matching the
   monthly deck's house look.
4. **Writes** to `reports/`:
   - `<YYYY-MM>.html` — the month's report page
   - `index.html` — landing page linking every month, newest first
   - `latest.md` — plain digest readable on GitHub
   - `report.json` / `<YYYY-MM>.json` — machine-readable, with all derived fields

Served (once on `main`) at <https://ddalgin.github.io/reports/>.

## Add next month's report

Drop a new `bot/data/<YYYY-MM>.json` (copy the May file and update the
numbers) and run the bot — no code changes needed:

```bash
python bot/finserv_report_bot.py                          # newest data file
python bot/finserv_report_bot.py --data bot/data/2026-06.json
python bot/test_report.py                                 # offline tests
```

The May file is seeded from the real May 2026 report; the `--data` file's
`period` block sets the month, and the analysis engine reconciles the rest
(e.g. discovery YTD rolls to 204, revenue YTD to ~$19.49M vs ~$20.41M).

## Schedule

`.github/workflows/finserv-report.yml` rebuilds on the **1st of each month**
(13:00 UTC), on any **push that changes a `bot/data/*.json` file**, and on
demand from the **Actions tab → FinServ Monthly Report → Run workflow**.

> Note: the scheduled trigger only activates once the workflow is on the
> default branch (`main`).

---

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
