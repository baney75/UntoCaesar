# Cross-check against OpenTaxSolver 2025

Test build: synthetic cases only, not for real records. Every case is synthetic.

OpenTaxSolver (OTS) is an independent, open source tax program. Each prepared golden case in `tests/golden/2025` was run through it, and every line that both programs produce was compared.

## Result (2026-11-17, mfj-one-business-each added 2026-11-22)

Every one of the 542 shared lines agrees within $1.01. Of those, 517 match exactly once the OTS amount is rounded to whole dollars. All 25 others come from one cause: OTS keeps cents on Schedule SE and Form 8995 lines, while caesar rounds every line to whole dollars as it goes.

| Case | Lines compared | Exact | Within $5 | Largest gap |
| --- | --- | --- | --- | --- |
| single-w2 | 35 (1040) | 35 | 35 | $0.00 |
| hostile-payer-name | 35 (1040) | 35 | 35 | $0.00 |
| mfj-two-children | 55 (1040, 8812) | 55 | 55 | $0.00 |
| hoh-blind-two-dependents | 49 (1040, 8812) | 49 | 49 | $0.00 |
| mfj-seniors | 46 (1040, Schedule 1-A) | 46 | 46 | $0.00 |
| freelancer-schedule-c | 91 (1040, C, SE, Schedules 1 and 2, 8995) | 79 | 91 | $0.88 |
| w2-plus-side-business | 93 (1040, C, SE, Schedules 1 and 2, 8995) | 86 | 93 | $0.60 |
| mfj-one-business-each | 138 (1040, two C, two SE, Schedules 1 and 2, 8995) | 132 | 138 | $1.01 |
| Total | 542 | 517 | 542 | |

The refusal cases and the misread W-2 case stop before a return, so they have nothing to compare.

## The 25 differences

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

No difference changes a tax, credit, refund or amount owed by more than $1.01, and none comes from a different rule.

## How it was run

- **Source:** OpenTaxSolver 2025 v23.07 for Linux (released 2026-09-25), from the extracted tree already recorded in the UntoCaesar study evidence. Nothing was downloaded again, and the shipped binaries were not run.
- **Build:** five solvers, built from source one at a time while the 1-minute load average was under 8: `nice -n 19 gcc -O1 -w -o taxsolve_X taxsolve_X.c` for US_1040_2025, US_1040_Sched_C_2025, US_1040_Sched_SE_2025, f8812_2025 and f8995_2025. Compiler: gcc 16.2.1. Binaries and run folders live outside the repo in `~/Projects/_work/flagship/opentaxsolver`.
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
