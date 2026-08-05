# MonkeyDo Documentation Index

This directory is the documentation-only source of truth for the future MonkeyDo website. It contains requirements and planning material, not application code, infrastructure configuration, provider credentials, or legal approval.

## Authoritative documents

- [`MONKEYDO_REQUIREMENTS.md`](MONKEYDO_REQUIREMENTS.md): consolidated functional, business, design, architecture, data, security, testing, provider, and implementation requirements.
- [`DECISION_LOG.md`](DECISION_LOG.md): dated record of owner-confirmed business decisions. Later entries supersede earlier status statements when circumstances change.
- [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md): only unresolved choices, approvals, credentials/configuration steps, and launch blockers. Confirmed requirements belong in the requirements document and decision log, not as unresolved bullets.
- [`DIGITALOCEAN_VPS_PLAN.md`](DIGITALOCEAN_VPS_PLAN.md): detailed hosting, database-operation, hardening, provisioning, and deployment direction.
- [`brand-assets/README.md`](brand-assets/README.md): handling rules and availability status for the original logo and advertisement assets.

## Precedence and maintenance

1. Direct later owner confirmation supersedes earlier planning recommendations.
2. Confirmed behavior must be reflected in `MONKEYDO_REQUIREMENTS.md` and dated in `DECISION_LOG.md`.
3. Resolved items must be removed from the unresolved portion of `OPEN_DECISIONS.md`.
4. Historical entries may remain in `DECISION_LOG.md`, but superseded status must be labeled so it cannot be mistaken for the current state.
5. Provider credentials, API keys, passwords, private keys, and raw card data must never be written into these documents or committed anywhere in the repository.

## Current checkpoint limitation

The original logo/advertisement source files and `MD Waiver (1).pdf` are not present in this local checkout. A supplied GitHub screenshot shows the waiver PDF on `main`, but this checkout has no Git remote configured, so that separate repository state cannot currently be fetched or inspected here.

No application implementation should begin until the owner approves the complete plan. No payment, messaging, waiver, cancellation/no-show, or deployment feature may be described as production-ready until its applicable provider setup, credentials, approved wording/policies, legal review, and end-to-end tests are complete.
