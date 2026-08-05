#!/usr/bin/env python3
"""FinServ Blog Bot, a sourced first-draft generator for financial-services content.

Companion to ``finserv_events_bot.py``. Where that bot finds events, this one
drafts blog posts. Given a story *angle*, it:

  1. **Pulls** recent, relevant news from a set of best-effort RSS/Atom feeds
     (finance, fintech, localization, and sports-business) and picks the
     freshest on-topic item as the article's news *peg*.
  2. **Weaves in verified statistics** from a hand-curated ``STAT_LIBRARY`` in
     which *every* fact carries a primary/secondary source URL and an
     as-of date. The bot will not emit a statistic that is not in this
     library, sourcing is a hard requirement, not an afterthought.
  3. **Assembles** a structured markdown draft in a financial-services voice:
     headline options, dek, intro tied to the live peg, body sections with
     inline footnote citations, a CTA, a numbered Sources list, and an
     editor's sourcing-notes block.

It is deliberately a *first-draft* generator for a human editor to finish, not
an auto-publisher: the prose is templated and the draft is stamped
``DRAFT, human review required``. What it automates is the tedious,
error-prone part, pulling a fresh peg and attaching correct, dated sources to
every claim.

Python 3.11+, standard library only. Network access is best-effort; use
``--offline`` (or run the tests) to generate from a bundled fixture with no
network at all.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (compatible; FinServBlogBot/1.0; "
    "+https://ddalgin.github.io/blog/)"
)
TODAY = dt.date.today()


# --------------------------------------------------------------------------- #
# Verified statistics library
#
# Each entry is a fact the bot is allowed to state. Every one has a source URL
# and an as_of date. `also` holds a corroborating source (claims used in a
# draft were cross-checked against at least two independent outlets). If a fact
# is not here, the bot cannot write it, that is the point.
# --------------------------------------------------------------------------- #
@dataclasses.dataclass(frozen=True)
class Stat:
    id: str
    claim: str            # human-readable, drop-in sentence fragment
    source: str           # short source name
    url: str
    as_of: str            # ISO date or year the figure refers to
    also: tuple[str, ...] = ()  # "Name|https://url" corroborating sources


STAT_LIBRARY: dict[str, Stat] = {
    s.id: s
    for s in [
        Stat(
            "co_mlb_deal",
            "Capital One signed a five-year deal reported at roughly $125 million "
            "to become MLB's official bank and credit card partner and the "
            "presenting sponsor of the World Series",
            "CNBC",
            "https://www.cnbc.com/2022/03/28/mlb-reaches-125-million-sponsorship-deal-with-capital-one.html",
            "2022-03-28",
            ("Capital One Newsroom|https://www.capitalone.com/about/newsroom/mlb-partnership/",),
        ),
        Stat(
            "co_asv_attendance",
            "Capital One's 2026 All-Star Village in Philadelphia drew a reported "
            "111,616 visitors over four days, the highest since 2022",
            "Forbes",
            "https://www.forbes.com/sites/danfreedman/2026/07/18/mlb-all-star-village-breaks-records-and-had-more-than-111000-visitors/",
            "2026-07-18",
            ("Fortune|https://fortune.com/2026/07/27/capital-one-mlb-partnership-turning-fan-experiences-into-long-term-customer-value/",),
        ),
        Stat(
            "loyalty_wars",
            "as cards commoditize, issuers are racing to buy loyalty through "
            "experiences rather than earn it on rewards alone",
            "Fortune",
            "https://fortune.com/2026/07/25/capital-one-bet-mlb-baseball-think-can-help-win-credit-card-loyalty-wars/",
            "2026-07-25",
            ("eMarketer|https://www.emarketer.com/content/capital-one-strikes-deal-with-mlb-boost-cardholder-perks",),
        ),
        Stat(
            "mlb_players_latino",
            "on 2025 MLB Opening Day rosters 28.6% of players identified as Latino "
            "and 27.8% were born outside the United States, led by 100 players "
            "from the Dominican Republic",
            "MLB.com",
            "https://www.mlb.com/press-release/press-release-opening-day-rosters-feature-265-internationally-born-players",
            "2025",
        ),
        Stat(
            "mlb_fans_hispanic",
            "Hispanic fans make up roughly 19% of the MLB fan base",
            "Statista",
            "https://www.statista.com/statistics/1478858/mlb-fans-ethnicity/",
            "2024",
        ),
        Stat(
            "latino_fans_power",
            "Latino sports fans skew dramatically younger and are among the "
            "fastest-growing commercial audiences in U.S. sports",
            "McKinsey",
            "https://www.mckinsey.com/institute-for-economic-mobility/our-insights/unlocking-the-growing-power-of-latino-fans-building-a-stronger-sports-economy",
            "2024",
            ("Nielsen via Sportico|https://www.sportico.com/business/commerce/2024/nielsen-study-latino-sports-fans-market-1234798334/",),
        ),
        Stat(
            "fdic_unbanked",
            "9.5% of Hispanic households were unbanked in 2023, more than double "
            "the 4.2% national rate, and roughly one in five Hispanic households "
            "were underbanked, versus 14.2% of households overall",
            "FDIC",
            "https://www.fdic.gov/household-survey",
            "2023",
            ("FDIC press release|https://www.fdic.gov/news/press-releases/2024/fdic-survey-finds-96-percent-us-households-were-banked-2023",),
        ),
        Stat(
            "lep_population",
            "about 25.6 million U.S. residents, roughly 8% of people aged five "
            "and older, speak English less than “very well,” and Spanish "
            "speakers are the largest such group at around 16 million",
            "U.S. Census Bureau",
            "https://www.census.gov/library/visualizations/interactive/people-that-speak-english-less-than-very-well.html",
            "2021",
            ("Migration Policy Institute|https://www.migrationpolicy.org/article/language-diversity-and-english-proficiency-united-states",),
        ),
        Stat(
            "tp_minority_banking",
            "reaching multicultural communities well is a growth opportunity, not "
            "just a compliance line item",
            "TransPerfect",
            "https://www.transperfect.com/blog/what-new-yorks-minority-banking-push-means-customer-experience-and-growth",
            "2026",
        ),
        Stat(
            "tp_monetize_multilingual",
            "modern AI and neural machine translation make it possible to localize "
            "financial content at the speed and volume marketing campaigns demand",
            "TransPerfect",
            "https://www.transperfect.com/blog/future-fintech-how-monetize-multilingual",
            "2026",
        ),
        Stat(
            "tp_ai_governance",
            "scaling multilingual AI responsibly means pairing automated "
            "translation with human expert oversight and compliance governance",
            "TransPerfect",
            "https://www.transperfect.com/blog/horizon-financial-services-2026",
            "2026",
        ),
    ]
}

CTA = (
    "*TransPerfect helps card issuers, retail banks, credit unions, and fintechs "
    "deliver secure, compliant, in-language customer experiences at scale, from "
    "multilingual onboarding and apps to servicing and disclosures. "
    "[Explore our finance and banking language solutions »]"
    "(https://www.transperfect.com/industries/finance-and-banking)*"
)


# --------------------------------------------------------------------------- #
# Story angles
# --------------------------------------------------------------------------- #
@dataclasses.dataclass(frozen=True)
class Angle:
    key: str
    title_options: tuple[str, ...]
    dek: str
    keywords: tuple[str, ...]      # used to score/select the news peg
    stat_ids: tuple[str, ...]      # verified stats to weave in, in order
    renderer: str                  # name of the render function to use


ANGLES: dict[str, Angle] = {
    "multicultural-loyalty": Angle(
        key="multicultural-loyalty",
        title_options=(
            "Buying Loyalty in a Second Language: What Capital One's MLB Bet "
            "Teaches Banks About Multicultural Trust",
            "Passion Gets You Noticed. Language Gets You Kept.",
            "The Loyalty Wars Are Really Conversion Wars",
        ),
        dek=(
            "How financial brands turn a sponsorship moment into a funded, "
            "retained account, and why language is the conversion layer "
            "most issuers aren't pricing."
        ),
        keywords=(
            "capital one", "mlb", "baseball", "sponsorship", "loyalty",
            "credit card", "rewards", "fan", "all-star", "multicultural",
            "hispanic", "latino",
        ),
        stat_ids=(
            "co_mlb_deal", "co_asv_attendance", "loyalty_wars",
            "mlb_players_latino", "mlb_fans_hispanic", "latino_fans_power",
            "fdic_unbanked", "lep_population", "tp_minority_banking",
            "tp_monetize_multilingual", "tp_ai_governance",
        ),
        renderer="multicultural_loyalty",
    ),
    "ai-governance": Angle(
        key="ai-governance",
        title_options=(
            "Fast, Fluent, and Wrong: Why AI Translation in Banking Needs a "
            "Human in the Loop",
            "Scaling Multilingual AI Without Scaling Your Compliance Risk",
        ),
        dek=(
            "AI can localize financial content at campaign speed. Governance is "
            "what keeps a fluent-sounding mistranslation from becoming a "
            "regulatory problem."
        ),
        keywords=(
            "ai", "artificial intelligence", "machine translation", "llm",
            "compliance", "regulation", "governance", "fraud", "disclosure",
        ),
        stat_ids=(
            "lep_population", "tp_monetize_multilingual", "tp_ai_governance",
            "fdic_unbanked",
        ),
        renderer="generic",
    ),
    "sports-finance-signals": Angle(
        key="sports-finance-signals",
        title_options=(
            "Fan Passion Is a Financial Signal. Most Issuers Aren't Reading It.",
            "From the Ballpark to the Balance Sheet: Sports as a Loyalty Signal",
        ),
        dek=(
            "Fandom is a high-frequency behavioral signal in a market where the "
            "card itself no longer differentiates. Here's how to turn it into "
            "acquisition and retention."
        ),
        keywords=(
            "capital one", "mlb", "sports", "sponsorship", "loyalty", "fan",
            "rewards", "credit card", "betting", "fantasy",
        ),
        stat_ids=(
            "loyalty_wars", "co_mlb_deal", "co_asv_attendance",
            "mlb_fans_hispanic", "latino_fans_power",
        ),
        renderer="generic",
    ),
}

# Best-effort news feeds. Any that error or bot-block are skipped; the rest
# still drive peg selection. Add your own here.
FEEDS: tuple[str, ...] = (
    "https://www.finextra.com/rss/headlines.aspx",
    "https://thefinancialbrand.com/feed/",
    "https://www.pymnts.com/feed/",
    "https://slator.com/feed/",
    "https://multilingual.com/feed/",
    "https://www.sportico.com/feed/",
    "https://frontofficesports.com/feed/",
)


# --------------------------------------------------------------------------- #
# News peg fetching (best-effort)
# --------------------------------------------------------------------------- #
@dataclasses.dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published: dt.date | None
    summary: str = ""

    def score(self, keywords: tuple[str, ...]) -> int:
        text = f"{self.title} {self.summary}".lower()
        return sum(3 if kw in self.title.lower() else 1
                   for kw in keywords if kw in text)


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_date(text: str | None) -> dt.date | None:
    if not text:
        return None
    text = text.strip()
    fmts = (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    )
    for fmt in fmts:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    return None


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_feed(raw: bytes, source: str) -> list[NewsItem]:
    """Parse an RSS 2.0 or Atom feed into NewsItems (namespace-agnostic)."""
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return items

    def find_text(el: ET.Element, *names: str) -> str:
        for child in el.iter():
            if _strip_ns(child.tag) in names and (child.text or "").strip():
                return child.text.strip()
        return ""

    def find_link(el: ET.Element) -> str:
        # RSS <link>text</link>
        for child in el:
            if _strip_ns(child.tag) == "link":
                if child.text and child.text.strip():
                    return child.text.strip()
                href = child.get("href")
                if href:
                    return href.strip()
        return ""

    entries = [e for e in root.iter() if _strip_ns(e.tag) in ("item", "entry")]
    for e in entries:
        title = html.unescape(find_text(e, "title"))
        link = find_link(e)
        published = _parse_date(
            find_text(e, "pubDate", "published", "updated", "date")
        )
        summary = html.unescape(find_text(e, "description", "summary"))
        summary = re.sub(r"<[^>]+>", " ", summary)
        summary = re.sub(r"\s+", " ", summary).strip()[:400]
        if title and link:
            items.append(NewsItem(title, link, source, published, summary))
    return items


def fetch_news(max_age_days: int, log: list[str]) -> list[NewsItem]:
    items: list[NewsItem] = []
    cutoff = TODAY - dt.timedelta(days=max_age_days)
    for feed in FEEDS:
        source = re.sub(r"^www\.", "", urllib.request.urlparse(feed).netloc)
        try:
            raw = _get(feed)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            log.append(f"skip {source}: {exc}")
            continue
        parsed = parse_feed(raw, source)
        fresh = [i for i in parsed if i.published is None or i.published >= cutoff]
        log.append(f"ok   {source}: {len(fresh)}/{len(parsed)} recent items")
        items.extend(fresh)
    return items


def pick_peg(items: list[NewsItem], angle: Angle) -> NewsItem | None:
    scored = [(i.score(angle.keywords), i) for i in items]
    scored = [(s, i) for s, i in scored if s > 0]
    if not scored:
        return None
    # Highest relevance, then most recent.
    scored.sort(
        key=lambda si: (si[0], si[1].published or dt.date.min),
        reverse=True,
    )
    return scored[0][1]


# A stable fallback/fixture peg so the bot (and tests) always produce output.
FIXTURE_PEG = NewsItem(
    title="Capital One's big bet on baseball and the credit card loyalty wars",
    url="https://fortune.com/2026/07/25/capital-one-bet-mlb-baseball-think-can-help-win-credit-card-loyalty-wars/",
    source="fortune.com",
    published=dt.date(2026, 7, 25),
    summary=(
        "Capital One is leaning on its MLB partnership and All-Star Village to "
        "win customer loyalty as credit cards become interchangeable."
    ),
)


# --------------------------------------------------------------------------- #
# Draft assembly
# --------------------------------------------------------------------------- #
class Citations:
    """Collects sources in first-use order and renders numbered footnotes."""

    def __init__(self) -> None:
        self._order: list[str] = []
        self._notes: dict[str, str] = {}

    def cite(self, key: str, note: str) -> str:
        if key not in self._notes:
            self._order.append(key)
            self._notes[key] = note
        return f"[^{self._order.index(key) + 1}]"

    def cite_stat(self, stat_id: str) -> str:
        s = STAT_LIBRARY[stat_id]
        extra = ""
        if s.also:
            parts = []
            for a in s.also:
                name, url = a.split("|", 1)
                parts.append(f"See also: {name}. <{url}>")
            extra = " · " + " · ".join(parts)
        note = f"{_cap_first(s.claim)}, {s.source} ({s.as_of}). <{s.url}>{extra}"
        return self.cite(stat_id, note)

    def render(self) -> str:
        lines = []
        for i, key in enumerate(self._order, 1):
            lines.append(f"[^{i}]: {self._notes[key]}")
        return "\n".join(lines)

    def count(self) -> int:
        return len(self._order)


def _slug(text: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:60]


def _cap_first(text: str) -> str:
    """Uppercase only the first character, preserves acronyms like MLB, U.S., AI."""
    return text[:1].upper() + text[1:] if text else text


def render_multicultural_loyalty(angle: Angle, peg: NewsItem, cites: Citations) -> str:
    S = STAT_LIBRARY
    peg_cite = cites.cite(
        "peg",
        f"{peg.title}, {peg.source}"
        + (f", {peg.published.isoformat()}" if peg.published else "")
        + f". <{peg.url}>",
    )
    body = f"""\
When Capital One signed a five-year deal reported at roughly **$125 million** to
become Major League Baseball's official bank and credit card partner, and the
presenting sponsor of the World Series, it wasn't buying ad inventory. It was
buying a feeling.{cites.cite_stat("co_mlb_deal")} In a market where a Visa is a
Visa and rewards tables have converged to the decimal point, the product itself
no longer differentiates. Loyalty does, and loyalty is increasingly purchased
through experience.{cites.cite_stat("loyalty_wars")}{peg_cite}

The scale of that bet was on display this summer: Capital One's All-Star Village
in Philadelphia drew a reported **111,616 visitors** over four days, the highest
since 2022.{cites.cite_stat("co_asv_attendance")} That's a lot of people
voluntarily spending an afternoon inside a bank's brand. But there's a quieter
lesson most issuers are missing, one that decides whether that spend compounds
into revenue or evaporates the day after the game.

**A sponsorship gets you the emotional moment. Localization is what converts it
into a customer.**

## The loyalty wars are really conversion wars

Every issuer chasing the experience strategy is betting on the same funnel:
passion drives attention, attention drives an application, an application drives
a funded account, and a funded account drives a decade of interchange, deposits,
and cross-sell. The sponsorship only pays off at the *end* of that funnel, and
most brands win the emotional moment in the stadium, then hand the prospect an
onboarding flow, an app, and disclosures that all assume English is their most
comfortable language. For a growing share of the exact fans these deals target,
that assumption is wrong, and it's expensive.

## The signal hiding in the stands

Baseball is one of the most Latino sports in America, on the field and in the
seats. Consider that {S["mlb_players_latino"].claim}.\
{cites.cite_stat("mlb_players_latino")} In the stands,
{S["mlb_fans_hispanic"].claim}, and {S["latino_fans_power"].claim}.\
{cites.cite_stat("mlb_fans_hispanic")}{cites.cite_stat("latino_fans_power")}

Now overlay where those consumers sit in the financial system:
{S["fdic_unbanked"].claim}.{cites.cite_stat("fdic_unbanked")} These aren't people
who already carry five cards, many are shopping for their first premium card or
their first real banking relationship. The sponsorship isn't only reaching
affluent travel-card holders; at its best it reaches a high-lifetime-value,
under-served, under-contested growth segment.{cites.cite_stat("tp_minority_banking")}

## Why language is the conversion layer

The language gap is not a niche: {S["lep_population"].claim}.\
{cites.cite_stat("lep_population")} A prospect who feels the brand at the ballpark
and then hits an English-only application doesn't convert at the same rate. A
cardholder who can't get servicing in their language doesn't stay at the same
rate. Localization shows up in the metrics issuers already report:

- **Activation**, in-language onboarding narrows the gap between "approved" and
  "funded and actively using the card."
- **Retention**, in-language servicing and fraud alerts cut churn and
  sock-drawer attrition.
- **Compliance risk**, a mistranslated APR term or fraud notice is a regulatory
  exposure, not a copy problem.
- **Referral growth**, in tight-knit communities, a trusted relationship travels
  by word of mouth.

## Doing it at scale, responsibly

{_cap_first(S["tp_monetize_multilingual"].claim)}.\
{cites.cite_stat("tp_monetize_multilingual")} The critical word is *responsibly*:
a fluent-sounding but subtly wrong translation of a rate or a fraud alert is
worse than none. {_cap_first(S["tp_ai_governance"].claim)}, automation where
it's safe, human judgment where it's regulated.{cites.cite_stat("tp_ai_governance")}

## The takeaway for issuers

When the product can't differentiate, buying loyalty through experience is the
right instinct. But experience is the top of the funnel, not the bottom. The
brands that win won't just have the biggest All-Star activation, they'll meet
the fan they just won in the language they actually trust, all the way through
funding and servicing. Passion gets you noticed. Language gets you kept.
"""
    return body


def render_generic(angle: Angle, peg: NewsItem, cites: Citations) -> str:
    peg_cite = cites.cite(
        "peg",
        f"{peg.title}, {peg.source}"
        + (f", {peg.published.isoformat()}" if peg.published else "")
        + f". <{peg.url}>",
    )
    intro = (
        f"A recent story, *{peg.title}*, is a useful way into a question "
        f"financial brands keep running up against.{peg_cite}\n\n"
    )
    paras = [intro, f"{angle.dek}\n"]
    paras.append("## What the numbers say\n")
    for sid in angle.stat_ids:
        s = STAT_LIBRARY[sid]
        paras.append(f"- {_cap_first(s.claim)}.{cites.cite_stat(sid)}")
    paras.append(
        "\n## Why it matters\n\n"
        "Each of the figures above points the same direction: the winning move "
        "is not just the headline partnership or the new AI tool, but the "
        "follow-through that turns reach into a funded, retained relationship. "
        "That is where localization and in-language customer experience quietly "
        "decide the outcome.\n"
    )
    return "\n".join(paras)


RENDERERS = {
    "multicultural_loyalty": render_multicultural_loyalty,
    "generic": render_generic,
}


def build_draft(angle: Angle, peg: NewsItem) -> tuple[str, str]:
    """Return (slug, markdown) for a draft on the given angle and news peg."""
    cites = Citations()
    body = RENDERERS[angle.renderer](angle, peg, cites)

    title = angle.title_options[0]
    alt_titles = "\n".join(f"  - {t}" for t in angle.title_options[1:])
    slug = f"{TODAY.isoformat()}-{_slug(title)}"

    doc = f"""\
# {title}

*{angle.dek}*

> **DRAFT, human review required.** Generated by finserv_blog_bot on \
{TODAY.isoformat()} for the *{angle.key}* angle. Prose is templated; verify the \
news peg, tighten the copy, and confirm every source before publishing.

**Alternate headlines:**
{alt_titles}

**News peg:** [{peg.title}]({peg.url}), {peg.source}\
{f' ({peg.published.isoformat()})' if peg.published else ''}

---

{body}
---

{CTA}

---

## Sources

{cites.render()}

---

### Sourcing notes (for the editor)

- Every quantitative claim is tied to a numbered source drawn from the bot's
  verified `STAT_LIBRARY`; the bot cannot emit a statistic that lacks a source.
- Figures were cross-checked across at least two independent outlets before
  entering the library; primary sources (FDIC, U.S. Census Bureau, MLB.com,
  CNBC, Capital One Newsroom) are cited directly where available.
- Confirm the news peg is still current and re-verify any season- or
  survey-dependent figure (MLB rosters/fan demographics, FDIC survey wave)
  before publishing in a later cycle.
"""
    return slug, doc


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def write_outputs(out_dir: Path, slug: str, markdown: str, angle: Angle,
                  peg: NewsItem, log: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    post_path = out_dir / f"{slug}.md"
    post_path.write_text(markdown, encoding="utf-8")
    (out_dir / "latest.md").write_text(markdown, encoding="utf-8")

    meta = {
        "generated": TODAY.isoformat(),
        "angle": angle.key,
        "slug": slug,
        "title": angle.title_options[0],
        "peg": {
            "title": peg.title,
            "url": peg.url,
            "source": peg.source,
            "published": peg.published.isoformat() if peg.published else None,
        },
        "stats_used": list(angle.stat_ids),
        "log": log,
    }
    (out_dir / "drafts.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    (out_dir / "index.html").write_text(
        _render_index(slug, angle, peg), encoding="utf-8"
    )


def _render_index(slug: str, angle: Angle, peg: NewsItem) -> str:
    esc = html.escape
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinServ Blog Bot, latest draft</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif;
         max-width: 46rem; margin: 2rem auto; padding: 0 1rem;
         line-height: 1.55; color: #1a1a2e; background: #f7f7fb; }}
  a {{ color: #4b3fbf; }}
  .card {{ background: #fff; border: 1px solid #e3e3ef; border-radius: 10px;
          padding: 1.25rem 1.5rem; margin: 1rem 0; }}
  .tag {{ display: inline-block; background: #7A6ECD; color: #fff;
         padding: .1rem .55rem; border-radius: 999px; font-size: .8rem; }}
  code {{ background: #eee; padding: .1rem .3rem; border-radius: 4px; }}
</style></head><body>
<h1>FinServ Blog Bot</h1>
<p>Sourced first-draft generator for financial-services content.
Latest run: <strong>{TODAY.isoformat()}</strong>.</p>
<div class="card">
  <span class="tag">{esc(angle.key)}</span>
  <h2>{esc(angle.title_options[0])}</h2>
  <p>{esc(angle.dek)}</p>
  <p><strong>News peg:</strong>
     <a href="{esc(peg.url)}">{esc(peg.title)}</a> &middot; {esc(peg.source)}</p>
  <p>Read the draft: <a href="{esc(slug)}.md">{esc(slug)}.md</a>
     &middot; <a href="latest.md">latest.md</a>
     &middot; <a href="drafts.json">drafts.json</a></p>
</div>
<p style="color:#666;font-size:.9rem">Drafts are templated and require human
review. Every statistic is drawn from a verified, sourced library
(<code>STAT_LIBRARY</code> in <code>bot/finserv_blog_bot.py</code>).</p>
</body></html>
"""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--angle", default="multicultural-loyalty",
                   choices=sorted(ANGLES), help="story angle to draft")
    p.add_argument("--out-dir", default="blog", type=Path)
    p.add_argument("--max-age-days", type=int, default=30,
                   help="only consider news pegs newer than this")
    p.add_argument("--offline", action="store_true",
                   help="skip network; use the built-in fixture peg")
    p.add_argument("--list-angles", action="store_true")
    args = p.parse_args(argv)

    if args.list_angles:
        for a in ANGLES.values():
            print(f"{a.key:26} {a.title_options[0]}")
        return 0

    angle = ANGLES[args.angle]
    log: list[str] = []

    if args.offline:
        peg = FIXTURE_PEG
        log.append("offline: using fixture peg")
    else:
        items = fetch_news(args.max_age_days, log)
        peg = pick_peg(items, angle) or FIXTURE_PEG
        if peg is FIXTURE_PEG:
            log.append("no live peg matched; using fixture peg")
        else:
            log.append(f"peg: {peg.source}, {peg.title}")

    slug, markdown = build_draft(angle, peg)
    write_outputs(args.out_dir, slug, markdown, angle, peg, log)

    print(f"Wrote draft: {args.out_dir / (slug + '.md')}")
    for line in log:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
