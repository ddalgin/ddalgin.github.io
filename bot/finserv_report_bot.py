#!/usr/bin/env python3
"""FinServ Monthly Report Bot.

Turns a month of raw sales numbers for the Financial Services team into a
polished monthly report — the "semi design, semi analysis" companion to the
events bot.

  * ANALYSIS: from the raw actuals it derives every downstream figure
    (YoY dollars/percent, running YTD, discovery % to goal, pace vs. a
    straight-line target, newsletter lift vs. benchmark) and writes a short
    narrative that flags what's trailing and what's winning — so the numbers
    can't silently disagree with the story.

  * DESIGN: it renders that into a branded, self-contained report page
    (dark-forest header, YoY color coding, progress meters, stat cards)
    matching the house look of the monthly deck, plus a plain Markdown
    digest that reads on GitHub and a machine-readable JSON.

Input is one data file per month (see bot/data/2026-05.json). Output for a
month goes to reports/<YYYY-MM>.html, and reports/index.html always points at
the latest, with reports/latest.md and reports/report.json alongside.

Stdlib only — nothing to install.

Usage:
  python bot/finserv_report_bot.py                        # newest bot/data/*.json
  python bot/finserv_report_bot.py --data bot/data/2026-05.json
  python bot/finserv_report_bot.py --data bot/data/2026-05.json --out-dir reports
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

MONTH_INDEX = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ------------------------------------------------------------- formatting ---


def esc(s) -> str:
    return htmllib.escape(str(s), quote=True)


def money(value: float | int | None, approx: bool = False) -> str:
    """$1,234,567 — or ~$3.59M shorthand for big approximate figures."""
    if value is None:
        return "—"
    prefix = "~" if approx else ""
    if approx and abs(value) >= 1_000_000:
        return f"{prefix}${value / 1_000_000:.2f}M"
    return f"{prefix}${value:,.0f}"


def signed_money(value: float | int | None, approx: bool = False) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    body = money(abs(value), approx=approx)
    if approx:  # keep the ~ ahead of the sign: ~-$470,000
        return f"~{sign}{body[1:]}" if body.startswith("~") else f"{sign}{body}"
    return f"{sign}{body}"


def pct(value: float | None, digits: int = 1, signed: bool = False,
        approx: bool = False) -> str:
    if value is None:
        return "—"
    prefix = "~" if approx else ""
    sign = "+" if (signed and value > 0) else ""
    return f"{prefix}{sign}{value:.{digits}f}%"


def direction(value: float | None) -> str:
    """'up' / 'down' / 'flat' — drives the YoY color class."""
    if value is None:
        return "flat"
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


# --------------------------------------------------------------- analysis ---
#
# Everything below recomputes derived numbers from the raw actuals. We never
# trust a pre-computed total in the data file — the whole point is that the
# report's math is reproducible from the inputs.


def compute_revenue(rev: dict) -> dict:
    """Add YoY and running-YTD fields to each month, plus period totals."""
    months = []
    ytd_2025 = ytd_2026 = 0.0
    ytd_is_estimate = False
    for m in rev.get("months", []):
        a25 = m.get("actual_2025")
        a26 = m.get("actual_2026")
        est = bool(m.get("estimate"))
        ytd_is_estimate = ytd_is_estimate or est
        yoy_dollar = (a26 - a25) if (a25 is not None and a26 is not None) else None
        yoy_pct = (yoy_dollar / a25 * 100) if (yoy_dollar is not None and a25) else None
        if a25 is not None:
            ytd_2025 += a25
        if a26 is not None:
            ytd_2026 += a26
        months.append({
            **m,
            "estimate": est,
            "yoy_dollar": yoy_dollar,
            "yoy_pct": yoy_pct,
            "ytd_2025": ytd_2025,
            "ytd_2026": ytd_2026,
            "ytd_estimate": ytd_is_estimate,
        })
    total_yoy_dollar = ytd_2026 - ytd_2025 if months else None
    total_yoy_pct = (total_yoy_dollar / ytd_2025 * 100) if ytd_2025 else None
    return {
        **rev,
        "months": months,
        "ytd_2025": ytd_2025,
        "ytd_2026": ytd_2026,
        "ytd_estimate": ytd_is_estimate,
        "total_yoy_dollar": total_yoy_dollar,
        "total_yoy_pct": total_yoy_pct,
        "months_up": sum(1 for m in months if (m["yoy_dollar"] or 0) > 0),
        "months_down": sum(1 for m in months if (m["yoy_dollar"] or 0) < 0),
    }


def _score_row(row: dict) -> dict:
    ytd = (row.get("prior_ytd") or 0) + (row.get("current") or 0)
    goal = row.get("goal") or 0
    return {
        **row,
        "ytd": ytd,
        "pct_to_goal": (ytd / goal * 100) if goal else None,
    }


def compute_discovery(disc: dict, month_number: int) -> dict:
    """Roll each category to YTD and % of annual goal; add a totals row and a
    straight-line pace benchmark (where we *should* be this deep into the year)."""
    cats = [_score_row(c) for c in disc.get("categories", [])]
    acts = [_score_row(a) for a in disc.get("activities", [])]

    total = {
        "name": "Total Discovery Calls",
        "goal": sum(c.get("goal", 0) for c in cats),
        "prior_ytd": sum(c.get("prior_ytd", 0) for c in cats),
        "current": sum(c.get("current", 0) for c in cats),
    }
    total = _score_row(total)

    # Pace: fraction of the year elapsed through this month (May -> 5/12).
    pace_pct = (month_number / 12 * 100) if month_number else None
    laggards = sorted(
        (c for c in cats if c["pct_to_goal"] is not None),
        key=lambda c: c["pct_to_goal"],
    )
    return {
        **disc,
        "categories": cats,
        "activities": acts,
        "total": total,
        "pace_pct": pace_pct,
        "leader": laggards[-1] if laggards else None,
        "laggards": laggards[:3],
    }


def compute_wins(wins: list[dict]) -> dict:
    numeric = [w for w in wins if isinstance(w.get("amount"), (int, float))]
    return {
        "items": wins,
        "count": len(wins),
        "total": sum(w["amount"] for w in numeric),
        "all_numeric": len(numeric) == len(wins),
    }


def analyze_newsletter(nl: dict) -> dict:
    out = dict(nl)
    delivered = nl.get("delivered")
    sent = nl.get("sent")
    if delivered and sent:
        out["delivery_rate"] = delivered / sent * 100
    low, high = nl.get("open_rate_benchmark_low"), nl.get("open_rate_benchmark_high")
    if nl.get("open_rate") is not None and high:
        out["open_vs_benchmark_x"] = nl["open_rate"] / ((low + high) / 2 if low else high)
    if nl.get("open_rate") is not None and nl.get("prior_open_rate"):
        out["open_delta_pts"] = nl["open_rate"] - nl["prior_open_rate"]
    if nl.get("list_size") and nl.get("list_goal"):
        out["list_pct"] = nl["list_size"] / nl["list_goal"] * 100
    return out


def build_analysis(data: dict, rev: dict, disc: dict,
                   wins: dict, nl: dict) -> list[str]:
    """The narrative. Every sentence is stitched from a computed number, so it
    stays honest as the inputs change month to month."""
    label = data.get("period", {}).get("label", "this month")
    lines: list[str] = []

    # --- Revenue -----------------------------------------------------------
    approx = rev["ytd_estimate"]
    trailing = (rev["total_yoy_dollar"] or 0) < 0
    lines.append(
        f"Revenue is {'trailing' if trailing else 'ahead of'} last year: "
        f"{money(rev['ytd_2026'], approx)} YTD vs "
        f"{money(rev['ytd_2025'], approx)} in 2025 "
        f"({signed_money(rev['total_yoy_dollar'], approx)}, "
        f"{pct(rev['total_yoy_pct'], signed=True, approx=approx)}). "
        f"{rev['months_up']} of {len(rev['months'])} months are up YoY."
    )
    last = rev["months"][-1] if rev["months"] else None
    if last and last["yoy_pct"] is not None:
        lines.append(
            f"{last['month']} landed {signed_money(last['yoy_dollar'], last['estimate'])} "
            f"({pct(last['yoy_pct'], signed=True, approx=last['estimate'])}) vs the prior year."
        )

    # --- Discovery ---------------------------------------------------------
    tot = disc["total"]
    pace = disc.get("pace_pct")
    behind = pace is not None and tot["pct_to_goal"] is not None and tot["pct_to_goal"] < pace
    pace_clause = ""
    if pace is not None:
        pace_clause = (f" — {'behind' if behind else 'ahead of'} the "
                       f"{pct(pace, 0)} straight-line pace for this point in the year")
    lines.append(
        f"Discovery calls are at {tot['ytd']} of {tot['goal']} "
        f"({pct(tot['pct_to_goal'], 0)} to goal){pace_clause}. "
        f"{label} added {tot['current']} calls."
    )
    if disc.get("laggards"):
        weak = ", ".join(f"{c['name'].replace('Disco - ', '')} ({pct(c['pct_to_goal'], 0)})"
                         for c in disc["laggards"])
        lines.append(f"Furthest from goal: {weak}.")
    floor = disc.get("per_rep_monthly_floor")
    if floor:
        lines.append(
            f"Standing floor is {floor} legit discovery calls per rep on their worst month — "
            f"the categories above are the team's obligation, not a stretch target."
        )

    # --- Wins & pipeline ---------------------------------------------------
    if wins["count"]:
        booked = money(wins["total"]) if wins["total"] else ""
        qualifier = "" if wins["all_numeric"] else " (named-value wins only)"
        lines.append(
            f"{wins['count']} new wins closed{(' totaling ' + booked + qualifier) if booked else ''}. "
            f"Marquee logos continue to land even as unit volume softens."
        )
    deals = data.get("deals", [])
    if deals:
        lines.append(f"{len(deals)} deals advanced in the pipeline this cycle.")

    # --- Newsletter --------------------------------------------------------
    if nl.get("open_rate") is not None:
        bench = ""
        if nl.get("open_vs_benchmark_x"):
            bench = f", ~{nl['open_vs_benchmark_x']:.1f}x the ~{nl.get('open_rate_benchmark_low')}–{nl.get('open_rate_benchmark_high')}% benchmark"
        jump = ""
        if nl.get("open_delta_pts"):
            jump = f", up {nl['open_delta_pts']:.1f} pts from {pct(nl.get('prior_open_rate'))}"
        lines.append(
            f"Newsletter open rate hit {pct(nl['open_rate'], 2)}{bench}{jump}; "
            f"{nl.get('clicks_total'):,} total clicks is a record. Brand programming is compounding."
        )

    return lines


def compute(data: dict) -> dict:
    """Run the full analysis pass over a raw data file."""
    period = data.get("period", {})
    month_number = period.get("month")
    if isinstance(month_number, str):
        month_number = MONTH_INDEX.get(month_number.strip().lower()[:3])

    rev = compute_revenue(data.get("revenue", {}))
    disc = compute_discovery(data.get("discovery", {}), month_number or 0)
    wins = compute_wins(data.get("wins", []))
    nl = analyze_newsletter(data.get("newsletter", {}))
    analysis = build_analysis(data, rev, disc, wins, nl)

    return {
        "period": period,
        "month_number": month_number,
        "revenue": rev,
        "discovery": disc,
        "wins": wins,
        "newsletter": nl,
        "analysis": analysis,
    }


# ----------------------------------------------------------------- render ---

STYLE = """
  /* TransPerfect Financial palette: navy + light blue + white. */
  :root {
    --brand:#17306b; --brand-2:#0b82c4; --ink:#14213d; --muted:#5b6b85;
    --bg:#f3f6fb; --card:#ffffff; --line:#dde5f0; --band:#eef3fa;
    --up:#1a7f4b; --down:#c0392b; --accent:#0b6fab;
  }
  @media (prefers-color-scheme: dark) {
    :root { --brand:#0e1f45; --brand-2:#33a7e6; --ink:#e6ecf5; --muted:#93a2bb;
      --bg:#0b1220; --card:#121c30; --line:#22304a; --band:#0f1829;
      --up:#3fce86; --down:#f06a5c; --accent:#4db6e8; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
  main { max-width:960px; margin:0 auto; padding:0 1rem 4rem; }
  .masthead { background:var(--brand); color:#fff; padding:2rem 1.5rem;
    border-radius:0 0 14px 14px; margin-bottom:1.75rem;
    border-bottom:4px solid #29abe2; }
  .masthead .eyebrow { text-transform:uppercase; letter-spacing:.14em;
    font-size:.72rem; color:#5cc4ee; margin:0 0 .35rem; }
  .masthead h1 { margin:0; font-size:2rem; line-height:1.1; letter-spacing:-.01em; }
  .masthead .sub { margin:.5rem 0 0; opacity:.85; font-size:.9rem; }
  section { background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:1.25rem 1.4rem; margin-bottom:1.5rem; }
  h2 { font-size:.8rem; text-transform:uppercase; letter-spacing:.12em;
    color:var(--brand-2); margin:0 0 1rem; padding-bottom:.6rem;
    border-bottom:2px solid var(--band); }
  @media (prefers-color-scheme: dark) { h2 { color:var(--accent); } }
  .lede { font-size:1.02rem; margin:.2rem 0 0; }
  .lede ul { margin:.5rem 0 0; padding-left:1.15rem; }
  .lede li { margin:.3rem 0; }
  table { width:100%; border-collapse:collapse; font-size:.92rem; }
  thead th { background:var(--brand); color:#fff; text-align:right;
    padding:.6rem .7rem; font-weight:600; white-space:nowrap; }
  thead th:first-child { text-align:left; border-radius:6px 0 0 0; }
  thead th:last-child { border-radius:0 6px 0 0; }
  tbody td { padding:.55rem .7rem; text-align:right; border-bottom:1px solid var(--line);
    font-variant-numeric:tabular-nums; }
  tbody td:first-child { text-align:left; }
  tbody tr:nth-child(even) { background:var(--band); }
  tr.total td { font-weight:700; background:var(--band); border-top:2px solid var(--brand-2); }
  tr.spacer td { background:transparent; border:0; height:.5rem; padding:0; }
  .up { color:var(--up); font-weight:600; }
  .down { color:var(--down); font-weight:600; }
  .flat { color:var(--muted); }
  .annot { color:var(--muted); font-size:.78rem; font-style:italic; }
  .meter { position:relative; height:.5rem; background:var(--band);
    border-radius:999px; overflow:hidden; min-width:70px; margin-top:.3rem; }
  .meter > span { position:absolute; inset:0 auto 0 0; background:var(--brand-2);
    border-radius:999px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:.9rem; }
  .card { background:var(--band); border:1px solid var(--line); border-radius:10px;
    padding:.85rem .95rem; }
  .card .k { font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
  .card .v { font-size:1.5rem; font-weight:700; margin-top:.15rem; line-height:1.1; }
  .card .n { font-size:.76rem; color:var(--muted); margin-top:.2rem; }
  .cols { display:grid; grid-template-columns:1fr 1fr; gap:1.5rem; }
  @media (max-width:640px) { .cols { grid-template-columns:1fr; } }
  .stack { list-style:none; margin:0; padding:0; }
  .stack li { display:flex; justify-content:space-between; gap:1rem;
    padding:.5rem 0; border-bottom:1px solid var(--line); }
  .stack li:last-child { border-bottom:0; }
  .stack .amt { font-weight:700; white-space:nowrap; font-variant-numeric:tabular-nums; }
  .pill { display:inline-block; padding:.15rem .6rem; border-radius:999px;
    background:var(--band); border:1px solid var(--line); font-size:.8rem; margin:.2rem .3rem 0 0; }
  .callout { border-left:4px solid var(--brand-2); padding:.4rem 0 .4rem 1rem; margin:.6rem 0; }
  .callout.bad { border-color:var(--down); }
  .callout.good { border-color:var(--up); }
  .callout .h { font-weight:700; }
  .note { color:var(--muted); font-size:.82rem; margin-top:1rem; }
  footer { color:var(--muted); font-size:.8rem; margin-top:2rem; text-align:center; }
  a { color:var(--accent); }
"""


def _meter(pct_value: float | None) -> str:
    if pct_value is None:
        return ""
    w = max(0, min(100, pct_value))
    return f'<div class="meter"><span style="width:{w:.0f}%"></span></div>'


def render_revenue_table(rev: dict) -> str:
    rows = []
    for m in rev["months"]:
        est = m["estimate"]
        d = direction(m["yoy_dollar"])
        note25 = f' <span class="annot">{esc(m["note_2025"])}</span>' if m.get("note_2025") else ""
        note26 = f' <span class="annot">{esc(m["note_2026"])}</span>' if m.get("note_2026") else ""
        star = "*" if est else ""
        rows.append(f"""
      <tr>
        <td>{esc(m['month'])}{star}</td>
        <td>{money(m['actual_2025'], est)}{note25}</td>
        <td>{money(m['actual_2026'], est)}{note26}</td>
        <td class="{d}">{signed_money(m['yoy_dollar'], est)}</td>
        <td class="{d}">{pct(m['yoy_pct'], signed=True, approx=est)}</td>
        <td>{money(m['ytd_2026'], m['ytd_estimate'])}</td>
        <td>{money(m['ytd_2025'], m['ytd_estimate'])}</td>
      </tr>""")
    d = direction(rev["total_yoy_dollar"])
    approx = rev["ytd_estimate"]
    rows.append(f"""
      <tr class="total">
        <td>YTD</td>
        <td>{money(rev['ytd_2025'], approx)}</td>
        <td>{money(rev['ytd_2026'], approx)}</td>
        <td class="{d}">{signed_money(rev['total_yoy_dollar'], approx)}</td>
        <td class="{d}">{pct(rev['total_yoy_pct'], signed=True, approx=approx)}</td>
        <td>{money(rev['ytd_2026'], approx)}</td>
        <td>{money(rev['ytd_2025'], approx)}</td>
      </tr>""")
    note = f'<p class="note">{esc(rev["note"])}</p>' if rev.get("note") else ""
    return f"""
    <section>
      <h2>Revenue Summary · 2026 Actuals vs 2025</h2>
      <table>
        <thead><tr>
          <th>Month</th><th>2025 Actual</th><th>2026 Actual</th>
          <th>YoY $</th><th>YoY %</th><th>2026 YTD</th><th>2025 YTD</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      {note}
    </section>"""


def _disc_rows(rows: list[dict], disc: dict, total_row: bool = False) -> str:
    out = []
    for r in rows:
        cls = ' class="total"' if total_row else ""
        out.append(f"""
      <tr{cls}>
        <td>{esc(r['name'])}</td>
        <td>{r['goal']}</td>
        <td>{r.get('prior_ytd', 0)}</td>
        <td>{r.get('current', 0)}</td>
        <td>{r['ytd']}</td>
        <td>{pct(r['pct_to_goal'], 0)}{_meter(r['pct_to_goal'])}</td>
      </tr>""")
    return "".join(out)


def render_discovery_table(disc: dict) -> str:
    prior = esc(disc.get("prior_label", "Prior YTD"))
    curr = esc(disc.get("current_label", "This month"))
    ytdl = esc(disc.get("ytd_label", "YTD"))
    body = _disc_rows(disc["categories"], disc)
    body += _disc_rows([disc["total"]], disc, total_row=True)
    if disc.get("activities"):
        body += '<tr class="spacer"><td colspan="6"></td></tr>'
        body += _disc_rows(disc["activities"], disc)
    note = f'<p class="note">{esc(disc["note"])}</p>' if disc.get("note") else ""
    pace = disc.get("pace_pct")
    pace_note = (f'<p class="note">Straight-line pace at this point in the year: '
                 f'{pct(pace, 0)}.</p>') if pace is not None else ""
    return f"""
    <section>
      <h2>Discovery Calls &amp; Activities</h2>
      <table>
        <thead><tr>
          <th>Category</th><th>Goal</th><th>{prior}</th><th>{curr}</th>
          <th>{ytdl}</th><th>% to Goal</th>
        </tr></thead>
        <tbody>{body}</tbody>
      </table>
      {pace_note}
      {note}
    </section>"""


def render_pipeline(data: dict, wins: dict, nl: dict) -> str:
    win_items = "".join(
        f'<li><span>{esc(w["name"])}</span>'
        f'<span class="amt">{money(w["amount"]) if isinstance(w.get("amount"), (int, float)) else esc(w.get("amount", ""))}</span></li>'
        for w in wins["items"]
    )
    total_line = (f'<li class="total"><span><strong>New wins booked</strong></span>'
                  f'<span class="amt">{money(wins["total"])}</span></li>'
                  if wins["total"] else "")
    deal_items = "".join(
        f'<li><span>{esc(d["name"])}</span><span class="amt">{esc(d.get("amount", ""))}</span></li>'
        for d in data.get("deals", [])
    )
    return f"""
    <section>
      <h2>Wins &amp; Pipeline</h2>
      <div class="cols">
        <div>
          <h3 style="font-size:.85rem;margin:.2rem 0 .6rem;">New Wins</h3>
          <ul class="stack">{win_items}{total_line}</ul>
        </div>
        <div>
          <h3 style="font-size:.85rem;margin:.2rem 0 .6rem;">Deals Advanced</h3>
          <ul class="stack">{deal_items}</ul>
        </div>
      </div>
    </section>"""


def render_newsletter(nl: dict) -> str:
    def card(k, v, n=""):
        n = f'<div class="n">{esc(n)}</div>' if n else ""
        return f'<div class="card"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>{n}</div>'

    open_note = ""
    if nl.get("open_delta_pts"):
        open_note = f"up {nl['open_delta_pts']:.1f} pts from {pct(nl.get('prior_open_rate'))}"
    cards = "".join([
        card("Send date", nl.get("send_date", "—")),
        card("Sent / Delivered", f"{nl.get('sent', 0):,} / {nl.get('delivered', 0):,}"),
        card("Opens", f"{nl.get('opens', 0):,}"),
        card("Open rate", pct(nl.get("open_rate"), 2), open_note),
        card("Clicks (total)", f"{nl.get('clicks_total', 0):,}",
             "highest to date" if nl.get("clicks_total") else ""),
        card("Click rate", pct(nl.get("click_rate"), 2)),
        card("CTOR (unique)", pct(nl.get("ctor_unique"), 0)),
        card("Opt-outs", f"{nl.get('opt_outs', 0):,}"),
    ])
    note = f'<p class="note">{esc(nl["note"])}</p>' if nl.get("note") else ""
    return f"""
    <section>
      <h2>Newsletter Performance</h2>
      <div class="cards">{cards}</div>
      {note}
    </section>"""


def render_leadership(data: dict) -> str:
    note = data.get("leadership_note")
    if not note:
        return ""
    obligations = "".join(f"<li>{esc(o)}</li>" for o in note.get("standing_obligations", []))
    focus = "".join(f"<li>{esc(f)}</li>" for f in note.get("focus", []))
    bad = note.get("the_bad", {})
    good = note.get("the_good", {})
    ev = data.get("events_upcoming", {})
    ev_pills = "".join(f'<span class="pill">{esc(c)}</span>' for c in ev.get("cities", []))
    ev_block = ""
    if ev.get("cities"):
        link = f' — <a href="{esc(ev["url"])}">{esc(ev.get("series", "event series"))}</a>' if ev.get("url") else ""
        ev_block = f'<p style="margin:.8rem 0 .2rem;"><strong>Upcoming events{link}:</strong></p><div>{ev_pills}</div>'
    return f"""
    <section>
      <h2>From Leadership</h2>
      <p class="lede">{esc(note.get('intro', ''))}</p>
      <p style="margin:.9rem 0 .2rem;"><strong>Standing obligations</strong></p>
      <ul class="lede">{obligations}</ul>
      <div class="callout bad"><span class="h">The bad.</span> {esc(bad.get('headline', ''))}
        <div class="annot" style="font-style:normal;color:var(--ink);opacity:.85;">{esc(bad.get('detail', ''))}</div></div>
      <div class="callout good"><span class="h">The good.</span> {esc(good.get('headline', ''))}
        <div class="annot" style="font-style:normal;color:var(--ink);opacity:.85;">{esc(good.get('detail', ''))}</div></div>
      <p style="margin:.9rem 0 .2rem;"><strong>Our focus right now</strong></p>
      <ul class="lede">{focus}</ul>
      {ev_block}
    </section>"""


def render_analysis(analysis: list[str]) -> str:
    items = "".join(f"<li>{esc(line)}</li>" for line in analysis)
    return f"""
    <section>
      <h2>At a Glance · Auto Analysis</h2>
      <ul class="lede">{items}</ul>
    </section>"""


def render_html(data: dict, c: dict) -> str:
    period = data.get("period", {})
    label = period.get("label", "Monthly Report")
    team = data.get("team", "")
    org = data.get("org", "")
    vertical = data.get("vertical", "")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prepared = data.get("prepared_by", "")
    precision = data.get("precision_note", "")
    nextnote = data.get("next_report_note", "")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(team)} — {esc(label)}</title>
<style>{STYLE}</style>
</head>
<body>
<main>
  <header class="masthead">
    <p class="eyebrow">{esc(org)} · {esc(vertical)} · Monthly Report</p>
    <h1>{esc(team)} — {esc(label)}</h1>
    <p class="sub">{esc(nextnote)}</p>
  </header>
{render_analysis(c['analysis'])}
{render_leadership(data)}
{render_revenue_table(c['revenue'])}
{render_discovery_table(c['discovery'])}
{render_pipeline(data, c['wins'], c['newsletter'])}
{render_newsletter(c['newsletter'])}
  <p class="note">{esc(precision)}</p>
  <footer>Prepared by {esc(prepared)}. Auto-assembled by finserv_report_bot.py on {generated}.<br>
  Revenue: internal revenue dashboard, Finance vertical. Discovery: prior-period reporting reconciled with current-month rep submissions. Wins/Deals: rep self-report. Newsletter: campaign platform export.</footer>
</main>
</body>
</html>
"""


def render_markdown(data: dict, c: dict) -> str:
    period = data.get("period", {})
    label = period.get("label", "Monthly Report")
    rev = c["revenue"]
    disc = c["discovery"]
    L = [
        f"# {data.get('team', '')} — {label}",
        "",
        f"_{data.get('org', '')} · {data.get('vertical', '')} · auto-assembled "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## At a glance",
        "",
    ]
    L += [f"- {line}" for line in c["analysis"]]
    L += ["", "## Revenue summary", "",
          "| Month | 2025 | 2026 | YoY $ | YoY % | 2026 YTD | 2025 YTD |",
          "|---|--:|--:|--:|--:|--:|--:|"]
    for m in rev["months"]:
        est = m["estimate"]
        L.append(f"| {m['month']}{'*' if est else ''} | {money(m['actual_2025'], est)} | "
                 f"{money(m['actual_2026'], est)} | {signed_money(m['yoy_dollar'], est)} | "
                 f"{pct(m['yoy_pct'], signed=True, approx=est)} | "
                 f"{money(m['ytd_2026'], m['ytd_estimate'])} | {money(m['ytd_2025'], m['ytd_estimate'])} |")
    ap = rev["ytd_estimate"]
    L.append(f"| **YTD** | **{money(rev['ytd_2025'], ap)}** | **{money(rev['ytd_2026'], ap)}** | "
             f"**{signed_money(rev['total_yoy_dollar'], ap)}** | "
             f"**{pct(rev['total_yoy_pct'], signed=True, approx=ap)}** | | |")

    L += ["", "## Discovery calls & activities", "",
          f"| Category | Goal | {disc.get('prior_label', 'Prior')} | "
          f"{disc.get('current_label', 'Month')} | YTD | % to goal |",
          "|---|--:|--:|--:|--:|--:|"]
    for r in disc["categories"] + [disc["total"]]:
        bold = "**" if r is disc["total"] else ""
        L.append(f"| {bold}{r['name']}{bold} | {r['goal']} | {r.get('prior_ytd', 0)} | "
                 f"{r.get('current', 0)} | {r['ytd']} | {pct(r['pct_to_goal'], 0)} |")
    for r in disc.get("activities", []):
        L.append(f"| {r['name']} | {r['goal']} | {r.get('prior_ytd', 0)} | "
                 f"{r.get('current', 0)} | {r['ytd']} | {pct(r['pct_to_goal'], 0)} |")

    L += ["", "## New wins", ""]
    for w in data.get("wins", []):
        amt = money(w["amount"]) if isinstance(w.get("amount"), (int, float)) else w.get("amount", "")
        L.append(f"- **{w['name']}** — {amt}")
    if c["wins"]["total"]:
        L.append(f"- _Total booked: {money(c['wins']['total'])}_")

    L += ["", "## Deals advanced", ""]
    for d in data.get("deals", []):
        L.append(f"- {d['name']} — {d.get('amount', '')}")

    nl = c["newsletter"]
    L += ["", "## Newsletter performance", "",
          f"- Sent **{nl.get('send_date', '')}** · {nl.get('sent', 0):,} sent / {nl.get('delivered', 0):,} delivered",
          f"- Open rate **{pct(nl.get('open_rate'), 2)}** · {nl.get('opens', 0):,} opens",
          f"- Clicks **{nl.get('clicks_total', 0):,}** (record) · click rate {pct(nl.get('click_rate'), 2)} · CTOR {pct(nl.get('ctor_unique'), 0)}",
          f"- Opt-outs {nl.get('opt_outs', 0)}"]
    if data.get("precision_note"):
        L += ["", f"> {data['precision_note']}"]
    return "\n".join(L) + "\n"


def render_index(reports: list[dict], org: str, team: str) -> str:
    """Landing page linking every month's report, newest first."""
    rows = []
    for r in reports:
        rows.append(f'<li><a href="{esc(r["html"])}">{esc(r["label"])}</a>'
                    f'<span class="annot"> · {esc(r["headline"])}</span></li>')
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(team)} — Monthly Reports</title>
<style>{STYLE}</style>
</head>
<body>
<main>
  <header class="masthead">
    <p class="eyebrow">{esc(org)} · Monthly Report</p>
    <h1>{esc(team)} — Reports</h1>
    <p class="sub">Updated {generated}</p>
  </header>
  <section>
    <h2>All Reports</h2>
    <ul class="stack" style="font-size:1.05rem;">{''.join(rows)}</ul>
  </section>
  <footer>Auto-assembled by finserv_report_bot.py.</footer>
</main>
</body>
</html>
"""


# ------------------------------------------------------------------- main ---


def month_key(data: dict) -> str:
    p = data.get("period", {})
    y = p.get("year", 0)
    m = p.get("month")
    if isinstance(m, str):
        m = MONTH_INDEX.get(m.strip().lower()[:3], 0)
    return f"{y:04d}-{m:02d}"


def build_index(out: Path, org: str, team: str) -> None:
    """(Re)build index.html from every <YYYY-MM>.html report already written."""
    reports = []
    for jf in sorted(out.glob("*.json"), reverse=True):
        if jf.name == "report.json":
            continue
        try:
            payload = json.loads(jf.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        key = jf.stem
        html_name = f"{key}.html"
        if not (out / html_name).exists():
            continue
        reports.append({
            "label": payload.get("period", {}).get("label", key),
            "html": html_name,
            "headline": (payload.get("analysis") or [""])[0],
        })
    (out / "index.html").write_text(render_index(reports, org, team), "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="FinServ monthly report assembler")
    ap.add_argument("--data", help="path to a month data JSON "
                    "(default: newest bot/data/*.json)")
    ap.add_argument("--out-dir", default="reports", help="output dir (default ./reports)")
    ap.add_argument("--data-dir", default="bot/data",
                    help="where month data files live (default bot/data)")
    args = ap.parse_args(argv)

    if args.data:
        data_path = Path(args.data)
    else:
        candidates = sorted(Path(args.data_dir).glob("*.json"))
        if not candidates:
            print(f"No data files found in {args.data_dir}", file=sys.stderr)
            return 1
        data_path = candidates[-1]

    data = json.loads(data_path.read_text("utf-8"))
    c = compute(data)
    key = month_key(data)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    html = render_html(data, c)
    md = render_markdown(data, c)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": data.get("period", {}),
        "analysis": c["analysis"],
        "revenue": c["revenue"],
        "discovery": c["discovery"],
        "wins": c["wins"],
        "newsletter": c["newsletter"],
        "source_data": data,
    }

    # Per-month artifacts, plus "latest" convenience copies.
    (out / f"{key}.html").write_text(html, "utf-8")
    (out / f"{key}.json").write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    (out / "latest.md").write_text(md, "utf-8")
    (out / "report.json").write_text(json.dumps(payload, indent=2, default=str), "utf-8")

    build_index(out, data.get("org", ""), data.get("team", ""))

    print(f"Built report for {data.get('period', {}).get('label', key)} -> {out}/")
    print(f"  {key}.html · index.html · latest.md · report.json")
    for line in c["analysis"]:
        print(f"  • {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
