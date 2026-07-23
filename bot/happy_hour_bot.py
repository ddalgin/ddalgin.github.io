#!/usr/bin/env python3
"""Happy Hour Bot.

Ranks the best happy-hour bars, rooftops, and restaurants in Washington DC
by walking distance from a chosen origin (default: Metro Center / downtown)
plus rooftop / view / deal quality, and writes:

  happyhour/happyhour.json  - machine-readable results
  happyhour/index.html      - browsable page (served at /happyhour/)
  happyhour/latest.md       - plain-text digest, easy to read on GitHub

The venue list is a hand-curated dataset (see SPOTS below) rather than a live
scrape, so the results are stable and don't break when a venue site blocks
bots. Happy-hour times and deals are best-effort and change often — always
confirm on the venue's page before you head out. Stdlib only, nothing to
install.

Usage:
  python bot/happy_hour_bot.py                       # rank everything near the office
  python bot/happy_hour_bot.py --category rooftop    # rooftops only
  python bot/happy_hour_bot.py --features view,outdoor --max-walk 12
  python bot/happy_hour_bot.py --happy-hour-only --top 10
  python bot/happy_hour_bot.py --origin white_house
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------- origins ---

# Named starting points. The default is the user's office at 1001 G St NW,
# which sits directly on top of the Metro Center station.
ORIGINS = {
    "office": (38.8983, -77.0264, "1001 G St NW (Metro Center)"),
    "metro_center": (38.8983, -77.0281, "Metro Center station"),
    "white_house": (38.8977, -77.0365, "The White House"),
    "chinatown": (38.8985, -77.0219, "Gallery Pl / Chinatown"),
    "the_wharf": (38.8790, -77.0228, "The Wharf"),
    "union_station": (38.8973, -77.0063, "Union Station"),
}

# ------------------------------------------------------------- the data ----

# Curated DC happy-hour spots. Coordinates are approximate street locations.
# `features` drives filtering/boosting: rooftop, view, outdoor, waterfront,
# cocktails, beer, wine, oysters, historic, livemusic, speakeasy, sports.
# `happy_hour` is "" when the venue has no standing happy hour.
SPOTS = [
    {
        "name": "Crimson View",
        "lat": 38.8996, "lng": -77.0220,
        "neighborhood": "Chinatown / Penn Quarter",
        "category": "rooftop",
        "url": "https://crimson-dc.com/crimson-view-rooftop",
        "happy_hour": "Mon–Fri 4–7pm",
        "deals": "$2 off beers & house wine; craft cocktails and small plates",
        "features": ["rooftop", "view", "cocktails", "outdoor"],
        "rating": 4.3, "price": "$$$",
        "notes": "12 stories up with Washington Monument + skyline views; closest true rooftop happy hour to the office.",
    },
    {
        "name": "VUE Rooftop",
        "lat": 38.8976, "lng": -77.0333,
        "neighborhood": "Downtown (Hotel Washington)",
        "category": "rooftop",
        "url": "https://www.vuerooftopdc.com/",
        "happy_hour": "",
        "deals": "No standing happy hour; à la carte cocktails, opens 4pm weekdays",
        "features": ["rooftop", "view", "cocktails"],
        "rating": 4.2, "price": "$$$$",
        "notes": "The iconic one — direct White House + Washington Monument views. Best for impressing someone; pricier, no HH deal.",
    },
    {
        "name": "The Rooftop DC",
        "lat": 38.9016, "lng": -77.0165,
        "neighborhood": "Mt. Vernon Triangle",
        "category": "rooftop",
        "url": "https://washington.org/visit-dc/rooftop-bars-restaurants-washington-dc",
        "happy_hour": "Mon–Fri 4–6pm",
        "deals": "Weekday happy hour; sportsbook + cocktail lounge",
        "features": ["rooftop", "outdoor", "sports", "cocktails"],
        "rating": 4.0, "price": "$$$",
        "notes": "Rooftop mixing a sportsbook with a cocktail lounge — good group / game-day hang.",
    },
    {
        "name": "Moonraker at Pendry",
        "lat": 38.8783, "lng": -77.0230,
        "neighborhood": "The Wharf",
        "category": "rooftop",
        "url": "https://www.pendry.com/washington-dc/dining/moonraker/",
        "happy_hour": "Check listing",
        "deals": "Japanese-inspired bites; craft cocktails",
        "features": ["rooftop", "view", "waterfront", "cocktails"],
        "rating": 4.4, "price": "$$$$",
        "notes": "Atop the Pendry with sweeping views of the Washington Channel and Wharf — worth the trip for a sunset.",
    },
    {
        "name": "Whiskey Charlie",
        "lat": 38.8790, "lng": -77.0228,
        "neighborhood": "The Wharf",
        "category": "rooftop",
        "url": "https://www.whiskeycharliedc.com/",
        "happy_hour": "Check listing",
        "deals": "Whiskey-forward cocktails; waterfront rooftop",
        "features": ["rooftop", "view", "waterfront", "cocktails"],
        "rating": 4.2, "price": "$$$",
        "notes": "Canopy Wharf rooftop with wide water views; more relaxed than Moonraker next door.",
    },
    {
        "name": "Old Ebbitt Grill",
        "lat": 38.8981, "lng": -77.0332,
        "neighborhood": "Downtown",
        "category": "restaurant",
        "url": "https://www.ebbitt.com/",
        "happy_hour": "Daily raw-bar specials (late afternoon & late night)",
        "deals": "Half-price oysters during oyster happy hour",
        "features": ["oysters", "historic", "cocktails"],
        "rating": 4.5, "price": "$$$",
        "notes": "DC's oldest saloon, steps from the office — the move for discounted oysters and a classic bar.",
    },
    {
        "name": "Jaleo",
        "lat": 38.8949, "lng": -77.0218,
        "neighborhood": "Penn Quarter",
        "category": "restaurant",
        "url": "https://www.jaleo.com/location/penn-quarter/",
        "happy_hour": "Mon–Fri 3–6:30pm",
        "deals": "$8 sangría roja, wine by the glass, discounted tapas (patatas bravas, gambas)",
        "features": ["tapas", "outdoor", "wine", "cocktails"],
        "rating": 4.4, "price": "$$$",
        "notes": "José Andrés tapas mainstay; one of the best-value happy hours downtown.",
    },
    {
        "name": "The Hamilton",
        "lat": 38.8968, "lng": -77.0316,
        "neighborhood": "Downtown",
        "category": "bar",
        "url": "https://thehamiltondc.com/",
        "happy_hour": "Mon–Fri, late afternoon",
        "deals": "Discounted drinks & bar bites; live music downstairs",
        "features": ["livemusic", "cocktails", "beer"],
        "rating": 4.3, "price": "$$",
        "notes": "Big, dependable spot two blocks away with a live-music venue in the basement.",
    },
    {
        "name": "Dirty Habit",
        "lat": 38.8955, "lng": -77.0229,
        "neighborhood": "Penn Quarter",
        "category": "bar",
        "url": "https://www.dirtyhabitdc.com/",
        "happy_hour": "Weekday happy hour",
        "deals": "Cocktail & small-plate specials on the courtyard patio",
        "features": ["outdoor", "cocktails"],
        "rating": 4.1, "price": "$$$",
        "notes": "Sceney cocktail bar with a large open-air courtyard patio.",
    },
    {
        "name": "Succotash Prime",
        "lat": 38.8968, "lng": -77.0244,
        "neighborhood": "Penn Quarter",
        "category": "restaurant",
        "url": "https://www.succotashrestaurant.com/penn-quarter/",
        "happy_hour": "Weekday happy hour",
        "deals": "Southern-style bar bites and drink specials",
        "features": ["cocktails", "southern"],
        "rating": 4.2, "price": "$$$",
        "notes": "Modern Southern kitchen; good deviled eggs / hush-puppies happy hour.",
    },
    {
        "name": "City Tap House DC",
        "lat": 38.9008, "lng": -77.0242,
        "neighborhood": "Mt. Vernon Triangle",
        "category": "bar",
        "url": "https://www.citytap.com/location/city-tap-dc/",
        "happy_hour": "Weekday happy hour",
        "deals": "Draft beer & wood-fired pizza specials; large patio",
        "features": ["beer", "outdoor", "sports"],
        "rating": 4.0, "price": "$$",
        "notes": "Enormous craft-beer list and a big patio — solid for a group after work.",
    },
    {
        "name": "Rosa Mexicano",
        "lat": 38.8955, "lng": -77.0217,
        "neighborhood": "Penn Quarter",
        "category": "restaurant",
        "url": "https://www.rosamexicano.com/location/penn-quarter/",
        "happy_hour": "Weekday happy hour",
        "deals": "Frozen pomegranate margaritas & guac; discounted antojitos",
        "features": ["margaritas", "outdoor", "cocktails"],
        "rating": 4.0, "price": "$$$",
        "notes": "Reliable margarita-and-guac happy hour near Capital One Arena.",
    },
    {
        "name": "Round Robin Bar",
        "lat": 38.8966, "lng": -77.0324,
        "neighborhood": "Downtown (Willard InterContinental)",
        "category": "bar",
        "url": "https://washington.intercontinental.com/round-robin-bar/",
        "happy_hour": "",
        "deals": "Classic cocktails; no standing HH but a landmark bar",
        "features": ["historic", "cocktails"],
        "rating": 4.4, "price": "$$$$",
        "notes": "Storied circular mahogany bar inside the Willard — a proper old-DC cocktail.",
    },
    {
        "name": "Off the Record",
        "lat": 38.9008, "lng": -77.0364,
        "neighborhood": "Downtown (Hay-Adams)",
        "category": "bar",
        "url": "https://www.hayadams.com/off-the-record",
        "happy_hour": "",
        "deals": "Power-player cocktail lounge; caricature coasters",
        "features": ["speakeasy", "historic", "cocktails"],
        "rating": 4.4, "price": "$$$$",
        "notes": "Below the Hay-Adams, across Lafayette Sq from the White House — quiet, classic, no HH.",
    },
    {
        "name": "RPM Italian",
        "lat": 38.9022, "lng": -77.0208,
        "neighborhood": "Mt. Vernon Triangle",
        "category": "restaurant",
        "url": "https://www.rpmrestaurants.com/rpm-italian/dc/",
        "happy_hour": "Weekday bar happy hour",
        "deals": "Aperitivo cocktails & bar snacks",
        "features": ["italian", "cocktails", "wine"],
        "rating": 4.3, "price": "$$$",
        "notes": "Glam Italian with a lively bar scene; good aperitivo hour.",
    },
    {
        "name": "Denson Liquor Bar",
        "lat": 38.8967, "lng": -77.0257,
        "neighborhood": "Penn Quarter",
        "category": "bar",
        "url": "https://www.densonbar.com/",
        "happy_hour": "Weekday happy hour",
        "deals": "Cocktails & bar bites; late-night kitchen",
        "features": ["cocktails", "latenight"],
        "rating": 4.1, "price": "$$",
        "notes": "Narrow, moody cocktail bar right in the heart of Penn Quarter.",
    },
    {
        "name": "Astro Beer Hall",
        "lat": 38.8983, "lng": -77.0296,
        "neighborhood": "Downtown",
        "category": "bar",
        "url": "https://www.astrobeerhall.com/",
        "happy_hour": "Weekday happy hour",
        "deals": "Draft beer, cocktails, and their signature fried chicken & donuts",
        "features": ["beer", "casual", "cocktails"],
        "rating": 4.0, "price": "$",
        "notes": "Casual multi-level beer hall a block from the office — easy, cheap, fun.",
    },
    {
        "name": "Quill",
        "lat": 38.9052, "lng": -77.0365,
        "neighborhood": "Downtown (Jefferson Hotel)",
        "category": "bar",
        "url": "https://www.jeffersondc.com/dine/quill",
        "happy_hour": "",
        "deals": "Refined seasonal cocktails; live piano",
        "features": ["cocktails", "historic"],
        "rating": 4.5, "price": "$$$$",
        "notes": "Intimate, upscale hotel bar — top-tier cocktails for a quieter evening.",
    },
]

# Desirability weight per feature, used to reward the things the user is
# after (rooftops with a view, outdoor seating) in the composite score.
FEATURE_BONUS = {
    "rooftop": 3.0,
    "view": 2.5,
    "waterfront": 1.5,
    "outdoor": 1.5,
    "oysters": 1.0,
    "cocktails": 0.5,
    "livemusic": 0.5,
    "historic": 0.5,
    "speakeasy": 0.5,
}

# --------------------------------------------------------------- model -----


@dataclass
class Spot:
    name: str
    lat: float
    lng: float
    neighborhood: str
    category: str
    url: str
    happy_hour: str
    deals: str
    features: list[str]
    rating: float
    price: str
    notes: str = ""
    # computed
    dist_mi: float = 0.0
    walk_min: int = 0
    score: float = 0.0
    matched: list[str] = field(default_factory=list)

    @property
    def has_happy_hour(self) -> bool:
        hh = self.happy_hour.strip().lower()
        return bool(hh) and hh != "check listing"


# --------------------------------------------------------------- helpers ---


def haversine_mi(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    """Great-circle distance between two points in miles."""
    r = 3958.8  # earth radius, miles
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dphi = math.radians(b_lat - a_lat)
    dlmb = math.radians(b_lng - a_lng)
    h = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def walking_minutes(dist_mi: float) -> int:
    """Estimate walking time. ~1.35x street factor over crow-flies, 3.0 mph."""
    street_mi = dist_mi * 1.35
    return max(1, round(street_mi / 3.0 * 60))


def score_spot(spot: Spot, wanted: set[str], happy_hour_only: bool) -> None:
    """Fill in dist/walk and a composite score. Higher is better."""
    # Rating contributes up to 10 points.
    rating_pts = spot.rating * 2.0

    # Proximity: full marks within ~4 min, tapering to 0 by ~24 min.
    proximity_pts = max(0.0, 10.0 - (spot.walk_min - 4) * 0.5)

    # Inherent desirability of the venue's features.
    feature_pts = sum(FEATURE_BONUS.get(f, 0.0) for f in spot.features)

    # Extra reward for features the user explicitly asked for.
    matched = sorted(wanted & set(spot.features))
    request_pts = 4.0 * len(matched)

    # Nudge spots that have an actual standing happy hour.
    hh_pts = 2.0 if spot.has_happy_hour else 0.0

    spot.matched = matched
    spot.score = round(
        rating_pts + proximity_pts + feature_pts + request_pts + hh_pts, 2
    )


def rank(origin: tuple[float, float, str], category: str, wanted: set[str],
         require_features: bool, max_walk: int | None,
         happy_hour_only: bool) -> list[Spot]:
    o_lat, o_lng, _ = origin
    spots: list[Spot] = []
    for raw in SPOTS:
        spot = Spot(**raw)
        spot.dist_mi = round(haversine_mi(o_lat, o_lng, spot.lat, spot.lng), 2)
        spot.walk_min = walking_minutes(spot.dist_mi)

        if category != "all" and spot.category != category:
            continue
        if max_walk is not None and spot.walk_min > max_walk:
            continue
        if happy_hour_only and not spot.has_happy_hour:
            continue
        if require_features and wanted and not wanted.issubset(set(spot.features)):
            continue

        score_spot(spot, wanted, happy_hour_only)
        spots.append(spot)

    spots.sort(key=lambda s: (-s.score, s.walk_min))
    return spots


# --------------------------------------------------------------- outputs ---


def hh_label(spot: Spot) -> str:
    return spot.happy_hour if spot.happy_hour else "no standing HH"


def write_json(spots: list[Spot], out: Path, meta: dict) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": meta,
        "spots": [asdict(s) for s in spots],
    }
    (out / "happyhour.json").write_text(json.dumps(payload, indent=2), "utf-8")


def write_markdown(spots: list[Spot], out: Path, meta: dict) -> None:
    lines = [
        "# DC Happy Hour — Ranked",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"from {meta['origin_label']} · {meta['filter_label']}_",
        "",
    ]
    if not spots:
        lines.append("_No spots matched these filters._")
    for i, s in enumerate(spots, 1):
        feats = ", ".join(s.features)
        lines.append(
            f"{i}. **[{s.name}]({s.url})** — {s.walk_min} min walk · "
            f"{s.neighborhood} · ⭐{s.rating} · {s.price}"
        )
        lines.append(f"   - Happy hour: {hh_label(s)}" + (f" — {s.deals}" if s.deals else ""))
        if s.notes:
            lines.append(f"   - {s.notes}")
        lines.append(f"   - _{feats}_")
        lines.append("")
    lines.append("---")
    lines.append("_Happy-hour times and deals change often — confirm on the "
                 "venue page before you go._")
    (out / "latest.md").write_text("\n".join(lines), "utf-8")


def write_html(spots: list[Spot], out: Path, meta: dict) -> None:
    def esc(s: str) -> str:
        return htmllib.escape(str(s), quote=True)

    rows = []
    for i, s in enumerate(spots, 1):
        hh_cls = "hh" if s.has_happy_hour else "nohh"
        feat_tags = " ".join(
            f"<span class='tag{' hit' if f in s.matched else ''}'>{esc(f)}</span>"
            for f in s.features
        )
        rows.append(f"""
      <li class="spot">
        <div class="rank">{i}</div>
        <div class="body">
          <div class="title">
            <a href="{esc(s.url)}" target="_blank" rel="noopener">{esc(s.name)}</a>
            <span class="cat">{esc(s.category)}</span>
          </div>
          <div class="line">
            <span class="walk">🚶 {s.walk_min} min</span>
            <span class="hood">{esc(s.neighborhood)}</span>
            <span class="rating">⭐ {esc(s.rating)}</span>
            <span class="price">{esc(s.price)}</span>
          </div>
          <div class="hhline {hh_cls}">🍸 {esc(hh_label(s))}{(' — ' + esc(s.deals)) if s.deals else ''}</div>
          {f'<div class="notes">{esc(s.notes)}</div>' if s.notes else ''}
          <div class="tags">{feat_tags}</div>
        </div>
        <div class="score" title="composite score">{s.score:g}</div>
      </li>""")

    body = "\n".join(rows) if rows else \
        "<li class='empty'>No spots matched these filters.</li>"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DC Happy Hour — Ranked</title>
<style>
  :root {{ --bg:#f7f7fb; --card:#fff; --ink:#1c1e26; --muted:#6b7280;
           --accent:#b91c5c; --hh:#047857; --line:#e5e7eb; --hit:#b45309; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#121319; --card:#1c1e28; --ink:#e7e8ee; --muted:#9aa0ae;
             --accent:#f472b6; --hh:#34d399; --line:#2a2d3a; --hit:#fbbf24; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
         background:var(--bg); color:var(--ink); padding:2rem 1rem 4rem; }}
  main {{ max-width:820px; margin:0 auto; }}
  h1 {{ font-size:1.6rem; margin:0 0 .25rem; }}
  .sub {{ color:var(--muted); font-size:.9rem; margin-bottom:1.75rem; }}
  ul {{ list-style:none; margin:0; padding:0; }}
  .spot {{ display:flex; gap:.9rem; align-items:flex-start; background:var(--card);
          border:1px solid var(--line); border-radius:12px; padding:1rem 1.1rem;
          margin-bottom:.9rem; }}
  .rank {{ flex:0 0 1.6rem; font-weight:800; color:var(--accent);
          font-variant-numeric:tabular-nums; font-size:1.05rem; }}
  .body {{ flex:1; min-width:0; }}
  .title {{ font-size:1.08rem; }}
  .title a {{ color:var(--accent); text-decoration:none; font-weight:700; }}
  .title a:hover {{ text-decoration:underline; }}
  .cat {{ margin-left:.5rem; font-size:.68rem; text-transform:uppercase;
         letter-spacing:.05em; color:var(--muted); border:1px solid var(--line);
         border-radius:999px; padding:.05rem .45rem; vertical-align:middle; }}
  .line {{ color:var(--muted); font-size:.86rem; margin:.2rem 0; display:flex;
          flex-wrap:wrap; gap:.75rem; }}
  .hhline {{ font-size:.9rem; margin:.35rem 0 .3rem; }}
  .hhline.hh {{ color:var(--hh); font-weight:600; }}
  .hhline.nohh {{ color:var(--muted); }}
  .notes {{ font-size:.86rem; color:var(--ink); opacity:.85; margin:.2rem 0 .4rem; }}
  .tags {{ display:flex; flex-wrap:wrap; gap:.35rem; margin-top:.35rem; }}
  .tag {{ font-size:.7rem; border:1px solid var(--line); border-radius:999px;
         padding:.05rem .5rem; color:var(--muted); }}
  .tag.hit {{ color:var(--hit); border-color:var(--hit); font-weight:700; }}
  .score {{ flex:0 0 auto; font-weight:800; color:var(--muted);
           font-variant-numeric:tabular-nums; font-size:.95rem; }}
  .empty {{ color:var(--muted); }}
  footer {{ color:var(--muted); font-size:.8rem; margin-top:2rem; }}
</style>
</head>
<body>
<main>
  <h1>🍸 DC Happy Hour — Ranked</h1>
  <div class="sub">From {esc(meta['origin_label'])} · {esc(meta['filter_label'])}.
    Ranked by walk time, rooftop/view quality, ratings & deals.
    Updated {generated}. <a href="happyhour.json">JSON</a> · <a href="latest.md">Markdown</a></div>
  <ul>{body}</ul>
  <footer>Auto-generated by happy_hour_bot.py from a curated venue list.
  Happy-hour times and deals change often — confirm on each venue's page
  before you go.</footer>
</main>
</body>
</html>
"""
    (out / "index.html").write_text(page, "utf-8")


# ------------------------------------------------------------------ main ---


def build_filter_label(category: str, wanted: set[str], max_walk: int | None,
                       happy_hour_only: bool) -> str:
    parts = []
    parts.append("all spots" if category == "all" else f"{category}s")
    if wanted:
        parts.append("features: " + "+".join(sorted(wanted)))
    if max_walk is not None:
        parts.append(f"≤{max_walk} min walk")
    if happy_hour_only:
        parts.append("happy hour only")
    return " · ".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DC happy-hour ranker")
    ap.add_argument("--origin", default="office", choices=sorted(ORIGINS),
                    help="starting point for walk distances (default: office)")
    ap.add_argument("--category", default="all",
                    choices=["all", "rooftop", "bar", "restaurant"],
                    help="venue category filter (default: all)")
    ap.add_argument("--features", default="",
                    help="comma-separated features to prioritize "
                         "(e.g. rooftop,view,outdoor)")
    ap.add_argument("--require-features", action="store_true",
                    help="hard-filter to spots that have ALL --features "
                         "(default: features only boost ranking)")
    ap.add_argument("--max-walk", type=int, default=None,
                    help="drop spots farther than N minutes on foot")
    ap.add_argument("--happy-hour-only", action="store_true",
                    help="only show spots with a standing happy hour")
    ap.add_argument("--top", type=int, default=None,
                    help="keep only the top N results")
    ap.add_argument("--out-dir", default="happyhour",
                    help="output directory (default ./happyhour)")
    args = ap.parse_args(argv)

    origin = ORIGINS[args.origin]
    wanted = {f.strip().lower() for f in args.features.split(",") if f.strip()}

    spots = rank(origin, args.category, wanted, args.require_features,
                 args.max_walk, args.happy_hour_only)
    if args.top is not None:
        spots = spots[: args.top]

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "origin": args.origin,
        "origin_label": origin[2],
        "category": args.category,
        "features": sorted(wanted),
        "max_walk": args.max_walk,
        "happy_hour_only": args.happy_hour_only,
        "filter_label": build_filter_label(args.category, wanted,
                                            args.max_walk, args.happy_hour_only),
        "count": len(spots),
    }
    write_json(spots, out, meta)
    write_markdown(spots, out, meta)
    write_html(spots, out, meta)

    print(f"Origin: {origin[2]} · {meta['filter_label']} · {len(spots)} spots")
    for i, s in enumerate(spots, 1):
        print(f"  {i:>2}. {s.name:<22} {s.walk_min:>2}min  "
              f"score={s.score:<5g} {hh_label(s)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
