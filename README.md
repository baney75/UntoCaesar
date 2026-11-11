# Unto Caesar

> "Render unto Caesar the things that are Caesar's." Matthew 22:21

Unto Caesar is an open-source tax filing app that runs on local AI. A person, a business, or an organization that files for others should be able to open it, answer plain questions, hand over their documents, and get a correct, finished return without a tax background and without sending their financial life to a cloud service.

## Who it's for

- **Individuals** filing their own returns.
- **Service providers** such as universities, VITA-style volunteer sites, and community hubs that help many people file.
- **Businesses** handling their own filings.

## What it does

- Guides the user through their return in an extremely easy GUI.
- Reads tax documents (W-2s, 1099s, receipts) and fills in the return.
- Finds deductions and credits the user qualifies for and explains why.
- Checks the return for errors and missing items before it's finished.
- Runs entirely on local models that are safe, reputable and trusted. No tax data leaves the machine.

## How it's built

Unto Caesar is an arrangement of standardized skills and solid code bundled behind one simple interface. The skills tell the model exactly how to handle each form and rule, and the code does the math and validation, so the AI never has to guess.

## Filing

- **Phase 1:** prepare the complete return for the person to review, sign and submit. Service providers can put a volunteer review step here.
- **Phase 2:** direct e-file, through IRS authorized e-file provider approval or an approved e-file partner.

## Scope

US federal and state returns come first. The long-term goal is global.

## Setup

Unto Caesar runs on [Fonsviva](https://github.com/baney75/Fonsviva), the shared local compute layer. If Fonsviva is already installed, Unto Caesar uses it and you pick models inside the app. If not, the app installs it for you and walks you through setup. Cloud providers are set up only in Fonsviva, for personal use only.

Agents setting this up for someone: start at [docs/agents.md](docs/agents.md) or [llms.txt](llms.txt). Site: https://baney75.github.io/UntoCaesar/

## Status

Early planning. Contributions and ideas are welcome.

## License

MIT
