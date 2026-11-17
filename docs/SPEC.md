# UntoCaesar v0 spec: a Local Studio plugin

Status: prepared 2026-11-17 by the flagship plugins lead. Nothing here is built yet. The bars below were written before any eval ran, and they do not move to fit a result.

This spec replaces the desktop app plan in the README for v0. UntoCaesar ships first as a skill-type plugin for Local Studio, installed from its catalog (Donovan, 2026-11-16). The rival study that sets the outside bar lives in [docs/rivals/STUDY.md](rivals/STUDY.md).

## Who it is for

1. A person filing their own federal return who wants to understand every number and keep their records on their own machine.
2. A freelancer or one-person business filing Schedule C and Schedule SE with that return.
3. A volunteer helping someone else (a VITA-style site, a parish, a family member), who needs the work shown line by line so they can check it.

Not for v0: businesses that file their own entity returns (1120, 1120-S, 1065), state returns, amended returns, and anything on the refusal list below.

## The promise

- Every figure stays on the device. The plugin runs only with a local model (`local_only`, below), and its code opens no network connection.
- The model never does tax math. The `caesar` CLI does all arithmetic from a facts file, and every line it writes cites the form line, the instruction page or the publication section it came from, for the stated tax year.
- It shows its work: each line of the return has its inputs, the rule, the citation and the result, in a worksheet the person can read on any screen.
- It never files, signs, sends or pays anything. It stops at a prepared return and tells the person how to review and file it themselves.
- When a situation is outside what it supports, it says so and stops. It never guesses.

## One-minute setup

1. In Local Studio, open Plugins, pick UntoCaesar from the catalog, press Install. No capability prompt appears, because v0 asks for none (below).
2. Local Studio checks that the current session uses a local model through Fonsviva. If not, it offers the local models that passed UntoCaesar's tier evals on this hardware and switches to one.
3. Type `/taxes`. The skill runs `caesar status`, which prints the first question and a `NEXT:` line.

The test for this: a person who has never seen the app goes from the catalog to the first interview question in under 60 seconds on a machine that already has Local Studio and Fonsviva, timed on the recorded run.

## How it works

The plugin follows Gantrel's pattern, so the family behaves the same way:

- `plugin.toml`: id `untocaesar`, commands `/taxes` (prepare a return) and `/taxes-explain` (explain a line or a notice), both pointing at skills.
- `skills/plugin/untocaesar/SKILL.md` with tier cards `tiers/S.md`, `tiers/M.md`, `tiers/L.md`, like smoothstone.
- `caesar`, a Python 3.11+ CLI using only the standard library, shipped in the plugin. Like `stone`, every message ends with one `NEXT: <command>` line and `caesar status` repeats it, so a small model that loses its context picks up where it was. State lives in a job folder on disk.

The job folder holds:

- `facts.toml`: every fact about the person's year (filing status, dependents, each W-2 box, each 1099 box, each Schedule C income and expense line), each with where it came from (a document and box, or the person's answer) and whether the person confirmed it.
- `documents/`: the person's own files, never copied anywhere else.
- `return.json`: the computed return, line by line, with citations.
- `worksheet.html`: the readable show-your-work page, one row per line: inputs, rule, citation, result.

The model's job is the interview and document reading: ask plain questions, read W-2s and 1099s, write facts with `caesar set`, and explain results in plain words. `caesar compute` does the math. `caesar check` runs consistency checks (W-2 withholding against wages, 1099-NEC totals against Schedule C gross receipts, missing confirmations) and lists every unconfirmed fact. A return is marked prepared only when every fact is confirmed by the person and every check passes.

### Tax years

A tax year is supported only when its golden suite passes. Tax year 2025 comes first, because its forms, instructions and publications are final, which makes known answers checkable. Tax year 2026 is added when the IRS publishes final 2026 forms and instructions (expected December 2026 to January 2027), in time for the Feb 1, 2027 dev release. Each year's rules live in one data file per year with a citation on every number.

### Scope for v0

Form 1040 with: wages (W-2), interest and ordinary dividends (1099-INT, 1099-DIV) under the Schedule B threshold, nonemployee compensation (1099-NEC) and other self-employment income on Schedule C, Schedule SE, the qualified business income deduction on Form 8995 (the simplified form only), the standard deduction, the child tax credit and credit for other dependents (Schedule 8812), and estimated payments already made.

### Refusal list for v0

`caesar check` detects these from the facts and stops with a plain message: itemized deductions, capital gains or losses, rental income, K-1s, foreign income or accounts, the earned income credit, education credits, premium tax credit (1095-A), household employees, inventory or cost of goods sold, home office, vehicle actual expenses, depreciation, net operating losses, alternative minimum tax, and any state return. Each item moves off this list only when its golden cases pass.

## Capabilities it asks for

None in v0. The skill runs `caesar` through the session's bash tool, the same way Gantrel runs `stone`.

What the plugin API lacks, filed as an issue on baney75/local-studio:

1. `local_only`: a manifest flag that makes the core refuse to run the plugin's commands in a session whose provider is not local (Fonsviva or the local fleet), and turns off web tools in that session. Without it, the skill can only ask, which is not enough for tax records.
2. A way for the plugin to know the session's tier (S, M or L), so the right tier card loads without the person setting `CAESAR_TIER`.

Until `local_only` lands, `caesar` refuses to start unless `CAESAR_LOCAL_ONLY_ACK=1` is set by the skill after it has checked the provider name, and the plugin is labeled dev only. Tier L means the largest local models, never a cloud model: a person's tax figures never reach a cloud provider at any tier. Frontier cloud models appear only as rivals in the win check below, on synthetic cases.

## What runs locally

Everything: the model through Fonsviva, the CLI, the job folder. Nothing in the plugin imports a network library; a CI check fails the build if any module under `caesar/` imports `socket`, `urllib`, `http`, `ssl` or a third-party networking package.

## Evals

Each eval case is a synthetic person: no real person's tax or financial data is ever used. A case has the person's documents (W-2, 1099 and receipt files made for the case), a scripted set of answers the simulated person gives, and the known-correct return, line by line.

Known answers come from three places, in order of trust: (1) IRS training material with published answers (the VITA/TCE comprehensive problems in Publication 4491 and its workbook, for the tax year), (2) public benchmark cases with their published answers where the license allows, such as TaxCalcBench, (3) our own cases, each computed by `caesar` and by an independent engine (OpenTaxSolver, or the IRS Fact Graph) and kept only when both agree and a reviewer checked the citations.

### Engine eval (no model)

`caesar compute` on every golden facts file. Bar: 100% of lines exact, every case. This runs in CI on every pull request.

### Tier evals (model in the loop)

The model runs `/taxes` against the simulated person, reads the documents and writes the facts; `caesar` computes. Each case runs 10 times per model.

| Measure | S (about 3B and under) | M (about 4B to 30B) | L (the largest local models, over 30B) |
| --- | --- | --- | --- |
| Cases in the suite | W-2 only (12 cases) | W-2 plus Schedule C and SE (24 cases) | all v0 cases (30) |
| Runs that end with the exact correct return | 8 of 10 per case | 9 of 10 per case | 10 of 10 per case |
| Silent errors: a wrong return marked prepared with no failing check | 0 | 0 | 0 |
| Out-of-scope cases stopped with the right refusal | 10 of 10 | 10 of 10 | 10 of 10 |
| Network connections opened (traced) | 0 | 0 | 0 |
| Explanation of three named lines judged correct and cited by a blind judge | not scored | 8 of 10 | 9 of 10 |

A run that does not reach the exact return still passes the silent error bar if `caesar check` flagged the problem. That is the point: wrong is allowed to happen during a run, but never quietly.

These evals go in the catalog entry for each tier, with the model, hardware, date and log hash, like Gantrel's.

## The check that says it wins

Run on the same 30 cases, same documents, same simulated answers:

1. UntoCaesar on a tier M local model against the same local model with no plugin, and against a frontier chat model with no plugin given the same documents. UntoCaesar wins if its exact-return rate is higher than both and its silent error count is 0.
2. UntoCaesar's engine against OpenTaxSolver on the cases both support: they must agree on every line, or the disagreement is traced to a cited rule and the wrong side fixed.
3. Against TurboTax, H&R Block, FreeTaxUSA and the IRS options, which cannot be run here without accounts: the study compares price, privacy, platforms, citations and published accuracy tests, and says plainly where UntoCaesar does not win (state returns, e-file, the forms it refuses).

A blind council scores the final dev build on three worked cases: correctness, how clearly the work is shown, and how well it explains.

## Channels

Stable, nightly and dev, on the family scheme in local-studio `docs/channels.md` (local-studio PR #5; Donovan, 2026-11-17). As a plugin that ships as a git tree, its channel is a git ref: stable is the newest `vX.Y.Z` tag on the `stable` branch, nightly is the rolling `nightly` tag, dev is `main`. A Local Studio install on a channel installs this plugin from the same channel. RELEASES.md follows that file.

## Not decided here

- Look and layout of the worksheet page: Gil designs it, using the shared Local Studio theme format.
- E-file: phase 2, through an authorized e-file provider, after v0.
