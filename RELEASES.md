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
2. Each day `main` becomes nightly when CI and the tier evals in TESTING.md pass and no open issue is labeled `regression` and `blocks-nightly`.
3. A nightly is promoted to stable after 72 hours on nightly with no open regression, every TESTING.md check passing for every supported model, and plain release notes. `stable` fast-forwards to it and it is tagged `vX.Y.Z`.
4. Hotfixes go to `stable` by pull request with a check that fails before the fix, then merge back into `main` the same day.

## Update rules

- User data is backed up before every update, and migrations are reversible.
- Every update can be rolled back to the previous version.
- What changed is shown in plain words before updating.
- No update deletes user data or changes work in progress without asking.
