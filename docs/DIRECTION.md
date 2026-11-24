# Direction

The owner's standing direction for Unto Caesar. Every plan, skill and pull request is checked against it.

Donovan Baney, 2026-11-22, in his words:

> REMEMBER smoothstone and GANTREL are to be to better and they need to integrate very well and easily with things such as Creality CLI and other openstandards for connecting to 3D printers, and later other types of engineering devices, as gantrel is also for product design I want to be able to design my products in it, of course I will be using larger models, but over time we will "distill" through skills so lesser models can learn how to do said things too, and generalize widely and when I mean small I mean
>
> - 1.7B-31B for
> - then up and higher and that
>
> Unto caesar will work in a similar way one can use their sub but the goal is that eventually it will get so Good that local models can easily do taxes for people revolutionizing and helping the world, and I mean the world, write down what I have writted of course yet, ensure this will be done to a high standard


And in the next message:

> It needs an MCP to act with grokbot, and again will have a waitlist for tunnels unless they use dev mode and use their own
> as we will need to either charge or negotiate with them

## What it means for Unto Caesar

### 1. Today and the goal

- Today a person can do their taxes with Unto Caesar on their own subscription model, reached the way the ground rules allow ([AGENTS.md](../AGENTS.md): compute goes through Fonsviva).
- The goal is that local models do anyone's taxes easily, with no tax data leaving the machine, for people everywhere, not only in the US. US federal comes first.

### 2. Distill through skills to small models

- Each form, rule and step is a skill with an eval, and the math stays in the IRS Fact Graph or tested code, never in the model. When a larger model handles a case well, it becomes skill material so smaller models handle it too.
- Small means 1.7B to 31B parameters, with larger models above that. Each skill is benchmarked across that ladder ([BENCHMARKS.md](../BENCHMARKS.md)), and the results are published.
- "Easily" and "generalize widely" are measured: held-out returns the skills were never tuned on, checked line by line against known-correct returns.

### 3. An MCP server for Grok Bot

- Unto Caesar has an MCP server so Grok Bot, and any assistant that speaks MCP, can act through it. Sending tax data to a cloud assistant is the person's own explicit choice, the same as using their subscription; the local path never needs it.
- Reaching it from away from home follows Local Studio's tunnel rule ([local-studio docs/tunnel.md](https://github.com/baney75/local-studio/blob/main/docs/tunnel.md)): there is no hosted tunnel and no waitlist (Donovan, 2026-11-24). Everyone sets up a tunnel on their own free Cloudflare account and domain, and `local-studio tunnel byo` walks them through it; Tailscale stays the option without a domain. This replaces the earlier waitlist rule quoted above.
- A server reached through a tunnel needs auth on every path and the public-tools consent ([local-studio#13](https://github.com/baney75/local-studio/issues/13)).

### 4. A high standard

- Tax accuracy is the product. Every rule cites its official source, a person reviews and signs, and nothing is claimed in [SUPPORTED.md](../SUPPORTED.md) without a passing test.

Progress is tracked in the "Direction" issue on this repository.
