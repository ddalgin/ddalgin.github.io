#!/usr/bin/env python3
"""Offline tests for finance_bot.compute — pins the arithmetic.

Run: python bot/test_finance.py   (from repo root)
     python test_finance.py       (from bot/)
No network, no pip installs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from finance_bot import compute, money  # noqa: E402

# A fixture that mirrors the shape of the real snapshot with round numbers.
FIXTURE = {
    "owner": "Test",
    "as_of": "2026-07-30",
    "cash_accounts": [
        {"name": "Checking", "amount": 1600, "ringfenced": False},
        {"name": "Savings", "amount": 330, "ringfenced": False},
        {"name": "HYSA", "amount": 800, "ringfenced": True},
    ],
    "cards": [
        {"name": "Big", "balance": 1600, "amount_due": 1443, "due_date": "2026-08-22"},
        {"name": "Med", "balance": 215, "amount_due": 0, "due_date": "2026-09-06"},
        {"name": "Small", "balance": 105, "amount_due": 58, "due_date": "2026-08-11"},
        {"name": "Apple", "balance": 531, "amount_due": 407, "due_date": "2026-08-31"},
    ],
    "investments": [
        {"name": "IRA", "amount": 2400},
        {"name": "Brokerage", "amount": 2400},
        {"name": "Work", "amount": 160},
    ],
    "income": {"biweekly_paycheck": 1450, "monthly_commission": 200,
               "paychecks_per_month": 2, "paychecks_per_year": 26},
    "outflows": {"fixed": 1675, "variable": 900},
    "surplus_allocation": [
        {"phase": "Phase 1 — clear card balances", "pct": 0.70},
        {"phase": "Phase 2 — emergency fund", "pct": 0.20},
        {"phase": "Phase 3 — trip + investing", "pct": 0.10},
    ],
    "emergency_fund_tiers": [
        {"label": "Tier 1", "months": 1},
        {"label": "Tier 2", "months": 3},
        {"label": "Tier 3", "months": 6},
    ],
    "trip_fund": {"target": 2500, "saved": 0},
    "retirement": {"ira_limit_2026": 7500, "plan_401k_limit_2026": 24500,
                   "contribution_per_pay": 120, "match_per_pay": 30, "match_rate": 0.25},
    "plan": {
        "title": "Aug 2026",
        "goal": "pay in full",
        "entries": [
            {"date": "2026-07-30", "action": "Start", "in": None, "out": None},
            {"date": "2026-08-07", "action": "Paycheck", "in": 1450, "out": None},
            {"date": "2026-08-11", "action": "Amazon", "in": None, "out": 105},
            {"date": "2026-08-15", "action": "Fixed 1", "in": None, "out": 838},
            {"date": "2026-08-21", "action": "Paycheck", "in": 1450, "out": None},
            {"date": "2026-08-22", "action": "Freedom", "in": None, "out": 1600},
            {"date": "2026-08-28", "action": "Commission", "in": 200, "out": None},
            {"date": "2026-08-30", "action": "Fixed 2", "in": None, "out": 837},
            {"date": "2026-08-31", "action": "Apple", "in": None, "out": 531},
            {"date": "2026-08-31", "action": "Variable", "in": None, "out": 900},
        ],
    },
    "monthly_log": [
        {"month": "Aug", "income": 3100, "fixed": 1675, "variable": 900,
         "card_paydown": 400, "saved": 100, "invested": 25, "net_worth": 5300},
    ],
}

FAILS = []


def check(name, got, want):
    if got != want:
        FAILS.append(f"{name}: got {got!r}, want {want!r}")
    else:
        print(f"  ok  {name} = {got!r}")


def approx(name, got, want, tol=0.01):
    if abs(got - want) > tol:
        FAILS.append(f"{name}: got {got!r}, want ~{want!r}")
    else:
        print(f"  ok  {name} = {got!r}")


def main():
    r = compute(FIXTURE)

    print("Net worth:")
    nw = r["net_worth"]
    check("total_cash", nw["total_cash"], 2730)
    check("total_card_debt", nw["total_card_debt"], 2451)
    check("net_liquid_position", nw["net_liquid_position"], 279)
    check("total_invested", nw["total_invested"], 4960)
    check("total_net_worth", nw["total_net_worth"], 5239)

    print("Cash flow:")
    cf = r["cash_flow"]
    check("typical_income", cf["typical_income"], 3100)
    check("three_paycheck_income", cf["three_paycheck_income"], 4550)
    check("annualized_income", cf["annualized_income"], 40100)
    check("total_outflows", cf["total_outflows"], 2575)
    check("surplus", cf["surplus"], 525)
    approx("surplus_pct", cf["surplus_pct"], 0.1694)
    check("alloc_phase1", cf["allocation"][0]["monthly"], 367.5)
    check("alloc_phase2", cf["allocation"][1]["monthly"], 105.0)
    check("alloc_phase3", cf["allocation"][2]["monthly"], 52.5)
    check("alloc_sum", round(sum(a["monthly"] for a in cf["allocation"]), 2), 525.0)

    print("Debt:")
    d = r["debt"]
    check("total_due", d["total_due"], 1908)
    check("payoff_first", d["payoff_order"][0]["name"], "Small")
    check("payoff_last", d["payoff_order"][-1]["name"], "Big")
    check("income_left_for_cards", d["stress_test"]["income_left_for_cards"], 525)
    check("gap_from_cash", d["stress_test"]["gap_from_cash"], -1383)
    check("cash_after", d["stress_test"]["cash_after"], 1347)

    print("Plan:")
    p = r["plan"]
    check("plan_start_balance", p["rows"][0]["balance"], 1930)  # excludes ring-fenced 800
    check("plan_end_balance", p["end_balance"], 219)
    check("plan_total_in", p["total_in"], 3100)
    check("plan_total_out", p["total_out"], 4811)
    check("plan_ringfenced", p["ringfenced"], 800)
    check("plan_total_cash_after", p["total_cash_after"], 1019)

    print("Emergency fund:")
    ef = r["emergency_fund"]
    check("tier1_target", ef[0]["target"], 2575)
    check("tier1_gap", ef[0]["gap"], 2296)
    check("tier2_target", ef[1]["target"], 7725)
    check("tier3_target", ef[2]["target"], 15450)

    print("Trip fund:")
    tf = r["trip_fund"]
    check("trip_monthly", tf["monthly"], 52.5)
    check("trip_months_to_fund", tf["months_to_fund"], 48)

    print("Retirement:")
    check("annual_match", r["retirement"]["annual_match"], 780)

    print("Monthly log:")
    check("log_income_total", r["monthly_log"]["totals"]["income"], 3100)

    print("Edge cases:")
    check("money_none", money(None), 0.0)
    empty = compute({})
    check("empty_net_worth", empty["net_worth"]["total_net_worth"], 0)
    check("empty_surplus_pct", empty["cash_flow"]["surplus_pct"], 0.0)

    print()
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for f in FAILS:
            print("  -", f)
        return 1
    print("All finance tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
