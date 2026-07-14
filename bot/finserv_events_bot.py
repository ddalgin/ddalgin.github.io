#!/usr/bin/env python3
"""FinServ Events Bot.

Scans public event listings for financial-services events (meetups, panels,
mixers, summits) in Washington DC, New York City, Philadelphia, and Boston,
keeps the free / reasonably priced ones, and writes:

  events/events.json  - machine-readable results
  events/index.html   - browsable page (served by GitHub Pages at /events/)
  events/latest.md    - plain-text digest, easy to read on GitHub

Stdlib only - no pip installs needed. Every source is best-effort: a source
that errors or gets bot-blocked is reported in the output instead of killing
the run.

Usage:
  python bot/finserv_events_bot.py                 # scan and write ./events/
  python bot/finserv_events_bot.py --max-price 50 --days 45
"""

from __future__ import annotations

import argparse
import gzip
import html as htmllib
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------- config ---

CITIES = {
    "Washington DC": {
        "eventbrite_slug": "dc--washington",
        "tentimes_slug": "washington-us",
        "luma_slugs": ["dc", "washington-dc"],
    },
    "New York City": {
        "eventbrite_slug": "ny--new-york",
        "tentimes_slug": "newyork-us",
        "luma_slugs": ["nyc", "new-york"],
        "garysguide": True,  # Gary's Guide covers NYC only
    },
    "Philadelphia": {
        "eventbrite_slug": "pa--philadelphia",
        "tentimes_slug": "philadelphia-us",
        "luma_slugs": ["philadelphia", "philly"],
    },
    "Boston": {
        "eventbrite_slug": "ma--boston",
        "tentimes_slug": "boston-us",
        "luma_slugs": ["boston"],
    },
}

# Search terms used against keyword-search sources (one request per term per
# city on Eventbrite). Broad terms are fine; the relevance scorer prunes.
SEARCH_TERMS = ["fintech", "financial services", "banking", "capital markets"]

# Relevance scoring over title + description. An event is kept when its
# score meets --min-score. Positive terms indicate industry events where
# finserv companies show up; negative terms weed out the personal-finance /
# get-rich seminar spam that dominates "finance" searches on Eventbrite.
KEYWORD_WEIGHTS = {
    "financial services": 4,
    "fintech": 4,
    "capital markets": 4,
    "asset management": 4,
    "wealth management": 3,
    "hedge fund": 3,
    "private equity": 3,
    "venture capital": 2,
    "insurtech": 4,
    "regtech": 4,
    "banking": 3,
    "bankers": 3,
    "payments": 3,
    "lending": 2,
    "underwriting": 2,
    "treasury": 2,
    "trading": 2,
    "investment": 2,
    "investor": 1,
    "insurance": 2,
    "compliance": 2,
    "risk management": 2,
    "cfa": 3,
    "fdic": 3,
    "federal reserve": 3,
    "sec ": 1,
    "finance": 2,
    "financial": 1,
    "credit union": 3,
    "wall street": 2,
    "quant": 2,
    "actuarial": 2,
    "blockchain": 1,
    "crypto": 1,
    "digital assets": 2,
    "stablecoin": 3,
    "onchain": 2,
    "defi": 2,
    "money20/20": 4,
    "money 20/20": 4,
    " vc ": 2,
    "angel investor": 2,
    "financial technology": 4,
    "networking": 1,
    "summit": 1,
    "conference": 1,
    "mixer": 1,
    "happy hour": 1,
}

NEGATIVE_WEIGHTS = {
    "personal finance": -4,
    "financial freedom": -5,
    "financial literacy": -3,
    "credit repair": -6,
    "build your credit": -6,
    "real estate invest": -4,
    "homebuyer": -6,
    "home buyer": -6,
    "wholesaling": -6,
    "passive income": -5,
    "get rich": -6,
    "millionaire": -5,
    "manifest": -6,
    "forex": -4,
    "day trading": -3,
    "trading class": -4,
    "retirement planning": -3,
    "estate planning": -4,
    "tax prep": -4,
    "mlm": -6,
    "network marketing": -6,
    "grant writing": -4,
    "notary": -6,
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# --------------------------------------------------------------- helpers ---


@dataclass
class Event:
    title: str
    url: str
    start: str  # ISO date YYYY-MM-DD (best effort)
    city: str
    source: str
    venue: str = ""
    description: str = ""
    price_min: float | None = None  # None = unknown
    is_free: bool | None = None
    score: int = 0
    matched: list[str] = field(default_factory=list)


@dataclass
class SourceStatus:
    source: str
    city: str
    ok: bool
    detail: str = ""
    found: int = 0


# When set (via --debug-dump), every fetched body is saved here so a CI run
# can expose real page markup as a workflow artifact.
DEBUG_DUMP_DIR: Path | None = None


def fetch(url: str, timeout: int = 25) -> str:
    """GET a URL with browser-ish headers; returns decoded body text."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        charset = resp.headers.get_content_charset() or "utf-8"
        body = raw.decode(charset, errors="replace")
    if DEBUG_DUMP_DIR is not None:
        DEBUG_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", url)[:150]
        (DEBUG_DUMP_DIR / f"{name}.txt").write_text(body, "utf-8")
    return body


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(s or "")).strip()


def parse_price(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", str(value))
    return float(m.group(1).replace(",", "")) if m else None


def parse_date_any(value: str) -> str:
    """Best-effort: normalize assorted date strings to YYYY-MM-DD ('' if hopeless)."""
    if not value:
        return ""
    value = value.strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    if m:
        return m.group(1)
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    # "Mon, Jul 14" style with no year: assume the next occurrence
    m = re.search(r"([A-Z][a-z]{2,8})\s+(\d{1,2})", value)
    if m:
        for fmt in ("%b %d %Y", "%B %d %Y"):
            try:
                today = date.today()
                d = datetime.strptime(f"{m.group(1)} {m.group(2)} {today.year}", fmt).date()
                if d < today - timedelta(days=7):
                    d = d.replace(year=today.year + 1)
                return d.isoformat()
            except ValueError:
                pass
    return ""


def score_event(title: str, description: str) -> tuple[int, list[str]]:
    text = f" {title} {description} ".lower()
    score, matched = 0, []
    for kw, w in KEYWORD_WEIGHTS.items():
        if kw in text:
            score += w
            if w >= 2:
                matched.append(kw.strip())
    for kw, w in NEGATIVE_WEIGHTS.items():
        if kw in text:
            score += w
            matched.append(f"-{kw}")
    return score, matched


def extract_jsonld_events(html_text: str) -> list[dict]:
    """Pull every schema.org Event out of ld+json blocks (handles @graph,
    ItemList, and plain lists). Works on 10times, many venue sites, etc."""
    found: list[dict] = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            t = node.get("@type", "")
            types = t if isinstance(t, list) else [t]
            if any(str(x).endswith("Event") for x in types if x):
                found.append(node)
            for key in ("@graph", "itemListElement", "item", "subEvent"):
                if key in node:
                    walk(node[key])

    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.DOTALL | re.IGNORECASE,
    ):
        block = m.group(1).strip()
        try:
            walk(json.loads(block))
        except json.JSONDecodeError:
            # some sites emit multiple JSON objects or trailing commas; try
            # to salvage individual objects
            try:
                walk(json.loads(re.sub(r",\s*([}\]])", r"\1", block)))
            except json.JSONDecodeError:
                continue
    return found


def extract_server_data(html_text: str) -> dict:
    """Extract Eventbrite's embedded window.__SERVER_DATA__ JSON object."""
    marker = "window.__SERVER_DATA__"
    idx = html_text.find(marker)
    if idx == -1:
        raise ValueError("__SERVER_DATA__ not found")
    idx = html_text.index("=", idx) + 1
    while idx < len(html_text) and html_text[idx] in " \t\r\n":
        idx += 1
    obj, _ = json.JSONDecoder().raw_decode(html_text, idx)
    return obj

# --------------------------------------------------------------- sources ---


def source_eventbrite(city: str, cfg: dict, days: int) -> tuple[list[Event], list[SourceStatus]]:
    """Scrape Eventbrite public search pages (they embed a JSON payload)."""
    events, statuses = [], []
    slug = cfg.get("eventbrite_slug")
    if not slug:
        return events, statuses
    for term in SEARCH_TERMS:
        q = urllib.parse.quote(term.replace(" ", "-"))
        url = f"https://www.eventbrite.com/d/{slug}/{q}/?page=1"
        try:
            data = extract_server_data(fetch(url))
            results = (
                data.get("search_data", {}).get("events", {}).get("results", [])
            )
            for ev in results:
                if ev.get("is_online_event"):
                    continue
                tickets = ev.get("ticket_availability") or {}
                min_price = tickets.get("minimum_ticket_price") or {}
                venue = ev.get("primary_venue") or {}
                events.append(
                    Event(
                        title=clean_text(ev.get("name", "")),
                        url=ev.get("url", ""),
                        start=parse_date_any(ev.get("start_date", "")),
                        city=city,
                        source="eventbrite",
                        venue=clean_text(venue.get("name", "")),
                        description=clean_text(ev.get("summary", "")),
                        price_min=parse_price(min_price.get("major_value")),
                        is_free=tickets.get("is_free"),
                    )
                )
            statuses.append(SourceStatus("eventbrite", city, True,
                                         f"'{term}'", len(results)))
        except Exception as exc:  # noqa: BLE001 - sources are best-effort
            statuses.append(SourceStatus("eventbrite", city, False,
                                         f"'{term}': {type(exc).__name__}: {exc}"))
    return events, statuses


def source_tentimes(city: str, cfg: dict, days: int) -> tuple[list[Event], list[SourceStatus]]:
    """Scrape 10times.com banking-finance city listings via JSON-LD."""
    events, statuses = [], []
    slug = cfg.get("tentimes_slug")
    if not slug:
        return events, statuses
    url = f"https://10times.com/{slug}/finance"
    try:
        nodes = extract_jsonld_events(fetch(url))
        for node in nodes:
            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            loc = node.get("location") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            price = parse_price(offers.get("price"))
            events.append(
                Event(
                    title=clean_text(node.get("name", "")),
                    url=node.get("url", ""),
                    start=parse_date_any(str(node.get("startDate", ""))),
                    city=city,
                    source="10times",
                    venue=clean_text(loc.get("name", "")),
                    description=clean_text(str(node.get("description", ""))),
                    price_min=price,
                    is_free=(price == 0) if price is not None else None,
                )
            )
        statuses.append(SourceStatus("10times", city, True, "", len(nodes)))
    except Exception as exc:  # noqa: BLE001
        statuses.append(SourceStatus("10times", city, False,
                                     f"{type(exc).__name__}: {exc}"))
    return events, statuses


def source_garysguide(city: str, cfg: dict, days: int) -> tuple[list[Event], list[SourceStatus]]:
    """Scrape Gary's Guide (NYC tech/finance event list, plain old HTML)."""
    events, statuses = [], []
    if not cfg.get("garysguide"):
        return events, statuses
    url = "https://www.garysguide.com/events"
    try:
        body = fetch(url)
        # Anchors to individual event pages carry the title; a date header
        # like "Mon, Jul 14" precedes each day's block; FREE/$NN appears in
        # the same row chunk as the anchor.
        # hrefs are relative (/events/{id}/{slug}); skip utility links like
        # /events/newsletter/...
        anchor_re = re.compile(
            r'<a[^>]+href="(?:https?://(?:www\.)?garysguide\.com)?'
            r'(/events/[a-z0-9]+/[^"]+)"[^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        date_re = re.compile(r"[A-Z][a-z]{2},\s+([A-Z][a-z]{2}\s+\d{1,2})")
        matches = list(anchor_re.finditer(body))
        for i, m in enumerate(matches):
            title = clean_text(re.sub(r"<[^>]+>", " ", m.group(2)))
            if not title or len(title) < 4:
                continue
            preceding = body[: m.start()]
            dm = None
            for dm in date_re.finditer(preceding):
                pass  # keep last date header before this anchor
            start = parse_date_any(dm.group(1)) if dm else ""
            chunk_end = matches[i + 1].start() if i + 1 < len(matches) else m.end() + 600
            chunk = body[m.start(): chunk_end]
            price = None
            is_free = None
            if re.search(r"\bFREE\b", chunk):
                price, is_free = 0.0, True
            else:
                pm = re.search(r"\$\s*(\d[\d,]*)", chunk)
                if pm:
                    price = parse_price(pm.group(1))
                    is_free = price == 0
            events.append(
                Event(
                    title=title,
                    url=urllib.parse.urljoin("https://www.garysguide.com/", m.group(1)),
                    start=start,
                    city=city,
                    source="garysguide",
                    price_min=price,
                    is_free=is_free,
                )
            )
        statuses.append(SourceStatus("garysguide", city, True, "", len(events)))
    except Exception as exc:  # noqa: BLE001
        statuses.append(SourceStatus("garysguide", city, False,
                                     f"{type(exc).__name__}: {exc}"))
    return events, statuses


def source_luma(city: str, cfg: dict, days: int) -> tuple[list[Event], list[SourceStatus]]:
    """Luma (lu.ma) city discover feed - public JSON API, no key needed.

    GET api.lu.ma/discover/get-paginated-events?slug={city}&pagination_limit=50
    returns {events: [...], has_more, next_cursor}; follow the cursor for a
    few pages. Fintech/VC meetups are heavily hosted on Luma.
    """
    events, statuses = [], []
    slugs = cfg.get("luma_slugs") or []
    if not slugs:
        return events, statuses
    for slug in slugs:
        found_here = 0
        try:
            cursor = None
            for _page in range(5):
                params = {"slug": slug, "pagination_limit": "50"}
                if cursor:
                    # the web app sends pagination_cursor; keep cursor too
                    params["pagination_cursor"] = cursor
                    params["cursor"] = cursor
                url = ("https://api.lu.ma/discover/get-paginated-events?"
                       + urllib.parse.urlencode(params))
                data = json.loads(fetch(url))
                page_events = data.get("events") or data.get("entries") or []
                for node in page_events:
                    ev = node.get("event", node) if isinstance(node, dict) else {}
                    if ev.get("location_type") not in (None, "offline"):
                        continue  # skip online-only
                    ticket = ev.get("ticket_info") or {}
                    price = None
                    is_free = ticket.get("is_free")
                    price_obj = ticket.get("price")
                    if isinstance(price_obj, dict) and "cents" in price_obj:
                        price = price_obj["cents"] / 100.0
                    elif is_free:
                        price = 0.0
                    ev_url = ev.get("url", "")
                    if ev_url and not ev_url.startswith("http"):
                        ev_url = f"https://lu.ma/{ev_url}"
                    events.append(
                        Event(
                            title=clean_text(ev.get("name", "")),
                            url=ev_url,
                            start=parse_date_any(str(ev.get("start_at", ""))),
                            city=city,
                            source="luma",
                            venue=clean_text(str(ev.get("city", "") or "")),
                            description=clean_text(str(
                                ev.get("description_short", "")
                                or ev.get("description", "") or "")),
                            price_min=price,
                            is_free=is_free,
                        )
                    )
                    found_here += 1
                cursor = data.get("next_cursor")
                if not data.get("has_more") or not cursor:
                    break
            statuses.append(SourceStatus("luma", city, True,
                                         f"slug '{slug}'", found_here))
            break  # first slug that works wins
        except Exception as exc:  # noqa: BLE001
            statuses.append(SourceStatus("luma", city, False,
                                         f"slug '{slug}': {type(exc).__name__}: {exc}"))
            continue  # try the next slug
    return events, statuses


SOURCES = (source_eventbrite, source_tentimes, source_garysguide, source_luma)

# -------------------------------------------------------------- pipeline ---


def collect(days: int) -> tuple[list[Event], list[SourceStatus]]:
    all_events: list[Event] = []
    statuses: list[SourceStatus] = []
    for city, cfg in CITIES.items():
        for source_fn in SOURCES:
            evs, sts = source_fn(city, cfg, days)
            all_events.extend(evs)
            statuses.extend(sts)
    return all_events, statuses


def filter_events(events: list[Event], max_price: float, days: int,
                  min_score: int) -> list[Event]:
    today = date.today()
    horizon = today + timedelta(days=days)
    seen: set[tuple[str, str]] = set()
    kept: list[Event] = []
    for ev in events:
        if not ev.title or not ev.url:
            continue
        ev.score, ev.matched = score_event(ev.title, ev.description)
        if ev.score < min_score:
            continue
        if ev.start:
            try:
                d = date.fromisoformat(ev.start)
                if d < today or d > horizon:
                    continue
            except ValueError:
                ev.start = ""
        if ev.price_min is not None and ev.price_min > max_price:
            continue
        key = (re.sub(r"\W+", "", ev.title.lower())[:60], ev.start)
        if key in seen:
            continue
        seen.add(key)
        kept.append(ev)
    kept.sort(key=lambda e: (e.start or "9999-99-99", -e.score))
    return kept

# --------------------------------------------------------------- outputs ---


def price_label(ev: Event) -> str:
    if ev.is_free or ev.price_min == 0:
        return "FREE"
    if ev.price_min is not None:
        return f"from ${ev.price_min:,.0f}"
    return "price unlisted"


def write_json(events: list[Event], statuses: list[SourceStatus],
               out: Path, meta: dict) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": meta,
        "sources": [asdict(s) for s in statuses],
        "events": [asdict(e) for e in events],
    }
    (out / "events.json").write_text(json.dumps(payload, indent=2), "utf-8")


def write_markdown(events: list[Event], statuses: list[SourceStatus],
                   out: Path, meta: dict) -> None:
    lines = [
        "# FinServ Events Digest",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"window: next {meta['days']} days · max ticket ${meta['max_price']:,.0f}_",
        "",
    ]
    for city in CITIES:
        city_events = [e for e in events if e.city == city]
        lines.append(f"## {city} ({len(city_events)})")
        lines.append("")
        if not city_events:
            lines.append("_No qualifying events found this run._")
        for e in city_events:
            when = e.start or "date TBD"
            venue = f" @ {e.venue}" if e.venue else ""
            lines.append(f"- **{when}** · [{e.title}]({e.url}) — "
                         f"{price_label(e)}{venue} _({e.source})_")
        lines.append("")
    failures = [s for s in statuses if not s.ok]
    if failures:
        lines.append("## Source issues this run")
        lines.append("")
        for s in failures:
            lines.append(f"- `{s.source}` / {s.city}: {s.detail}")
        lines.append("")
    (out / "latest.md").write_text("\n".join(lines), "utf-8")


def write_html(events: list[Event], statuses: list[SourceStatus],
               out: Path, meta: dict) -> None:
    def esc(s: str) -> str:
        return htmllib.escape(s, quote=True)

    cards = []
    for city in CITIES:
        city_events = [e for e in events if e.city == city]
        rows = []
        for e in city_events:
            badge_cls = "free" if (e.is_free or e.price_min == 0) else (
                "paid" if e.price_min is not None else "unknown")
            tags = " ".join(f"<span class='tag'>{esc(t)}</span>"
                            for t in e.matched[:4] if not t.startswith("-"))
            rows.append(f"""
        <li class="event">
          <div class="when">{esc(e.start or 'TBD')}</div>
          <div class="what">
            <a href="{esc(e.url)}" target="_blank" rel="noopener">{esc(e.title)}</a>
            <div class="meta">{esc(e.venue)}<span class="src">via {esc(e.source)}</span> {tags}</div>
          </div>
          <div class="price {badge_cls}">{esc(price_label(e))}</div>
        </li>""")
        body = "\n".join(rows) if rows else \
            "<li class='empty'>No qualifying events found this run.</li>"
        cards.append(f"""
    <section>
      <h2>{esc(city)} <span class="count">{len(city_events)}</span></h2>
      <ul>{body}</ul>
    </section>""")

    failures = [s for s in statuses if not s.ok]
    src_note = ""
    if failures:
        items = "".join(
            f"<li><code>{esc(s.source)}</code> / {esc(s.city)}: {esc(s.detail)}</li>"
            for s in failures)
        src_note = f"""
    <details class="issues"><summary>{len(failures)} source fetch issue(s) this run</summary>
      <ul>{items}</ul>
    </details>"""

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinServ Events — DC · NYC · Philly · Boston</title>
<style>
  :root {{ --bg:#f7f7fb; --card:#fff; --ink:#1c1e26; --muted:#6b7280;
           --accent:#4f46e5; --free:#047857; --line:#e5e7eb; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#121319; --card:#1c1e28; --ink:#e7e8ee; --muted:#9aa0ae;
             --accent:#8b85f4; --free:#34d399; --line:#2a2d3a; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
         background:var(--bg); color:var(--ink); padding:2rem 1rem 4rem; }}
  main {{ max-width:860px; margin:0 auto; }}
  h1 {{ font-size:1.6rem; margin:0 0 .25rem; }}
  .sub {{ color:var(--muted); font-size:.9rem; margin-bottom:2rem; }}
  section {{ background:var(--card); border:1px solid var(--line);
            border-radius:12px; padding:1rem 1.25rem; margin-bottom:1.5rem; }}
  h2 {{ font-size:1.1rem; margin:.25rem 0 .75rem; }}
  .count {{ color:var(--muted); font-weight:normal; font-size:.9rem; }}
  ul {{ list-style:none; margin:0; padding:0; }}
  .event {{ display:flex; gap:1rem; padding:.6rem 0; border-top:1px solid var(--line);
           align-items:baseline; }}
  .when {{ flex:0 0 6.2rem; font-variant-numeric:tabular-nums; color:var(--muted);
          font-size:.9rem; }}
  .what {{ flex:1; min-width:0; }}
  .what a {{ color:var(--accent); text-decoration:none; font-weight:600; }}
  .what a:hover {{ text-decoration:underline; }}
  .meta {{ color:var(--muted); font-size:.82rem; margin-top:.15rem; }}
  .src {{ margin-left:.5rem; font-style:italic; }}
  .tag {{ display:inline-block; margin-left:.4rem; padding:0 .4rem;
         border:1px solid var(--line); border-radius:999px; font-size:.72rem; }}
  .price {{ flex:0 0 auto; font-size:.82rem; font-weight:700; }}
  .price.free {{ color:var(--free); }}
  .price.unknown {{ color:var(--muted); font-weight:400; }}
  .empty {{ color:var(--muted); padding:.5rem 0; }}
  .issues {{ color:var(--muted); font-size:.85rem; }}
  footer {{ color:var(--muted); font-size:.8rem; margin-top:2rem; }}
</style>
</head>
<body>
<main>
  <h1>Financial Services Events</h1>
  <div class="sub">DC · NYC · Philly · Boston — next {meta['days']} days,
    tickets up to ${meta['max_price']:,.0f}. Updated {generated}.
    <a href="events.json">JSON</a> · <a href="latest.md">Markdown</a></div>
{''.join(cards)}
{src_note}
  <footer>Auto-generated by finserv_events_bot.py. Listings come from public
  sources (Eventbrite, 10times, Gary's Guide); always confirm details on the
  event page.</footer>
</main>
</body>
</html>
"""
    (out / "index.html").write_text(page, "utf-8")

# ------------------------------------------------------------------ main ---


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="FinServ events scanner")
    ap.add_argument("--max-price", type=float, default=150.0,
                    help="max minimum-ticket price in USD (default 150)")
    ap.add_argument("--days", type=int, default=75,
                    help="look-ahead window in days (default 75)")
    ap.add_argument("--min-score", type=int, default=2,
                    help="relevance score threshold (default 2)")
    ap.add_argument("--out-dir", default="events",
                    help="output directory (default ./events)")
    ap.add_argument("--debug-dump", default="",
                    help="directory to dump every fetched page body into "
                         "(for diagnosing parsers against live markup)")
    args = ap.parse_args(argv)

    if args.debug_dump:
        global DEBUG_DUMP_DIR
        DEBUG_DUMP_DIR = Path(args.debug_dump)

    raw, statuses = collect(args.days)

    if DEBUG_DUMP_DIR is not None:
        print(f"--- raw events before filtering ({len(raw)}) ---")
        for ev in raw[:400]:
            sc, _ = score_event(ev.title, ev.description)
            print(f"  {ev.city[:12]:<12} {ev.source:<10} {ev.start or '????-??-??'} "
                  f"score={sc:<3} price={ev.price_min} | {ev.title[:70]}")

    events = filter_events(raw, args.max_price, args.days, args.min_score)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = {"max_price": args.max_price, "days": args.days,
            "min_score": args.min_score}
    write_json(events, statuses, out, meta)
    write_markdown(events, statuses, out, meta)
    write_html(events, statuses, out, meta)

    ok = sum(1 for s in statuses if s.ok)
    print(f"Sources OK: {ok}/{len(statuses)} · raw events: {len(raw)} · "
          f"kept after filters: {len(events)}")
    for s in statuses:
        flag = "ok " if s.ok else "ERR"
        print(f"  [{flag}] {s.source:<11} {s.city:<15} {s.detail} "
              f"({s.found} found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
