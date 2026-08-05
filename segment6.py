#!/usr/bin/env python3
"""Six-department segmentation: Marketing, CX/Operations, Product, Digital & Martech,
Compliance, AI  (+ residual 'Other' for roles outside these six)."""
import json

rows = json.load(open("/tmp/persona_rows.json"))  # (fn, ln, title, company, old_persona)

def seg6(title):
    t = " " + title.lower().replace("|", " ").replace("/", " / ") + " "
    def has(*ks):
        return any(k in t for k in ks)

    # product marketing is a Marketing discipline (guard before AI/Product)
    if "product marketing" in t:
        return "Marketing"

    # 1) AI  (strong AI signals only)
    if has("artificial intelligence", "genai", "gen ai", "conversational", "agentic",
            "machine learning", "ai / ml", "ai/ml", "data & ai", "data and ai",
            "ai transformation", "ai product", "ai research", "ai change", "ai adoption",
            "ai innovation", "ai applied", "ai officer", "head of ai", "ai lead"):
        return "AI"

    # 2) Compliance / Risk
    if has("compliance", " aml", "kyc", " risk", "risk ", "risk&", "risk management",
            "operational risk", "screening", "regulat", "financial crime", "fraud",
            " legal", "surveillance", "information security", "sanction", " afc", " esg"):
        return "Compliance"

    # 3) Digital & Martech
    if has("martech", "marketing technology", "marketing automation", "adtech", " crm",
            "lifecycle", "engagement platform", "marketing operations", "marketing ops",
            "marketing effectiveness", "marketing tech", "digital marketing", "digital sales",
            "digital channel", "digital contact", "digital platform", "digital transformation",
            "digital information", "digital banking", "omnichannel", "performance marketing",
            "paid ", "paid search", "paid acquisition", " seo", "programmatic",
            "social & influencer", "social and influencer", "influencer", "affiliate",
            "field marketing"):
        return "Digital & Martech"

    # 4) Marketing (brand / content / comms / creative / campaign / growth / general marketing)
    if has("brand", "content", "communication", " comms", "creative", "campaign",
            "growth", " media", "cmo", "chief marketing", "sponsor", " event",
            "go-to-market", " gtm", "marketing"):
        return "Marketing"

    # 5) Product & Design
    if has("product", "design", " ux", " ui ", "mobile"):
        return "Product"

    # 6) CX / Operations
    if has("customer experience", "customer journey", "customer engagement", "customer insight",
            "customer satisfaction", "customer service", "customer strategy", "customer operation",
            "customer contact", "vulnerable customer", " cx", "cx ", "chief cx", "cex",
            "client experience", "experience design", "experience lead", "experience manager",
            "experience &", "operation", "delivery", "production", "procurement", "vendor",
            "project", "process", "workforce", "expertise center", "business support",
            "onboarding", "servicing", "customer center"):
        return "CX / Operations"

    # 7) Everything else (Engineering / Sales / Commercial / Strategy / Exec / Banking / HR)
    return "Other (outside these 6)"

# Manual overrides where the keyword rule misfires -> "Company||First||Last": segment
OVERRIDES6 = {
    "HSBC||Nicole||German": "Marketing",              # Global CMO (has 'digital experience')
    "HSBC||Hazem||El Taha": "Digital & Martech",       # Group Marketing Technology
    "Santander||Adam||Beardmore": "Product",           # Product Operations, Digital Channels
    "Monzo||Rannie||Powell": "Digital & Martech",      # Marketing Tech, AI & Insights
    "ABN AMRO||Yorick||Naeff": "Product",              # Head of Innovation -> product/innovation
    "Credit Agricole||Julian||Nastase": "Other (outside these 6)",  # COO & Business Manager
    "Starling Bank||Lisa||Cunico": "Marketing",        # 'Production' != Product (creative production, CMO org)
    "Millennium BCP||Pedro||Mendes": "CX / Operations", # Diretor Experiencia do Cliente (PT) = Customer Experience
}

from collections import Counter, defaultdict
counts = Counter()
groups = defaultdict(list)
out_rows = []
for fn, ln, title, company, _old in rows:
    key = f"{company}||{fn}||{ln}"
    s = OVERRIDES6.get(key) or seg6(title)
    counts[s] += 1
    groups[s].append((company, f"{fn} {ln}".strip(), title))
    out_rows.append((fn, ln, title, company, s))

ORDER = ["Marketing", "CX / Operations", "Product", "Digital & Martech",
         "Compliance", "AI", "Other (outside these 6)"]
total = len(rows)
print(f"TOTAL: {total}\n")
for s in ORDER:
    print(f"{counts[s]:3d}  {100*counts[s]/total:4.0f}%  {s}")

json.dump(out_rows, open("/tmp/segment6_rows.json", "w"))
