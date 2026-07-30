> This folder holds two bots: the **FinServ Events Bot** (below) and the
> **[Personal Finance Bot](#personal-finance-bot)**.

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

# Personal Finance Bot

Turns a plain-JSON snapshot of your money into a dashboard. `finance_bot.py`
does all the arithmetic the old spreadsheet did — **net worth**, **net liquid
position** (your true cash cushion, cash minus card debt), **debt payoff order**,
a month-by-month **pay-in-full calendar** with a running balance, **emergency-fund
tiers**, **surplus allocation**, and **goal / match tracking** — and writes:

- `finance/index.html` — the dashboard (KPI tiles, tables, progress bars)
- `finance/finance.json` — the snapshot plus every computed figure
- `finance/latest.md` — a plain-text digest, readable on GitHub

Stdlib only — nothing to install.

## 🔒 Privacy — read this first

`ddalgin.github.io` is a **public** website. So the bot keeps your real numbers
out of the repo:

- **Committed (public):** the bot code and `bot/finance_data.sample.json` —
  obviously-fake numbers. The demo at `finance/index.html` is built from that
  sample and shows a "sample data" banner.
- **Local only (gitignored, never pushed):** `finance/data.json` (your real
  figures) and `finance/private/` (your real dashboard). Both are listed in
  `.gitignore`.

## Your real dashboard (local)

Your real numbers already live in `finance/data.json`. Edit that file, then:

```bash
python bot/finance_bot.py --data finance/data.json --out-dir finance/private
open finance/private/index.html      # macOS; or just double-click it
```

Nothing you build this way is tracked by git, so real figures can't be pushed
by accident.

## Rebuild the public sample demo

```bash
python bot/finance_bot.py                 # sample -> finance/
python bot/test_finance.py                # offline arithmetic tests
```

## Updating your numbers

Everything is edited in `finance/data.json` — no code changes needed:

- `cash_accounts` — set `"ringfenced": true` on accounts the pay-in-full plan
  should not touch (they still count toward net worth).
- `cards` — balances, amounts due, due dates, and optional `apr`. Payoff order
  is smallest-balance-first; if APRs vary a lot, pay highest-APR first instead.
- `income` / `outflows` — surplus, the allocation split, and the emergency-fund
  tiers all derive from these. `variable` outflow is usually your biggest
  unknown; refine it.
- `plan.entries` — the dated calendar. The bot computes the running balance
  column and totals; the first entry is the opening balance.
- `trip_fund`, `retirement`, `monthly_log` — goals, employer match, and a
  month-end log whose column totals are summed for you.

## Want to publish it instead?

If you ever decide the dashboard should be public, build it into `finance/`
(not `finance/private/`) with your real data and remove the `finance/data.json`
line from `.gitignore`. Only do that if you're comfortable with your balances
being on the open web and indexed by search engines.
