# Security Policy

## Supported Scope

Security reports are accepted for:

- Repository documentation that could encourage unsafe deployment.
- Qdrant demo configuration that exposes credentials or unsafe defaults.
- Agent rules that could leak secrets, local sessions, logs, or private documents.
- Future application code added under the documented architecture.

## Reporting a Vulnerability

Do not open a public issue for exploitable vulnerabilities or leaked secrets.

Send a private report to the maintainers with:

- Affected file or component.
- Reproduction steps.
- Impact assessment.
- Suggested mitigation, if available.

If no private channel is published yet, create a public issue that only says you have a security report and need a maintainer contact. Do not include exploit details in that issue.

## Secret Handling

Never commit:

- API keys, tokens, passwords, certificates, or private keys.
- Internal URLs, customer identifiers, or production hostnames.
- Raw documents, model weights, vector database snapshots, audit exports, or logs.
- Local agent memory, sessions, or authentication files.

Use `.env.example` to document configuration names without real values.
