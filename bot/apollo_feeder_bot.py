#!/usr/bin/env python3
"""Apollo Feeder Bot.

A sibling to finserv_events_bot.py, but for prospecting. It talks to the
Apollo.io API to build a prioritized pipeline of **global, deep-pocket
financial-services firms** and the senior buyers inside them, then writes an
Apollo-ready contact list plus a browsable dashboard. It also ingests an
exported Apollo *sequence-stats* CSV and produces optimization recommendations
so you can tune your sequences step by step.

What it does, all best-effort (an API call that errors is reported, not fatal):

  1. Account search  - POST /api/v1/mixed_companies/search
     Large, high-revenue financial-services organizations in the world's
     financial hubs, scored for "deep pockets" (revenue + headcount +
     subsector + funding).
  2. People search    - POST /api/v1/mixed_people/search
     Senior decision-makers (C-suite / VP / Head / Director) inside those
     accounts, matched to your buyer personas.
  3. Feed             - writes apollo/apollo_import.csv (import into an Apollo
     list, or use --create-list NAME to push the contacts into Apollo directly
     via POST /api/v1/contacts under a named list label).
  4. Sequence analysis - with --sequence-csv PATH, reads an exported Apollo
     sequence-stats CSV and writes recommendations (weak steps, bounce/open
     problems, best-performing step, subject-line notes).

Outputs (served by GitHub Pages at /apollo/):
  apollo/accounts.json        - scored accounts (machine-readable)
  apollo/contacts.json        - matched contacts (machine-readable)
  apollo/apollo_import.csv     - Apollo contact-import CSV
  apollo/sequence_analysis.md  - sequence recommendations (if --sequence-csv)
  apollo/index.html            - browsable dashboard
  apollo/latest.md             - plain-text digest, easy to read on GitHub

Stdlib only - no pip installs. The API key is read from the APOLLO_API_KEY
environment variable (never hard-coded). Without a key, the bot skips the API
calls, still writes a valid dashboard reporting the status, and still runs the
sequence analysis if a CSV was supplied.

By default the bot only READS from Apollo (search) and exports a CSV; it never
mutates your Apollo workspace. Writing contacts into Apollo (--create-list) and
revealing/enriching emails (--enrich) consume Apollo credits and are opt-in.

Usage:
  APOLLO_API_KEY=... python bot/apollo_feeder_bot.py
  APOLLO_API_KEY=... python bot/apollo_feeder_bot.py --pages 3 --min-revenue 1000000000
  APOLLO_API_KEY=... python bot/apollo_feeder_bot.py --create-list "Q3 FinServ Whales"
  python bot/apollo_feeder_bot.py --sequence-csv exports/seq.csv   # analysis only
"""

from __future__ import annotations

import argparse
import csv
import gzip
import html as htmllib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- config ---

API_BASE = "https://api.apollo.io"

# Apollo keyword tags that identify financial-services firms. Broad on purpose;
# the deep-pockets scorer prioritizes the whales.
FINSERV_KEYWORDS = [
    "financial services",
    "investment banking",
    "asset management",
    "private equity",
    "hedge fund",
    "venture capital",
    "wealth management",
    "capital markets",
    "banking",
    "insurance",
    "reinsurance",
    "sovereign wealth fund",
    "pension fund",
    "brokerage",
    "fintech",
]

# The world's financial centers (Apollo "organization_locations" strings).
FINANCIAL_HUBS = [
    "New York, US",
    "London, United Kingdom",
    "Hong Kong",
    "Singapore",
    "Zurich, Switzerland",
    "Frankfurt, Germany",
    "Tokyo, Japan",
    "Toronto, Canada",
    "Paris, France",
    "Dubai, United Arab Emirates",
    "Chicago, US",
    "Boston, US",
    "San Francisco, US",
    "Sydney, Australia",
    "Amsterdam, Netherlands",
]

# Only large firms qualify as "deep pockets" (Apollo employee-range buckets).
EMPLOYEE_RANGES = [
    "1001,5000",
    "5001,10000",
    "10001,50000",
    "50001,100000",
    "100001,10000000",
]

# Buyer personas: senior decision-makers we want inside each account.
PERSONA_SENIORITIES = ["c_suite", "partner", "vp", "head", "director"]
PERSONA_TITLES = [
    "Chief Investment Officer",
    "Chief Financial Officer",
    "Chief Operating Officer",
    "Chief Technology Officer",
    "Chief Data Officer",
    "Chief Digital Officer",
    "Head of Trading",
    "Head of Operations",
    "Head of Data",
    "Head of Wealth Management",
    "Head of Compliance",
    "Head of Procurement",
    "Head of Digital Transformation",
    "VP Technology",
    "Managing Director",
]

# Deep-pockets subsector weights (matched against industry + keywords).
SUBSECTOR_WEIGHTS = {
    "asset management": 5,
    "investment banking": 5,
    "private equity": 5,
    "hedge fund": 5,
    "sovereign wealth": 5,
    "capital markets": 4,
    "wealth management": 4,
    "reinsurance": 4,
    "pension": 4,
    "insurance": 3,
    "banking": 3,
    "brokerage": 3,
    "venture capital": 3,
    "fintech": 2,
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# --------------------------------------------------------------- models ---


@dataclass
class Account:
    apollo_id: str
    name: str
    domain: str = ""
    website: str = ""
    linkedin: str = ""
    industry: str = ""
    employees: int | None = None
    revenue: float | None = None       # annual revenue in USD, best effort
    funding: float | None = None       # total funding in USD, best effort
    city: str = ""
    country: str = ""
    keywords: list[str] = field(default_factory=list)
    score: int = 0
    tier: str = ""                     # Whale / Priority / Standard
    reasons: list[str] = field(default_factory=list)


@dataclass
class Contact:
    apollo_id: str
    first_name: str
    last_name: str
    title: str = ""
    seniority: str = ""
    email: str = ""
    email_status: str = ""
    linkedin: str = ""
    company: str = ""
    domain: str = ""
    city: str = ""
    country: str = ""
    account_id: str = ""


@dataclass
class SourceStatus:
    source: str
    ok: bool
    detail: str = ""
    found: int = 0

# --------------------------------------------------------------- client ---


class ApolloClient:
    """Minimal stdlib Apollo API client. Best-effort: callers catch errors."""

    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = timeout

    def post(self, path: str, body: dict) -> dict:
        url = f"{API_BASE}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Api-Key": self.api_key,
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return json.loads(raw.decode(charset, errors="replace") or "{}")

# --------------------------------------------------------------- helpers ---


def clean_text(s) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(str(s or ""))).strip()


def to_number(value) -> float | None:
    """Parse '$1.2B', '450M', '1,234', 0.45, '45%' -> float (None if hopeless)."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower().replace(",", "").replace("$", "").replace("%", "")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    num = float(m.group(1))
    if "b" in s or "bn" in s or "billion" in s:
        num *= 1_000_000_000
    elif "m" in s or "mm" in s or "million" in s:
        num *= 1_000_000
    elif "k" in s or "thousand" in s:
        num *= 1_000
    return num


def score_account(acct: Account) -> tuple[int, str, list[str]]:
    """Score an account for 'deep pockets'. Returns (score, tier, reasons)."""
    score, reasons = 0, []

    # Revenue is the strongest signal.
    if acct.revenue is not None:
        if acct.revenue >= 10_000_000_000:
            score += 6; reasons.append("revenue $10B+")
        elif acct.revenue >= 1_000_000_000:
            score += 4; reasons.append("revenue $1B+")
        elif acct.revenue >= 250_000_000:
            score += 2; reasons.append("revenue $250M+")

    # Headcount as a proxy for budget when revenue is unknown.
    if acct.employees is not None:
        if acct.employees >= 50_000:
            score += 4; reasons.append("50k+ employees")
        elif acct.employees >= 10_000:
            score += 3; reasons.append("10k+ employees")
        elif acct.employees >= 1_000:
            score += 1; reasons.append("1k+ employees")

    # High-value subsector.
    hay = f"{acct.industry} {' '.join(acct.keywords)}".lower()
    best_sub = 0
    for sub, w in SUBSECTOR_WEIGHTS.items():
        if sub in hay:
            if w > best_sub:
                best_sub = w
            if w >= 4:
                reasons.append(sub)
    score += best_sub

    # Well-funded firms have money to spend.
    if acct.funding is not None and acct.funding >= 500_000_000:
        score += 1; reasons.append("well funded")

    tier = "Whale" if score >= 12 else "Priority" if score >= 7 else "Standard"
    # de-dupe reasons, keep order
    seen, uniq = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r); uniq.append(r)
    return score, tier, uniq

# --------------------------------------------------------------- sources ---


def _org_fields(org: dict) -> Account:
    kw = org.get("keywords") or []
    if isinstance(kw, str):
        kw = [k.strip() for k in kw.split(",") if k.strip()]
    return Account(
        apollo_id=str(org.get("id", "")),
        name=clean_text(org.get("name", "")),
        domain=clean_text(org.get("primary_domain") or org.get("domain") or ""),
        website=clean_text(org.get("website_url", "")),
        linkedin=clean_text(org.get("linkedin_url", "")),
        industry=clean_text(org.get("industry", "")),
        employees=(int(org["estimated_num_employees"])
                   if org.get("estimated_num_employees") else None),
        revenue=to_number(org.get("annual_revenue")
                          or org.get("organization_revenue")),
        funding=to_number(org.get("total_funding")),
        city=clean_text(org.get("city", "")),
        country=clean_text(org.get("country", "")),
        keywords=[clean_text(k) for k in kw][:12],
    )


def search_accounts(client: ApolloClient, hubs: list[str], keywords: list[str],
                    min_revenue: float, pages: int,
                    per_page: int = 25) -> tuple[list[Account], list[SourceStatus]]:
    accounts: list[Account] = []
    statuses: list[SourceStatus] = []
    for page in range(1, pages + 1):
        body = {
            "q_organization_keyword_tags": keywords,
            "organization_locations": hubs,
            "organization_num_employees_ranges": EMPLOYEE_RANGES,
            "revenue_range": {"min": int(min_revenue)},
            "page": page,
            "per_page": per_page,
        }
        try:
            data = client.post("/api/v1/mixed_companies/search", body)
            orgs = data.get("organizations") or data.get("accounts") or []
            for org in orgs:
                acct = _org_fields(org)
                if not acct.apollo_id or not acct.name:
                    continue
                acct.score, acct.tier, acct.reasons = score_account(acct)
                accounts.append(acct)
            statuses.append(SourceStatus("accounts", True, f"page {page}", len(orgs)))
            total_pages = ((data.get("pagination") or {}).get("total_pages"))
            if total_pages is not None and page >= total_pages:
                break
        except Exception as exc:  # noqa: BLE001 - best-effort
            statuses.append(SourceStatus(
                "accounts", False, f"page {page}: {type(exc).__name__}: {exc}"))
            break
    return accounts, statuses


def _person_fields(p: dict) -> Contact:
    org = p.get("organization") or {}
    email = clean_text(p.get("email", ""))
    # Apollo returns a locked placeholder until an email is revealed/enriched.
    status = clean_text(p.get("email_status", ""))
    if email.startswith("email_not_unlocked") or "domain.com" in email:
        email, status = "", status or "locked"
    return Contact(
        apollo_id=str(p.get("id", "")),
        first_name=clean_text(p.get("first_name", "")),
        last_name=clean_text(p.get("last_name", "")),
        title=clean_text(p.get("title", "")),
        seniority=clean_text(p.get("seniority", "")),
        email=email,
        email_status=status,
        linkedin=clean_text(p.get("linkedin_url", "")),
        company=clean_text(org.get("name", "")),
        domain=clean_text(org.get("primary_domain") or org.get("website_url") or ""),
        city=clean_text(p.get("city", "")),
        country=clean_text(p.get("country", "")),
        account_id=str(org.get("id", "")),
    )


def search_people(client: ApolloClient, account_ids: list[str], titles: list[str],
                  seniorities: list[str], pages: int,
                  per_page: int = 25) -> tuple[list[Contact], list[SourceStatus]]:
    contacts: list[Contact] = []
    statuses: list[SourceStatus] = []
    if not account_ids:
        statuses.append(SourceStatus("people", False, "no accounts to search within"))
        return contacts, statuses
    for page in range(1, pages + 1):
        body = {
            "organization_ids": account_ids,
            "person_titles": titles,
            "person_seniorities": seniorities,
            "page": page,
            "per_page": per_page,
        }
        try:
            data = client.post("/api/v1/mixed_people/search", body)
            people = data.get("people") or data.get("contacts") or []
            for p in people:
                c = _person_fields(p)
                if not c.apollo_id or not (c.first_name or c.last_name):
                    continue
                contacts.append(c)
            statuses.append(SourceStatus("people", True, f"page {page}", len(people)))
            total_pages = ((data.get("pagination") or {}).get("total_pages"))
            if total_pages is not None and page >= total_pages:
                break
        except Exception as exc:  # noqa: BLE001
            statuses.append(SourceStatus(
                "people", False, f"page {page}: {type(exc).__name__}: {exc}"))
            break
    return contacts, statuses


def push_contacts_to_list(client: ApolloClient, contacts: list[Contact],
                          list_name: str) -> list[SourceStatus]:
    """Create contacts in Apollo under a named list label. Mutating + credits."""
    statuses: list[SourceStatus] = []
    created = 0
    for c in contacts:
        body = {
            "first_name": c.first_name,
            "last_name": c.last_name,
            "title": c.title,
            "organization_name": c.company,
            "website_url": (f"https://{c.domain}" if c.domain
                            and not c.domain.startswith("http") else c.domain),
            "label_names": [list_name],
        }
        try:
            client.post("/api/v1/contacts", body)
            created += 1
        except Exception as exc:  # noqa: BLE001
            statuses.append(SourceStatus(
                "create-list", False,
                f"{c.first_name} {c.last_name}: {type(exc).__name__}: {exc}"))
    statuses.append(SourceStatus("create-list", True,
                                 f"list '{list_name}'", created))
    return statuses

# ------------------------------------------------------- sequence analysis ---

# Fuzzy header -> canonical metric. Apollo exports vary between views.
SEQ_COLUMN_ALIASES = {
    "step": ["step", "step number", "step #", "order", "sequence step"],
    "subject": ["subject", "subject line", "email subject", "template"],
    "sent": ["sent", "delivered", "emails sent", "num sent", "deliveries"],
    "opened": ["opened", "opens", "open", "unique opens"],
    "replied": ["replied", "replies", "reply", "responded", "responses"],
    "bounced": ["bounced", "bounces", "bounce"],
    "clicked": ["clicked", "clicks", "click"],
    "open_rate": ["open rate", "opened rate", "% opened", "open %"],
    "reply_rate": ["reply rate", "replied rate", "% replied", "reply %"],
    "bounce_rate": ["bounce rate", "bounced rate", "% bounced", "bounce %"],
}


RATE_COLUMNS = {"open_rate", "reply_rate", "bounce_rate"}


def parse_rate(cell) -> float | None:
    """Parse a rate cell to a 0-1 fraction. Handles '45%', '0.3%', '45', 0.45."""
    n = to_number(cell)
    if n is None:
        return None
    if "%" in str(cell):
        return n / 100.0            # explicit percent, whatever the magnitude
    return n / 100.0 if n > 1.5 else n


def _match_column(header: str) -> str | None:
    h = header.strip().lower()
    for canon, aliases in SEQ_COLUMN_ALIASES.items():
        if h in aliases or any(h == a for a in aliases):
            return canon
    for canon, aliases in SEQ_COLUMN_ALIASES.items():
        if any(a in h for a in aliases):
            return canon
    return None


def parse_sequence_rows(text: str) -> list[dict]:
    """Parse an Apollo sequence-stats CSV into normalized per-step dicts."""
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return []
    header = rows[0]
    colmap = {i: _match_column(h) for i, h in enumerate(header)}
    steps: list[dict] = []
    for idx, raw in enumerate(rows[1:], start=1):
        rec: dict = {}
        for i, cell in enumerate(raw):
            canon = colmap.get(i)
            if not canon:
                continue
            if canon == "subject":
                rec["subject"] = clean_text(cell)
            elif canon in RATE_COLUMNS:
                rec[canon] = parse_rate(cell)   # already a 0-1 fraction
            else:
                rec[canon] = to_number(cell)
        if not rec:
            continue
        rec.setdefault("step", float(idx))

        sent = rec.get("sent")
        # Prefer an explicit rate column; else derive from counts / sent.
        def rate(count_key, rate_key):
            if rec.get(rate_key) is not None:
                return rec[rate_key]
            if sent and rec.get(count_key) is not None:
                return rec[count_key] / sent if sent else None
            return None

        rec["open_rate"] = rate("opened", "open_rate")
        rec["reply_rate"] = rate("replied", "reply_rate")
        rec["bounce_rate"] = rate("bounced", "bounce_rate")
        steps.append(rec)
    steps.sort(key=lambda r: r.get("step", 0))
    return steps


def analyze_sequence(steps: list[dict]) -> dict:
    """Turn normalized steps into findings + recommendations."""
    findings: list[str] = []
    recs: list[str] = []
    if not steps:
        return {"steps": [], "findings": ["No parseable rows in the CSV."],
                "recommendations": [], "summary": {}}

    total_sent = sum(s.get("sent") or 0 for s in steps)
    replies = [s for s in steps if s.get("reply_rate") is not None]
    opens = [s for s in steps if s.get("open_rate") is not None]
    avg_reply = (sum(s["reply_rate"] for s in replies) / len(replies)
                 if replies else None)
    avg_open = (sum(s["open_rate"] for s in opens) / len(opens)
                if opens else None)

    best = max(replies, key=lambda s: s["reply_rate"]) if replies else None
    worst = min(replies, key=lambda s: s["reply_rate"]) if replies else None

    for s in steps:
        n = int(s.get("step", 0))
        br = s.get("bounce_rate")
        orr = s.get("open_rate")
        rr = s.get("reply_rate")
        if br is not None and br > 0.03:
            findings.append(f"Step {n}: bounce rate {br:.1%} is high (>3%).")
            recs.append(f"Step {n}: clean the list / re-verify emails before "
                        f"this step; high bounces hurt domain reputation.")
        if orr is not None and orr < 0.30:
            findings.append(f"Step {n}: open rate {orr:.1%} is low (<30%).")
            recs.append(f"Step {n}: test new subject lines and check "
                        f"deliverability (SPF/DKIM, warm-up, send volume).")
        if rr is not None and rr < 0.01 and (s.get("sent") or 0) >= 50:
            findings.append(f"Step {n}: reply rate {rr:.2%} is very low.")
            recs.append(f"Step {n}: rewrite the body around a single, specific "
                        f"CTA; consider cutting or merging this step.")

    if best and worst and best is not worst:
        recs.append(
            f"Step {int(best['step'])} is your strongest (reply {best['reply_rate']:.1%}); "
            f"model weaker steps on it. Step {int(worst['step'])} is weakest "
            f"(reply {worst['reply_rate']:.1%}) - rewrite or drop it.")

    for s in steps:
        subj = s.get("subject")
        if subj and len(subj) > 60:
            recs.append(f"Step {int(s.get('step', 0))}: subject is {len(subj)} "
                        f"chars - shorten to <50 for mobile inboxes.")

    if not findings:
        findings.append("No red flags on bounce/open/reply thresholds. "
                        "Keep A/B testing subjects and CTAs.")

    return {
        "steps": steps,
        "findings": findings,
        "recommendations": recs,
        "summary": {
            "num_steps": len(steps),
            "total_sent": total_sent,
            "avg_open_rate": avg_open,
            "avg_reply_rate": avg_reply,
        },
    }

# --------------------------------------------------------------- outputs ---


def dedupe_accounts(accounts: list[Account]) -> list[Account]:
    seen, out = set(), []
    for a in accounts:
        key = a.apollo_id or (a.name.lower(), a.domain.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    out.sort(key=lambda a: -a.score)
    return out


def dedupe_contacts(contacts: list[Contact]) -> list[Contact]:
    seen, out = set(), []
    for c in contacts:
        key = c.apollo_id or (c.first_name.lower(), c.last_name.lower(), c.domain.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


CSV_HEADERS = [
    "First Name", "Last Name", "Title", "Seniority", "Company", "Email",
    "Website", "Person Linkedin Url", "City", "Country",
    "Apollo Contact Id", "Apollo Account Id", "Account Tier",
]


def write_csv(contacts: list[Contact], accounts: list[Account], out: Path) -> None:
    tier_by_id = {a.apollo_id: a.tier for a in accounts}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_HEADERS)
    for c in contacts:
        website = (f"https://{c.domain}" if c.domain and not c.domain.startswith("http")
                   else c.domain)
        w.writerow([
            c.first_name, c.last_name, c.title, c.seniority, c.company, c.email,
            website, c.linkedin, c.city, c.country,
            c.apollo_id, c.account_id, tier_by_id.get(c.account_id, ""),
        ])
    (out / "apollo_import.csv").write_text(buf.getvalue(), "utf-8")


def write_json(accounts: list[Account], contacts: list[Contact],
               statuses: list[SourceStatus], seq: dict | None,
               out: Path, meta: dict) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta": meta,
        "sources": [asdict(s) for s in statuses],
        "accounts": [asdict(a) for a in accounts],
        "contacts": [asdict(c) for c in contacts],
        "sequence_analysis": seq,
    }
    (out / "accounts.json").write_text(
        json.dumps({k: payload[k] for k in
                    ("generated_at", "meta", "sources", "accounts")}, indent=2),
        "utf-8")
    (out / "contacts.json").write_text(
        json.dumps({"generated_at": payload["generated_at"],
                    "contacts": payload["contacts"]}, indent=2), "utf-8")


def _pct(v) -> str:
    return f"{v:.1%}" if isinstance(v, (int, float)) else "n/a"


def write_sequence_md(seq: dict, out: Path) -> None:
    s = seq.get("summary", {})
    lines = [
        "# Apollo Sequence Analysis",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        f"- Steps analyzed: **{s.get('num_steps', 0)}**",
        f"- Total emails sent: **{int(s.get('total_sent') or 0):,}**",
        f"- Avg open rate: **{_pct(s.get('avg_open_rate'))}**",
        f"- Avg reply rate: **{_pct(s.get('avg_reply_rate'))}**",
        "",
        "## Findings",
        "",
    ]
    lines += [f"- {f}" for f in seq.get("findings", [])] or ["- None."]
    lines += ["", "## Recommendations", ""]
    lines += [f"- {r}" for r in seq.get("recommendations", [])] or ["- None."]
    lines.append("")
    (out / "sequence_analysis.md").write_text("\n".join(lines), "utf-8")


def write_markdown(accounts: list[Account], contacts: list[Contact],
                   statuses: list[SourceStatus], seq: dict | None,
                   out: Path, meta: dict) -> None:
    lines = [
        "# Apollo Feeder Digest",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"{len(accounts)} accounts · {len(contacts)} contacts_",
        "",
        "## Top accounts (deep pockets first)",
        "",
    ]
    if not accounts:
        lines.append("_No accounts this run (check API key / status below)._")
    for a in accounts[:40]:
        rev = f"${a.revenue/1e9:.1f}B" if a.revenue and a.revenue >= 1e9 else (
            f"${a.revenue/1e6:.0f}M" if a.revenue else "rev n/a")
        emp = f"{a.employees:,} emp" if a.employees else "emp n/a"
        loc = " · ".join(x for x in (a.city, a.country) if x)
        why = f" — {', '.join(a.reasons)}" if a.reasons else ""
        lines.append(f"- **[{a.tier}]** {a.name} ({rev}, {emp}"
                     f"{', ' + loc if loc else ''}){why}")
    lines += ["", f"## Contacts fed to Apollo ({len(contacts)})", ""]
    for c in contacts[:60]:
        lines.append(f"- {c.first_name} {c.last_name} — {c.title} @ {c.company}")
    failures = [s for s in statuses if not s.ok]
    if failures:
        lines += ["", "## API issues this run", ""]
        lines += [f"- `{s.source}`: {s.detail}" for s in failures]
    if seq:
        s = seq.get("summary", {})
        lines += ["", "## Sequence analysis", "",
                  f"- Steps: {s.get('num_steps', 0)} · avg reply "
                  f"{_pct(s.get('avg_reply_rate'))} · avg open "
                  f"{_pct(s.get('avg_open_rate'))}", ""]
        lines += [f"- {r}" for r in seq.get("recommendations", [])[:8]]
    lines.append("")
    (out / "latest.md").write_text("\n".join(lines), "utf-8")


def write_html(accounts: list[Account], contacts: list[Contact],
               statuses: list[SourceStatus], seq: dict | None,
               out: Path, meta: dict) -> None:
    def esc(s) -> str:
        return htmllib.escape(str(s), quote=True)

    rows = []
    for a in accounts:
        rev = (f"${a.revenue/1e9:.1f}B" if a.revenue and a.revenue >= 1e9 else
               (f"${a.revenue/1e6:.0f}M" if a.revenue else "—"))
        emp = f"{a.employees:,}" if a.employees else "—"
        loc = " · ".join(x for x in (a.city, a.country) if x)
        tier_cls = a.tier.lower() if a.tier else "standard"
        tags = " ".join(f"<span class='tag'>{esc(r)}</span>" for r in a.reasons[:4])
        link = (f'<a href="{esc(a.website or ("https://" + a.domain if a.domain else ""))}"'
                f' target="_blank" rel="noopener">{esc(a.name)}</a>'
                if (a.website or a.domain) else esc(a.name))
        rows.append(f"""
        <tr>
          <td><span class="tier {tier_cls}">{esc(a.tier or '—')}</span></td>
          <td class="name">{link}<div class="sub">{esc(a.industry)} {tags}</div></td>
          <td class="num">{esc(rev)}</td>
          <td class="num">{esc(emp)}</td>
          <td class="loc">{esc(loc)}</td>
        </tr>""")
    acct_table = ("".join(rows) if rows else
                  '<tr><td colspan="5" class="empty">No accounts this run.</td></tr>')

    crows = []
    for c in contacts[:200]:
        crows.append(f"""
        <tr><td>{esc(c.first_name)} {esc(c.last_name)}</td>
        <td>{esc(c.title)}</td><td>{esc(c.company)}</td>
        <td class="loc">{esc(' · '.join(x for x in (c.city, c.country) if x))}</td></tr>""")
    contact_table = ("".join(crows) if crows else
                     '<tr><td colspan="4" class="empty">No contacts this run.</td></tr>')

    seq_html = ""
    if seq:
        s = seq.get("summary", {})
        rec_items = "".join(f"<li>{esc(r)}</li>" for r in seq.get("recommendations", []))
        find_items = "".join(f"<li>{esc(f)}</li>" for f in seq.get("findings", []))
        seq_html = f"""
    <section>
      <h2>Sequence analysis</h2>
      <div class="stats">
        <div><b>{esc(s.get('num_steps', 0))}</b><span>steps</span></div>
        <div><b>{int(s.get('total_sent') or 0):,}</b><span>sent</span></div>
        <div><b>{_pct(s.get('avg_open_rate'))}</b><span>avg open</span></div>
        <div><b>{_pct(s.get('avg_reply_rate'))}</b><span>avg reply</span></div>
      </div>
      <h3>Findings</h3><ul>{find_items or '<li>None.</li>'}</ul>
      <h3>Recommendations</h3><ul class="recs">{rec_items or '<li>None.</li>'}</ul>
    </section>"""

    failures = [s for s in statuses if not s.ok]
    src_note = ""
    if failures:
        items = "".join(f"<li><code>{esc(s.source)}</code>: {esc(s.detail)}</li>"
                        for s in failures)
        src_note = (f'<details class="issues"><summary>{len(failures)} API '
                    f'issue(s) this run</summary><ul>{items}</ul></details>')

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    whales = sum(1 for a in accounts if a.tier == "Whale")
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Apollo Feeder — Global FinServ Whales</title>
<style>
  :root {{ --bg:#f7f7fb; --card:#fff; --ink:#1c1e26; --muted:#6b7280;
           --accent:#4f46e5; --whale:#7c3aed; --priority:#2563eb; --line:#e5e7eb; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#121319; --card:#1c1e28; --ink:#e7e8ee; --muted:#9aa0ae;
             --accent:#8b85f4; --whale:#a78bfa; --priority:#60a5fa; --line:#2a2d3a; }} }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
         background:var(--bg); color:var(--ink); padding:2rem 1rem 4rem; }}
  main {{ max-width:960px; margin:0 auto; }}
  h1 {{ font-size:1.6rem; margin:0 0 .25rem; }}
  .sub {{ color:var(--muted); font-size:.9rem; margin-bottom:1.5rem; }}
  section {{ background:var(--card); border:1px solid var(--line);
            border-radius:12px; padding:1rem 1.25rem; margin-bottom:1.5rem; }}
  h2 {{ font-size:1.15rem; margin:.25rem 0 .75rem; }}
  h3 {{ font-size:.95rem; margin:1rem 0 .35rem; color:var(--muted); }}
  table {{ width:100%; border-collapse:collapse; font-size:.9rem; }}
  th {{ text-align:left; color:var(--muted); font-weight:600; font-size:.78rem;
       text-transform:uppercase; letter-spacing:.03em; padding:.4rem .5rem;
       border-bottom:1px solid var(--line); }}
  td {{ padding:.55rem .5rem; border-bottom:1px solid var(--line);
       vertical-align:top; }}
  td.num {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
  td.loc {{ color:var(--muted); font-size:.85rem; }}
  .name a {{ color:var(--accent); text-decoration:none; font-weight:600; }}
  .name a:hover {{ text-decoration:underline; }}
  .sub {{ color:var(--muted); font-size:.8rem; margin-top:.15rem; }}
  .tag {{ display:inline-block; margin-left:.3rem; padding:0 .4rem;
         border:1px solid var(--line); border-radius:999px; font-size:.7rem; }}
  .tier {{ display:inline-block; padding:.05rem .45rem; border-radius:999px;
          font-size:.72rem; font-weight:700; color:#fff; background:var(--muted); }}
  .tier.whale {{ background:var(--whale); }}
  .tier.priority {{ background:var(--priority); }}
  .stats {{ display:flex; gap:1.5rem; flex-wrap:wrap; margin:.5rem 0 1rem; }}
  .stats div {{ display:flex; flex-direction:column; }}
  .stats b {{ font-size:1.4rem; }}
  .stats span {{ color:var(--muted); font-size:.78rem; }}
  .recs li {{ margin-bottom:.35rem; }}
  .empty {{ color:var(--muted); padding:.8rem; text-align:center; }}
  .issues {{ color:var(--muted); font-size:.85rem; }}
  .pills {{ display:flex; gap:1rem; flex-wrap:wrap; margin-bottom:1rem; }}
  .pill {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
          padding:.5rem .9rem; }}
  .pill b {{ font-size:1.3rem; display:block; }}
  .pill span {{ color:var(--muted); font-size:.78rem; }}
  footer {{ color:var(--muted); font-size:.8rem; margin-top:2rem; }}
  a.dl {{ color:var(--accent); }}
</style>
</head>
<body>
<main>
  <h1>Apollo Feeder — Global FinServ Whales</h1>
  <div class="sub">Deep-pocket financial-services accounts and their senior
    buyers, scored and ready to feed into Apollo. Updated {generated}.
    <a class="dl" href="apollo_import.csv">Apollo CSV</a> ·
    <a class="dl" href="accounts.json">accounts JSON</a> ·
    <a class="dl" href="contacts.json">contacts JSON</a> ·
    <a class="dl" href="latest.md">Markdown</a></div>
  <div class="pills">
    <div class="pill"><b>{len(accounts)}</b><span>accounts</span></div>
    <div class="pill"><b>{whales}</b><span>whales</span></div>
    <div class="pill"><b>{len(contacts)}</b><span>contacts</span></div>
  </div>
{src_note}
  <section>
    <h2>Accounts</h2>
    <table>
      <thead><tr><th>Tier</th><th>Company</th><th>Revenue</th>
      <th>Employees</th><th>HQ</th></tr></thead>
      <tbody>{acct_table}</tbody>
    </table>
  </section>
  <section>
    <h2>Contacts</h2>
    <table>
      <thead><tr><th>Name</th><th>Title</th><th>Company</th><th>Location</th></tr></thead>
      <tbody>{contact_table}</tbody>
    </table>
  </section>
{seq_html}
  <footer>Auto-generated by apollo_feeder_bot.py using the Apollo.io API.
  Search results only; verify and enrich inside Apollo before outreach.</footer>
</main>
</body>
</html>
"""
    (out / "index.html").write_text(page, "utf-8")

# ------------------------------------------------------------------ main ---


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apollo prospecting feeder")
    ap.add_argument("--pages", type=int, default=2,
                    help="pages to pull per search (25/page, default 2)")
    ap.add_argument("--min-revenue", type=float, default=500_000_000,
                    help="minimum account revenue in USD (default 500M)")
    ap.add_argument("--create-list", metavar="NAME", default=None,
                    help="push found contacts into an Apollo list (mutates, uses credits)")
    ap.add_argument("--enrich", action="store_true",
                    help="(reserved) reveal emails via enrichment (uses credits)")
    ap.add_argument("--sequence-csv", metavar="PATH", default=None,
                    help="analyze an exported Apollo sequence-stats CSV")
    ap.add_argument("--out-dir", default="apollo", help="output directory")
    args = ap.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    statuses: list[SourceStatus] = []
    accounts: list[Account] = []
    contacts: list[Contact] = []

    api_key = os.environ.get("APOLLO_API_KEY", "").strip()
    if api_key:
        client = ApolloClient(api_key)
        accounts, acct_status = search_accounts(
            client, FINANCIAL_HUBS, FINSERV_KEYWORDS, args.min_revenue, args.pages)
        statuses += acct_status
        accounts = dedupe_accounts(accounts)

        account_ids = [a.apollo_id for a in accounts if a.apollo_id][:100]
        contacts, ppl_status = search_people(
            client, account_ids, PERSONA_TITLES, PERSONA_SENIORITIES, args.pages)
        statuses += ppl_status
        contacts = dedupe_contacts(contacts)

        if args.create_list and contacts:
            statuses += push_contacts_to_list(client, contacts, args.create_list)
    else:
        statuses.append(SourceStatus(
            "apollo-api", False,
            "APOLLO_API_KEY not set - skipped account/people search"))

    seq = None
    if args.sequence_csv:
        try:
            text = Path(args.sequence_csv).read_text("utf-8", errors="replace")
            seq = analyze_sequence(parse_sequence_rows(text))
            statuses.append(SourceStatus(
                "sequence-csv", True, args.sequence_csv,
                seq["summary"].get("num_steps", 0)))
            write_sequence_md(seq, out)
        except Exception as exc:  # noqa: BLE001
            statuses.append(SourceStatus(
                "sequence-csv", False, f"{type(exc).__name__}: {exc}"))

    meta = {"pages": args.pages, "min_revenue": args.min_revenue,
            "hubs": FINANCIAL_HUBS, "keywords": FINSERV_KEYWORDS}
    write_csv(contacts, accounts, out)
    write_json(accounts, contacts, statuses, seq, out, meta)
    write_markdown(accounts, contacts, statuses, seq, out, meta)
    write_html(accounts, contacts, statuses, seq, out, meta)

    ok = sum(1 for s in statuses if s.ok)
    print(f"Sources OK: {ok}/{len(statuses)} · accounts: {len(accounts)} · "
          f"contacts: {len(contacts)}")
    for s in statuses:
        flag = "ok " if s.ok else "ERR"
        print(f"  [{flag}] {s.source:<13} {s.detail} ({s.found} found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
