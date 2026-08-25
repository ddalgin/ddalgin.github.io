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


def markup_x(value: float | None) -> str:
    """10.0327 -> '10.03x'."""
    if value is None:
        return "TBD"
    return f"{value:.2f}x"


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
    """Add YoY and running-YTD fields to each month, plus period totals.

    Handles partial months: a month with only one year's actual (e.g. June
    2026 billed but June 2025 not yet supplied) still renders — YoY and the
    incomplete side's YTD fall back to '—' rather than silently reading zero.
    """
    months = []
    ytd_2025 = ytd_2026 = 0.0
    ytd_is_estimate = False
    ytd_25_est = ytd_26_est = False
    complete_25 = complete_26 = True
    for m in rev.get("months", []):
        a25 = m.get("actual_2025")
        a26 = m.get("actual_2026")
        # Precision can differ by year within a month (e.g. May 2025 exact but
        # May 2026 still rounded). estimate_2025 / estimate_2026 override the
        # row-level `estimate` when present.
        base_est = bool(m.get("estimate"))
        est_25 = bool(m.get("estimate_2025", base_est))
        est_26 = bool(m.get("estimate_2026", base_est))
        if a25 is not None and est_25:
            ytd_25_est = True
        if a26 is not None and est_26:
            ytd_26_est = True
        ytd_is_estimate = ytd_is_estimate or est_25 or est_26
        yoy_dollar = (a26 - a25) if (a25 is not None and a26 is not None) else None
        yoy_pct = (yoy_dollar / a25 * 100) if (yoy_dollar is not None and a25) else None
        if a25 is not None:
            ytd_2025 += a25
        else:
            complete_25 = False
        if a26 is not None:
            ytd_2026 += a26
        else:
            complete_26 = False
        months.append({
            **m,
            "estimate": est_25 or est_26,
            "est_25": est_25,
            "est_26": est_26,
            "reported": a25 is not None and a26 is not None,
            "yoy_dollar": yoy_dollar,
            "yoy_pct": yoy_pct,
            "ytd_2025": ytd_2025,
            "ytd_2026": ytd_2026,
            "ytd_25_complete": complete_25,
            "ytd_26_complete": complete_26,
            "ytd_25_est": ytd_25_est,
            "ytd_26_est": ytd_26_est,
            "ytd_estimate": ytd_is_estimate,
        })
    both_complete = complete_25 and complete_26
    total_yoy_dollar = (ytd_2026 - ytd_2025) if (months and both_complete) else None
    total_yoy_pct = (total_yoy_dollar / ytd_2025 * 100) if (total_yoy_dollar is not None and ytd_2025) else None

    # Overall markup vs the same month last year (revenue / cost multiple).
    mk = rev.get("markup") or {}
    v26, v25 = mk.get("value_2026"), mk.get("value_2025")
    markup = {
        **mk,
        "value_2026": v26,
        "value_2025": v25,
        "delta": (v26 - v25) if (v26 is not None and v25 is not None) else None,
    } if mk else None

    return {
        **rev,
        "months": months,
        "ytd_2025": ytd_2025,
        "ytd_2026": ytd_2026,
        "ytd_25_complete": complete_25,
        "ytd_26_complete": complete_26,
        "ytd_25_est": ytd_25_est,
        "ytd_26_est": ytd_26_est,
        "ytd_estimate": ytd_is_estimate,
        "total_yoy_dollar": total_yoy_dollar,
        "total_yoy_pct": total_yoy_pct,
        "markup": markup,
        "months_reported": sum(1 for m in months if m["reported"]),
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

    # Total row: sum of the categories by default, but an explicit
    # `discovery.total` override wins when the team tracks a headline total
    # that doesn't reconcile to the (partly uncategorized) category rows.
    cat_ytd = sum(c["ytd"] for c in cats)
    override = disc.get("total") or {}
    total = _score_row({
        "name": override.get("name", "Total Discovery Calls"),
        "goal": override.get("goal", sum(c.get("goal") or 0 for c in cats)),
        "prior_ytd": override.get("prior_ytd", sum(c.get("prior_ytd") or 0 for c in cats)),
        "current": override.get("current", sum(c.get("current") or 0 for c in cats)),
    })
    total["uncategorized"] = (total["ytd"] - cat_ytd) if override else 0

    # Pace: fraction of the year elapsed through this month (May -> 5/12).
    pace_pct = (month_number / 12 * 100) if month_number else None
    laggards = sorted(
        (c for c in cats if c["pct_to_goal"] is not None),
        key=lambda c: c["pct_to_goal"],
    )

    # Per-AE breakdown: every rep named with their disco-call count, flagged
    # against the monthly floor. The 'reps' key being present (even empty)
    # switches the per-AE table on.
    reps = None
    team_calls = below = reps_reported = None
    if "reps" in disc:
        floor = disc.get("per_rep_monthly_floor")
        reps = []
        for r in disc.get("reps", []):
            calls = r.get("calls")
            meets = (calls >= floor) if (calls is not None and floor is not None) else None
            reps.append({**r, "calls": calls, "meets_floor": meets})
        reported = [r for r in reps if isinstance(r.get("calls"), (int, float))]
        team_calls = sum(r["calls"] for r in reported)
        reps_reported = len(reported)
        below = [r for r in reps if r["meets_floor"] is False]

    return {
        **disc,
        "categories": cats,
        "activities": acts,
        "total": total,
        "pace_pct": pace_pct,
        "leader": laggards[-1] if laggards else None,
        "laggards": laggards[:3],
        "reps": reps,
        "team_calls": team_calls,
        "reps_reported": reps_reported,
        "reps_below_floor": below,
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
    a26, a25 = rev["ytd_26_est"], rev["ytd_25_est"]
    yoy_ap = a25 or a26
    last_26 = next((m for m in reversed(rev["months"]) if m.get("actual_2026") is not None), None)
    last_both = next((m for m in reversed(rev["months"]) if m["reported"]), None)
    if rev["total_yoy_dollar"] is not None:
        trailing = rev["total_yoy_dollar"] < 0
        lines.append(
            f"Revenue is {'trailing' if trailing else 'ahead of'} last year: "
            f"{money(rev['ytd_2026'], a26)} YTD vs "
            f"{money(rev['ytd_2025'], a25)} in 2025 "
            f"({signed_money(rev['total_yoy_dollar'], yoy_ap)}, "
            f"{pct(rev['total_yoy_pct'], signed=True, approx=yoy_ap)}). "
            f"{rev['months_up']} of {rev['months_reported']} months are up YoY."
        )
    else:
        through = f" through {last_26['month']}" if last_26 else ""
        lines.append(
            f"Revenue billed {money(rev['ytd_2026'])}{through} 2026; full YoY "
            f"comparison pending the matching 2025 actuals."
        )
    if last_26 and not last_26["reported"] and last_26.get("actual_2026") is not None:
        mk_note = f" ({last_26['note_2026']})" if last_26.get("note_2026") else ""
        lines.append(f"{last_26['month']} billed {money(last_26['actual_2026'])}{mk_note}.")
    elif last_both and last_both["yoy_pct"] is not None:
        lines.append(
            f"{last_both['month']} landed {signed_money(last_both['yoy_dollar'], last_both['estimate'])} "
            f"({pct(last_both['yoy_pct'], signed=True, approx=last_both['estimate'])}) vs the prior year."
        )

    # --- Overall markup ----------------------------------------------------
    mk = rev.get("markup")
    mo = last_26["month"] if last_26 else "the prior year"
    if mk and mk.get("value_2026") is not None:
        if mk.get("value_2025") is not None:
            d = mk["delta"]
            lines.append(
                f"Overall markup is {markup_x(mk['value_2026'])} vs "
                f"{markup_x(mk['value_2025'])} last {mo} "
                f"({'+' if d >= 0 else ''}{d:.2f}x)."
            )
        else:
            lines.append(
                f"Overall markup is {markup_x(mk['value_2026'])}; the {mo} 2025 "
                f"markup for the year-over-year comparison is pending."
            )

    # --- Discovery (by category) -------------------------------------------
    floor = disc.get("per_rep_monthly_floor")
    if disc.get("categories"):
        tot = disc["total"]
        pace = disc.get("pace_pct")
        behind = pace is not None and tot["pct_to_goal"] is not None and tot["pct_to_goal"] < pace
        pace_clause = ""
        if pace is not None:
            pace_clause = (f" — {'behind' if behind else 'ahead of'} the "
                           f"{pct(pace, 0)} straight-line pace for this point in the year")
        added = f" {label} added {tot['current']} calls." if tot["current"] else ""
        lines.append(
            f"Discovery calls are at {tot['ytd']} of {tot['goal']} "
            f"({pct(tot['pct_to_goal'], 0)} to goal){pace_clause}.{added}"
        )
        if disc.get("laggards"):
            weak = ", ".join(f"{c['name'].replace('Disco - ', '')} ({pct(c['pct_to_goal'], 0)})"
                             for c in disc["laggards"])
            lines.append(f"Furthest from goal: {weak}.")
        if floor:
            lines.append(
                f"Standing floor is {floor} legit discovery calls per rep on their worst month — "
                f"the categories above are the team's obligation, not a stretch target."
            )

    # --- Discovery (by AE) -------------------------------------------------
    if disc.get("reps") is not None:
        total_reps = len(disc["reps"])
        if disc.get("reps_reported"):
            below = disc["reps_below_floor"]
            names = ", ".join(r["name"] for r in below)
            floor_clause = (f" {len(below)} below the {floor}-call floor: {names}."
                            if below else f" Every reporting AE cleared the {floor}-call floor.")
            pending = total_reps - disc["reps_reported"]
            pending_clause = (f" {pending} of {total_reps} AEs still pending — team total will rise."
                              if pending else "")
            lines.append(
                f"By AE: {disc['reps_reported']} of {total_reps} reps have reported "
                f"{disc['team_calls']} discovery calls in {label} so far.{floor_clause}{pending_clause}"
            )
        else:
            lines.append(
                f"Per-AE discovery is set up — awaiting each AE named with their "
                f"disco-call count against the {floor}-call floor."
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
  .masthead { background:var(--brand); color:#fff; padding:1.5rem 1.5rem;
    border-radius:0 0 14px 14px; margin-bottom:1.1rem;
    border-bottom:4px solid #29abe2; }
  .masthead .eyebrow { text-transform:uppercase; letter-spacing:.14em;
    font-size:.72rem; color:#5cc4ee; margin:0 0 .35rem; }
  .masthead h1 { margin:0; font-size:2rem; line-height:1.1; letter-spacing:-.01em; }
  .masthead .sub { margin:.5rem 0 0; opacity:.85; font-size:.9rem; }
  section { background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:1rem 1.25rem; margin-bottom:1rem; }
  h2 { font-size:.8rem; text-transform:uppercase; letter-spacing:.12em;
    color:var(--brand-2); margin:0 0 .8rem; padding-bottom:.5rem;
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
  .hero { display:grid; grid-template-columns:repeat(auto-fit,minmax(155px,1fr)); gap:.9rem; margin-bottom:1.4rem; }
  .tile { background:var(--card); border:1px solid var(--line); border-top:3px solid var(--brand-2);
    border-radius:12px; padding:1rem 1.1rem; }
  .tile.good { border-top-color:var(--up); }
  .tile .k { font-size:.7rem; text-transform:uppercase; letter-spacing:.09em; color:var(--muted); }
  .tile .v { font-size:1.75rem; font-weight:800; line-height:1.05; margin-top:.28rem; letter-spacing:-.02em; }
  .tile .s { font-size:.8rem; margin-top:.3rem; font-weight:600; color:var(--muted); }
  .tile .s.up { color:var(--up); } .tile .s.down { color:var(--down); }
  .banner { display:flex; gap:.6rem; align-items:baseline; background:rgba(38,146,86,.12);
    border:1px solid rgba(38,146,86,.4); border-radius:10px; padding:.75rem 1rem; margin-bottom:1.5rem;
    font-size:.95rem; }
  .banner .mark { color:var(--up); font-weight:800; }
  .banner strong { color:var(--up); }
  .chips2 { display:flex; flex-wrap:wrap; gap:.5rem; }
  .ae-chip { display:flex; flex-direction:column; gap:.05rem; padding:.45rem .75rem;
    border-radius:9px; border:1px solid var(--line); background:var(--band); min-width:116px; }
  .ae-chip.met { background:rgba(38,146,86,.13); border-color:rgba(38,146,86,.45); }
  .ae-chip .top { display:flex; justify-content:space-between; gap:.8rem; align-items:baseline; }
  .ae-chip .nm { font-weight:600; font-size:.86rem; }
  .ae-chip .ct { font-weight:800; font-variant-numeric:tabular-nums; font-size:.95rem; }
  .ae-chip.met .ct { color:var(--up); }
  .ae-chip .ac { color:var(--muted); font-size:.72rem; }
  .pending-names { color:var(--muted); font-size:.86rem; margin-top:.9rem; }
  .wtable th, .wtable td { text-align:left; white-space:normal; vertical-align:top; }
  .wtable td.rk { width:2.2rem; color:var(--muted); font-weight:700; }
  .wtable td.val { font-weight:700; white-space:nowrap; }
  .wtable td.note { color:var(--muted); font-size:.86rem; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); gap:.55rem; }
  .card { background:var(--band); border:1px solid var(--line); border-radius:9px;
    padding:.55rem .7rem; }
  .card .k { font-size:.66rem; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }
  .card .v { font-size:1.2rem; font-weight:700; margin-top:.1rem; line-height:1.1; }
  .card .n { font-size:.7rem; color:var(--muted); margin-top:.15rem; }
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
  .note { color:var(--muted); font-size:.82rem; margin-top:.6rem; }
  .empty { color:var(--muted); padding:.7rem 0; font-style:italic; }
  td.empty { text-align:center; }
  .draft-pill { display:inline-block; vertical-align:middle; font-size:.68rem;
    letter-spacing:.14em; background:#f5c518; color:#3a2d00; padding:.22rem .6rem;
    border-radius:6px; margin-left:.6rem; font-weight:800; }
  footer { color:var(--muted); font-size:.8rem; margin-top:2rem; text-align:center; }
  a { color:var(--accent); }
"""


def _meter(pct_value: float | None) -> str:
    if pct_value is None:
        return ""
    w = max(0, min(100, pct_value))
    return f'<div class="meter"><span style="width:{w:.0f}%"></span></div>'


def render_markup(rev: dict, month_abbr: str) -> str:
    """The 'overall markup vs last year' comparison band."""
    mk = rev.get("markup")
    if not mk or (mk.get("value_2026") is None and mk.get("value_2025") is None):
        return ""
    d = mk.get("delta")
    dcell = f"{'+' if d >= 0 else ''}{d:.2f}x" if d is not None else "TBD"
    dcls = direction(d)
    note = f'<p class="note">{esc(mk["note"])}</p>' if mk.get("note") else ""
    return f"""
      <div class="cards" style="margin-bottom:1.1rem;">
        <div class="card"><div class="k">Overall Markup · {esc(month_abbr)} '26</div><div class="v">{markup_x(mk.get('value_2026'))}</div></div>
        <div class="card"><div class="k">{esc(month_abbr)} '25</div><div class="v">{markup_x(mk.get('value_2025'))}</div></div>
        <div class="card"><div class="k">YoY</div><div class="v {dcls}">{dcell}</div></div>
      </div>{note}"""


def render_revenue_table(rev: dict, month_abbr: str = "") -> str:
    rows = []
    for m in rev["months"]:
        est25, est26 = m["est_25"], m["est_26"]
        yoy_est = est25 or est26
        d = direction(m["yoy_dollar"])
        note25 = f' <span class="annot">{esc(m["note_2025"])}</span>' if m.get("note_2025") else ""
        note26 = f' <span class="annot">{esc(m["note_2026"])}</span>' if m.get("note_2026") else ""
        star = "*" if yoy_est else ""
        ytd26 = money(m['ytd_2026'], m['ytd_26_est']) if m['ytd_26_complete'] else "—"
        ytd25 = money(m['ytd_2025'], m['ytd_25_est']) if m['ytd_25_complete'] else "—"
        rows.append(f"""
      <tr>
        <td>{esc(m['month'])}{star}</td>
        <td>{money(m['actual_2025'], est25)}{note25}</td>
        <td>{money(m['actual_2026'], est26)}{note26}</td>
        <td class="{d}">{signed_money(m['yoy_dollar'], yoy_est)}</td>
        <td class="{d}">{pct(m['yoy_pct'], signed=True, approx=yoy_est)}</td>
        <td>{ytd26}</td>
        <td>{ytd25}</td>
      </tr>""")
    d = direction(rev["total_yoy_dollar"])
    approx = rev["ytd_25_est"] or rev["ytd_26_est"]
    t26 = money(rev['ytd_2026'], rev['ytd_26_est']) if rev['ytd_26_complete'] else "—"
    t25 = money(rev['ytd_2025'], rev['ytd_25_est']) if rev['ytd_25_complete'] else "—"
    rows.append(f"""
      <tr class="total">
        <td>YTD</td>
        <td>{t25}</td>
        <td>{t26}</td>
        <td class="{d}">{signed_money(rev['total_yoy_dollar'], approx)}</td>
        <td class="{d}">{pct(rev['total_yoy_pct'], signed=True, approx=approx)}</td>
        <td>{t26}</td>
        <td>{t25}</td>
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


def _cell(v, tbd: str = "TBD"):
    return tbd if v is None else v


def _disc_rows(rows: list[dict], disc: dict, total_row: bool = False) -> str:
    out = []
    for r in rows:
        cls = ' class="total"' if total_row else ""
        out.append(f"""
      <tr{cls}>
        <td>{esc(r['name'])}</td>
        <td>{_cell(r.get('goal'), '—')}</td>
        <td>{_cell(r.get('prior_ytd'), '—')}</td>
        <td>{_cell(r.get('current'))}</td>
        <td>{_cell(r['ytd'], '—')}</td>
        <td>{pct(r['pct_to_goal'], 0)}{_meter(r['pct_to_goal'])}</td>
      </tr>""")
    return "".join(out)


def render_discovery_reps(disc: dict) -> str:
    """Per-person discovery: reporters as compact chips (green = hit the floor),
    non-reporters listed compactly. No red — not-green carries the message."""
    if disc.get("reps") is None:
        return ""
    floor = disc.get("per_rep_monthly_floor")
    # Validation policy: only show discovery calls tied to a named prospect —
    # calls without a validatable account are excluded entirely (no name, no
    # number).
    reported = [r for r in disc["reps"] if r.get("calls") and r.get("accounts")]
    if not reported:
        return ""

    chips = ""
    for r in sorted(reported, key=lambda x: -x["calls"]):
        met = "met" if r.get("meets_floor") else ""
        acct = f'<span class="ac">{esc(r["accounts"])}</span>'
        chips += (f'<div class="ae-chip {met}"><div class="top">'
                  f'<span class="nm">{esc(r["name"])}</span>'
                  f'<span class="ct">{r["calls"]}</span></div>{acct}</div>')
    chips_block = f'<div class="chips2">{chips}</div>'

    shown = sum(r["calls"] for r in reported)
    hit = sum(1 for r in reported if r.get("meets_floor"))
    summ = (f'<p class="note"><strong>{len(reported)} reps</strong> · {shown} discovery calls '
            f'with a named prospect · {hit} hit the {floor}-call floor (green). '
            f'Calls without a named prospect are not shown.</p>')
    return f"""
    <section>
      <h2>Discovery Calls · By Person</h2>
      {chips_block}
      {summ}
    </section>"""


def render_discovery_table(disc: dict) -> str:
    if not disc.get("categories"):
        return ""
    prior = esc(disc.get("prior_label", "Prior YTD"))
    curr = esc(disc.get("current_label", "This month"))
    ytdl = esc(disc.get("ytd_label", "YTD"))
    body = _disc_rows(disc["categories"], disc)
    body += _disc_rows([disc["total"]], disc, total_row=True)
    if disc.get("activities"):
        body += '<tr class="spacer"><td colspan="6"></td></tr>'
        body += _disc_rows(disc["activities"], disc)
    note = f'<p class="note">{esc(disc["note"])}</p>' if disc.get("note") else ""
    pace_note = ""
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
    ) or '<li class="empty">Pending — to be updated.</li>'
    total_line = (f'<li class="total"><span><strong>New wins booked</strong></span>'
                  f'<span class="amt">{money(wins["total"])}</span></li>'
                  if wins["total"] else "")
    deal_items = "".join(
        f'<li><span>{esc(d["name"])}</span><span class="amt">{esc(d.get("amount", ""))}</span></li>'
        for d in data.get("deals", [])
    ) or '<li class="empty">Pending — to be updated.</li>'
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
    if not (nl.get("sent") or nl.get("open_rate") or nl.get("send_date")):
        return """
    <section>
      <h2>Newsletter Performance</h2>
      <p class="empty">Pending — campaign platform export to be added.</p>
    </section>"""

    def card(k, v, n=""):
        n = f'<div class="n">{esc(n)}</div>' if n else ""
        return f'<div class="card"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>{n}</div>'

    open_note = ""
    if nl.get("open_delta_pts"):
        d = nl["open_delta_pts"]
        open_note = f"{'up' if d >= 0 else 'down'} {abs(d):.1f} pts from {pct(nl.get('prior_open_rate'))}"
    deliv = nl.get("delivery_rate")
    if nl.get("delivered") is not None:
        sd_val = f"{nl.get('sent', 0):,} / {nl['delivered']:,}"
        deliv_note = f"{deliv:.0f}% delivered" if deliv is not None else ""
    else:
        sd_val, deliv_note = f"{nl.get('sent', 0):,}", ""
    parts = []
    if nl.get("send_date"):
        parts.append(card("Send date", nl["send_date"]))
    parts += [
        card("Sent / Delivered", sd_val, deliv_note),
        card("Opens", f"{nl.get('opens', 0):,}"),
        card("Open rate", pct(nl.get("open_rate"), 2), open_note),
        card("Clicks (total)", f"{nl.get('clicks_total', 0):,}", nl.get("clicks_note", "")),
        card("Click rate", pct(nl.get("click_rate"), 2)),
        card("CTOR (unique)", pct(nl.get("ctor_unique"), 0)),
    ]
    if nl.get("opt_outs") is not None:
        parts.append(card("Opt-outs", f"{nl['opt_outs']:,}"))
    cards = "".join(parts)
    note = f'<p class="note">{esc(nl["note"])}</p>' if nl.get("note") else ""
    return f"""
    <section class="page-close">
      <h2>Newsletter Performance</h2>
      <div class="cards">{cards}</div>
      {note}
    </section>"""


def render_engagement(data: dict) -> str:
    """Brand / client-touch highlights (e.g. client kits), one green callout each."""
    items = data.get("engagement")
    if not items:
        return ""
    blocks = "".join(f'<div class="callout good">{esc(x)}</div>' for x in items)
    return f"""
    <section>
      <h2>Brand &amp; Client Engagement</h2>
      {blocks}
    </section>"""


def render_opportunities(data: dict) -> str:
    """New Opportunities Logged (net-new pipeline): a count, the opportunity
    names, and an optional by-owner ranking. Renders only when declared."""
    o = data.get("opportunities_logged")
    if o is None:
        return ""
    title = o.get("title", "New Opportunities Logged")
    items = o.get("items") or []
    by_owner = o.get("by_owner") or []
    count = o.get("count")
    if count is None and items:
        count = len(items)
    count_str = f"{count:,}" if count is not None else "—"

    if items:
        lis = "".join(
            f'<li><span>{esc(it.get("name", ""))}</span>'
            f'<span class="amt">{esc(it.get("owner", ""))}</span></li>'
            for it in items)
        names = f'<ul class="stack">{lis}</ul>'
    else:
        names = '<p class="empty">Opportunity names to be added.</p>'

    owner_block = ""
    if by_owner:
        rows = "".join(
            f'<tr><td>{esc(r.get("name", ""))}</td>'
            f'<td class="val">{_cell(r.get("count"), "—")}</td></tr>'
            for r in sorted(by_owner, key=lambda x: -(x.get("count") or 0)))
        owner_block = (f'<h3 style="font-size:.85rem;margin:1rem 0 .5rem;">By owner</h3>'
                       f'<table class="wtable"><thead><tr><th>Owner</th><th>Logged</th></tr>'
                       f'</thead><tbody>{rows}</tbody></table>')
    note = f'<p class="note">{esc(o["note"])}</p>' if o.get("note") else ""
    return f"""
    <section>
      <h2>{esc(title)}</h2>
      <div class="cards"><div class="card"><div class="k">Logged</div>
        <div class="v">{count_str}</div></div></div>
      {names}
      {owner_block}
      {note}
    </section>"""


def render_gifting(data: dict) -> str:
    """FS Gifting Program tracker: total delivered (aggregate) + by AE.
    Renders only when the `gifting` key is declared; empty-states its header."""
    g = data.get("gifting")
    if g is None:
        return ""
    title = g.get("program", "FS Gifting Program")
    by_ae = g.get("by_ae") or []
    total = g.get("total_delivered")
    if total is None and any(x.get("delivered") is not None for x in by_ae):
        total = sum(x.get("delivered") or 0 for x in by_ae)
    total_str = f"{total:,}" if total is not None else "—"
    if by_ae:
        rows = "".join(
            f'<tr><td>{esc(x.get("name", ""))}</td>'
            f'<td class="val">{_cell(x.get("delivered"), "—")}</td></tr>'
            for x in by_ae)
        body = (f'<table class="wtable"><thead><tr><th>AE</th><th>Delivered</th></tr>'
                f'</thead><tbody>{rows}</tbody></table>')
    else:
        body = '<p class="empty">Aggregate and by-AE delivery counts to be tracked here.</p>'
    return f"""
    <section>
      <h2>{esc(title)}</h2>
      <div class="cards"><div class="card"><div class="k">Total Delivered</div>
        <div class="v">{total_str}</div></div></div>
      {body}
    </section>"""


def render_cx_engagement(data: dict) -> str:
    """CX Engagement Program tracker: outcomes (event attendance, referrals,
    VIP confirmations, …). Renders only when the `cx_engagement` key is declared."""
    cx = data.get("cx_engagement")
    if cx is None:
        return ""
    title = cx.get("program", "CX Engagement Program")
    outs = cx.get("outcomes") or []
    if outs:
        rows = "".join(
            f'<tr><td>{esc(o.get("outcome", ""))}</td>'
            f'<td class="val">{_cell(o.get("count"), "—")}</td>'
            f'<td class="note">{esc(o.get("detail", ""))}</td></tr>'
            for o in outs)
        body = (f'<table class="wtable"><thead><tr><th>Outcome</th><th>Count</th>'
                f'<th>Detail</th></tr></thead><tbody>{rows}</tbody></table>')
    else:
        body = ('<p class="empty">Outcomes to be tracked — event attendance, '
                'referrals, VIP event confirmations, etc.</p>')
    return f"""
    <section>
      <h2>{esc(title)}</h2>
      {body}
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
    bad_block = good_block = ""
    if bad.get("headline"):
        bad_block = (f'<div class="callout bad"><span class="h">The bad.</span> {esc(bad["headline"])}'
                     f'<div class="annot" style="font-style:normal;color:var(--ink);opacity:.85;">{esc(bad.get("detail", ""))}</div></div>')
    if good.get("headline"):
        good_block = (f'<div class="callout good"><span class="h">The good.</span> {esc(good["headline"])}'
                      f'<div class="annot" style="font-style:normal;color:var(--ink);opacity:.85;">{esc(good.get("detail", ""))}</div></div>')
    return f"""
    <section class="leadership">
      <h2>From Leadership</h2>
      <p class="lede">{esc(note.get('intro', ''))}</p>
      <p style="margin:.9rem 0 .2rem;"><strong>Standing obligations</strong></p>
      <ul class="lede">{obligations}</ul>
      {bad_block}
      {good_block}
      <p style="margin:.9rem 0 .2rem;"><strong>Our focus right now</strong></p>
      <ul class="lede">{focus}</ul>
      {ev_block}
    </section>"""


def _tile(k: str, v: str, s: str = "", s_cls: str = "", good: bool = False) -> str:
    s_html = f'<div class="s {s_cls}">{esc(s)}</div>' if s else ""
    return (f'<div class="tile{" good" if good else ""}">'
            f'<div class="k">{esc(k)}</div><div class="v">{esc(v)}</div>{s_html}</div>')


def render_hero(data: dict, c: dict) -> str:
    """Top-line KPI tiles — the numbers that matter, good ones flagged green."""
    rev, disc, wins, nl = c["revenue"], c["discovery"], c["wins"], c["newsletter"]
    tiles = []

    last = next((m for m in reversed(rev["months"]) if m.get("actual_2026") is not None), None)
    if last:
        yoy, e = last["yoy_dollar"], (last["est_26"] or last["est_25"])
        if yoy is not None:
            sub = f"{signed_money(yoy, e)} · {pct(last['yoy_pct'], 1, signed=True, approx=e)} YoY"
            tiles.append(_tile(f"{last['month']} Revenue", money(last['actual_2026'], last['est_26']),
                               sub, direction(yoy), good=yoy > 0))
        else:
            tiles.append(_tile(f"{last['month']} Revenue", money(last['actual_2026'], last['est_26']),
                               "YoY pending"))
    if rev["ytd_26_complete"]:
        tot = rev["total_yoy_dollar"]
        sub = (f"{pct(rev['total_yoy_pct'], 1, signed=True, approx=rev['ytd_25_est'] or rev['ytd_26_est'])} vs '25"
               if tot is not None else "vs '25 pending")
        tiles.append(_tile("2026 YTD", money(rev["ytd_2026"], rev["ytd_26_est"]),
                           sub, direction(tot)))
    mk = rev.get("markup")
    if mk and mk.get("value_2026") is not None:
        if mk.get("value_2025") is not None:
            d = mk["delta"]
            sub = f"vs {markup_x(mk['value_2025'])} '25 · {'+' if d >= 0 else ''}{d:.2f}x"
            tiles.append(_tile("Overall Markup", markup_x(mk["value_2026"]), sub,
                               "up" if d >= 0 else "down", good=d >= 0))
        else:
            tiles.append(_tile("Overall Markup", markup_x(mk["value_2026"]),
                               "vs last year — pending", "", good=True))
    if wins.get("total"):
        tiles.append(_tile("New Wins", money(wins["total"]),
                           f"{wins['count']} closed", "up", good=True))
    if nl.get("open_rate") is not None:
        tiles.append(_tile("Newsletter Open", pct(nl["open_rate"], 1),
                           esc(nl.get("open_note", "")), "up", good=True))
    return f'<div class="hero">{"".join(tiles)}</div>' if tiles else ""


def render_banner(c: dict) -> str:
    """One punchy good-news line, when there is one."""
    rev = c["revenue"]
    last, idx = None, 0
    for i in range(len(rev["months"]) - 1, -1, -1):
        if rev["months"][i]["reported"]:
            last, idx = rev["months"][i], i
            break
    if last and (last["yoy_dollar"] or 0) > 0:
        prior_ups = [m for m in rev["months"][:idx] if (m["yoy_dollar"] or 0) > 0]
        since = f"first up-month since {prior_ups[-1]['month']}" if prior_ups else "first up-month of the year"
        return (f'<div class="banner"><span class="mark">▲</span><div>'
                f'<strong>{last["month"]} revenue up {pct(last["yoy_pct"], 1, approx=last["est_26"])} '
                f'YoY</strong> ({signed_money(last["yoy_dollar"], last["est_26"])}) — the {since}, '
                f'even as unit volume stays soft.</div></div>')
    # No up-month? Lead with profitability if markup improved YoY.
    mk = rev.get("markup")
    if mk and mk.get("delta") is not None and mk["delta"] > 0:
        mo = last["month"] if last else "last year"
        return (f'<div class="banner"><span class="mark">▲</span><div>'
                f'<strong>More profitable YoY — markup {markup_x(mk["value_2026"])} vs '
                f'{markup_x(mk["value_2025"])} last {mo}</strong> (+{mk["delta"]:.2f}x), '
                f'even as revenue softened.</div></div>')
    return ""


def _ranked_table(block: dict, cols: list[tuple[str, str]], extra_class: str = "") -> str:
    """Render a ranked account table. `cols` is [(header, key), ...]; the first
    non-rank column is bolded as the account, a 'value' key is emphasized."""
    rows = block.get("rows", [])
    heads = "<th>Rank</th>" + "".join(f"<th>{esc(h)}</th>" for h, _ in cols)
    body = ""
    for i, r in enumerate(rows, 1):
        cells = f'<td class="rk">{i}</td>'
        for _, key in cols:
            v = esc(r.get(key, ""))
            if key == "account":
                cells += f"<td><strong>{v}</strong></td>"
            elif key == "value":
                cells += f'<td class="val">{v}</td>'
            elif key in ("note", "risk"):
                cells += f'<td class="note">{v}</td>'
            else:
                cells += f"<td>{v}</td>"
        body += f"<tr>{cells}</tr>"
    sc = f' class="{extra_class}"' if extra_class else ""
    return (f'<section{sc}>\n      <h2>{esc(block.get("title", ""))}</h2>\n'
            f'      <table class="wtable"><thead><tr>{heads}</tr></thead>'
            f'<tbody>{body}</tbody></table>\n    </section>')


def render_wins_ranked(data: dict) -> str:
    """The ranked Confirmed Wins + Highest-Value Pipeline tables."""
    out = ""
    if data.get("wins_confirmed"):
        out += _ranked_table(data["wins_confirmed"],
                             [("Account", "account"), ("Value", "value"),
                              ("Strategic Note", "note")], extra_class="page-wins")
    if data.get("pipeline_ranked"):
        out += _ranked_table(data["pipeline_ranked"],
                             [("Account", "account"), ("Value", "value"),
                              ("Status", "status"), ("Risk Flag", "risk")])
    return out


def render_closing(data: dict, c: dict) -> str:
    """Wins / Pipeline / Newsletter — each part shows fully when it has data and
    collapses to a compact pending line when it doesn't, so a populated section
    (e.g. the newsletter) never drags empty ones along as blank columns."""
    nl = c["newsletter"]
    out = ""
    ranked = render_wins_ranked(data)
    if ranked:
        out += ranked
    elif bool(data.get("wins")) or bool(data.get("deals")):
        out += render_pipeline(data, c["wins"], nl)
    else:
        out += """
    <section>
      <h2>Wins &amp; Pipeline</h2>
      <p class="empty">Pending — new wins and deals advanced land with final June reporting.</p>
    </section>"""
    out += render_newsletter(nl)  # renders its own "pending" line when empty
    return out


ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


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
    mnum = c.get("month_number") or 0
    month_abbr = ABBR[mnum] if 0 < mnum < len(ABBR) else ""
    is_draft = str(data.get("status", "")).upper() == "DRAFT"
    draft_badge = '<span class="draft-pill">DRAFT</span>' if is_draft else ""
    title = data.get("report_title", team)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} — {esc(label)}</title>
<style>{STYLE}</style>
</head>
<body>
<main>
  <header class="masthead">
    <p class="eyebrow">{esc(org)} · {esc(vertical)} · Monthly Report</p>
    <h1>{esc(title)} — {esc(label)}{draft_badge}</h1>
    {f'<p class="sub">{esc(nextnote)}</p>' if nextnote else ''}
  </header>
{render_hero(data, c)}
{render_banner(c)}
{render_revenue_table(c['revenue'], month_abbr)}
{render_discovery_table(c['discovery'])}
{render_discovery_reps(c['discovery'])}
{render_closing(data, c)}
{render_opportunities(data)}
{render_engagement(data)}
{render_gifting(data)}
{render_cx_engagement(data)}
{render_leadership(data)}
  {f'<p class="note">{esc(precision)}</p>' if precision else ''}
  {('<footer>Prepared by ' + esc(prepared) + '. Auto-assembled by finserv_report_bot.py on ' + generated + '.<br>Revenue: internal revenue dashboard, Finance vertical. Discovery: prior-period reporting reconciled with current-month rep submissions. Wins/Deals: rep self-report. Newsletter: campaign platform export.</footer>') if data.get('show_footer', True) else ''}
</main>
</body>
</html>
"""


def _md_cell(v, tbd="TBD"):
    return tbd if v is None else v


def render_markdown(data: dict, c: dict) -> str:
    period = data.get("period", {})
    label = period.get("label", "Monthly Report")
    rev = c["revenue"]
    disc = c["discovery"]
    mnum = c.get("month_number") or 0
    month_abbr = ABBR[mnum] if 0 < mnum < len(ABBR) else ""
    draft = " [DRAFT]" if str(data.get("status", "")).upper() == "DRAFT" else ""
    L = [
        f"# {data.get('team', '')} — {label}{draft}",
        "",
        f"_{data.get('org', '')} · {data.get('vertical', '')} · auto-assembled "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## At a glance",
        "",
    ]
    L += [f"- {line}" for line in c["analysis"]]

    L += ["", "## Revenue summary", ""]
    mk = rev.get("markup")
    if mk and mk.get("value_2026") is not None:
        L.append(f"**Overall markup — {month_abbr} '26:** {markup_x(mk.get('value_2026'))} "
                 f"vs {markup_x(mk.get('value_2025'))} last year"
                 + (f" ({'+' if mk['delta'] >= 0 else ''}{mk['delta']:.2f}x)." if mk.get("delta") is not None else "."))
        L.append("")
    L += ["| Month | 2025 | 2026 | YoY $ | YoY % | 2026 YTD | 2025 YTD |",
          "|---|--:|--:|--:|--:|--:|--:|"]
    for m in rev["months"]:
        est25, est26 = m["est_25"], m["est_26"]
        yoy_est = est25 or est26
        ytd26 = money(m['ytd_2026'], m['ytd_26_est']) if m['ytd_26_complete'] else "—"
        ytd25 = money(m['ytd_2025'], m['ytd_25_est']) if m['ytd_25_complete'] else "—"
        L.append(f"| {m['month']}{'*' if yoy_est else ''} | {money(m['actual_2025'], est25)} | "
                 f"{money(m['actual_2026'], est26)} | {signed_money(m['yoy_dollar'], yoy_est)} | "
                 f"{pct(m['yoy_pct'], signed=True, approx=yoy_est)} | {ytd26} | {ytd25} |")
    t26 = money(rev['ytd_2026'], rev['ytd_26_est']) if rev['ytd_26_complete'] else "—"
    t25 = money(rev['ytd_2025'], rev['ytd_25_est']) if rev['ytd_25_complete'] else "—"
    ap = rev["ytd_25_est"] or rev["ytd_26_est"]
    L.append(f"| **YTD** | **{t25}** | **{t26}** | "
             f"**{signed_money(rev['total_yoy_dollar'], ap)}** | "
             f"**{pct(rev['total_yoy_pct'], signed=True, approx=ap)}** | | |")

    named = [r for r in (disc.get("reps") or []) if r.get("calls") and r.get("accounts")]
    if named:
        floor = disc.get("per_rep_monthly_floor")
        L += ["", "## Discovery calls by person (named prospects only)", "",
              "| Person | Disco Calls | Prospects | vs Floor |", "|---|--:|---|:--|"]
        for r in sorted(named, key=lambda x: -x["calls"]):
            status = "✓ meets floor" if r.get("meets_floor") else "—"
            L.append(f"| {r['name']} | {r['calls']} | {r.get('accounts','')} | {status} |")

    if disc.get("categories"):
        L += ["", "## Discovery calls & activities", "",
              f"| Category | Goal | {disc.get('prior_label', 'Prior')} | "
              f"{disc.get('current_label', 'Month')} | YTD | % to goal |",
              "|---|--:|--:|--:|--:|--:|"]
        for r in disc["categories"] + [disc["total"]]:
            bold = "**" if r is disc["total"] else ""
            L.append(f"| {bold}{r['name']}{bold} | {_md_cell(r.get('goal'), '—')} | "
                     f"{_md_cell(r.get('prior_ytd'), '—')} | {_md_cell(r.get('current'))} | "
                     f"{_md_cell(r['ytd'], '—')} | {pct(r['pct_to_goal'], 0)} |")
        for r in disc.get("activities", []):
            L.append(f"| {r['name']} | {_md_cell(r.get('goal'), '—')} | "
                     f"{_md_cell(r.get('prior_ytd'), '—')} | {_md_cell(r.get('current'))} | "
                     f"{_md_cell(r['ytd'], '—')} | {pct(r['pct_to_goal'], 0)} |")

    conf, pipe = data.get("wins_confirmed"), data.get("pipeline_ranked")
    if conf or pipe:
        if conf:
            L += ["", f"## {conf.get('title', 'Confirmed wins')}", "",
                  "| # | Account | Value | Strategic Note |", "|--:|---|---|---|"]
            for i, r in enumerate(conf.get("rows", []), 1):
                L.append(f"| {i} | {r.get('account','')} | {r.get('value','')} | {r.get('note','')} |")
        if pipe:
            L += ["", f"## {pipe.get('title', 'Pipeline')}", "",
                  "| # | Account | Value | Status | Risk Flag |", "|--:|---|---|---|---|"]
            for i, r in enumerate(pipe.get("rows", []), 1):
                L.append(f"| {i} | {r.get('account','')} | {r.get('value','')} | "
                         f"{r.get('status','')} | {r.get('risk','')} |")
    else:
        L += ["", "## New wins", ""]
        if data.get("wins"):
            for w in data["wins"]:
                amt = money(w["amount"]) if isinstance(w.get("amount"), (int, float)) else w.get("amount", "")
                L.append(f"- **{w['name']}** — {amt}")
            if c["wins"]["total"]:
                L.append(f"- _Total booked: {money(c['wins']['total'])}_")
        else:
            L.append("_Pending — to be updated._")
        L += ["", "## Deals advanced", ""]
        if data.get("deals"):
            for d in data["deals"]:
                L.append(f"- {d['name']} — {d.get('amount', '')}")
        else:
            L.append("_Pending — to be updated._")

    nl = c["newsletter"]
    L += ["", "## Newsletter performance", ""]
    if nl.get("sent") or nl.get("open_rate") or nl.get("send_date"):
        L += [f"- Sent **{nl.get('send_date', '')}** · {nl.get('sent', 0):,} sent / {nl.get('delivered', 0):,} delivered",
              f"- Open rate **{pct(nl.get('open_rate'), 2)}** · {nl.get('opens', 0):,} opens",
              f"- Clicks **{nl.get('clicks_total', 0):,}** · click rate {pct(nl.get('click_rate'), 2)} · CTOR {pct(nl.get('ctor_unique'), 0)}",
              f"- Opt-outs {nl.get('opt_outs', 0)}"]
    else:
        L.append("_Pending — campaign platform export to be added._")
    if data.get("engagement"):
        L += ["", "## Brand & client engagement", ""]
        L += [f"- {x}" for x in data["engagement"]]
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
        is_draft = str(payload.get("status", "")).upper() == "DRAFT"
        label = payload.get("period", {}).get("label", key)
        reports.append({
            "label": f"{label} · DRAFT" if is_draft else label,
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
        "status": data.get("status", ""),
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
