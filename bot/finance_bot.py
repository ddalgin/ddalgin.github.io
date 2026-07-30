#!/usr/bin/env python3
"""Personal Finance Bot.

Reads a plain-JSON snapshot of your money (cash, cards, investments, income,
outflows, goals) and turns it into a dashboard. It does all the arithmetic the
spreadsheet used to do — net worth, true cash cushion, debt payoff order, a
month-by-month pay-in-full calendar, emergency-fund tiers, surplus allocation —
and writes:

  <out>/index.html    - browsable dashboard (served by GitHub Pages)
  <out>/finance.json  - machine-readable snapshot + every computed figure
  <out>/latest.md     - plain-text digest, easy to read on GitHub

Stdlib only - no pip installs needed.

PRIVACY: your real numbers live in `finance/data.json`, which is gitignored and
never pushed. The committed demo is built from `bot/finance_data.sample.json`
(fake numbers). To build your real dashboard locally:

  python bot/finance_bot.py --data finance/data.json --out-dir finance/private

`finance/private/` is gitignored too, so real figures never land in the repo.

Usage:
  python bot/finance_bot.py                                   # sample -> finance/
  python bot/finance_bot.py --data finance/data.json --out-dir finance/private
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import math
import sys
from datetime import datetime, date, timezone
from pathlib import Path

DEFAULT_DATA = "bot/finance_data.sample.json"


# ------------------------------------------------------------- computation ---


def money(x) -> float:
    """Coerce a possibly-None number to float; None -> 0.0."""
    return float(x) if x is not None else 0.0


def compute(data: dict) -> dict:
    """Turn the raw snapshot into every derived figure the dashboard shows.

    Kept deliberately pure (dict in, dict out) so test_finance.py can pin the
    arithmetic without touching files.
    """
    cash = data.get("cash_accounts", [])
    cards = data.get("cards", [])
    inv = data.get("investments", [])
    income = data.get("income", {})
    outflows = data.get("outflows", {})

    # --- Net worth snapshot -------------------------------------------------
    total_cash = sum(money(a.get("amount")) for a in cash)
    total_card_debt = sum(money(c.get("balance")) for c in cards)
    net_liquid = total_cash - total_card_debt
    total_invested = sum(money(a.get("amount")) for a in inv)
    net_worth = total_cash - total_card_debt + total_invested

    # --- Cash flow ----------------------------------------------------------
    biweekly = money(income.get("biweekly_paycheck"))
    commission = money(income.get("monthly_commission"))
    per_month = int(income.get("paychecks_per_month", 2) or 2)
    per_year = int(income.get("paychecks_per_year", 26) or 26)

    typical_income = biweekly * per_month + commission
    three_check_income = biweekly * (per_month + 1) + commission
    annualized_income = biweekly * per_year + commission * 12

    fixed = money(outflows.get("fixed"))
    variable = money(outflows.get("variable"))
    total_outflows = fixed + variable
    surplus = typical_income - total_outflows
    surplus_pct = (surplus / typical_income) if typical_income else 0.0

    allocation = []
    for a in data.get("surplus_allocation", []):
        pct = money(a.get("pct"))
        allocation.append({
            "phase": a.get("phase", ""),
            "pct": pct,
            "monthly": round(surplus * pct, 2),
            "note": a.get("note", ""),
        })

    # --- Debt: payoff order + stress test -----------------------------------
    total_due = sum(money(c.get("amount_due")) for c in cards)
    open_cards = [c for c in cards if money(c.get("balance")) > 0]
    # Smallest balance first (snowball); if APRs are known and vary a lot, the
    # note in the UI reminds you highest-APR-first is cheaper.
    payoff_order = sorted(open_cards, key=lambda c: money(c.get("balance")))

    income_left_for_cards = typical_income - total_outflows
    gap_from_cash = income_left_for_cards - total_due
    cash_after = total_cash + gap_from_cash if gap_from_cash < 0 else total_cash

    # --- Pay-in-full plan: running balance ----------------------------------
    plan = data.get("plan", {})
    ringfenced = sum(money(a.get("amount")) for a in cash if a.get("ringfenced"))
    running = total_cash - ringfenced  # start balance excludes ring-fenced cash
    plan_rows = []
    total_in = total_out = 0.0
    for i, e in enumerate(plan.get("entries", [])):
        amt_in = money(e.get("in"))
        amt_out = money(e.get("out"))
        if i == 0:
            # first row is the opening balance; its in/out are informational
            pass
        else:
            running += amt_in - amt_out
            total_in += amt_in
            total_out += amt_out
        plan_rows.append({
            "date": e.get("date", ""),
            "action": e.get("action", ""),
            "in": amt_in or None,
            "out": amt_out or None,
            "balance": round(running, 2),
            "why": e.get("why", ""),
        })
    plan_end = round(running, 2)

    # --- Emergency fund tiers ----------------------------------------------
    tiers = []
    for t in data.get("emergency_fund_tiers", []):
        target = round(total_outflows * money(t.get("months")), 2)
        tiers.append({
            "label": t.get("label", ""),
            "months": money(t.get("months")),
            "target": target,
            "current": round(net_liquid, 2),
            "gap": round(target - net_liquid, 2),
        })

    # --- Trip / goal fund ---------------------------------------------------
    trip = data.get("trip_fund", {})
    trip_target = money(trip.get("target"))
    trip_saved = money(trip.get("saved"))
    trip_monthly = next(
        (a["monthly"] for a in allocation if "3" in a["phase"] or "trip" in a["phase"].lower()),
        allocation[-1]["monthly"] if allocation else 0.0,
    )
    trip_remaining = max(trip_target - trip_saved, 0.0)
    trip_months = math.ceil(trip_remaining / trip_monthly) if trip_monthly > 0 else None

    # --- Retirement / match -------------------------------------------------
    ret = data.get("retirement", {})
    match_per_pay = money(ret.get("match_per_pay"))
    annual_match = round(match_per_pay * per_year, 2)

    # --- Monthly log totals -------------------------------------------------
    log = data.get("monthly_log", [])
    log_cols = ("income", "fixed", "variable", "card_paydown", "saved", "invested")
    log_totals = {c: round(sum(money(r.get(c)) for r in log), 2) for c in log_cols}

    return {
        "owner": data.get("owner", ""),
        "as_of": data.get("as_of", ""),
        "net_worth": {
            "cash_accounts": cash,
            "total_cash": round(total_cash, 2),
            "cards": cards,
            "total_card_debt": round(total_card_debt, 2),
            "net_liquid_position": round(net_liquid, 2),
            "investments": inv,
            "total_invested": round(total_invested, 2),
            "total_net_worth": round(net_worth, 2),
        },
        "cash_flow": {
            "typical_income": round(typical_income, 2),
            "three_paycheck_income": round(three_check_income, 2),
            "annualized_income": round(annualized_income, 2),
            "fixed": round(fixed, 2),
            "variable": round(variable, 2),
            "total_outflows": round(total_outflows, 2),
            "surplus": round(surplus, 2),
            "surplus_pct": round(surplus_pct, 4),
            "allocation": allocation,
        },
        "debt": {
            "total_balance": round(total_card_debt, 2),
            "total_due": round(total_due, 2),
            "payoff_order": [
                {"name": c.get("name", ""), "balance": money(c.get("balance")),
                 "apr": c.get("apr"), "due_date": c.get("due_date", "")}
                for c in payoff_order
            ],
            "stress_test": {
                "total_due": round(total_due, 2),
                "income": round(typical_income, 2),
                "outflows": round(total_outflows, 2),
                "income_left_for_cards": round(income_left_for_cards, 2),
                "gap_from_cash": round(gap_from_cash, 2),
                "cash_after": round(cash_after, 2),
            },
        },
        "plan": {
            "title": plan.get("title", ""),
            "goal": plan.get("goal", ""),
            "rows": plan_rows,
            "total_in": round(total_in, 2),
            "total_out": round(total_out, 2),
            "end_balance": plan_end,
            "ringfenced": round(ringfenced, 2),
            "total_cash_after": round(plan_end + ringfenced, 2),
            "remaining_after": plan.get("remaining_after", []),
        },
        "emergency_fund": tiers,
        "trip_fund": {
            "target": trip_target,
            "saved": trip_saved,
            "monthly": trip_monthly,
            "remaining": round(trip_remaining, 2),
            "months_to_fund": trip_months,
            "note": trip.get("note", ""),
        },
        "retirement": {
            "ira_limit_2026": money(ret.get("ira_limit_2026")),
            "plan_401k_limit_2026": money(ret.get("plan_401k_limit_2026")),
            "contribution_per_pay": money(ret.get("contribution_per_pay")),
            "match_per_pay": match_per_pay,
            "match_rate": money(ret.get("match_rate")),
            "annual_match": annual_match,
            "note": ret.get("note", ""),
        },
        "monthly_log": {"rows": log, "totals": log_totals},
    }


# ---------------------------------------------------------------- outputs ---


def usd(x, cents: bool = False) -> str:
    if x is None:
        return "—"
    return f"${x:,.2f}" if cents else f"${x:,.0f}"


def signed_usd(x) -> str:
    if x is None:
        return "—"
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def pretty_date(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%b %-d, %Y")
    except (ValueError, TypeError):
        return iso or ""


def write_json(result: dict, raw: dict, out: Path) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": raw,
        "computed": result,
    }
    (out / "finance.json").write_text(json.dumps(payload, indent=2), "utf-8")


def write_markdown(r: dict, out: Path) -> None:
    nw = r["net_worth"]
    cf = r["cash_flow"]
    L = [
        f"# {r['owner']} — Financial Dashboard".strip(" —"),
        "",
        f"_Snapshot as of {r['as_of']}. Generated "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}._",
        "",
        "## Headline numbers",
        "",
        f"- **Net worth:** {usd(nw['total_net_worth'])}",
        f"- **Net liquid position (true cash cushion):** {usd(nw['net_liquid_position'])} "
        f"— cash {usd(nw['total_cash'])} minus card debt {usd(nw['total_card_debt'])}",
        f"- **Invested:** {usd(nw['total_invested'])}",
        f"- **Monthly surplus:** {usd(cf['surplus'])} "
        f"({cf['surplus_pct']*100:.1f}% of {usd(cf['typical_income'])} income)",
        "",
        "## Debt — payoff order (smallest balance first)",
        "",
    ]
    for i, c in enumerate(r["debt"]["payoff_order"], 1):
        apr = f" · {c['apr']}% APR" if c.get("apr") else ""
        L.append(f"{i}. **{c['name']}** — {usd(c['balance'])} "
                 f"(due {pretty_date(c['due_date'])}{apr})")
    st = r["debt"]["stress_test"]
    L += [
        "",
        f"Total balance {usd(r['debt']['total_balance'])} · total due now "
        f"{usd(r['debt']['total_due'])}. Stress test: income leaves "
        f"{usd(st['income_left_for_cards'])} for cards, "
        f"{'gap of ' + usd(abs(st['gap_from_cash'])) + ' drawn from cash' if st['gap_from_cash'] < 0 else 'no cash draw needed'}.",
        "",
        f"## {r['plan']['title']}",
        "",
        r["plan"]["goal"],
        "",
        "| Date | Action | In | Out | Balance |",
        "|---|---|--:|--:|--:|",
    ]
    for row in r["plan"]["rows"]:
        L.append(f"| {pretty_date(row['date'])} | {row['action']} | "
                 f"{usd(row['in']) if row['in'] else ''} | "
                 f"{usd(row['out']) if row['out'] else ''} | {usd(row['balance'])} |")
    L += [
        f"| | **Totals** | **{usd(r['plan']['total_in'])}** | "
        f"**{usd(r['plan']['total_out'])}** | **{usd(r['plan']['end_balance'])}** |",
        "",
        f"End-of-month cash: {usd(r['plan']['total_cash_after'])} "
        f"(plan balance {usd(r['plan']['end_balance'])} + ring-fenced "
        f"{usd(r['plan']['ringfenced'])}).",
        "",
        "## Emergency fund",
        "",
        "| Tier | Target | Current | Gap |",
        "|---|--:|--:|--:|",
    ]
    for t in r["emergency_fund"]:
        L.append(f"| {t['label']} | {usd(t['target'])} | {usd(t['current'])} | {usd(t['gap'])} |")
    tf = r["trip_fund"]
    months = f"{tf['months_to_fund']} months" if tf["months_to_fund"] else "—"
    L += [
        "",
        "## Goals",
        "",
        f"- **Trip fund:** {usd(tf['saved'])} of {usd(tf['target'])} · "
        f"{usd(tf['monthly'], cents=True)}/mo → {months} to fund",
        f"- **Employer match captured:** {usd(r['retirement']['annual_match'])}/yr "
        f"(free money at {r['retirement']['match_rate']*100:.0f}¢ per dollar)",
        "",
        "## Surplus allocation",
        "",
    ]
    for a in cf["allocation"]:
        L.append(f"- **{a['phase']}** — {usd(a['monthly'], cents=True)}/mo "
                 f"({a['pct']*100:.0f}%) · {a['note']}")
    L.append("")
    (out / "latest.md").write_text("\n".join(L), "utf-8")


def write_html(r: dict, out: Path, is_sample: bool) -> None:
    def esc(s) -> str:
        return htmllib.escape(str(s), quote=True)

    nw = r["net_worth"]
    cf = r["cash_flow"]
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sample_banner = (
        '<div class="banner">Showing <strong>sample data</strong>. Your real '
        'dashboard is built locally from <code>finance/data.json</code> and is '
        'never pushed. See <a href="https://github.com/ddalgin/ddalgin.github.io'
        '/blob/main/bot/README.md">the README</a>.</div>' if is_sample else "")

    # Net worth rows
    cash_rows = "".join(
        f'<tr><td>{esc(a["name"])}{" 🔒" if a.get("ringfenced") else ""}</td>'
        f'<td class="num">{esc(usd(money(a["amount"])))}</td>'
        f'<td class="note">{esc(a.get("note",""))}</td></tr>'
        for a in nw["cash_accounts"])
    card_rows = "".join(
        f'<tr><td>{esc(c["name"])}</td>'
        f'<td class="num neg">{esc(signed_usd(-money(c["balance"])))}</td>'
        f'<td class="note">{esc(c.get("note",""))}</td></tr>'
        for c in nw["cards"])
    inv_rows = "".join(
        f'<tr><td>{esc(a["name"])}</td>'
        f'<td class="num">{esc(usd(money(a["amount"])))}</td>'
        f'<td class="note">{esc(a.get("note",""))}</td></tr>'
        for a in nw["investments"])

    # Debt payoff
    payoff = "".join(
        f'<li><span class="rank">{i}</span> <strong>{esc(c["name"])}</strong> '
        f'<span class="amt">{esc(usd(c["balance"]))}</span>'
        f'<span class="meta">due {esc(pretty_date(c["due_date"]))}'
        f'{" · " + esc(str(c["apr"])) + "% APR" if c.get("apr") else ""}</span></li>'
        for i, c in enumerate(r["debt"]["payoff_order"], 1))
    st = r["debt"]["stress_test"]
    stress = (
        f'Income leaves <strong>{esc(usd(st["income_left_for_cards"]))}</strong> for cards after outflows. '
        + (f'Gap of <strong class="neg">{esc(usd(abs(st["gap_from_cash"])))}</strong> covered from cash → '
           f'<strong>{esc(usd(st["cash_after"]))}</strong> left.'
           if st["gap_from_cash"] < 0 else 'No cash draw needed this month.'))

    # Plan table
    plan_rows = ""
    for row in r["plan"]["rows"]:
        plan_rows += (
            f'<tr><td class="d">{esc(pretty_date(row["date"]))}</td>'
            f'<td>{esc(row["action"])}<div class="why">{esc(row["why"])}</div></td>'
            f'<td class="num pos">{esc(usd(row["in"])) if row["in"] else ""}</td>'
            f'<td class="num neg">{esc(usd(row["out"])) if row["out"] else ""}</td>'
            f'<td class="num bal">{esc(usd(row["balance"]))}</td></tr>')
    plan_rows += (
        f'<tr class="tot"><td></td><td>Totals</td>'
        f'<td class="num pos">{esc(usd(r["plan"]["total_in"]))}</td>'
        f'<td class="num neg">{esc(usd(r["plan"]["total_out"]))}</td>'
        f'<td class="num bal">{esc(usd(r["plan"]["end_balance"]))}</td></tr>')

    # Emergency fund
    ef = ""
    for t in r["emergency_fund"]:
        pct = 0 if t["target"] <= 0 else max(0, min(100, t["current"] / t["target"] * 100))
        ef += (
            f'<div class="tier"><div class="tier-head"><span>{esc(t["label"])}</span>'
            f'<span class="meta">{esc(usd(t["current"]))} of {esc(usd(t["target"]))}</span></div>'
            f'<div class="bar"><div class="fill" style="width:{pct:.1f}%"></div></div>'
            f'<div class="meta">Gap {esc(usd(t["gap"]))}</div></div>')

    # Allocation
    alloc = "".join(
        f'<tr><td>{esc(a["phase"])}</td>'
        f'<td class="num">{esc(usd(a["monthly"], cents=True))}</td>'
        f'<td class="num">{a["pct"]*100:.0f}%</td>'
        f'<td class="note">{esc(a["note"])}</td></tr>'
        for a in cf["allocation"])

    tf = r["trip_fund"]
    months = f'{tf["months_to_fund"]} months' if tf["months_to_fund"] else "—"
    ret = r["retirement"]

    title = f'{r["owner"]} — Financial Dashboard'.strip(" —") or "Financial Dashboard"

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
  :root {{ --bg:#f5f6fb; --card:#fff; --ink:#1c1e26; --muted:#6b7280;
           --accent:#4f46e5; --pos:#047857; --neg:#b91c1c; --line:#e5e7eb;
           --chip:#eef2ff; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0f1017; --card:#1a1c26; --ink:#e7e8ee; --muted:#9aa0ae;
             --accent:#8b85f4; --pos:#34d399; --neg:#f87171; --line:#2a2d3a;
             --chip:#20233a; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
         background:var(--bg); color:var(--ink); padding:2rem 1rem 4rem; }}
  main {{ max-width:900px; margin:0 auto; }}
  h1 {{ font-size:1.7rem; margin:0 0 .2rem; }}
  .sub {{ color:var(--muted); font-size:.9rem; margin-bottom:1.5rem; }}
  .banner {{ background:var(--chip); border:1px solid var(--line); color:var(--ink);
            border-radius:10px; padding:.7rem 1rem; font-size:.85rem; margin-bottom:1.5rem; }}
  .banner a {{ color:var(--accent); }}
  .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
          gap:1rem; margin-bottom:1.5rem; }}
  .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
         padding:1rem 1.1rem; }}
  .kpi .label {{ color:var(--muted); font-size:.78rem; text-transform:uppercase;
                letter-spacing:.03em; }}
  .kpi .value {{ font-size:1.5rem; font-weight:700; margin-top:.2rem;
                font-variant-numeric:tabular-nums; }}
  .kpi .value.pos {{ color:var(--pos); }} .kpi .value.neg {{ color:var(--neg); }}
  .kpi .hint {{ color:var(--muted); font-size:.75rem; margin-top:.15rem; }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
            padding:1.1rem 1.25rem; margin-bottom:1.25rem; }}
  h2 {{ font-size:1.1rem; margin:.1rem 0 .9rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
  td, th {{ text-align:left; padding:.4rem .3rem; border-top:1px solid var(--line);
           vertical-align:top; }}
  tr:first-child td, tr:first-child th {{ border-top:none; }}
  .num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
  .pos {{ color:var(--pos); }} .neg {{ color:var(--neg); }} .bal {{ font-weight:600; }}
  .note {{ color:var(--muted); font-size:.82rem; }}
  tr.subtotal td {{ font-weight:600; border-top:2px solid var(--line); }}
  tr.tot td {{ font-weight:700; border-top:2px solid var(--line); }}
  .why {{ color:var(--muted); font-size:.76rem; }}
  td.d {{ white-space:nowrap; color:var(--muted); }}
  ol.payoff {{ list-style:none; margin:0; padding:0; }}
  ol.payoff li {{ display:flex; align-items:center; gap:.6rem; padding:.45rem 0;
                 border-top:1px solid var(--line); }}
  ol.payoff li:first-child {{ border-top:none; }}
  .rank {{ flex:0 0 1.6rem; height:1.6rem; border-radius:50%; background:var(--chip);
          display:grid; place-items:center; font-size:.8rem; font-weight:700; }}
  .payoff .amt {{ margin-left:auto; font-weight:600; font-variant-numeric:tabular-nums; }}
  .payoff .meta, .meta {{ color:var(--muted); font-size:.8rem; }}
  .payoff .meta {{ flex-basis:100%; margin-left:2.2rem; }}
  .stress {{ margin-top:.8rem; padding-top:.8rem; border-top:1px solid var(--line);
            font-size:.9rem; color:var(--muted); }}
  .tier {{ margin-bottom:.9rem; }}
  .tier-head {{ display:flex; justify-content:space-between; font-size:.9rem;
               margin-bottom:.3rem; }}
  .bar {{ height:8px; background:var(--chip); border-radius:99px; overflow:hidden; }}
  .fill {{ height:100%; background:var(--accent); border-radius:99px; }}
  .cols {{ display:grid; grid-template-columns:1fr 1fr; gap:1.25rem; }}
  @media (max-width:640px) {{ .cols {{ grid-template-columns:1fr; }} }}
  footer {{ color:var(--muted); font-size:.8rem; margin-top:2rem; }}
  footer a {{ color:var(--accent); }}
</style>
</head>
<body>
<main>
  <h1>{esc(title)}</h1>
  <div class="sub">Snapshot as of {esc(r["as_of"])} · updated {generated} ·
    <a href="finance.json">JSON</a> · <a href="latest.md">Markdown</a></div>
  {sample_banner}

  <div class="kpis">
    <div class="kpi"><div class="label">Net worth</div>
      <div class="value">{esc(usd(nw["total_net_worth"]))}</div>
      <div class="hint">cash + investments − card debt</div></div>
    <div class="kpi"><div class="label">Net liquid position</div>
      <div class="value {'pos' if nw['net_liquid_position']>=0 else 'neg'}">{esc(usd(nw["net_liquid_position"]))}</div>
      <div class="hint">true cash cushion</div></div>
    <div class="kpi"><div class="label">Invested</div>
      <div class="value">{esc(usd(nw["total_invested"]))}</div>
      <div class="hint">retirement + taxable</div></div>
    <div class="kpi"><div class="label">Monthly surplus</div>
      <div class="value {'pos' if cf['surplus']>=0 else 'neg'}">{esc(usd(cf["surplus"]))}</div>
      <div class="hint">{cf['surplus_pct']*100:.1f}% of {esc(usd(cf['typical_income']))} income</div></div>
  </div>

  <div class="cols">
    <section>
      <h2>Net worth snapshot</h2>
      <table>
        {cash_rows}
        <tr class="subtotal"><td>Total cash</td><td class="num">{esc(usd(nw["total_cash"]))}</td><td></td></tr>
        {card_rows}
        <tr class="subtotal"><td>Total card debt</td><td class="num neg">{esc(signed_usd(-nw["total_card_debt"]))}</td><td></td></tr>
        <tr class="subtotal"><td>Net liquid position</td><td class="num">{esc(usd(nw["net_liquid_position"]))}</td><td class="note">cash − cards</td></tr>
        {inv_rows}
        <tr class="subtotal"><td>Total invested</td><td class="num">{esc(usd(nw["total_invested"]))}</td><td></td></tr>
        <tr class="tot"><td>Total net worth</td><td class="num">{esc(usd(nw["total_net_worth"]))}</td><td></td></tr>
      </table>
    </section>

    <section>
      <h2>Debt — pay smallest first</h2>
      <ol class="payoff">{payoff}</ol>
      <div class="stress">{stress}</div>
    </section>
  </div>

  <section>
    <h2>{esc(r["plan"]["title"])}</h2>
    <div class="note" style="margin-bottom:.7rem">{esc(r["plan"]["goal"])}</div>
    <table>
      <tr><th>Date</th><th>Action</th><th class="num">In</th><th class="num">Out</th><th class="num">Balance</th></tr>
      {plan_rows}
    </table>
    <div class="stress">End-of-month cash <strong>{esc(usd(r["plan"]["total_cash_after"]))}</strong>
      (plan balance {esc(usd(r["plan"]["end_balance"]))} + ring-fenced {esc(usd(r["plan"]["ringfenced"]))}).</div>
  </section>

  <div class="cols">
    <section>
      <h2>Emergency fund</h2>
      {ef}
    </section>

    <section>
      <h2>Goals</h2>
      <table>
        <tr><td>Trip fund</td><td class="num">{esc(usd(tf["saved"]))} / {esc(usd(tf["target"]))}</td></tr>
        <tr><td>Monthly contribution</td><td class="num">{esc(usd(tf["monthly"], cents=True))}</td></tr>
        <tr><td>Months to fund</td><td class="num">{esc(months)}</td></tr>
        <tr class="subtotal"><td>Employer match captured</td><td class="num pos">{esc(usd(ret["annual_match"]))}/yr</td></tr>
        <tr><td class="note" colspan="2">Free money at {ret['match_rate']*100:.0f}¢ per dollar. 2026 IRA limit {esc(usd(ret['ira_limit_2026']))}.</td></tr>
      </table>
    </section>
  </div>

  <section>
    <h2>Surplus allocation — {esc(usd(cf["surplus"]))}/mo</h2>
    <table>
      <tr><th>Phase</th><th class="num">Monthly</th><th class="num">Share</th><th>What it does</th></tr>
      {alloc}
    </table>
  </section>

  <footer>Auto-generated by finance_bot.py from a JSON snapshot you control.
    Not financial advice — figures are only as good as the numbers you feed it.</footer>
</main>
</body>
</html>
"""
    (out / "index.html").write_text(page, "utf-8")


# ------------------------------------------------------------------ main ---


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Personal finance dashboard builder")
    ap.add_argument("--data", default=DEFAULT_DATA,
                    help=f"input JSON snapshot (default {DEFAULT_DATA})")
    ap.add_argument("--out-dir", default="finance",
                    help="output directory (default ./finance)")
    args = ap.parse_args(argv)

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"error: data file not found: {data_path}", file=sys.stderr)
        return 2
    raw = json.loads(data_path.read_text("utf-8"))
    result = compute(raw)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    is_sample = data_path.name == Path(DEFAULT_DATA).name
    write_json(result, raw, out)
    write_markdown(result, out)
    write_html(result, out, is_sample)

    nw = result["net_worth"]
    print(f"Built dashboard from {data_path} -> {out}/")
    print(f"  net worth: {usd(nw['total_net_worth'])} · "
          f"net liquid: {usd(nw['net_liquid_position'])} · "
          f"surplus: {usd(result['cash_flow']['surplus'])}/mo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
