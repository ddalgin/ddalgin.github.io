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

---

# Apollo Feeder Bot

A sibling bot for **prospecting**, not events. `apollo_feeder_bot.py` talks to
the **Apollo.io API** to build a prioritized pipeline of **global, deep-pocket
financial-services firms** and the senior buyers inside them, exports an
**Apollo-ready contact list**, and can **analyze an exported sequence-stats CSV**
to help optimize your Apollo sequences.

## How it works

1. **Account search** (`POST /api/v1/mixed_companies/search`): large,
   high-revenue financial-services orgs across the world's financial hubs
   (New York, London, Hong Kong, Singapore, Zurich, Frankfurt, Tokyo, …).
   Each account is scored for **"deep pockets"** — revenue, headcount,
   subsector (asset management / IB / PE / hedge fund score highest), funding —
   and bucketed **Whale / Priority / Standard**.
2. **People search** (`POST /api/v1/mixed_people/search`): senior
   decision-makers (C-suite / VP / Head / Director across CIO, CFO, COO, CTO,
   Head of Data/Trading/Wealth/Compliance/Procurement, …) inside those
   accounts.
3. **Feed**: writes `apollo/apollo_import.csv` to import into an Apollo list,
   or with `--create-list "NAME"` pushes the contacts straight into Apollo
   (`POST /api/v1/contacts` under a list label).
4. **Sequence analysis**: with `--sequence-csv PATH`, ingests an exported
   Apollo sequence-stats CSV (fuzzy column matching), derives per-step
   open/reply/bounce rates, and writes findings + recommendations (weak steps,
   deliverability/bounce problems, best-performing step, subject-line length).

Outputs to `apollo/` (served at <https://ddalgin.github.io/apollo/>):
`accounts.json`, `contacts.json`, `apollo_import.csv`, `index.html`,
`latest.md`, and `sequence_analysis.md` (when a sequence CSV is supplied).

Like the events bot, every API call is best-effort: an error (rate limit,
auth, network) is reported in the dashboard/log instead of killing the run.

## The API key (required for the search half)

The key is read from the **`APOLLO_API_KEY`** environment variable and is
never hard-coded. In CI it comes from a repo secret:

**Settings → Secrets and variables → Actions → New repository secret →
`APOLLO_API_KEY`.**

Without a key the bot skips the API calls, still writes a valid dashboard
noting the status, and still runs the sequence analysis if a CSV was given.

> **Credits & safety.** By default the bot only *reads* from Apollo (search)
> and exports a CSV — it never mutates your workspace. `--create-list` (writes
> contacts) and `--enrich` (reveals emails, reserved) consume Apollo credits
> and are opt-in. People Search returns locked email placeholders; the CSV
> leaves email blank and you enrich inside Apollo.

## Schedule

`.github/workflows/apollo-feeder.yml` runs **Mondays and Thursdays at 13:00
UTC** and commits any changes. Run on demand from **Actions → Apollo Feeder
Bot → Run workflow**, overriding pages, minimum revenue, or a list name.

## Run locally

```bash
export APOLLO_API_KEY=...                              # your Apollo API key
python bot/apollo_feeder_bot.py                        # search + export CSV
python bot/apollo_feeder_bot.py --pages 3 --min-revenue 1000000000
python bot/apollo_feeder_bot.py --create-list "Q3 FinServ Whales"   # push to Apollo
python bot/apollo_feeder_bot.py --sequence-csv exports/seq.csv      # analysis (no key needed)
python bot/test_apollo_feeder.py                       # offline tests
```

## Tuning

- **Targeting**: edit `FINSERV_KEYWORDS`, `FINANCIAL_HUBS`, `EMPLOYEE_RANGES`
  in `apollo_feeder_bot.py`.
- **Personas**: edit `PERSONA_TITLES` / `PERSONA_SENIORITIES`.
- **Deep-pockets scoring**: edit `SUBSECTOR_WEIGHTS` and the thresholds in
  `score_account()` (revenue/headcount tiers, Whale/Priority cutoffs).
- **Revenue floor**: `--min-revenue` (default $500M).

## Known limitations / ideas

- The Apollo endpoint/field names follow Apollo's documented v1 API; if Apollo
  changes a field, the parser degrades gracefully (missing values → `None`)
  and the run is still reported. Adjust `_org_fields` / `_person_fields` to
  track any changes.
- People Search does not return verified emails — enrich inside Apollo (or
  wire up `POST /api/v1/people/match` behind the reserved `--enrich` flag).
- Good next steps: pull live sequence stats via the Apollo sequences API
  instead of a CSV export, and add intent/technographic filters (hiring
  signals, tech stack) to sharpen the "deep pockets" score.
