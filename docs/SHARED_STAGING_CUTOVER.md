# One staging site for design review and booking tests

The owner's current instruction supersedes the earlier frozen-preview/two-URL proposal. Everyone uses **https://staging.monkeydoplay.com/** and sees the same deployed design. Customers/testers land on the homepage after the shared staging gate. Staff/owner enter **/staff/** and authenticate separately; the shared gate never grants staff permissions. Staff links are absent from public navigation, and pages remain noindex/no-store. Search exclusion is not access control; staff permissions are the access control.

## What can be tested now

The merged customer self-booking code supports phone/Last Name matching, selecting Open or Supervised Play, attendee/sock counts, itemized estimates, revision, pending test reservation creation, staff lookup/review/cancellation and a browser-owned receipt. The source templates contain the current homepage design, images, text and CSS motion; functional routing uses those templates instead of the frozen HTML gallery/index.

No additional booking feature is required before testing that scope. Payments, saved cards, waivers/signatures, active membership benefits and booking confirmation emails are not implemented. These remain explicitly pending test reservations, not confirmed visits. Use fictional contacts, cancel test bookings when their spaces need to be made available, and do not invite paying customers to transact here.

## Deployment readiness and access

This follow-up prepares code/configuration; it does not establish hosted readiness. The connected coding environment has no Droplet SSH identity or configured provider secrets. The owner's existing Windows SSH access can perform the host steps. Never paste private keys, Resend keys, passwords or environment-file contents in chat/GitHub.

Before switching, obtain the host's `free -h` and `df -h /` output. Only the functional application needs to remain running after cutover; stop the old design worker process after successful verification. Resource sufficiency is determined from actual host results, not the plan's advertised RAM alone.

The initial environment/database/service and account email must be configured as described in [CUSTOMER_BOOKING_DEVELOPMENT.md](CUSTOMER_BOOKING_DEVELOPMENT.md). This preserves the old database while giving booking tests their own database and restricted runtime role on the same Droplet. It requires no second public address, new Droplet or paid-service activation. Real owner MFA/reset delivery must pass before inviting testers; a configured key or mocked test is not evidence of delivery.

## Activation sequence (operator work, not yet executed)

1. Record current release, running service and existing nginx staging virtual-host filename. Preserve that nginx file privately with root ownership and restrictive permissions. Record existing TLS paths. Keep old releases/database intact. Do not reset existing accounts or data.
2. Check resources; prepare the functional runtime/migration roles, database, protected environment, exact approved release and virtualenv. Review/apply migration 0021 only to the functional database using its migration role. Configure the owner, staff permissions and hidden staging-password prompt. No helper automatically applies schema changes.
3. Start `monkeydo-functional.service` on its private Unix socket. Run Django deploy checks, migrate --check and `functional_staging_preflight` as the functional runtime user. Test the gate, homepage, booking schedule and staff sign-in through the socket before changing nginx. Verify account mail privately. Stop here on failure; the old website is still routed normally.
4. Replace only the existing staging virtual host with the reviewed functional proxy configuration, retaining the existing certificate and unrelated nginx settings. Do not install a second conflicting staging server block. Run `nginx -t`; on failure restore the saved file without reload. If valid, reload nginx. The source `deploy/nginx-functional.conf.example` is an example requiring inspection of actual host paths, not an installer.
5. Verify HTTPS gate -> homepage (not gallery), public navigation, chosen session -> estimate -> pending save, separate-browser staff login -> same booking -> Cancel booking, and updated customer receipt. Test unauthorized staff access, owner MFA, static images/fonts, and desktop/phone layouts. Noindex/no-store and secure cookies must remain. If any required check fails, restore the saved nginx configuration, validate and reload it to route back to the old design socket. Keep the old service running until this checkpoint succeeds.
6. After success, stop/disable `monkeydo-design-review.service` to free memory. Keep its files/database for recovery. Install the updated deployment helper/wrapper from the exact approved release with `-Target Functional`, then verify `-Target Functional -Status`. Subsequent design and booking changes deploy together using that target and exact-commit ZIP.

## Recovery boundaries

Routine Functional rollback restores its previous code/venv/service override and preserves test data. It does not roll back database schema or change nginx. The first cutover has no previous managed functional deployment: its recovery is restoring the saved nginx host and, if already stopped, restarting the old design service. Confirm that recovery before declaring the site ready. Reverting to a design release temporarily removes booking functionality; it is not a way to continue tests on the old version.

Do not run the legacy default Design deploy command after cutover. Its health checks are for frozen routes. Until/unless a separate change deliberately retires that compatibility mode, the shared-site command must include **-Target Functional**. This switch is internal; users still visit the same URL.

No deployment success, actual server capacity, external email delivery or actual TLS/service rollback has yet been verified from this coding environment.
