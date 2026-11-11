# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor and others) working in Unto Caesar.

## What this project is

Open-source tax filing on safe, trusted local AI. It is for individuals, families, small and large businesses, and volunteers or institutions (universities, community hubs) filing for others. It runs as a desktop app, a self-hosted site with no GUI, or across shared compute nodes, and it prepares returns, finds deductions, tracks local, state and federal deadlines, and keeps everything encrypted.

## Ground rules

- **Local first.** Features must work with local models on the user's own hardware. Cloud or private compute providers (for example RunPod) are optional add-ons, never required.
- **Private and secure by default.** User data is encrypted at rest and in transit. Never log, print or send secrets or personal data.
- **Trusted models only.** Use safe, reputable open models. Document which models a feature was tested with.
- **Easy beats clever.** Every feature has to be usable by a non-technical person.
- **Design comes from DESIGN.md.** Follow it for all UI work. If it is empty or silent on something, ask the designer rather than inventing a style.
- **Prove it works.** Back every change with behavior tests or a recorded real run. Don't claim something works without evidence.
- **Small, reviewable changes.** One concern per pull request, with a clear description.
- **Tax accuracy is the product.** Tax rules belong in skills and tested code, never in model guesses. Cite the official source (IRS, state, local) for every rule.
- **A human signs.** The app prepares returns; a person reviews and submits them.

## Skills

Skills live in `skills/maintainer/` (for building this project) and `skills/runtime/` (used by agents inside the app). All are original and tested; see `skills/README.md`. Load the skill that matches your task before starting, and improve it when you learn something.

## Testing and honesty

Never claim the software can do something without a passing test. Follow `TESTING.md`, keep `SUPPORTED.md` honest, and benchmark models per `BENCHMARKS.md`. Model-specific instructions live in `models/<model>/`.

## Releases

Unto Caesar ships on two channels, Nightly and Stable. See `RELEASES.md`. Never push directly to `stable`.

## Repository layout

- `AGENTS.md`: this file
- `CLAUDE.md`: Claude Code entry point, points here
- `DESIGN.md`: design system and UX rules, owned by the designer
- `RELEASES.md`: Nightly and Stable channels
- `CONTRIBUTING.md`: how to contribute, including design work and coauthorship
- `TESTING.md`, `SUPPORTED.md`, `BENCHMARKS.md`: accuracy, honest scope and model benchmarks
- `skills/maintainer/`, `skills/runtime/`: original, tested skills
- `models/`: per-model instructions
- `tests/`, `benchmarks/results/`: tests and published results
- `design/`: design exports and notes
