# FinServ Bots

Two standalone, stdlib-only bots for financial-services content:

- **[FinServ Events Bot](#finserv-events-bot)** — finds upcoming finserv events.
- **[FinServ Blog Bot](#finserv-blog-bot)** — drafts sourced blog posts.

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

---

# FinServ Blog Bot

Drafts **sourced financial-services blog posts** in a localization/CX voice
(built for a TransPerfect-style finance blog). It's a *first-draft generator
with rigorous sourcing*, not an auto-publisher: it pulls a fresh news peg and
attaches a correct, dated source to every factual claim, then leaves the polish
to a human editor.

## How it works

`finserv_blog_bot.py` (Python 3.11+, stdlib only):

1. **Pulls** recent items from best-effort RSS/Atom feeds (Finextra, The
   Financial Brand, PYMNTS, Slator, MultiLingual, Sportico, Front Office
   Sports) and picks the freshest on-topic story as the article's news *peg*.
2. **Weaves in verified statistics** from a hand-curated `STAT_LIBRARY` where
   **every fact carries a source URL and an as-of date**, cross-checked against
   at least two independent outlets. The bot *cannot* emit a statistic that
   isn't in this library — sourcing is a hard constraint. Primary sources
   (FDIC, U.S. Census Bureau, MLB.com, CNBC, Capital One Newsroom) are cited
   directly where available.
3. **Assembles** a structured markdown draft: headline options, dek, an intro
   tied to the live peg, body sections with inline footnote citations, a CTA,
   a numbered Sources list, and an editor's sourcing-notes block. The draft is
   stamped `DRAFT — human review required`.
4. **Writes** to `blog/`:
   - `<date>-<slug>.md` — the dated draft
   - `latest.md` — the newest draft
   - `drafts.json` — machine-readable metadata (peg, stats used, run log)
   - `index.html` — browsable summary, live at
     <https://ddalgin.github.io/blog/>

Network is best-effort: if every feed bot-blocks the run, the bot falls back to
a built-in fixture peg and still produces a complete, sourced draft.

## Story angles

Pick one with `--angle` (see them with `--list-angles`):

- `multicultural-loyalty` *(flagship)* — Capital One's MLB bet as the case for
  in-language CX as the conversion layer. Fully hand-finished companion post:
  [`blog/2026-capital-one-mlb-multilingual-loyalty.md`](../blog/2026-capital-one-mlb-multilingual-loyalty.md).
- `ai-governance` — scaling multilingual AI in banking without scaling risk.
- `sports-finance-signals` — fandom as a loyalty/acquisition signal.

## Schedule

`.github/workflows/finserv-blog.yml` runs the bot **Tuesdays at 13:00 UTC** and
commits any changes. You can also run it on demand from the **Actions tab →
FinServ Blog Bot → Run workflow**, choosing the angle and news-peg window.

> Note: the scheduled trigger only activates once the workflow is on the
> default branch (`main`).

## Run locally

```bash
python bot/finserv_blog_bot.py                          # flagship angle, live pegs
python bot/finserv_blog_bot.py --angle ai-governance
python bot/finserv_blog_bot.py --offline                # no network; fixture peg
python bot/finserv_blog_bot.py --list-angles
python bot/test_blog_bot.py                             # offline tests
```

## Adding facts and angles

- **New citable fact**: add a `Stat(...)` to `STAT_LIBRARY` — always with a
  `source`, `url`, and `as_of`, and a corroborating source in `also=(...)`.
- **New angle**: add an `Angle(...)` to `ANGLES` with its keywords (for peg
  selection), the ordered `stat_ids` to include, and a renderer
  (`multicultural_loyalty` for bespoke prose, or `generic` for a scaffold).
- **New feeds**: add URLs to `FEEDS`.

## Known limitations / ideas

- Prose is templated; the bot guarantees *sourcing*, not *style*. Treat output
  as a first draft to edit, never as publish-ready copy.
- Re-verify season- or survey-dependent figures (MLB rosters/fan demographics,
  FDIC survey wave) before publishing in a later cycle.
- Good next step: an LLM pass over the templated draft for fluency, keeping the
  verified `STAT_LIBRARY` as the sourcing guardrail.
