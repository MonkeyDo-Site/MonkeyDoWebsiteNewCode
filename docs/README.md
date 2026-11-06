# MonkeyDo documentation index

Consolidated November 5, 2026. These documents capture the future website's current intended behavior, not an implementation or a production-readiness claim.

## Reading order and authority

| Document | Responsibility |
|---|---|
| [MONKEYDO_REQUIREMENTS.md](MONKEYDO_REQUIREMENTS.md) | Public content, booking, customers, waivers, admin, permissions, security, and quality |
| [MEMBERSHIPS.md](MEMBERSHIPS.md) | Subscription/Unlimited places, benefit allocation, dates, renewals, and conversion credits |
| [PROGRAMS.md](PROGRAMS.md) | Supervised play, clubs/participants, parties, physical gift cards, and socks |
| [PAYMENTS.md](PAYMENTS.md) | Payment timing, card lifecycle, cancellations, fee/tax calculations, sandbox/provider evidence |
| [EMAIL_TEMPLATES.md](EMAIL_TEMPLATES.md) | Email wording, conditions, combined confirmations, delivery handling |
| [DIGITALOCEAN_VPS_PLAN.md](DIGITALOCEAN_VPS_PLAN.md) | Deployment direction, staging separation, storage, backups, restoration, costs |
| [OPEN_DECISIONS.md](OPEN_DECISIONS.md) | Only genuinely unanswered owner/account decisions and future implementation inputs |
| [DECISION_LOG.md](DECISION_LOG.md) | Current consolidation/supersession record followed by explicitly historical entries |
| [RECONSTRUCTION.md](RECONSTRUCTION.md) | Source coverage, commit evidence, limitations, approval boundaries, acceptance cases |
| [brand-assets/README.md](brand-assets/README.md) | Original logo, advertisements, and photographs; actual file availability |
| [waivers/README.md](waivers/README.md) | Preserved waiver source, checksum, approval status, prototype limitation |

Each subject has one primary home. Cross-references are used instead of maintaining competing versions of a rule.

## Precedence

1. The owner's latest explicit instructions in the reconstruction task supersede earlier conversation answers where they conflict.
2. In the supplied history, later owner answers supersede earlier owner instructions; unchanged earlier decisions remain applicable.
3. Prompt AG contains the owner's inline answers to a copied assistant response. It has no subsequent assistant response. Copied unanswered-question lists do not override the answers embedded above them.
4. Assistant proposals, recommendations, API observations, and user decisions are distinct. Account-specific provider behavior is not established by public API documentation.
5. Closed, unmerged PR #4 is not an approved requirements source.
6. Archived decision-log text describes the past. The current subject documents and latest consolidation entry govern present requirements.
7. Preserve the source waiver PDF and exact original logo. No secret values, real customer data, or signed customer waivers may be committed.

## Approval boundary

The owner authorized this documentation update and pull request. Application development remains separately gated. Do not deploy, purchase infrastructure, connect DNS, enable live payments, open booking, or send real customer messages on the strength of this checkpoint alone.

Confirmed waiver wording and signature interaction are owner-approved; counsel review is not an owner-required gate. This does not mean the existing HTML prototype implements electronic-signature persistence.

Local source coverage and original-asset provenance are described in [RECONSTRUCTION.md](RECONSTRUCTION.md). Do not describe code or attachments as recovered without verifying their actual contents.
