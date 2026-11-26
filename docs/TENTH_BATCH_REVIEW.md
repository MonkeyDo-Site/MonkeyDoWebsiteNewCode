# Tenth document — follow-up review in PR #35

The entire document and all 20 screenshots were reviewed before implementation. It combines feedback on the ninth gallery with issues on the deployed site. Keep this work in PR #35 and the existing numbered gallery. No merge or deployment is authorized until the owner finishes screenshot review.

## Decisions and changes

- Staff card setup shows only the first three cancellation sentences. Fee calculations, minimum admission, member rules and owner-comped exceptions remain unchanged.
- Use remaining balance fills the exact unallocated non-card total for that row; it neither records funds nor requests payment. Arrival counts and socks continue updating the live estimate before the waiver answer.
- A declined booking exposes both manual owner Retry card and Review remaining payment when permitted. Neither fires automatically. Existing pending/unknown payment safeguards remain enforced.
- Booking Payment places the card label immediately above its change link. An expected non-card payment labels it Backup booking card. Comments move into the right column between price and Messages.
- Every new pricing version sets baby-only/adult-only minimum admission to its child price. The independent pricing input is removed. Existing immutable policy versions and accepted quotes are preserved.
- Public Confirm booking uses rose. Card-funded public quotes say Total that will be charged at arrival; non-card quotes keep Total due at arrival.
- Open Play attempting fewer than one adult explains that an adult must accompany a baby or child. Staff selecting Supervised Play while adults remain sees an immediate message at the adult field. Counts are retained for correction; invalid estimates clear the old breakdown rather than displaying stale pricing.
- Missing-phone email recovery recognizes an existing email even after a failed earlier lookup. It verifies the surname before showing stored profile details, then requires explicit confirmation. An already entered matching name is reused. Unknown email/name combinations disclose no stored phone. Revisions, rate limits and session ownership remain enforced.
- A verified email-first conflict may now continue with that profile after explicit confirmation, replacing the former mandatory restart for that particular branch. When name and phone match one profile and name and email match another, retain the verified two-profile choice. The phone option still requires that profile's email; the email option displays its phone only after the surname match. Neither customer record is merged or edited. Existing conflict Dashboard alerts remain.
- Public duplicate-email guidance uses the owner's short text, the entered formatted phone and a session-preserving restart link. It does not offer to remove another customer's email.
- Post-signing coverage lists Yes before No. The completion reminder starts Please remember to send the link, while held places and Waiver pending records remain in the workflow.
- Gift cards never pay cancellation/no-show fees. Remove that UI option and reject it in fee preview and remaining-fee collection services. Physical gift cards remain available for ordinary arrival admission payments. Earlier gift-card receipts remain in history. Recorded Zelle prepayments still reconcile against the chosen fee.
- Price adjustment groups item, processing-fee and tax adjustments before cancellation fees. The latter explicitly says no sales tax. Arithmetic and accounting classification do not change.

## Banquest rendering boundary

The screenshot's regression follows PR #34's container-only flex overrides. Restore the provider's earlier responsive container layout and explicitly size the card-number input within its container, using documented HostedTokenization style keys. Do not replace secure provider fields with application-owned card fields.

The runtime permits Banquest API/documentation hosts, but not `tokenization.sandbox.banquestgateway.com`; a direct request is rejected by the network proxy (CONNECT 403). Actual hosted-frame verification remains pending that domain grant. Gallery fields and outcomes are simulated local fixtures and are labelled accordingly. Do not claim that these images verify Banquest rendering, issuer approval or external delivery.

## Validation and release boundary

688 local PostgreSQL tests pass, including fresh regression cases for failed-email recovery followed by an existing email, name-before-phone disclosure, stale profile rejection, explicit profile choices, duplicate-email guidance, manual retry alternatives, linked minimum pricing and fee-tender rejection. Updated historical tests reflect the owner's superseding copy and recovery decisions. Ruff/format, JavaScript syntax and migration-drift checks pass. Browser review covers desktop and phone; final results and the latest images are in the existing gallery.

No additional schema migration is needed beyond PR #35's reviewed 0052. No hosted data/configuration, real provider operation, email delivery, backup activation or active membership development is performed. Merge, final test guide and pinned ZIP/single deployment command follow the owner's completed review.
