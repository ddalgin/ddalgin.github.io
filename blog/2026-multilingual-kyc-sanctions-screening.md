# One Name, Six Spellings: The Multilingual Blind Spot in KYC and Sanctions Screening

*As banks, fintechs, and sportsbooks scale across markets, the hardest part of onboarding isn't the tech. It's the name.*

*Draft for the TransPerfect Financial Services blog · 2026-08-12*

---

Look at any global sports roster and you see the compliance problem in miniature. A Major League roster spans nearly 20 countries; a top European football club fields names that arrive in Latin, Cyrillic, Arabic, and CJK scripts, each with several valid romanizations. A single Arabic given name can be spelled Mohamed, Mohammed, or Muhammad; a Cyrillic surname can transliterate half a dozen ways into English. It's charming on a jersey. It's a nightmare in a sanctions filter.

**The more locales you serve, the harder KYC and screening become.** When one name has many spellings, two things happen at once: real sanctions and PEP hits can slip through under an unexpected transliteration, while thousands of harmless customers get flagged because their common surname fuzzy-matches a watchlist entry. Name-based screening is where this bites hardest, and the numbers are brutal. Financial institutions routinely report [false-positive rates above 90-95%](https://www.sanctions.io/blog/the-problem-of-false-positives-in-aml-screening), meaning analysts and MLRO teams spend the overwhelming majority of their time clearing [noise created by spelling and transliteration variants](https://www.facctum.com/blog/sanctions-screening-statistics), not catching bad actors.

## The stakes are enforcement-grade

This is not hypothetical. On August 3, 2026, FinCEN assessed a [record $125 million penalty against UBS](https://www.fincen.gov/news/news-releases/fincen-assesses-historic-125-million-penalty-against-ubs-financial-services-inc) for repeat, willful AML failures, after the firm left tens of thousands of foreign-currency wires under-monitored, [years after settling over the same weakness](https://www.americanbanker.com/news/fincen-fines-ubs-125m-for-money-laundering-recidivism). It's the latest in a decade where screening and monitoring gaps carried nine- and ten-figure price tags: [TD Bank paid about $3.09 billion in 2024](https://namescan.io/insights/the-5-largest-aml-penalties-in-2024/), the largest Bank Secrecy Act penalty on record; [Standard Chartered $1.1 billion in 2019](https://www.enzuzo.com/blog/biggest-aml-fines) for processing transactions tied to sanctioned countries; and [BNP Paribas nearly $9 billion in 2014](https://www.enzuzo.com/blog/biggest-aml-fines) for concealing sanctioned-party transactions. When a sanctioned name slips through under an unfamiliar spelling, that is the downside on the table.

## Why this is getting harder in 2026

Two forces are converging. First, regulation is centralizing: the EU's new [Anti-Money Laundering Authority (AMLA)](https://www.moodys.com/web/en/us/kyc/resources/insights/a-review-of-amla-and-amlr-2026.html) began operating from Frankfurt in July 2025, and a directly applicable "single rulebook" [takes effect across all 27 member states from July 2027](https://www.pwc.ie/services/audit-assurance/insights/eu-new-anti-money-laundering-authority.html), introducing perpetual KYC. A digital bank adding markets can no longer treat screening as a per-country afterthought.

Second, whole new regulated sectors are scaling into the same obligation. Legal sports betting has exploded across the US and Europe, and operators must run KYC, AML, and sanctions checks on millions of bettors across jurisdictions and languages, a duty European bodies like the [EGBA](https://www.egba.eu/) actively push on. More markets, more scripts, more names that don't match cleanly.

## What good looks like

The fix isn't a better black-box algorithm. It's getting the language layer right: multilingual KYC and onboarding, plus sanctions-ready name transliteration and matching, so core client processes and screening hold up consistently whatever market or script the name arrives in. Done well, it does two jobs at once: it keeps genuine sanctions exposure from hiding behind a spelling, and it cuts the false-positive load that buries review teams as you add markets.

Leading US and European financial institutions already lean on this capability to keep onboarding clean and reduce MLRO review load as they expand. The name on the shirt should be the same name your screening sees, in every language.

**Related reading:** [Buying Loyalty in a Second Language](https://www.transperfect.com/blog/buying-loyalty-in-a-second-language) and [NYCFC Names Viamericas Its Remittance Partner](https://www.transperfect.com/blog/nycfc-viamericas-remittance-partner) *(swap for live URLs)*, our ongoing look at where sports, multicultural finance, and language meet.

---

*TransPerfect helps banks, fintechs, and regulated operators deliver secure, compliant, multilingual KYC and onboarding at scale, including sanctions-ready transliteration and name matching. [Explore our finance and banking language solutions »](https://www.transperfect.com/industries/finance-and-banking)*

---

## Sources

- The problem of false positives in AML screening (90-95%+ false-positive rates; transliteration a key driver): [sanctions.io](https://www.sanctions.io/blog/the-problem-of-false-positives-in-aml-screening) · [Facctum, Sanctions Screening Statistics 2026](https://www.facctum.com/blog/sanctions-screening-statistics)
- FinCEN assesses historic $125M penalty against UBS Financial Services for recidivist BSA violations (Aug 3, 2026): [FinCEN](https://www.fincen.gov/news/news-releases/fincen-assesses-historic-125-million-penalty-against-ubs-financial-services-inc) · [American Banker](https://www.americanbanker.com/news/fincen-fines-ubs-125m-for-money-laundering-recidivism)
- Largest AML/sanctions fines (TD Bank ~$3.09B 2024; Standard Chartered $1.1B 2019; BNP Paribas ~$9B 2014): [NameScan](https://namescan.io/insights/the-5-largest-aml-penalties-in-2024/) · [Enzuzo](https://www.enzuzo.com/blog/biggest-aml-fines)
- EU Anti-Money Laundering Authority (AMLA) and single rulebook / perpetual KYC: [Moody's](https://www.moodys.com/web/en/us/kyc/resources/insights/a-review-of-amla-and-amlr-2026.html) · [PwC](https://www.pwc.ie/services/audit-assurance/insights/eu-new-anti-money-laundering-authority.html)
- European Gaming and Betting Association (AML in regulated betting): [EGBA](https://www.egba.eu/)
- Related TransPerfect posts: [Buying Loyalty in a Second Language](https://www.transperfect.com/blog/buying-loyalty-in-a-second-language) · [NYCFC x Viamericas](https://www.transperfect.com/blog/nycfc-viamericas-remittance-partner)
