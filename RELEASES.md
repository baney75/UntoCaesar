# Releases: stable, nightly and dev

Unto Caesar follows the Local Studio family release scheme in [local-studio docs/channels.md](https://github.com/baney75/local-studio/blob/main/docs/channels.md). Where this file and that one disagree, that one wins.

Unto Caesar ships as a Local Studio plugin from a git tree, so each channel is a git ref:

| Channel | Ref | Who it's for |
|---|---|---|
| **stable** | newest `vX.Y.Z` tag on the `stable` branch | Everyone. The default. |
| **nightly** | rolling `nightly` tag, moved at 07:00 UTC when `main` changed and its checks pass | Daily users who want new work first |
| **dev** | `main` | Developers and agents testing a change |

## How a change reaches users

1. Work merges into `main` by pull request with CI green. That is dev.
2. No nightly or stable ships until the plugin declares `local_only`, `confirm` uses the person-only question card, the session's tools run with network off (local-studio#33), and the job folder is in encrypted plugin storage (local-studio#7) (docs/SPEC.md, "Capabilities it asks for"); until then `main` is a dev build for synthetic cases only.
3. Each day `main` becomes nightly when CI and the tier evals in [docs/SPEC.md](docs/SPEC.md#tier-evals) pass and no open issue is labeled `regression` and `blocks-nightly`.
4. A nightly is promoted to stable after 72 hours on nightly with no open regression, every TESTING.md check passing for every supported model, and plain release notes. `stable` fast-forwards to it and it is tagged `vX.Y.Z`.
5. Hotfixes go to `stable` by pull request with a check that fails before the fix, then merge back into `main` the same day.

## Update rules

- Every install and update is verified before it runs: the Local Studio catalog pins each channel to a commit and a SHA-256 tree hash, and the core refuses a tree that does not match (local-studio plugin catalog, `docs/channels.md`).
- User data is backed up before every update, and migrations are reversible.
- Every update can be rolled back to the previous version.
- What changed is shown in plain words before updating.
- No update deletes user data or changes work in progress without asking.
