# Cross-check against OpenTaxSolver 2025

Test build: synthetic cases only, not for real records. Every case is synthetic.

OpenTaxSolver (OTS) is an independent, open source tax program. Each prepared golden case in `tests/golden/2025` was run through it, and every line that both programs produce was compared.

## Result (2026-11-23, 29 prepared cases)

Every one of the 2,262 shared lines agrees within $1.01. Of those, 2,168 match exactly once the OTS amount is rounded to whole dollars. All 94 others come from one cause: OTS keeps cents on Schedule SE and Form 8995 lines, while caesar rounds every line to whole dollars as it goes. No line 16 tax, credit, refund or amount owed differs by more than $1.01.

The first run (2026-11-17) covered 8 cases and 542 lines. The tier eval cases added on 2026-11-23 bring it to 29: each new case was kept only after this cross-check, and each case's input.json says so in `untocaesar.notes`.

| Case | Lines compared | Exact | Within $5 | Largest gap |
| --- | --- | --- | --- | --- |
| business-under-400 | 83 (1040, C, SE, Schedule 1, 8995) | 83 | 83 | $0.23 |
| business-with-employees | 91 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 90 | 91 | $0.77 |
| cash-business-no-1099 | 91 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 91 | 91 | $0.29 |
| freelancer-owes | 91 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 79 | 91 | $0.63 |
| freelancer-schedule-c | 91 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 79 | 91 | $0.88 |
| hoh-blind-business-two-deps | 113 (1040, C, SE, Schedule 1, Schedule 2, 8995, 8812) | 112 | 113 | $0.63 |
| hoh-blind-two-dependents | 49 (1040, 8812) | 49 | 49 | $0.00 |
| hoh-business-one-child | 105 (1040, C, SE, Schedule 1, Schedule 2, 8995, 8812) | 105 | 105 | $0.46 |
| hoh-one-child | 49 (1040, 8812) | 49 | 49 | $0.00 |
| hostile-payer-name | 35 (1040) | 35 | 35 | $0.00 |
| mfj-business-two-kids | 107 (1040, C, SE, Schedule 1, Schedule 2, 8995, 8812) | 107 | 107 | $0.42 |
| mfj-many-forms | 107 (1040, C, SE, Schedule 1, Schedule 2, 8995, 8812) | 93 | 107 | $0.68 |
| mfj-one-business-each | 138 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 132 | 138 | $1.01 |
| mfj-seniors | 46 (1040, Schedule 1-A) | 46 | 46 | $0.00 |
| mfj-seniors-business | 102 (1040, C, SE, Schedule 1, Schedule 2, Schedule 1-A, 8995) | 95 | 102 | $0.90 |
| mfj-three-children-actc | 55 (1040, 8812) | 55 | 55 | $0.00 |
| mfj-two-children | 55 (1040, 8812) | 55 | 55 | $0.00 |
| mfj-two-w2-interest-dividends | 35 (1040) | 35 | 35 | $0.00 |
| mfs-one-w2 | 35 (1040) | 35 | 35 | $0.00 |
| nec-only-two-payers | 91 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 79 | 91 | $0.66 |
| qss-business-child | 108 (1040, C, SE, Schedule 1, Schedule 2, 8995, 8812) | 108 | 108 | $0.45 |
| senior-w2-and-business | 101 (1040, C, SE, Schedule 1, Schedule 2, Schedule 1-A, 8995) | 86 | 101 | $0.62 |
| single-many-forms | 93 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 87 | 93 | $0.70 |
| single-senior | 43 (1040, Schedule 1-A) | 43 | 43 | $0.00 |
| single-two-w2-owes | 34 (1040) | 34 | 34 | $0.00 |
| single-w2 | 35 (1040) | 35 | 35 | $0.00 |
| travel-meals-two-nec | 93 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 92 | 93 | $0.53 |
| w2-plus-nec-mileage | 93 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 93 | 93 | $0.47 |
| w2-plus-side-business | 93 (1040, C, SE, Schedule 1, Schedule 2, 8995) | 86 | 93 | $0.60 |
| Total | 2,262 | 2,168 | 2,262 | |

The refusal cases and the misread W-2 case stop before a return, so they have nothing to compare.

### A case moved off a Tax Table row edge

w2-plus-nec-mileage first had 1,200 business miles. caesar, rounding every amount, got taxable income of exactly $37,250, the first dollar of the $37,250 to $37,300 Tax Table row ($4,235). OTS, keeping cents on the deductible half of SE tax, got $37,249.86 and the row below ($4,229), so line 16 differed by $6. Both follow the 2025 Form 1040 instructions, which allow either rounding method as long as it is used for every amount, so neither side is wrong. A known answer should not depend on that choice, so the case now has 1,150 miles (taxable income $37,276 in both), and every line agrees.

## Where the differences come from

All of them trace back to Schedule SE, where caesar rounds and OTS keeps cents. The 2025 Form 1040 instructions allow either method under "Rounding Off to Whole Dollars" (https://www.irs.gov/pub/irs-prior/i1040gi--2025.pdf): "You can round off cents to whole dollars on your return and schedules. If you do round to whole dollars, you must round all amounts." caesar rounds every amount.

freelancer-schedule-c: Schedule C line 31 is $53,100 in both.
- **caesar:** line 4a is 53,100 × 92.35% = 49,037.85, rounded to 49,038. Line 10 is 6,081 and line 11 is 1,422, so line 12 is 7,503 and line 13 is 3,751.50, rounded to 3,752.
- **OTS:** keeps cents and gets 7,502.79 on line 12 and 3,751.40 on line 13.
- **Effect:** the 60 cent gap in the deductible half of SE tax carries into 1040 lines 10, 11a, 11b and 15, Schedule 1 lines 15 and 26, and Form 8995 lines 1, 2, 4, 11 and 13. The tax on line 16 is the same ($2,987), because both taxable incomes ($26,878 and $26,878.88) fall in the same Tax Table row.

w2-plus-side-business:
- **caesar:** SE tax is $1,483.
- **OTS:** SE tax is $1,483.60.
- **Effect:** the gap carries into Schedule 2 lines 4 and 21, 1040 lines 23, 24 and 37, and 1040 line 15 ($25,300 against $25,300.56). The tax on line 16 is the same ($2,562, the IRS Tax Table example in the 1040 instructions).

mfj-one-business-each: each spouse has one Schedule C, and each files a separate Schedule SE (2025 Instructions for Schedule SE, Joint Returns, page 2). Both programs compute a Schedule SE for each owner, and every line of both agrees.
- **caesar:** SE tax is $2,444 for the taxpayer and $1,483 for the spouse, $3,927 on Schedule 2 line 4.
- **OTS:** SE tax is $2,444.41 and $1,483.60, $3,928.01 on Schedule 2 line 4.
- **Effect:** the two rounding gaps add up to $1.01 on Schedule 2 lines 4 and 21 and 1040 lines 23, 24 and 37. The tax on line 16 is the same ($4,104).

The new business cases follow the same pattern, each under $1. No difference changes a tax, credit, refund or amount owed by more than $1.01, and none comes from a different rule.

## How it was run

- **Source:** OpenTaxSolver 2025 v23.07 for Linux (released 2026-09-25), from the extracted tree already recorded in the UntoCaesar study evidence. Nothing was downloaded again, and the shipped binaries were not run.
- **Build:** five solvers, built from source one at a time while the 1-minute load average was under 8: `nice -n 19 gcc -O1 -w -o taxsolve_X taxsolve_X.c` for US_1040_2025, US_1040_Sched_C_2025, US_1040_Sched_SE_2025, f8812_2025 and f8995_2025. Compiler: gcc 16.2.1. Binaries and run folders live outside the repo (`~/Projects/_work/flagship/opentaxsolver` on chapel1 for the first run, `~/Projects/_work/ots2025-work` on abbey1 for the 2026-11-23 run, built the same way with gcc 16).
- **Driver:** `tests/crosscheck/ots.py`.
  - It reads each case's facts through `tests/golden/to_facts.py` and fills the stock OTS templates from those facts, not from caesar's computed lines.
  - It runs Schedule C, then Schedule SE, once for each business owner, then the 1040, then Form 8995, then the 1040 again, then Schedule 8812, then the 1040 a last time.
  - Wherever one OTS form tells the user to carry a number to another, the driver carries the OTS number.
  - The 1040 program takes the QBI deduction and the child tax credit as typed inputs, so those come from OTS's own 8995 and 8812 programs.
- **Form 8995:** line 1 has one row per business owner, typed in with the same formula OTS's auto calculation uses (that owner's Schedule C line 31 less their Schedule SE line 13). With auto calculation on, the stock template's row iii name field, which holds a lone `;`, counts as a second business and doubles line 2.
- **Comparison:** a line counts as exact when the OTS amount, rounded half up to whole dollars, equals caesar's line. It counts as within $5 when the unrounded gap is $5 or less.

To repeat it:

```
python3 tests/crosscheck/ots.py --src <OpenTaxSolver2025_23.07_linux64 folder> --work ~/Projects/_work/flagship/opentaxsolver
```
