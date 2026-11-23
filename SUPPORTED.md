# What Unto Caesar supports

This file is the honest list of what Unto Caesar can and cannot do today. Only a situation with a passing test suite in `tests/golden/` may be listed as supported.

Test build: synthetic cases only, not for real records. Every case below is synthetic. No real person's tax or financial data is used anywhere.

## Supported (tax year 2025, caesar v0)

Each row names the golden case whose every computed line passes `uv run --group dev pytest -q`.

| Situation | Golden case |
| --- | --- |
| Single filer, one W-2, standard deduction, Tax Table | `tests/golden/2025/single-w2` |
| Married filing jointly, two W-2s, two qualifying children, child tax credit and additional child tax credit (Schedule 8812) | `tests/golden/2025/mfj-two-children` |
| Head of household, blind filer, a qualifying child and an other dependent, credit for other dependents | `tests/golden/2025/hoh-blind-two-dependents` |
| Single freelancer with Form 1099-NEC, Schedule C, Schedule SE, Form 8995 qualified business income deduction, estimated payments | `tests/golden/2025/freelancer-schedule-c` |
| Married filing jointly, W-2 wages plus a spouse's side business on Schedule C and SE | `tests/golden/2025/w2-plus-side-business` |
| Married filing jointly, one Schedule C for each spouse, a Schedule SE for each spouse, Form 8995 with one row per owner | `tests/golden/2025/mfj-one-business-each` |
| Married filing jointly, both 65 or older, Schedule 1-A senior deduction, Tax Computation Worksheet | `tests/golden/2025/mfj-seniors` |
| A payer name with HTML in it renders inert on worksheet.html | `tests/golden/2025/hostile-payer-name` |
| A misread W-2 box 1 that the person rejects at confirm ends in a failing check | `tests/golden/2025/misread-w2-box1` |

Only the person confirms a fact: caesar-mcp's confirm asks through Local Studio's question card, checks that the socket's peer is the installed Local Studio app, and keeps each answer in a ledger signed with a key in the OS keychain. These cases pass:

| Situation | Test |
| --- | --- |
| caesar-mcp started by an outside assistant refuses a job made in Local Studio | `tests/test_mcp.py::test_golden_outside_server_refuses_a_local_studio_job` |
| A job made with an outside assistant and confirmed in Local Studio reaches prepared | `tests/test_mcp.py::test_golden_outside_job_confirmed_in_local_studio_reaches_prepared` |
| A model that edits facts.toml to set a confirmed flag ends computed, not confirmed | `tests/test_confirm.py::test_golden_model_edits_facts_toml_to_set_a_flag` |
| A model that starts its own question socket and calls confirm ends computed, not confirmed (macOS and Linux) | `tests/test_confirm.py::test_golden_model_starts_its_own_listener_and_calls_confirm` |

A confirm round trip through a real Local Studio question card has not been run yet. On Windows, Local Studio has no question socket, so nothing is confirmed there.

caesar also stops, with a plain message and a citation, for each of these golden refusal cases: Form SSA-1099, Form 1099-R, Form 1099-G, taxable interest over the Schedule B threshold, qualified dividends, a W-2 filer with one child who may qualify for the earned income credit, a W-2 filer whose child may qualify them for the earned income credit without being their dependent, and a joint return whose W-2 shows Additional Medicare Tax withheld (two W-2s from one employer) though the wages are under every Form 8959 threshold.

## Not supported yet

Everything else. caesar knows only the facts in the year's v0 schema, rejects any other fact, and refuses any income, document, adjustment, credit or tax with no rule. The full refusal list is in `docs/SPEC.md` under "Refusals for v0". Items move up only when their tests pass.
