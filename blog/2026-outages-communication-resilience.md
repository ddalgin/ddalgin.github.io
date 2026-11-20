# Clarity Is the New Uptime

*A two-week cascade of outages, from a routine patch that took the NSA's classified network offline to grounded flights and wobbly payment systems, made one thing clear: going dark is a shared condition of modern infrastructure, not a mark against any one institution. For banks, that reframes what resilience has to mean.*

*Draft for the TransPerfect Financial Services blog · 2026-11-20*

---

The run of disruptions kept coming. Across about two weeks in November, a major cloud-productivity platform went down, a nationwide [FAA ground stop](https://abc7.com/live-updates/faa-ground-stop-live-updates-what-know-nationwide-flights-are-grounded/20038887/) halted flights after a new router overwhelmed an aging air-traffic system, a [United Airlines system](https://www.nbcnews.com/news/us-news/united-airlines-system-outage-rcna609712) stalled hundreds of departures, several large banks had [payments wobbles](https://www.newsweek.com/major-banks-down-america-everything-broken-microsoft-faa-outages-12723495), a ransomware crew made [unverified claims](https://www.techradar.com/pro/security/visa-confirms-apparent-cyberattack-hackers-also-claim-hit-on-jpmorgan) against big card and banking names, and, most tellingly, the [NSA's classified internal network went offline for days](https://www.cnn.com/2026/11/20/politics/nsa-highly-classified-network-outage-resolved). Almost none of it was an attack. The NSA outage, like most of the others, traced to something mundane: a [routine software patch](https://www.cbsnews.com/news/national-security-agency-network-outage-software-vulnerability/) that did not come back up cleanly.

If the agency that defines the state of the art in security can be knocked offline by its own maintenance, the lesson for everyone else is plain. In an economy this interconnected, going dark is not a sign of a weak or careless institution. It is a condition of modern infrastructure, and it arrives from every direction: your own code, a patch, a vendor three steps removed, an aging shared system, or, occasionally, an actual attacker. Most organizations, as this month showed, recover quickly. The useful question is not how to never have an incident. It is what an incident actually tests.

Here is the part that tends to get overlooked. When everything is working, an institution's product is its technology: the app, the rails, the instant transfer. When something breaks, all of that is, by definition, unavailable, and the only product the institution can still deliver is communication, telling people what is happening, what to do, and when it will be back. A disruption quietly flips the value proposition from engineering to language. And communication is hardest at the exact moment it matters most: volume spikes instantly, uncertainty runs high, and the audience is the entire customer base at once, which for any large institution today means many languages, not one.

## What it means for banks

Banks sit at the center of this in a way an airline or an intelligence agency does not, because money is the service customers panic about fastest. A grounded flight is frustrating; a card declined at the grocery store, or a transfer that stalls mid-payment, feels like an emergency. Three implications follow.

First, assume disruption and plan for the customer, not just the system. If the NSA and the FAA can go dark from routine maintenance, no bank should treat an outage as a tail risk. Recovery runbooks are table stakes. The gap is usually in the customer-facing plan: who says what, through which channels, and in which languages, within minutes rather than hours.

Second, the risk now lives largely outside your own walls. This month's disruptions ran through contractors, patches, and shared payment rails, and one card network pointed to a third-party supplier for its incident. Concentration and third-party dependency are no longer abstract worries, and regulators have noticed. US banking agencies already require notification within [36 hours](https://www.occ.gov/news-issuances/bulletins/2021/bulletin-2021-55.html) of a significant incident, a rule that also obliges service providers to warn the banks they serve. The UK's [new operational-incident and third-party reporting rules](https://www.bankofengland.co.uk/prudential-regulation/publication/2026/march/operational-incident-and-third-party-reporting-policy-statement), which firms must meet by March 2027 with reports due [within 24 hours, or four for payment providers](https://www.tlt.com/insights-and-events/insight/new-operational-incident-reporting-rules-for-banks-and-crr-firms-what-you-need-to-do-before-march-2027), cover supplier failures explicitly, and the EU's DORA framework points the same way.

Third, the yardstick is changing. Alongside faster clocks, including the SEC's [four-business-day](https://incidentcost.com/industries/financial-services) disclosure rule, operational resilience is increasingly judged by customer outcomes and harm, not only by how fast a system comes back. That is precisely where communication lives. The ability to tell customers what is happening, clearly and in the languages they actually use, is shifting from good practice toward expectation, and the timing matters: these failures tend to cluster around peak demand, exactly when a bank's call volume and its multilingual customer base are largest.

Everyone goes down. What a customer remembers afterward is rarely the length of the downtime. It is whether, in those few minutes, someone told them what was happening, clearly, and in a language they understood. As resilience matures, and as the rules around it harden, that may turn out to be the most human part of it.

---

*TransPerfect spends a lot of its time on that last mile of resilience: helping financial institutions keep communication clear and multilingual when it counts. [More on our finance and banking work »](https://www.transperfect.com/industries/finance-and-banking)*

---

## Sources

- The November 2026 outage cluster (Microsoft, FAA ground stop, banks): [Newsweek](https://www.newsweek.com/major-banks-down-america-everything-broken-microsoft-faa-outages-12723495) · [FAA ground stop, ABC7](https://abc7.com/live-updates/faa-ground-stop-live-updates-what-know-nationwide-flights-are-grounded/20038887/) · [United Airlines system outage, NBC News](https://www.nbcnews.com/news/us-news/united-airlines-system-outage-rcna609712)
- NSA classified network offline for days from a software patch, not a cyberattack: [CNN](https://www.cnn.com/2026/11/20/politics/nsa-highly-classified-network-outage-resolved) · [CBS News](https://www.cbsnews.com/news/national-security-agency-network-outage-software-vulnerability/)
- A major bank outage this month was traced to a software bug, not a cyberattack: [CNN](https://www.cnn.com/2026/11/16/business/bank-outage-chase-us-bank-bank-of-america)
- A card network confirmed a third-party supplier incident while a ransomware group made unverified claims against major card and banking names: [TechRadar](https://www.techradar.com/pro/security/visa-confirms-apparent-cyberattack-hackers-also-claim-hit-on-jpmorgan)
- US Computer-Security Incident Notification rule (36-hour notification; service providers must alert banks): [OCC Bulletin 2021-55](https://www.occ.gov/news-issuances/bulletins/2021/bulletin-2021-55.html)
- SEC four-business-day cybersecurity disclosure requirement: [IncidentCost](https://incidentcost.com/industries/financial-services)
- UK FCA/PRA/Bank of England operational-incident and third-party reporting rules (comply by March 2027; 24-hour, or 4-hour for payment providers): [Bank of England PS7/26](https://www.bankofengland.co.uk/prudential-regulation/publication/2026/march/operational-incident-and-third-party-reporting-policy-statement) · [TLT](https://www.tlt.com/insights-and-events/insight/new-operational-incident-reporting-rules-for-banks-and-crr-firms-what-you-need-to-do-before-march-2027)
