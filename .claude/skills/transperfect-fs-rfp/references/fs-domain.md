# Financial Services + Localization: Domain Knowledge

Read this when an RFP touches regulated content, data protection, a specific FS sub-vertical, or
locale-specific requirements (especially US Spanish / crypto). It exists so answers are credible to a
subject-matter evaluator, not just a procurement generalist.

## Why FS localization is different

FS content is often **regulated**: mistranslation isn't just a quality issue, it's legal and compliance
exposure the client is trying to offload to a vendor they trust. Accuracy, consistency of regulated
terminology, auditability, and confidentiality outrank speed and price in most FS evaluations. Always
distinguish **content that must be precise and reviewed** (disclosures, contracts, filings, compliance)
from **content that should be adapted** (marketing, brand, lifecycle) — they need different workflows.

## Key document / content types by sub-vertical

- **Asset & wealth management:** prospectuses, KIIDs/KIDs (PRIIPs), fund fact sheets, factsheets, annual/
  semi-annual reports, shareholder communications, RFP responses, pitchbooks, marketing.
- **Banking:** account/legal agreements, disclosures, statements, customer communications, apps/websites.
- **Insurance:** policies, benefit summaries, claims, regulatory filings.
- **Capital markets / IR:** earnings releases and calls, AGM materials, investor roadshows, research.
- **Fintech / crypto / digital assets:** app & web product strings, wallet/exchange UI, terms of service,
  risk disclosures, compliance/AML/KYC content, help center, lifecycle/marketing.

## Regulatory landmarks to sound credible (US + EU)

- **US:** SEC (securities disclosure), FINRA (broker-dealer communications rules on fair/balanced,
  non-misleading content), state insurance/banking regulators, FinCEN & state **money-transmitter
  licenses** (crypto/payments), CFPB (consumer finance). Plain-language and "fair and not misleading"
  standards mean translations must preserve required disclosures exactly.
- **EU / global:** MiFID II, PRIIPs (KID), UCITS, ESMA guidance; many require investor documents in the
  local official language(s) — a core driver of FS translation demand.
- **Crypto specifics:** highly scrutinized; disclosures and risk warnings are compliance-critical.
  Binance.US operates under US state money-transmitter regimes and federal scrutiny — its legal/compliance
  strings need precise, review-gated translation, not creative adaptation.

> You don't need to give legal advice — you need to show the client that TransPerfect *understands their
> regulatory reality* and routes regulated content through accuracy-first, review-gated workflows.

## Locale precision — Spanish especially

Spanish is not one market. For a US audience use **US Spanish** (the variety used by US Hispanic
populations) — distinct from **neutral Latin American Spanish** and from **European (Spain) Spanish** in
terminology, register, and cultural reference. Financial and crypto terminology must be standardized in a
client-approved **glossary** and **style guide** and enforced via translation memory. Getting the variant
wrong is an immediate credibility loss with an evaluator who speaks the language — which is exactly why
buyers like Binance.US say the decision turns on proven regulated-FS work in that specific variant.

## Localization technology concepts (speak fluently)

- **TM (translation memory):** database of past translations; repeated/similar segments are reused →
  consistency + cost reduction (fuzzy/exact-match discounts).
- **Termbase / glossary:** approved terminology, critical for regulated terms.
- **Style guide:** tone, register, formatting, locale conventions.
- **TMS / GlobalLink:** the platform managing workflow, connectors, review, and reporting.
- **Continuous / agile localization:** connectors to code repos/CI-CD and CMS so product strings flow to
  translation and back automatically — essential for app/web string RFPs with frequent releases.
- **MT + post-editing (MTPE):** custom-trained MT with human post-edit for scale; tolerance varies by
  content type — acceptable for help center/high-volume, generally *not* for compliance/legal.
- **DTP:** desktop publishing/formatting of translated files (InDesign, PowerPoint, etc.).
- **Linguistic QA / back-translation:** independent checks; back-translation used where regulators or risk
  demand proof of fidelity.

## Security & confidentiality expectations (FS buyers)

Expect scrutiny on: ISO 27001 `[VERIFY]`, SOC 2 `[VERIFY]`, encryption in transit/at rest, access control,
NDAs with all personnel, secure transfer (SFTP or platform portal), data residency, retention/deletion,
sub-processor disclosure, and breach notification. For crypto/fintech, add: handling of pre-release
product content and market-sensitive material under strict NDA (relevant to "final volumes and test
content under NDA" clauses).

## Starter clarifying-question list for a localization RFP

Use/trim these when the RFP invites vendor questions:
1. Total and per-content-type **volumes** (word counts / string counts) and expected monthly cadence.
2. **Source formats and environments** — repos, CMS, design tools, existing TMS.
3. Existing **linguistic assets** — TM, glossary, style guide? Provided or to be built?
4. **Review model** — client in-country reviewers? SLA on their review turnaround?
5. **Translation-test content** type and length; scoring rubric.
6. **MT tolerance** by content type (product vs. legal vs. help center vs. marketing).
7. **Security/NDA** requirements; data residency; handling of pre-release/market-sensitive content.
8. **Turnaround/SLA** expectations and rush definition.
9. **Incumbent** situation and reason for the RFP (the pain to solve).
10. **Contract/commercial model** — platform + services scope, term, volume commitments.
