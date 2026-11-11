# Install UntoCaesar

> **Status: planned, not released.** UntoCaesar has no release yet, so there is nothing to install today. These steps are the target behavior. Each one becomes true only when its test in [TESTING.md](https://github.com/baney75/UntoCaesar/blob/main/TESTING.md) passes, and [SUPPORTED.md](https://github.com/baney75/UntoCaesar/blob/main/SUPPORTED.md) is the source of truth for what works now. An agent must check SUPPORTED.md first and tell the person plainly if a step isn't supported yet.

UntoCaesar runs on [Fonsviva](https://baney75.github.io/Fonsviva/), the shared local compute layer. Setup depends on whether Fonsviva is already on this machine or network.

## Steps

1. Install UntoCaesar from the [latest release](https://github.com/baney75/UntoCaesar/releases). (No release yet.)
2. Open UntoCaesar. It looks for Fonsviva at `http://127.0.0.1:7341/health` and on the local network.
3. **If Fonsviva is found:** UntoCaesar asks to connect. Approve the request in Fonsviva. Then pick or install models inside UntoCaesar (see [select models](select-models.md)).
4. **If Fonsviva is not found:** UntoCaesar offers to install it, asks before it does, then runs Fonsviva's setup inside UntoCaesar's onboarding: hardware scan, models already installed, a recommended first model, and the optional cloud step (see [add a cloud provider](add-cloud-provider.md)). Fonsviva stays installed and other apps reuse it.

## Check

1. `fonsviva status` shows Fonsviva running at `http://127.0.0.1:7341`.
2. `fonsviva keys list` shows a line for `untocaesar` with status `active`.
3. UntoCaesar's settings show "Connected to Fonsviva" and at least one model marked ready.

If any check fails, see [troubleshoot](troubleshoot.md).
