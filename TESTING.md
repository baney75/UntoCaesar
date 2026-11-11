# Testing: honest claims only

Unto Caesar must never claim it can do something it can't. Every claim in the README, the docs or the app has a test behind it, and the results are public in this repo.

## Tax accuracy standard

The bar is nearly zero error, and never unknown error. Every supported tax situation has golden test cases: complete scenarios with known-correct returns, drawn from IRS sample scenarios, VITA/TCE training cases, state examples and expert-prepared returns, each citing its source. A return is checked line by line against the expected result.

- The app may mark a return ready only for situations whose suite passes at 100% for the model in use.
- Any situation outside the supported list is detected and handed to the user plainly, never guessed.
- Pass rates per tax year, form and model are published in `benchmarks/results/`.

## Rules

- **No unknown error.** Any output that differs from the expected result fails the test, field by field. "Close enough" is a failure.
- **Known limits are declared.** Anything Unto Caesar doesn't support yet is listed in `SUPPORTED.md`. The app detects those situations and tells the user plainly instead of guessing.
- **Every model is tested separately.** A model is only offered for a task after it passes that task's suite (see `BENCHMARKS.md`).
- **Real behavior, not mocks.** Tests run the real skills against real local models and check real outputs.
- **Regressions block release.** A drop in any pass rate blocks promotion from Nightly to Stable.

## Layout

- `tests/golden/`: cases with known-correct expected outputs and their sources.
- `tests/skills/<skill-name>/`: tests for each skill.
- `benchmarks/results/`: published pass rates per model and hardware.
