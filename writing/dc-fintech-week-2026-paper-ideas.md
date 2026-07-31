# DC Fintech Week 2026 — Paper Concepts

_Prepared for the Fintech Foundation's Call for Papers (submissions ≤10,000 words, due Aug 30, 2026)._
_Angle: written from the vantage point TransPerfect Financial Services actually occupies — the language, localization, identity, and regulated-content layer that sits underneath cross-border digital finance._

---

## Why this vantage point is worth a paper

Almost every serious fintech-policy conversation treats language as solved. It isn't. Interoperability debates stop at message formats and APIs. Digital-identity debates stop at the credential and skip what happens when a name crosses a script boundary. Agentic-commerce debates assume the human read and understood a disclosure that was, in fact, machine-translated. Financial-inclusion debates rarely mention that tens of millions of people in the world's richest markets can't transact in the language their bank speaks.

That gap is the opening. TransPerfect FS lives in exactly the seam these papers keep stepping over — regulated translation (fund documents, PRIIPs KIDs, prospectuses, disclosures, proxy materials), multilingual legal and e-discovery review, AI/machine-translation pipelines, and the identity-and-screening problems that appear the moment finance touches more than one language. A paper written from here isn't a marketing piece; it's a genuinely under-covered layer of the stack, which is precisely what a rigorous call-for-papers wants.

Below are six concepts, ranked. Each is scoped to the conference's stated preference: short, digestible, and built around one novel idea rather than a literature dump.

---

## ★ Lead recommendation

### 1. The Localization Layer: Language as Missing Infrastructure for Cross-Border Digital Finance

- **One-line thesis:** Interoperability in cross-border finance is treated as a technical-messaging problem (ISO 20022, APIs, network rails), but the layer that actually fails for real users — disclosures, consent, identity across scripts — is *linguistic*, and no one owns it.
- **Listed topics it hits:** Interoperability across Payment Systems, Open Banking, and Digital Identity; Trust, Identity, and Verification Layers.
- **The gap:** There is rich literature on payment-system interoperability and almost none treating language/localization as a first-class interoperability problem. Yet a "successful" cross-border payment that arrives with a disclosure the recipient can't read has not actually interoperated in any meaningful sense.
- **Argument arc:**
  1. Define the localization layer and where it sits relative to the technical stack.
  2. Show three concrete break points: consumer disclosures, consent/authorization flows, and identity data (name/address across scripts).
  3. Argue that leaving this layer ungoverned pushes cost and risk onto the least-protected users and creates supervisory blind spots.
  4. Propose treating language access as an interoperability *requirement*, not a courtesy — with a light-touch standards angle regulators could actually adopt.
- **What's novel:** Reframing localization from back-office cost center to systemic interoperability dependency. Almost nobody in this forum is saying it.
- **Evidence TransPerfect can bring credibly:** patterns in regulated-content volume, turnaround, and error classes across jurisdictions; where multilingual disclosure obligations diverge (EU PRIIPs vs. US vs. APAC).
- **Format fit:** Excellent. This is a 4,000–6,000-word "big idea, cleanly argued" piece — exactly the digestible-for-a-broad-audience shape they asked for.

---

## Strong alternatives

### 2. Machine Translation Is Now a Regulated Financial Function

- **One-line thesis:** Once an LLM drafts or translates consumer-facing regulated content — KIDs, disclosures, complaint responses, chatbot answers — translation stops being editorial and becomes a model-governed function that belongs inside model-risk management (think SR 11-7), not procurement.
- **Listed topics it hits:** Artificial Intelligence and the Future of Work, Credit, and Market Access; Trust, Identity, and Verification Layers.
- **The gap:** Model-risk frameworks were written for credit and pricing models. No mainstream framework treats "the model that tells a customer what they're buying, in their language" as a governed model — even though a mistranslated risk warning is a compliance event.
- **Argument arc:** the shift from human-in-the-loop translation to generative pipelines → the specific failure modes (hallucinated numbers, softened risk language, false fluency that hides errors) → why existing MRM controls (validation, monitoring, human oversight tiers) map surprisingly well → a proposed control framework and a "which content tiers can be automated" decision rule.
- **What's novel:** A concrete governance proposal that regulators and banks could pick up, bridging the AI-risk and consumer-protection conversations through a layer nobody currently governs.
- **Why it's a contender for the lead:** It's the most *actionable* idea here and the most defensibly TransPerfect's expertise. Choose this over #1 if the goal is regulator utility over conceptual reframing.

### 3. Transliteration Risk: Names, Sanctions Screening, and Identity Across Scripts

- **One-line thesis:** Digital identity and sanctions/AML screening quietly fail at the script boundary — the same person is spelled a dozen ways across Arabic, Cyrillic, and CJK romanization — and this is a measurable, systemic, and largely unowned source of both false negatives (sanctions evasion) and false positives (wrongful exclusion).
- **Listed topics it hits:** Trust, Identity, and Verification Layers; AI and Market Access.
- **The gap:** Verifiable-credential and digital-ID literature assumes a canonical identity string. Real cross-border identity is a transliteration problem. Screening false-positive rates are a known operational pain but rarely framed as an identity-infrastructure design flaw.
- **What's novel:** Positions transliteration as a first-order digital-identity design constraint, with a taxonomy of failure and a case that AI matching without linguistic grounding makes it worse, not better.
- **Format fit:** Naturally short and vivid; carries strong concrete examples.

### 4. Agents Don't Read the Fine Print

- **One-line thesis:** Agentic commerce assumes disclosures exist to inform a human reading in one language. When an AI agent transacts on a user's behalf across jurisdictions, the chain of "was the user actually informed, in a language they understand?" breaks — and accountability for that break is undefined.
- **Listed topics it hits:** Agentic Commerce: Payments, Supervision, and Accountability.
- **Argument arc:** map the disclosure/consent chain in a human transaction → show where an agent removes the human's comprehension step → the cross-language twist (agent operates in English; user's binding terms are in another language, or vice versa) → an accountability framework: who attests that localized terms were surfaced and understood.
- **What's novel:** Connects agentic-commerce accountability to the comprehension/language question, which the current agent-payments discourse ignores entirely.

### 5. Language Access as Financial Inclusion: The LEP Gap in Digital Finance

- **One-line thesis:** The financial-inclusion agenda under-counts a huge, addressable population — limited-English-proficiency consumers in wealthy markets — and digital finance plus AI translation is the first tool that can close, rather than widen, that gap.
- **Listed topics it hits:** AI and the Future of Work, Credit, and Market Access; Community and Small-Bank Finance.
- **What's novel:** Frames language access (a CFPB/consumer-protection theme) as a fintech-inclusion opportunity with an AI mechanism, rather than a compliance burden. Optimistic, data-driven, and audience-friendly.

### 6. Smart Contracts Still Need Words

- **One-line thesis:** Programmable finance still depends on natural-language legal terms mapped to code — and across jurisdictions and languages, the prose↔code↔prose translation gap is exactly where enforcement and dispute resolution fail.
- **Listed topics it hits:** Smart Contracts and Programmable Finance: Law, Design, and Enforcement; Tokenization of Real-World Assets.
- **What's novel:** Brings the legal-translation lens (TransPerfect's legal/e-discovery heritage) to a debate dominated by cryptographers and lawyers who assume one legal language.

---

## How to choose

| If the goal is… | Submit |
|---|---|
| A memorable reframe that travels beyond the room | #1 The Localization Layer |
| Something a regulator can act on next quarter | #2 MT as a Regulated Function |
| Concrete, vivid, hard-to-argue-with risk | #3 Transliteration Risk |
| Riding the biggest 2026 narrative (agents) | #4 Agents Don't Read the Fine Print |

**My pick:** Lead with **#1**, and bank **#2** as the fallback if the committee signals it wants regulator-actionable over conceptual. The two share a spine (an ungoverned language layer) and could even be written as one paper with #2 as the closing "so what do we do" section — a strong ≤8,000-word combined submission.

---

## Draft abstract for the lead concept (drop-in ready, ~180 words)

> Cross-border finance is getting faster at the plumbing and no better at being understood. Standards work on payment interoperability — ISO 20022, open-banking APIs, shared identity credentials — has advanced the technical layer while leaving a quieter one untouched: the language in which a payment, a product, or a consent is actually communicated to the person on the other end. This paper argues that localization is a first-class interoperability problem, not a downstream courtesy. Drawing on the divergence of multilingual disclosure regimes and on failure patterns in translated regulated content and cross-script identity data, it identifies three break points where "interoperable" systems stop interoperating for real users — disclosures, consent flows, and identity — and shows how leaving the language layer ungoverned concentrates risk on the least-protected participants while creating supervisory blind spots. It closes with a light-touch proposal: treat language access as an interoperability requirement, with practical attestations that regulators and networks could adopt without new heavy machinery. Language, the paper contends, is infrastructure — and it is the piece we keep forgetting to build.
