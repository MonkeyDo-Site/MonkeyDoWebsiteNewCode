# Remaining decisions and implementation inputs

Consolidated November 5, 2026. Owner authorized documentation reconciliation and PR. These items do not block recording approved requirements or imply that already-settled business questions must be answered again.

## 1. Genuine remaining owner/account decisions

| Item | Known direction | Remaining action |
|---|---|---|
| Production sales tax | Product categories and fee formula settled; staging6.6% | Owner supplies production rate/UEZ outcome before live billing. Do not use staging rate as production default. |
| Tax on retained original processing fee after admission-to-membership conversion | Reverse replaced admission/base tax; original fee nonrefundable | Owner/accountant to say whether tax on retained fee stays/reverses. Example .03 tax on retained .45 fee. Do not silently settle. |
| Exact hosting/staging/monitoring cost | DO~2vCPU4GB NY, start with staging only; later assess shared production resources | Present actual resource/provider/backup/monitoring costs for approval before purchase; owner explicitly deferred until pricing known. |

## 2. Technical design and provider verification (developer work)

- Django and its ORM/migrations with PostgreSQL are now owner-approved. Complete custom authentication/permissions, durable jobs and integration design against the full requirements; do not present the foundation as a complete application.
- Banquest actual sandbox processor (Fiserv default reported, account unidentified); confirm from configuration/provider before processor-specific payment test claims. Not a blocker to general staging work.
- Banquest 3DS/Paay enablement, account costs, authentication-required responses/recovery, appropriate recurring/installment/source permissions, exact date/DST/no-retry behavior, metadata fees if any, complete deletion/derived-reference semantics and fraud behavior on amount change. Owner reports token storage free, no holds wanted and automatic gateway surcharge disabled. Do not reopen those choices merely because integration untested.
- Safe payment-operation identity/reconciliation when response is unknown; public duplicate detection is not verified exactly-once idempotency. Validate sandbox timeout/replay and no receipts/retries before payment-readiness claim.
- Approved proportional split allocation needs deterministic cent/rounding handling for actual inclusive tender amounts. No extra customer question on whether proportional allocation is allowed.
- Protected isolated restore runner/decryption-key access with key outside DO/R2; supported R2 credential/deletion/retention protection; exact production restoration and incident/key-rotation procedure. Do not claim automatic restoration tested before execution.
- Final photo mapping, accessible image alternative text and staging presentation. These do not reopen approved visible copy, four About areas or logo handling.

## 3. Inputs/configuration for future authorized setup

The owner subsequently supplied the original logo, two advertisements and nine facility photos in `monkeydo.zip`. Exact files and checksums are recorded in [brand-assets/README.md](brand-assets/README.md). Preserve these originals; final placement and accessible image descriptions remain staging choices. Original PDF/HTML waiver exist and wording is owner-approved; verify implementation matches them, do not ask again for counsel review.

Secure installation/verification is still needed for existing provider accounts: DO scoped access/SSH, R2 test/production buckets and keys, Resend replacement key/sender DNS, Banquest sandbox/live/private/public keys and webhook endpoint key, production DNS/TLS, test-card material. Owner already has sandbox credentials/test-card PDF; don't ask for values in chat or commit them. Existing account ownership is not proof configuration/testing done.

Email wording is collected in [EMAIL_TEMPLATES.md](EMAIL_TEMPLATES.md) for this PR's review, including latest owner edits. Conditional variant construction and delivery tests remain implementation work, not a broad unanswered “supply all email text” requirement.

## 4. Explicitly resolved — do not reopen

Banquest selection (not Stripe), purchased monkeydoplay.com/Cloudflare proxy, bookings@ sender/Reply-To, Zelle account and sender-name flow, no appointment reminders, staff/owner permissions/MFA, Last Name-only customers and IDs, card history/consent/removal distinction, normal35child/50combined capacity and owner/arrival overrides, cancellation amounts, party package/discount order, memberships/mixed adult allowances, January29leap reset, actual-date grace renewal, no unpaid phantom credit, credit eligible uses/retention, socks35online/unrestricted in person, physical gift cards **without** digital ledger/PIN, split failure preservation/proportional allocation, waiver wording/no counsel gate/two-year file retention, nightly/monthly backup retention, monthly two-copy manual desktop download, manual staging resets, and test-email recipients.

## 5. Deferred beyond initial launch

- SMS provider/compliance/opt-in/number/template/cost implementation, optional extra text confirmations only; no appointment reminders.
- Participant merging tool.
- Day-camp/group invoice generation.
- Optional payment-retry policy review after owner uses initial no-retry workflow and observes failure frequency. Separate approval required.
- Potential paper-waiver scanning/uploads, if later requested; not an initial requirement.

## 6. Authorization, not another business question

The owner subsequently explicitly authorized staging website/database development and approved Django with PostgreSQL. Development and review PRs may proceed. Production deployment, DNS connection, live payments and opening booking keep their independent written gates. Costs/purchases require review before commitment. Never treat the copied sample authorization in history AG as an actual instruction to build.
