# Staging payment confirmation — code-only correction

November 20, 2026. The operator reported HTTP 500 after the final arrival/charge
confirmation, after successfully saving an integrated booking, receiving its TEST
email and seeing provider-reported delivery in message history.

## Findings

The read-only staging query showed that the reported booking remained unarrived,
with zero checkouts, sales and payment operations. Its confirmation transaction
had not queued an admission charge. The runtime role could SELECT financial sales
but correctly had no UPDATE permission on them.

A new local regression reproduced the final-confirmation failure using a
non-admin PostgreSQL role with the reviewed financial grants. The failing line
was `FinancialSale.objects.select_for_update()`: PostgreSQL requires UPDATE
permission for that row lock even though the code does not intend to edit a sale.
Ordinary tests running as the database owner had not exposed this mismatch.

This is an application locking defect. It is separate from any processor-specific
rules for sandbox expiry/CVV values; those can affect later gateway acceptance
but do not explain this reproduced database exception.

## Change and affected paths

- Serialize financial allocations with a transaction-scoped per-sale advisory
  lock instead of a write-requiring lock on an immutable sale. Acquire any booking
  row first to match arrival/remaining-payment order. Sales without bookings still
  receive allocation serialization.
- Apply the same protection when removing uncharged card fees from an unpaid
  remainder. Invoice adjustments remain append-only; the original sale is retained.
- For owner import of an already completed correction, acquire the same sale guard
  and lock only the mutable payment-operation row, excluding its joined sale.
- Cover arrival, cancellation/no-show collections, remaining payments and owner
  correction imports through their shared services. No payment policy, amount,
  fee/tax calculation, waiver rule, public matching or homepage design is changed.

The patch does not widen permissions or modify migration files. SQL/ORM guards
against rewriting/deleting accepted financial facts remain in force.

## Validation and rollout

The restricted-role suite covers card confirmation/idempotent replay with no
inline provider request, cash arrival and correction, original fact update/delete
denial, non-card remainder adjustments, verified card-refund import without a
refund POST, and competing allocations with and without a booking. The restricted
worker also completes one simulated card receipt once, preserving a single
posting on repeat execution. All 594 local PostgreSQL tests pass; the final
restricted-role/worker checks pass too. GitHub PostgreSQL 17 and native Windows
PowerShell checks must pass on the final PR head before merge.

Deploy this as a normal code-only Functional update using the reviewed browser
ZIP and one PowerShell block. Do not pass a reviewed schema-batch flag. Existing
integration settings/signing secrets remain; do not rerun initial activation or
change grants to work around the exception. Backups remain disabled pending the
owner recovery key.

After verified deployment, return to the existing booking through the Bookings
list, open a fresh Start arrival form, review the amount and explicitly confirm
the sandbox charge once. Check attendance and the resulting payment status, then
verify the Banquest event/callback. No records need to be deleted or manually
marked paid. Actual gateway collection and signed Banquest event acceptance are
still to be verified on staging.
