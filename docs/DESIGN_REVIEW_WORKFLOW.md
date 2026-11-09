# Frozen design review workflow

The owner authorized a stable design review while backend development continues. V1 captures the application at `7a7b674` (merged PR #15); no product layout/copy/assets are changed by this increment.

## Available now

[Review gallery](design-review/v1/README.md) contains 16 screens, each at desktop 1440px and phone 390px: five public pages and the current customer/booking/membership-draft/calendar screens. HTML pages are exported from real Django views using an isolated in-memory database and artificial Sample Family records. No operational database, credential, real customer, provider or email is accessed. Form actions, scripts and CSRF tokens are removed; controls are disabled and internal links point to captured pages. Missing/unfinished actions are labeled disabled.

For offline browsing, download the repository archive at the pinned review commit, extract it and open `docs/design-review/v1/index.html`. Keep relative source CSS/original images together. Gallery screenshots provide an easy phone-review alternative. A normal offline browser can open these files; managed Cloud Chrome blocks file navigation, so verification serves them over a temporary loopback HTTP server instead.

## Freeze and parallel development

- Use an immutable Git commit link for the gallery/archive. Do not send a moving main-branch link as the frozen review.
- Never rewrite V1 while the owner reviews it. Keep the deployed review in its own pinned release directory; backend development uses another checkout/branch and later release.
- Record numbered owner comments in [DESIGN_FEEDBACK.md](DESIGN_FEEDBACK.md), including version, page/device and exact comment. Track pending, implementation, ready-for-review and explicit approval separately.
- Implement design feedback in reviewable PRs, preserving settled business rules. Create the next frozen version at an agreed checkpoint. Do not treat a missing unfinished workflow as a fresh unanswered business question.

## Reproducing/validating V1

Use a clean checkout of the pinned application source. The exporter verifies source paths against that commit and refuses to overwrite an existing review. It switches its own process to SQLite `:memory:` before Django initializes any database connection; this is visual fixture rendering, not evidence of PostgreSQL business/concurrency correctness.

```sh
python tools/build_design_review.py --source-commit 7a7b674a477a42d76ecb3b7074c502c56b4dd425
python tools/check_design_review.py --capture
```

The full source hash is recorded in `docs/design-review/v1/manifest.json`. The first command requires project Python dependencies. The optional screenshot/check tool requires development Playwright and Chromium; they are not application dependencies. Run the checker without `--capture` to verify existing images and layouts without rewriting them. It checks links/assets, disabled forms, absence of scripts/CSRF tokens, responsive overflow and JavaScript errors. Existing captures are never overwritten.

## Hosted preview blocker

Current runtime reports no DigitalOcean/SSH secret binding and no server address/user is recorded. No shared-desktop control or externally forwarded preview tool is offered in this turn. A persistent hosted URL requires access to the existing Droplet; no URL or deployment is claimed. Ask only for non-secret host/user details in chat and arrange the SSH credential through protected environment configuration. Keep existing production/DNS resources unchanged while assessing access and price; no additional paid service is authorized. Existing Droplet resize authorization persists but no resize is needed for the gallery.

Once access is available, inspect the host before choosing changes. Serve the pinned design release privately, verify HTTPS/access protection and original assets, then provide the working URL. Preserve the read-only review release while functional backend staging develops separately. Existing application's MFA/staging-security requirements remain intact; do not weaken real staff authentication to show sample layouts.
