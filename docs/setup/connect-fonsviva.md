# Connect UntoCaesar to Fonsviva

> **Status: planned, not released.** UntoCaesar has no release yet, so there is nothing to install today. These steps are the target behavior. Each one becomes true only when its test in [TESTING.md](https://github.com/baney75/UntoCaesar/blob/main/TESTING.md) passes, and [SUPPORTED.md](https://github.com/baney75/UntoCaesar/blob/main/SUPPORTED.md) is the source of truth for what works now. An agent must check SUPPORTED.md first and tell the person plainly if a step isn't supported yet.

UntoCaesar doesn't run models itself. It connects to [Fonsviva](https://baney75.github.io/Fonsviva/).

## Steps

1. Make sure Fonsviva is running: `fonsviva status`.
2. In UntoCaesar, open **Settings → Connect to Fonsviva** and choose **Connect**. UntoCaesar sends a connection request.
3. Approve it in Fonsviva's web app under **Connect**, or run `fonsviva keys approve untocaesar`.

## Check

- `fonsviva keys list` shows `untocaesar` as `active`.
- UntoCaesar shows "Connected to Fonsviva" with the machines and models it can use.
- Every job in UntoCaesar shows where it ran.

Fonsviva on another machine: enter its address (for example a Tailscale name) in the Connect screen instead.
