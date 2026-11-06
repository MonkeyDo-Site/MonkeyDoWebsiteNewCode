# MonkeyDo website

Requirements for the MonkeyDo children's indoor playspace in Lakewood, New Jersey.

Start with the [documentation index](docs/README.md) and [current requirements](docs/MONKEYDO_REQUIREMENTS.md). The November 5, 2026 consolidation reconciles the original chronological history (prompts A–AG) with the owner's subsequent clarifications in the reconstruction task.

## Current state and authorization

The owner has authorized staging development and explicitly approved **Django with PostgreSQL**. The local build provides page previews, a database/availability foundation, staff customer records/corrections/history and temporary login protection; it is not yet a functioning public booking application. See [development setup](docs/DEVELOPMENT.md), [build status](docs/BUILD_STATUS.md), and the [staging test plan](docs/STAGING_TEST_PLAN.md). The preserved [HTML waiver](waiver.html) is a standalone prototype: it displays the waiver but does not save signatures or connect to bookings. The source PDF remains unchanged.

Staging development and review PRs are authorized. Infrastructure purchases, production deployment, DNS changes, live payments, and opening customer bookings retain their separate approval gates. Start with staging only on DigitalOcean; assess shared staging/production resources before launch. No hosting has been purchased or deployed by this increment.

The official future public address is **https://monkeydoplay.com**, with `www` redirecting to it. This repository does not establish that a deployment is live.

## Review

- [Business and operational requirements](docs/MONKEYDO_REQUIREMENTS.md)
- [Membership and supervised-play rules](docs/MEMBERSHIPS.md)
- [Clubs, parties, gift cards, and socks](docs/PROGRAMS.md)
- [Payments, tax calculations, and Banquest findings](docs/PAYMENTS.md)
- [Customer email wording](docs/EMAIL_TEMPLATES.md)
- [Hosting, staging, and backup plan](docs/DIGITALOCEAN_VPS_PLAN.md)
- [Remaining decisions and implementation inputs](docs/OPEN_DECISIONS.md)
- [Reconstruction evidence and validation plan](docs/RECONSTRUCTION.md)

No credentials, payment-card details, signed customer waivers, or customer records belong in this repository.
