# Hands-on log, 2026-11-17, host chapel1 (Linux, 8 cores, shared)

All inputs below are synthetic. No real person's data was used. No account was created, nothing was bought, no local LLM was run.

## Load
- 13:15 load 13.30 (over 8): held builds.
- 13:21 load 6.11, 13:23 6.12, 13:24 5.89: ran the light builds below under `nice -n 19`.
- 13:31 load 26.37 from other jobs: stopped all compute.

## Repos cloned (shallow, read only, under evidence/repos)
| Repo | Commit | Commit date | License |
| --- | --- | --- | --- |
| column-tax/tax-calc-bench | b86f35f5fab6 | 2026-11-15 | MIT, plus CANARY.txt: "EVALUATION ONLY. DO NOT USE FOR MODEL TRAINING." |
| IRS-Public/fact-graph | 5599f75ba304 | 2026-09-01 | Public domain in US, CC0 worldwide (LICENSE.md) |
| IRS-Public/direct-file | e365f9f43446 | 2026-06-11 | Public domain in US, CC0 worldwide; README says "archived and is no longer maintained" |
| PSLmodels/Tax-Calculator | 98fa3098de5d | 2026-11-14 | Public domain in US |

## OpenTaxSolver 2025 v23.07 (released 2026-09-25 per 0_README.txt; SourceForge RSS pubDate Sun, 27 Sep 2026)
- Download: https://sourceforge.net/projects/opentaxsolver/files/OTS_2025/v23.07_linux/OpenTaxSolver2025_23.07_linux64.tgz/download, sha256 69b9f6a4ff55f60a70b76233f00459c602ae7abc22854277a344159a2a8eaeea, 20,187,023 bytes. Tarball deleted after extraction; extracted tree kept in evidence/ots-download/x.
- Shipped binaries were NOT run. Built only three CLI solvers from source: `nice -n 19 gcc -O1 -w -o taxsolve_X taxsolve_X.c` for US_1040_2025 (8.1 s), US_1040_Sched_C_2025 (4.7 s), US_1040_Sched_SE_2025 (5.5 s). No warnings shown (-w), no errors, no extra libraries.
- Input format: one plain-text template per form (`Field value ;` lines with `{ comments }`), program writes `<name>_out.txt` with `Lnn = amount` lines.
- Case A, single, W-2 box 1 $50,000, withholding $5,000 (files hands-on/ots/w2.txt, w2_out.txt):
  L1a 50000, L9 50000, L12 15750, L15 34250, L16 3875 (tax table midpoint), L24 3875, L25d 5000, L34 1125, L35a 1125. Matches hand calculation from TY2025 standard deduction $15,750 and the tax table row 34,250 to 34,300.
- Case B, Schedule C gross receipts $40,000, advertising $10,000 (c.txt, c_out.txt): L7 40000, L28 10000, L31 30000.
- Case B Schedule SE, L2 30000 (se.txt, se_out.txt): L4a 27705, L10 3435.42, L11 803.45, L12 4238.86, L13 2119.43. Wage base constant in source: 176100 for 2025.
- Limits found in the templates and source: EIC (1040 L27), child tax credit (L19) and QBI deduction (L13a) are typed in by the user, not computed by the 1040 program (`GetLine( "L27", &L[27] )`; separate f8812 and f8995 programs exist). Schedule C, SE and 1040 are separate programs; the user carries numbers across ("Also enter this number on Schedule-2, line 4"). SE lines keep cents.
- To run UntoCaesar golden cases through OTS: write a converter from our case JSON to the OTS text templates (1040, C, SE, 8812, 8995), run the three to five programs in order, parse `Lnn =` lines, compare by line. About a day of work; build cost is seconds.

## Tax-Calculator 6.8.5 (PyPI taxcalc)
- `uv venv -p 3.12` in scratchpad, `uv pip install taxcalc`: 71 s wall, mostly download; imports fine.
- Script: hands-on/taxcalc/run.py. Output: hands-on/taxcalc/output.txt.
- Case A: AGI 50000, standard 15750, taxable 34250, taxbc 3871.50 (rate schedule, not the tax table; the 1040 line 16 answer is 3875), payrolltax 7650 (FICA employee plus employer is how it models it).
- Case B (e00900 = 30000): AGI 27880.57, QBI deduction 2426.11, taxable 9704.45, income tax 970.45 (table answer for taxable 9,700 to 9,750 is 973), SE tax 4238.865.
- Verdict: runs, matches statutory math to the cent, but does not use the tax table and does not round, so it would fail TaxCalcBench strict on line 16 and pass lenient (within $5). It is a microsimulation model with variable names like e00200, not 1040 lines. Useful as an independent oracle with a $5 tolerance, not as the line-exact reference.

## IRS Fact Graph (IRS-Public/fact-graph)
- Not built: needs a JDK, Scala 3 and sbt 1.11.4 (ONBOARDING.md, project/build.properties). This host has no java, sbt or scala, and the standing rules bar running installers. node is present, but the JS build is produced by sbt fastOptJS.
- Repo is the engine plus a demo (demo/all-facts.xml, 3,045 `<Fact ` entries) and docs/fact-dictionary-specification-3.1.md.
- To run our cases: install a JDK and sbt (coursier), `sbt compile fastOptJS publishLocal`, load a fact dictionary, set input facts per case, read derived facts. The tax rules themselves live in the Direct File repo (TY2024 only).

## IRS Direct File (IRS-Public/direct-file)
- Fact dictionary: 36 XML modules in direct-file/backend/src/main/resources/tax, 3,030 `<Fact ` entries, tax law "as of Tax Year 2024" (README).
- No Schedule C or SE: `/line21OfSchedule2` ("Other taxes, including self-employment") is `<Derived><Dollar>0</Dollar></Derived>` in taxCalculations.xml; Schedule 1 SE lines are comments only.
- 55 distinct `/flowKnockout...` facts: the screener that stops unsupported situations (for example /flowKnockoutUnsupportedState, /flowKnockoutHouseholdEmployee, /flowKnockoutHasForeignTaxPaid). This is the pattern UntoCaesar's refusal gate should copy.
- 27 saved fact-graph test files in docs/testing/fact-graphs.

## TaxCalcBench (column-tax/tax-calc-bench)
- TY24: 51 cases, each `input.json` (Column Tax input schema: return_header, return_data with irs1040, irs1040_schedulec list, irs8995a_schedulec, ssa_1099, etc.) plus `output.xml` (MeF XML). 13 case names include Schedule C.
- TY25 v2 (June 2026): 50 cases, 10 each for us, ca, il, ny, va. Each `input/` holds realistic PDFs (W-2, 1098, 1099-B, prior-year 1040) plus remaining_data.json; expected `output.xml`.
- Scored lines: TY24 19 Form 1040 lines (tax_return_evaluator.py LINES_TO_XPATH_VALUES); TY25 us 19, ca 14, il 15, ny 18, va 16 (ty25_scoring.py).
- Model output format: `Line N: Description | Explanation | Amount`, parsed and compared to XPath values.
- Metrics: strict (every line exact), lenient (every line within $5), by line, by line lenient; pass@1 and pass^k when repeated.
- Running it needs provider API keys; `--quick-eval` rescores saved outputs with no API calls. Not run here (no keys, no paid API use).
