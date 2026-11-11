# Benchmarking local models

We need to know which local models can actually do Unto Caesar's work, on which hardware. Guessing is not allowed.

## Built on the Local AI registry

Model launches come from Sybil Solutions' [Local AI registry](https://github.com/sybil-solutions/local-ai-registry) ([local.sybilsolutions.ai](https://local.sybilsolutions.ai)). Each registry recipe is a validated way to run a model on a specific GPU that passed its general gates: it loads, chats, reasons, calls tools, holds context and decodes at 15 tok/s or more. This works on any device the registry covers.

Unto Caesar adds its own task gates on top. A model only counts as working for Unto Caesar when it passes them.

## Unto Caesar task gates

- **Return accuracy:** golden returns match line by line.
- **Document extraction:** W-2s, 1099s and bank CSVs are read with every field correct.
- **Deduction finding:** finds every deduction in the golden set and invents none.
- **Deadline accuracy:** local, state and federal due dates are correct.
- **Refusal:** situations outside `SUPPORTED.md` are flagged, not answered.

## How a run works

1. Pick a registry recipe for the hardware and launch it.
2. Run the task gates in `tests/` against it.
3. Save the result to `benchmarks/results/<model>/<card>.json` with the recipe ID, date, hardware, pass rate per gate and a log hash.
4. The app offers a model for a task only where a passing result exists for that hardware.

## Per-model instructions

Each model that passes gets a folder in `models/<model>/` (copy `models/_template/`) with the prompt format, settings and skill wording that model needs, plus its own tests. Skills stay shared; only model-specific adjustments live here.
