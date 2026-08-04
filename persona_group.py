#!/usr/bin/env python3
"""Classify the full prospect list into marketing-outreach personas and group them."""
from build_prospect_list import DATA as BASE_DATA  # original 220 (Company, [(name,title,email)])

# --- New / added contacts from the cleaned list (First, Last, Title, Company) ---
NEW = [
    ("Jennifer", "Scott", "Head of Digital Banking Technology", "NatWest Group"),

    ("Maximilian", "Meyer", "Chief Marketing Officer", "Scalable Capital"),
    ("Katherina", "Samusch H", "VP Technology", "Scalable Capital"),
    ("Michele", "Cola", "Senior Growth Marketing Manager", "Scalable Capital"),
    ("Johannes", "Weiss", "VP, Engineering", "Scalable Capital"),
    ("Sabrina", "Pichlbauer-Biebl", "Head of Operations", "Scalable Capital"),
    ("Katharina", "Brunsendorf", "Head of Content", "Scalable Capital"),
    ("Alessandro", "Saldutti", "Head of Italy", "Scalable Capital"),
    ("David", "Pichner", "VP, Growth & Engagement", "Scalable Capital"),
    ("Konstantin", "Eller", "Senior Manager CEO Office", "Scalable Capital"),
    ("Benjamin", "Otto", "Head of Mobile", "Scalable Capital"),
    ("Dirk", "Urmoneit", "Chief Strategy Officer", "Scalable Capital"),
    ("Julie", "Seibold", "Senior Risk Manager", "Scalable Capital"),
    ("Isabel", "Kornmayer", "Head of Banking Operations", "Scalable Capital"),
    ("Julia", "Lebmeister", "Senior KYC Operations Manager, ESG Officer", "Scalable Capital"),

    ("Bianca", "Zwart", "Chief Strategy Officer", "Bunq"),
    ("Ainhoa", "Montanchez", "Social & Influencer Marketing Lead", "Bunq"),
    ("Hazjier", "Pourkhalkhali", "VP of Growth, Banking as a Service", "Bunq"),
    ("Huseyin R", "Demirhisar", "Head of Global Operations / Operational Expansion", "Bunq"),
    ("Pablo", "Bernal-Mencia", "Head of Product", "Bunq"),
    ("Sebastian", "Kumeth", "Country Manager & Branch Managing Director Germany", "Bunq"),
    ("Shachar", "Bry", "Head of Operations Experience", "Bunq"),
    ("Abdo", "Kesserwani", "Head of Marketing", "Bunq"),
    ("Rowan Standish Hayes", "", "Head of Content Agency", "Bunq"),
    ("Mia", "Nguyen", "Paid Search Manager", "Bunq"),
    ("Gonzalo", "Herrero Crespo", "Growth Marketing & Acquisition - EEA", "Bunq"),
    ("Alper Can", "Ertan", "Head of Operational Risk", "Bunq"),
    ("Brent", "Van Assen", "Head of Ops Improvements", "Bunq"),
    ("Arjan", "Molenkamp", "International Expansion", "Bunq"),

    ("Toni", "Moorcroft", "Head of Content Strategy", "Featurespace"),
    ("Kendra", "Rogers", "Comms Chief & Marketing Officer", "Featurespace"),
    ("Juspal", "Manic", "Chief Revenue Officer", "Featurespace"),
    ("Patricia", "Gomez Santacruz", "Strategic Enterprise Director, Spain & Latam", "Featurespace"),
    ("Ahtesham 'Ash'", "Ahmed", "General Manager & VP of Sales, North America", "Featurespace"),
    ("Adam", "Hawkes", "Director, Information Security Architecture & Compliance", "Featurespace"),
    ("James", "MacDonald Turner", "VP Commercial", "Featurespace"),
    ("Janine", "Michaels", "Head of Marketing Operations", "Featurespace"),

    ("Jon", "Heaton", "SVP, Engineering", "Ebury"),
    ("Charles", "Hardaker", "Managing Director - Business Finance Solutions", "Ebury"),
    ("Sagi", "Winer", "SVP, Engineering", "Ebury"),
    ("Mark", "Hewlett", "Group Head of Banking and Infrastructure", "Ebury"),
    ("Bhavin", "Vaghela", "Senior Lead, Banking & Infrastructure", "Ebury"),
    ("Peter", "Brooks", "Partner, Global Head of Sports", "Ebury"),
    ("Esther", "Illana", "Chief Strategy Officer", "Ebury"),
    ("Enrique", "Colin", "Chief Product & Technology Officer", "Ebury"),
    ("Wesley", "Rickards", "Head of Product - Enabling Function", "Ebury"),
    ("Joyanne", "Joseph", "Marketing Lead, Mass Payments", "Ebury"),
    ("Aaron", "Goldstein", "Marketing Lead", "Ebury"),
    ("Duarte", "Monteiro", "Chief Business Officer", "Ebury"),
    ("Leah", "Zhang", "Marketing Executive, B2B", "Ebury"),
    ("Jigna", "Shah", "Global Content Marketing Manager", "Ebury"),
    ("Blanca", "Daunert", "Product Manager - Payments", "Ebury"),

    ("Ashwin", "Seshadri", "Head of International Product Marketing", "Stripe"),
    ("Nicholas", "Davies", "Marketing Operations Manager, EMEA", "Stripe"),
    ("Emily", "Howard", "Field Marketing Lead, EMEA Platforms", "Stripe"),
    ("James", "Lemon", "Global Lead - Hospitality, Travel & High Growth Industries", "Stripe"),
    ("Claire", "O'Toole", "Global Vendor Strategy", "Stripe"),
    ("Catherine", "Duffy", "Head of Product Experience Operations", "Stripe"),
    ("Mohammadou", "Wadjiri", "Risk Operations", "Stripe"),
    ("Karen", "Smyth", "L&D Program Manager, EMEA New Hire Programs", "Stripe"),
    ("Jason", "Nagle", "Global Operations", "Stripe"),
    ("Anna", "King", "Strategy & Operations Lead", "Stripe"),
    ("Avide", "Tayeby", "Head of Operations", "Stripe"),
    ("Teresa", "Doran", "EMEA Chief Operating Officer PCF-42 (EEA) & EMD (UK)", "Stripe"),
    ("Conor", "McNamara", "EMEA CRO", "Stripe"),
    ("Diana", "Meleciano Curley", "Global Support Operations Transformation & Workforce Systems", "Stripe"),
    ("Utku Can", "Utkan", "Sales Strategy and Operations, EMEA", "Stripe"),
    ("Richard", "Van Cleeff", "Senior Delivery Leader | Global Operations, Business Transformation & Vendor Strategy", "Stripe"),
    ("Ollie", "Rickman", "Head of Communications", "Stripe"),
    ("Julia", "Montgomery", "Global Product Marketing, SaaS Platforms", "Stripe"),
    ("Gargi", "Paira", "Marketing EMEA platforms", "Stripe"),
    ("Maximilian", "Scharf", "Marketing Lead - DACH & CEE", "Stripe"),

    ("Sebastian", "Broch", "Managing Director / Divisional Head of Business & Risk Management in Group Operations", "Commerzbank"),
    ("Thomas", "Ullmann", "Senior Application Operations Manager Trade & Communication Surveillance", "Commerzbank"),
    ("Metin", "Kucur", "Managing Director - Principal Project Manager (CTO IT Infrastruct. Technology Stack Transformation)", "Commerzbank"),
    ("Ahsan", "Afzal", "Director - Financial Crime Operations Lead", "Commerzbank"),
    ("Anshul", "Bhatia", "VP, Operations Cluster Manager", "Commerzbank"),
    ("Julia", "Kratzenberg", "Snr. Project Manager, Group Operations, Trade & Payments Customer Center", "Commerzbank"),
    ("Magdalena", "Zulch", "Head of Projects in Operations", "Commerzbank"),
    ("Sunwy Raj", "Balla", "Program, Product and Project Management", "Commerzbank"),
    ("Sarah", "Hughes", "Director, Head of Marketing at Commerzbank Corporates & Markets", "Commerzbank"),
    ("Nasrin", "Shaikh", "Head of Marketing | Managing Director", "Commerzbank"),
    ("Thomas", "Lohbreier", "Head of Marketing Automation", "Commerzbank"),
    ("Verena", "Geissbigler", "Head of Digital Marketing", "Commerzbank"),
    ("Miriam", "Halter", "Head of Marketing Strategy", "Commerzbank"),
    ("Julia", "Brehmer", "Head of Content & Product-Marketing", "Commerzbank"),
    ("Evelyn", "Fruhauf", "Head of Customer Satisfaction", "Commerzbank"),
    ("Chris", "Bartz", "Managing Director / Head of Strategy & Projects / Private & Small Business Customers", "Commerzbank"),
    ("Catalin", "Petcu", "Debt Capital Markets", "Commerzbank"),
]

# Build a flat list of (first, last, title, company)
def split_name(full):
    parts = full.split()
    return (parts[0], " ".join(parts[1:])) if len(parts) > 1 else (full, "")

ROWS = []
for company, people in BASE_DATA:
    for full, title, email in people:
        fn, ln = split_name(full)
        ROWS.append((fn, ln, title, company))
for fn, ln, title, company in NEW:
    ROWS.append((fn, ln, title, company))

# --- Persona classifier (priority order; first match wins) -------------------
def persona(title):
    t = " " + title.lower() + " "
    def has(*ks):
        return any(k in t for k in ks)

    # 2) Martech / Marketing Ops & Data  (check before general Marketing)
    if has("martech", "marketing technology", "marketing automation", "adtech",
           "marketing operations", "marketing ops", "marketing tech", "engagement platform",
           "marketing & engagement platform", "marketing effectiveness", "lifecycle",
           "crm", "digital platforms", "marketing data", "marketing analytics"):
        return "Martech / Marketing Ops & Data"

    # 3) CX / Customer Experience & AI  (check before general Marketing)
    if has("customer experience", "customer journey", "customer engagement", "customer insight",
           "customer satisfaction", " cx ", " cx&", "chief cx", "cex", " cx/",
           "conversational", "ai product", "ai transformation", "genai", "ai research",
           "data & ai", "ai/ml", "artificial intelligence", " ai ", "customer strategy",
           "vulnerable customer"):
        return "CX / Customer Experience & AI"

    # 1) Marketing / Digital / Brand
    if has("marketing", "brand", "communication", "comms", "growth", "performance",
           "content", "campaign", "acquisition", " media", "cmo", "advertis", "creative",
           "influencer", "affiliate", "seo", "paid search", "paid acquisition", "digital sales",
           "digital channel", "gtm", "go-to-market", "field marketing", "engagement"):
        return "Marketing / Digital / Brand"

    # 4) Product & Design / UX
    if has("product", "design", " ux", "ux ", "mobile"):
        return "Product & Design"

    # 5) Risk / Compliance / Financial Crime  (before Operations)
    if has("compliance", "aml", "kyc", "screening", "risk", "regulat", "financial crime",
           "fraud", "legal", "surveillance", "information security", "afc"):
        return "Risk / Compliance"

    # 6) Operations & Delivery
    if has("operation", "production", "procurement", "vendor", "project", "delivery",
           "process", "expertise center", "workforce"):
        return "Operations & Delivery"

    # 7) Everything else (Sales/Commercial, Engineering, Strategy, Banking, HR, Exec)
    return "Commercial / Sales / Eng / Strategy / Other"

# Manual overrides where the keyword rule misfires (Company||FirstName||Last -> persona)
OVERRIDES = {
    # "Digital Channels Planning & Control" is really digital-channel mgmt (marketing-adjacent)
    "Santander||Jorge||Varela": "Martech / Marketing Ops & Data",
    # Adam Beardmore: Product Operations, Digital Channels -> Product
    "Santander||Adam||Beardmore": "Product & Design",
    # Rannie Powell: Marketing Tech, AI & Insights -> Martech
    "Monzo||Rannie||Powell": "Martech / Marketing Ops & Data",
    # Hazem El Taha: Group Marketing Technology -> Martech
    "HSBC||Hazem||El Taha": "Martech / Marketing Ops & Data",
    # Matthew Harwood: Marketing & Engagement Platforms -> Martech
    "NatWest Group||Matthew||Harwood": "Martech / Marketing Ops & Data",
    # Katharina Pollak: Lifecycle (CRM) -> Martech
    "N26||Katharina||Pollak": "Martech / Marketing Ops & Data",
    # Genis Barnich: Adtech - Marketing Technology -> Martech
    "CaixaBank||Genis||Barnich Fonolla": "Martech / Marketing Ops & Data",
    # Thomas Lohbreier: Marketing Automation -> Martech
    "Commerzbank||Thomas||Lohbreier": "Martech / Marketing Ops & Data",
    # Katrina O'Donnell: Customer Engagement & CRM -> Martech (CRM) but also CX; keep CX -> leave
}

from collections import Counter, defaultdict
counts = Counter()
groups = defaultdict(list)
final_rows = []
for fn, ln, title, company in ROWS:
    key = f"{company}||{fn}||{ln}"
    p = OVERRIDES.get(key) or persona(title)
    counts[p] += 1
    groups[p].append((company, f"{fn} {ln}".strip(), title))
    final_rows.append((fn, ln, title, company, p))

total = len(ROWS)
print(f"TOTAL CONTACTS: {total}\n")
order = [p for p, _ in counts.most_common()]
for p in order:
    print(f"{counts[p]:3d}  {100*counts[p]/total:4.0f}%  {p}")

# Save for the workbook step
import json
with open("/tmp/persona_rows.json", "w") as f:
    json.dump(final_rows, f)
