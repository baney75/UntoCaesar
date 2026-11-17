# UntoCaesar rival study

Prepared 2026-11-17 by the research subagent for the UntoCaesar lead. Status: prepared, with the TaxCalcBench numbers, the Direct File code facts and the open-source runs verified first-hand (see `evidence/hands-on.md`). Everything else comes from pages read on 2026-11-17 and is labeled.

Labels: **(S)** settled: primary or vendor source read, current. **(F)** in flux: changes during the season, older year, secondary or affiliate source, or conflicting sources. **(J)** judgment: my reading. **unknown**: not found. Bracketed numbers point to the Sources list.

## Verdict

The bar on math is high and the bar on transparency is low. Every commercial product guarantees its calculations, and FreeTaxUSA and Cash App Taxes already prepare and e-file a federal return with Schedule C for $0 [21][29], so UntoCaesar cannot win on price, form coverage or filing. Language models on their own are not close: the best TaxCalcBench TY2025 score is 86.00% of returns exactly right, and that needs web search; the best score without tools is 62.00%, and the open-weight families in the table score 0% to 6% [44]. That makes UntoCaesar's design (a deterministic engine does the math, the local model only reads documents and explains) a requirement, not a preference, and it sets the bar: the engine alone is 100% strict on every supported case in a TaxCalcBench-format suite, and with a model reading the documents the tier bars in docs/SPEC.md apply (tier M: 9 of 10 runs strict exact on every case, 0 silent errors). Where UntoCaesar can win outright: no rival found keeps the return on the device with no IRC 7216 disclosure at all, none cites IRS sources line by line, and only OpenTaxSolver and web apps run on Linux. IRS Direct File is suspended (no 2026 season, nothing announced for 2027) [31][32], so there is no government direct-file option, but its public-domain code is reusable: its 55 "knockout" facts are the right model for UntoCaesar's refusal gate, though its rules stop at tax year 2024 and never covered Schedule C or SE [35][70]. One scope gap for the lead to settle: the repo README says the first version is W-2 only, while this brief includes Schedule C and SE.

## Comparison table

Prices are for tax year 2025 returns (filed in 2026) unless marked. "C+SE" means a Form 1040 with Schedule C and Schedule SE.

| Rival | (a) Simple W-2 federal | (b) C+SE federal; state | Data location and consent | Shows work; cites IRS | Accuracy guarantee | Platforms | Measured accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TurboTax | $0 Free Edition, simple 1040 only, "Roughly 37%" qualify [1] (S) | Premium "$139" federal shown next to "Starting at $79" [2] (F); state amount not shown by vendor, affiliates say about $59 to $69 [18] (F) | Cloud; desktop needs an Intuit Account to activate [5]; return info not used "unless you consent", stored in US, AI providers are service providers [6] (S) | Intuit Assist help page makes no citation claim [7] (S); line view unknown | Penalties and interest from a calc error, seven years; audit help "informational only" [4] (S) | Windows 11, macOS 15+ desktop [5] (S); web [9] (S); mobile unknown | AI assistant wrong on "more than half" of questions, 2024 [12] (S) |
| H&R Block | $0 Free Online, "$0 to $130" range [14] (F) | Self-Employed about $115 to $130 federal, $37 to $49 state [15][17][18] (F) | Cloud; AI Tax Assist "powered by Microsoft Azure, OpenAI" and sessions recorded [16] (F) | unknown | Up to $10,000 penalties and interest from a math error [19] (F) | Windows 10+, macOS desktop; web, iOS, Android [20] (F) | AI assistant wrong on "30 percent" of questions, 2024 [12] (S) |
| FreeTaxUSA | $0 federal "for everyone" [21] (S) | $0 federal incl. Self-Employed; $15.99 per state [21] (S) | Cloud; "We never sell your tax return information" [21] (S); 7216 consent text unknown | unknown | "All calculations are guaranteed 100% accurate"; max refund guarantee [21] (S) | Web [21] (S); native mobile app unknown | unknown |
| TaxAct | $0 Free tier [22] (S) | Self-Employed $109.99 federal; $64.99 per state [23] (S) | Cloud; "governed by Section 7216"; express consent for third-party offers [24] (S); AI input goes to an unnamed provider [25] (S) | unknown | "$100k Accuracy Guarantee" [27] (S) | Windows 11 download; Mac online only; web [28] (S) | unknown |
| Cash App Taxes | $0 federal and state [29] (S) | $0 federal and state; self-employed allowed [29] (S) | Cloud; shares with Block, Inc. affiliates; asks consent before sharing with ad partners [30] (S) | unknown | "accurate calculations and max refund guarantees", "Exclusions apply" [29] (S) | Phone or computer; Cash App download required to log in [29] (S) | unknown |
| IRS Direct File | Not offered in 2026 season [32] (S); 2027 not announced [36] (F) | Never covered SE: Schedule 2 SE line hardcoded to $0 in code [35][70] (S) | Ran on IRS systems; suspended Oct 2025 [31] (S) | Code is a declarative fact graph, public domain [35] (S); citations unknown | unknown | Web, phone and desktop browsers [35] (S) | Satisfaction 90% (2024), 94% (2025) [31] (S); error rate unknown |
| IRS Free File Guided | $0 under AGI limit: $89,000 in 2026 season [38] (F); IRS page now says $95,000 [37] (F) | Partner-specific [37] (S); Schedule C coverage unknown | Cloud, at 8 private partners [38] (F) | unknown | unknown | Partner websites [37] (S) | unknown |
| Free File Fillable Forms | $0, any income [40] (S) | $0; Schedules C and SE available; no state [40] (S) | IRS-run online forms [40] (S) | "Limited calculations"; user fills forms [40] (S) | unknown | Web [40] (S) | unknown |
| OpenTaxSolver 2025 | $0, open source [41] (S) | $0; 1040, C, SE and 11 states, no e-file [41] (S) | Offline on the user's machine [70] (S) | Line by line `Lnn = amount`; no citations [70] (S) | unknown | Windows, Mac, Linux builds [41] (S) | Matched hand math on 2 synthetic cases [70] (S) |
| IRS Fact Graph | $0, public domain engine [42] (S) | Engine only; rules are Direct File's TY2024 set [35] (S) | Library; runs wherever embedded [42] (S) | Facts are declarative and inspectable [42] (S); citations unknown | IRS disclaims accuracy [42] (S) | JVM and JavaScript [42] (S) | unknown |
| PSL Tax-Calculator | $0, public domain [43] (S) | $0; computes SE tax and QBI [70] (S) | Offline Python [70] (S) | Variables, not 1040 lines [70] (S); citations unknown | unknown | Python on any OS [43] (S) | Off by $3.50 on 1040 line 16 because it skips the tax table [70] (S) |
| General chat models | unknown | unknown | Cloud provider; TurboTax inside ChatGPT shares data with Intuit [10] (S) | unknown | None; Anthropic policy requires qualified human review of tax advice [68] (S) | unknown | Average miss "more than $2,000" on 8 returns, 2026 [51] (S); TaxCalcBench below |
| TaxGPT | Not a consumer filer [60] (S) | unknown | Cloud, "SOC 2 Type II" [60] (S) | Claims answers "pull directly from the IRC" [60] (vendor claim) | unknown | unknown | unknown |
| FlyFin | unknown | unknown (prices only in app); Standard plan covers one Schedule C [61] (S) | Cloud; Plaid account linking [61] (S) | unknown | "A dedicated CPA reviews every deduction" [61] (vendor claim) | iPhone [62] (S) | unknown |
| Keeper | $199/yr Standard, federal plus up to 2 states [63] (S) | unknown | Cloud; privacy names no AI provider [64] (S) | unknown | "100% accuracy guaranteed"; signed by a tax pro [63] (vendor claim) | iOS, Android, web [63] (S) | unknown |
| April | unknown (B2B, no public prices) [65] (S) | unknown | Cloud, embedded in partner apps [65] (S) | unknown | Math-error penalties up to $10,000 [65] (S) | Partner apps [65] (S) | unknown |
| Column Tax | unknown (B2B, "Book a demo") [66] (S) | unknown | Cloud, embedded API [66] (S) | unknown | "maximum refund and accuracy guarantee" [66] (vendor claim) | Partner sites [66] (S) | Runs TaxCalcBench on models, not on its own engine [44] (S) |

## Per-rival notes

**TurboTax.** Free Edition excludes Schedule C, 1099-NEC, stock sales and rental property [8] (S). Self-Employed was retired for tax year 2023; Premium now carries Schedule C [3] (S). Paying from the refund adds "$40" [2][9] (S). Intuit's privacy statement allows training "our artificial intelligence models" in R&D and lists generative AI providers as service providers [6] (S). TurboTax runs inside ChatGPT (needs a ChatGPT subscription; data "will be shared with Intuit") [10] and inside Claude since April 2026 [11][74] (S). Gemini and Document AI auto-fill ten forms including Schedule C [69] (S). No 7216 consent screen wording was found (unknown). Intuit Assist refusals are not documented (unknown).

**H&R Block.** Every hrblock.com page returned 403 to our fetchers, so all H&R Block facts are search summaries or affiliate pages and are marked (F). AI Tax Assist "does not give legal or financial advice or prepare your return" [16] (F). Prices disagree across sources; treat the table as a range.

**FreeTaxUSA.** Already open for tax year 2026 returns [21] (S). Revenue comes from state returns and add-ons: Deluxe Support $7.99, Pro Support $44.99, Audit Defense $19.99, pay-from-refund $24.99 [21] (S). It is also an IRS Free File Guided partner [38] (F). This is the real price bar for a C+SE filer: $0 federal plus $15.99 state, e-filed.

**TaxAct.** Free tier excludes self-employment, investments, rentals and itemizing [22] (S). TaxAct Intelligence AI "never uses your personal data to train its models" [26], yet its terms send input to an unnamed "service provider" and tell users not to enter sensitive data [25] (S). Xpert Assist price conflicts ($45 vs $60) [22] (F).

**Cash App Taxes.** Free for federal and one state; vendor page lists no exclusions, secondary reviews say no multi-state or part-year returns (F). Not an IRS Free File partner [38] (F).

**IRS Direct File.** Suspended in October 2025 for "high costs, limited participation" [31] (S). The IRS told states it "will not be available in Filing Season 2026" and "no launch date has been set" [32][33] (S). I found no 2027 announcement as of 2026-11-17 (F). Usage: 141,000 returns in 2024, over 309,000 in 2025 [31] (S). P.L. 119-21 funds a $15 million report on public-private free filing [31] (S). Last season: 25 states; W-2, Social Security, unemployment, interest up to $1,500; EITC, CTC, CDCC, PTC [34] (S). The CC0 code (repo archived, last push 2026-06-11) holds 36 fact modules with 3,030 facts for tax year 2024 and 55 knockout facts that screen out unsupported cases [35][70] (S). A TIGTA 2025 report reportedly found error rates "similar to or lower than" other software [71] (F, PDF unreadable).

**IRS Free File.** "IRS Free File has closed. Please check back January 2027" [37] (S). Program agreement runs through October 2029 [39] (S). Fillable Forms: no state, no amended returns, "Limited calculations", 1040-SR not supported [40] (S).

**OpenTaxSolver.** v23.07 for tax year 2025, released 2026-09-25 [41] (S). Built from source here in 18 seconds with plain gcc and ran two synthetic returns correctly [70] (S). It does not compute EIC, the child tax credit or the QBI deduction inside the 1040 program; the user types those in, and carries numbers between the Schedule C, SE and 1040 programs [70] (S). Text input templates make it easy to drive from a converter. It is the cheapest independent oracle for our golden cases.

**IRS Fact Graph.** Engine repo, public domain, last commit 2026-09-01, Scala 3 on JVM and JS [42] (S). Not built here: needs a JDK and sbt, and this host has neither; installing them was out of bounds [70]. The README says "The IRS does not endorse, maintain, or guarantee the accuracy" [42] (S). Using it for tax year 2025 means writing new fact modules for the 2025 law changes (J).

**PSL Tax-Calculator.** Installed and ran in a scratch venv (taxcalc 6.8.5) [43][70] (S). Matches statutory math to the cent but uses the rate schedule instead of the tax table and does not round, so it passes TaxCalcBench lenient and fails strict on line 16 [70] (S). Good as a second oracle with a $5 tolerance.

**Other open-source tools.** Column Tax's TaxCalcBench is the only open eval found that scores full returns [44] (S). No other maintained open-source 1040 preparer was confirmed in this pass (unknown).

**General chat models.** NYT test, March 2026: eight TaxSlayer scenarios through Gemini, ChatGPT, Claude and Grok, every tool missed, average miss "more than $2,000" [51][52] (S, via reprints). Anthropic's usage policy treats advising an individual on their taxes as high risk and requires review by "a qualified person" [68] (S). OpenAI's policy text was blocked [73] (unknown).

**TaxGPT, FlyFin, Keeper, April, Column Tax, Taxfyle.** All cloud, none publishes an independent accuracy number, none states IRS line citations on returns (TaxGPT claims source-grounded research answers for professionals) [60][61][63][65][66][67]. FlyFin and Keeper sell human review as the accuracy story (vendor claims).

## Published accuracy evidence

**Return calculation (the task UntoCaesar does)**

- **TaxCalcBench, Column Tax** [44][45] (S, verified from repo commit b86f35f, 2026-11-15).
  - TY2024 set: 51 federal cases (W-2, Schedule C, capital gains, interest, dividends; CTC, EITC, CDCC). Paper era best strict: Gemini 2.5 Pro 32.35%, Claude Opus 4 27.45%. Current TY2024 best strict: GPT-5.4 Pro and GPT-5.4 62.75%.
  - TY2025 v2 (June 2026): 50 cases, 10 each for federal-only, CA, IL, NY, VA, inputs are realistic PDFs. Best strict: Claude Fable 5.2 with web search 86.00% (lenient 88.00%, by line 92.93%). Best by line: GPT-6.1 Sol with web search 94.79%. Best strict without tools: Claude Fable 5.2 62.00%. Claude Opus 5.5: 72.00% with web search, 42.00% without.
  - Open-weight families without tools, strict: Kimi K3 6.00%, DeepSeek V4.1 Flash 4.00%, GLM 5.3 0.00%, MiniMax M3.1 Flash 0.00%, Mistral Large 4 0.00% [44] (S for scores; J that these are the open-weight ones).
  - 149 web-search runs were scored wrong because the model searched for the test case itself [44] (S).
- **Case format** [44][70] (S). TY2024: one directory per case with `input.json` (Column Tax schema: `return_header`, `return_data` with `irs1040`, `irs1040_schedulec` list, `irs8995a_schedulec`, `ssa_1099` and so on) and `output.xml` in IRS MeF schema. TY2025: `input/` with PDFs plus `remaining_data.json`, and `output.xml`.
- **Scoring rule** [44] (S). The model writes `Line N: Description | Explanation | Amount`. The evaluator maps each scored line to an MeF XPath (for example Line 1a to `/Return/ReturnData/IRS1040/WagesAmt`) and compares amounts. 19 Form 1040 lines are scored (1a, 9, 10, 11, 12, 15, 16, 19, 24, 25d, 26, 27, 28, 29, 32, 33, 34, 35a, 37); TY2025 state lines: CA 14, IL 15, NY 18, VA 16. Metrics: strict (every line exact; "the only actual metric that matters"), lenient (every line within $5), by line, by line lenient, plus pass@1 and pass^k over repeated runs.
- **License** [44] (S). MIT, plus CANARY.txt: "EVALUATION ONLY. DO NOT USE FOR MODEL TRAINING." UntoCaesar may run it as an eval; it must not fine-tune on it.
- **SARA** (Holzenberger, Blair-Stanek, Van Durme, 2020) [46] (S): 376 cases on nine IRC sections, 100 numerical; a Prolog encoding solves 100%; BERT-era models sit near the 50% baseline on entailment. GPT-3 (text-davinci-003) beat the earlier best on SARA in 2023 [48] (S); the abstract gives no figure.
- **Jurayj, Holzenberger, Van Durme, arXiv 2508.21051 v3, Feb 2026** [47] (S): on the 100 SARA tax calculations, exact to the dollar: GPT-5 direct 76, DeepSeek-R1 direct 74, o3 parsed to logic 75 correct with 10 abstentions, GPT-4.1 direct 48; with gold statutes and few-shot, GPT-4.1 87.
- **arXiv 2509.13471** [59] (S, abstract): LLM-written tax software, worst-case pass rate 45% for GPT-4o-mini.

**Tax questions (not full returns)**

- **Washington Post, Geoffrey Fowler, 2024-03-04** [12][13] (S): TurboTax's assistant wrong on "more than half" of the questions; H&R Block's "incorrect answers to 30 percent". Question count unknown.
- **Vals TaxEval v2** [49] (F): 1,223 questions, top 80.38%, archived as saturated. **Vals Tax Agent Bench** (Nov 16, 2026) [50] (F): 193 research questions, top 52.30%. 2024 TaxEval: GPT-4 54.5% [72] (F).
- **Saturn "Artificial Authority"** [57] (F): 121 money questions, 17 models, average 43%, best 61%.
- **Surge DAYJOB: Tax** [58] (F): 50 professional assignments, top 10.8%.

**Humans and commercial software**

- **GAO-14-467T, 2014** [54] (S): 2 of 19 paid preparers computed the correct refund.
- **TIGTA on VITA, 2011** [55] (S via Accounting Today): 14 of 36 returns (39%) correct; the IRS's own review said 87%.
- **TIGTA on Taxpayer Assistance Centers, 2026** [56] (S via Accounting Today): 28 of 61 assisted visits (46%) got incorrect tax-law guidance.
- **Consumer Reports, 2019** [53] (S via NBC): TurboTax, H&R Block, TaxAct and TaxSlayer each had "at least one glitch". No newer Consumer Reports test, and no Consumer Reports test of AI assistants, was found (unknown).
- No independent accuracy rate for any commercial engine's calculations was found (unknown). Their guarantees are the only public signal.

## Where the bar is

**Measured numbers UntoCaesar must beat**

1. **Engine: 100% strict on its own supported cases, no model in the loop.** Commercial engines guarantee their math [4][21][27][29]; a cited, local tool that is ever wrong on arithmetic loses to all of them. TESTING.md already demands this.
2. **TaxCalcBench strict above 86.00%** on the TY2025 set [44], and, with a tier M local model reading the documents, the docs/SPEC.md tier M bar (9 of 10 runs strict exact) on every in-scope case, with a hard refusal on the rest. Where this study and docs/SPEC.md differ, the spec governs. The fair comparison is by case type: UntoCaesar answers only what SUPPORTED.md lists and a refusal counts as correct only when the case is out of scope.
3. **Beat the best no-tools model by a wide margin on document reading.** TY2025 TaxCalcBench feeds PDFs; the best no-tools strict score is 62.00% and the open-weight families score 0% to 6% [44]. If UntoCaesar's local model extracts the W-2 and 1099 fields exactly and the engine computes, it should land near 100% on in-scope cases. That gap is the headline claim to prove.
4. **Independent oracles agree.** OpenTaxSolver (exact, table-based) and Tax-Calculator (within $5) both reproduced the synthetic W-2 and C+SE cases [70]. UntoCaesar's golden cases should pass all three: expected values, OTS, and Tax-Calculator within $5.
5. **Answer quality on questions** must beat 30% to 50% wrong (WaPo 2024) [12] by citing the exact IRS line, publication or IRC section for every explanation, and saying "not supported" instead of guessing.

**Dimensions a local, cited, show-your-work tool can win**

- **Privacy.** Every commercial and AI rival is cloud; several send data to third-party AI providers [6][16][25][10]. UntoCaesar's return never leaves the device, so there is no 7216 disclosure to consent to (J).
- **Citations.** No rival found cites IRS sources line by line on the return (table column 5). OpenTaxSolver shows line math without citations [70].
- **Linux and offline.** Only OpenTaxSolver, Tax-Calculator and web apps run on Linux [41][43].
- **Honest refusal.** Direct File's knockout design [35] is the model; no commercial rival publishes its refusal rules.
- **Auditable evals.** No commercial rival publishes an accuracy number; UntoCaesar can publish its TaxCalcBench-format results per model and hardware.

**Dimensions it cannot win yet**

- **Price.** FreeTaxUSA ($0 federal including Schedule C, $15.99 state) and Cash App Taxes ($0 federal and state) already set the floor [21][29]. UntoCaesar can only match $0.
- **Filing.** Every rival except OpenTaxSolver, Tax-Calculator and the Fact Graph e-files; UntoCaesar phase 1 prints for the person to file.
- **Money-backed guarantees, audit support, human experts.** Rivals offer penalty reimbursement up to $10,000 or $100,000 [19][27] and CPA review [61][63]. An open-source project cannot (J).
- **Breadth.** States, investments, rentals, prior-year import and mobile apps are standard elsewhere.

**Recommended eval format.** Reuse TaxCalcBench's TY2024 layout for UntoCaesar's own golden cases (`input.json` plus MeF `output.xml`, the same 19 scored lines, strict and lenient, pass^k over repeated runs) so results are comparable to the public leaderboard, and add two columns TaxCalcBench lacks: a citation check per line and a refusal check for out-of-scope cases. Write new tax year 2025 cases; TaxCalcBench's TY2024 cases use old law and its canary bars training on them.

## Sources

All read 2026-11-17. "summary only" means a search engine summary was seen but the page itself was blocked or not fetched.

1. https://turbotax.intuit.com/personal-taxes/compare/ (read 2026-11-17)
2. https://turbotax.intuit.com/personal-taxes/online/premium/ (read 2026-11-17)
3. https://turbotax.intuit.com/discontinued-products/ (read 2026-11-17)
4. https://turbotax.intuit.com/Guarantees (read 2026-11-17)
5. https://turbotax.intuit.com/personal-taxes/cd-download/tta-system-requirements/ (read 2026-11-17)
6. https://www.intuit.com/privacy/statement/ (read 2026-11-17)
7. https://ttlc.intuit.com/turbotax-support/en-us/help-article/data-privacy/intuit-assist/L8AA2pNTy_US_en_US (read 2026-11-17)
8. https://turbotax.intuit.com/personal-taxes/online/free-edition/ (read 2026-11-17)
9. https://turbotax.intuit.com/personal-taxes/online/ (read 2026-11-17; copy at evidence/turbotax-online-2026-11-17.md)
10. https://ttlc.intuit.com/turbotax-support/en-us/help-article/tax-return/access-turbotax-tools-chatgpt (read 2026-11-17)
11. https://investors.intuit.com/news-events/press-releases/detail/1305/intuit-and-anthropic-partner-to-bring-trusted-financial-intelligence-and-custom-ai-agents-to-consumers-and-businesses (read 2026-11-17)
12. https://ca.news.yahoo.com/turbotax-adds-ai-gives-horribly-171059895.html (Washington Post syndication; read 2026-11-17)
13. https://www.accountingtoday.com/news/intuit-h-r-block-tax-ais-critiqued-on-accuracy-of-answers-many-inaccurate (read 2026-11-17)
14. https://www.forbes.com/advisor/taxes/hr-block-review/ (summary only, 2026-11-17)
15. https://nerdwallet.com/blog/taxes/hr-block-vs-turbotax (summary only, 2026-11-17)
16. https://www.hrblock.com/tax-center/filing/filing-online/ai-tax-assist/ (summary only, 2026-11-17)
17. https://usesolvent.com/blog/turbotax-vs-hr-block/ (summary only, affiliate, 2026-11-17)
18. https://wealthvieu.com/taxes/tax-filing/turbotax-vs-hr-block/ (summary only, affiliate, 2026-11-17)
19. https://www.hrblock.com/tax-center/support/online/prepare-to-file-taxes-online/accuracy-guarantee/ (summary only, 2026-11-17)
20. https://www.hrblock.com/tax-center/support/software/technical-issues-software/software-system-requirements/ (summary only, 2026-11-17)
21. https://www.freetaxusa.com/ (read 2026-11-17)
22. https://www.taxact.com/ (read 2026-11-17)
23. https://www.taxact.com/taxes-online/file-your-own-taxes/self-employed-tax-filing (read 2026-11-17)
24. https://www.taxact.com/privacy-policy (read 2026-11-17)
25. https://www.taxact.com/terms-of-service/smartfile-ai (read 2026-11-17)
26. https://www.taxact.com/whats-new (read 2026-11-17)
27. https://support.taxact.com/support/334/taxact-product-guarantees (read 2026-11-17)
28. https://www.taxact.com/system-requirements (read 2026-11-17)
29. https://cash.app/taxes (read 2026-11-17)
30. https://taxes.cash.app/pages/privacy-policy (read 2026-11-17)
31. https://www.everycrsreport.com/files/2026-09-17_IF13314_7a5be865820f33882647d91cc0cadc376e538af6.html (CRS IF13314; read 2026-11-17)
32. https://federalnewsnetwork.com/it-modernization/2025/11/irs-direct-file-will-not-be-available-in-2026-agency-tells-states/ (read 2026-11-17)
33. https://www.route-fifty.com/digital-government/2025/11/direct-file-wont-happen-2026-irs-tells-states/409322/ (read 2026-11-17)
34. https://www.irs.gov/newsroom/irs-dont-overlook-free-options-for-preparing-and-filing-taxes-in-2025-direct-file-available-in-25-states (read 2026-11-17)
35. https://github.com/IRS-Public/direct-file (cloned at e365f9f, read 2026-11-17)
36. https://grantsights.com/blog/free-tax-help-vita-tce (summary only, 2026-11-17)
37. https://www.irs.gov/irs-free-file-do-your-taxes-for-free (read 2026-11-17)
38. https://dontmesswithtaxes.com/?p=12713 (read 2026-11-17)
39. https://www.irs.gov/newsroom/irs-announces-extension-of-free-file-program-through-2029 (read 2026-11-17)
40. https://www.irs.gov/e-file-providers/free-file-fillable-forms-program-limitations-and-available-forms (read 2026-11-17)
41. https://sourceforge.net/projects/opentaxsolver/ (v23.07 package and 0_README.txt; read 2026-11-17)
42. https://github.com/IRS-Public/fact-graph (cloned at 5599f75, read 2026-11-17)
43. https://github.com/PSLmodels/Tax-Calculator (cloned at 98fa309) and PyPI taxcalc 6.8.5 (read 2026-11-17)
44. https://github.com/column-tax/tax-calc-bench (cloned at b86f35f, read 2026-11-17)
45. https://arxiv.org/abs/2507.16126 (read 2026-11-17)
46. https://ar5iv.labs.arxiv.org/html/2005.05257 (read 2026-11-17)
47. https://arxiv.org/html/2508.21051v3 (read 2026-11-17)
48. https://arxiv.org/abs/2302.06100 (read 2026-11-17)
49. https://www.vals.ai/benchmarks/tax_eval_v2-03-13-2025 (read 2026-11-17)
50. https://vals.ai/benchmarks/tax_agent_bench (read 2026-11-17)
51. https://thenightly.com.au/from/the-new-york-times/the-new-york-times-a-word-to-the-wise-dont-trust-artificial-intelligence-to-file-your-taxes-c-21923105 (NYT reprint; read 2026-11-17)
52. https://www.thestar.com.my/tech/tech-news/2026/03/14/a-word-to-the-wise-dont-trust-ai-to-file-your-taxes (NYT reprint; read 2026-11-17)
53. https://www.nbcnews.com/better/amp/ncna986406 (read 2026-11-17)
54. https://www.gao.gov/products/gao-14-467t (read 2026-11-17)
55. https://www.accountingtoday.com/news/accuracy-rates-declining-at-volunteer-tax-prep-sites (read 2026-11-17)
56. https://www.accountingtoday.com/news/irs-taxpayer-assistance-centers-provided-wrong-answers-to-tax-questions (read 2026-11-17)
57. https://www.investmentnews.com/fintech/ai-chatbots-give-wrong-financial-answers-most-of-the-time-study-finds/268267 (read 2026-11-17)
58. https://zeli.app/story/50275626 (read 2026-11-17)
59. https://arxiv.org/abs/2509.13471 (read 2026-11-17)
60. https://taxgpt.com and https://taxgpt.com/pricing (read 2026-11-17)
61. https://flyfin.tax/ and https://flyfin.tax/fair-usage-policy (read 2026-11-17)
62. https://apps.apple.com/us/app/-/id1560766719 (read 2026-11-17)
63. https://www.keepertax.com and https://www.keepertax.com/pricing (read 2026-11-17)
64. https://www.keepertax.com/privacy (read 2026-11-17)
65. https://www.getapril.com (read 2026-11-17)
66. https://www.columntax.com (read 2026-11-17)
67. https://www.taxfyle.com (read 2026-11-17)
68. https://www.anthropic.com/legal/aup (read 2026-11-17)
69. https://www.googlecloudpresscorner.com/2025-04-09-Intuit-Further-Simplifies-Tax-Prep-for-Millions-of-TurboTax-Customers-this-Tax-Season-with-Google-Cloud-AI (read 2026-11-17)
70. evidence/hands-on.md, this study's own builds and runs on chapel1 (2026-11-17)
71. https://www.tigta.gov/sites/default/files/reports/2025-08/2025408015fr.pdf (summary only, PDF unreadable, 2026-11-17)
72. https://www.deeplearning.ai/the-batch/vals-ai-evaluates-large-language-models-on-industry-specific-tasks (read 2026-11-17)
73. https://openai.com/policies/usage-policies/ (403, summary only, 2026-11-17)
74. https://blog.turbotax.intuit.com/tax-help/turbotax-on-claude-chatgpt-for-ai-tax-help-144205/ (read 2026-11-17)
