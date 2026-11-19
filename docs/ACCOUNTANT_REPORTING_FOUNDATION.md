# Financial records needed for later accountant reports

Owner request, November 19, 2026: accountant reports will eventually cover income,
tax, refunds and income after refunds. The reporting screens may be built after
the website/database go live. Capture the necessary source records when payment
functionality is built, before collecting real money. This is a planning update,
not authorization to build reports or start the next application phase.

## Review finding and timing

The current database has immutable price policies, booking quote snapshots and
membership test drafts. These are estimates/plans, not proof of money received.
The approved payment stage already calls for payment operations, actual tenders,
refund/correction history, provider reconciliation, immutable financial history
and safe retention. No separate reporting server, new Banquest key or accounting
service is required merely to support future reports.

Stage 1A must make the following source-data requirements explicit. Later
membership, party, gift-card, socks and club work must use the same records.
Build the reporting UI, report-specific filters/layouts, accountant downloads and
optional accounting-software integration later. Existing separately required
operational exports/printing are not postponed by this reporting deferral.

## Source records to capture from the beginning

| Area | Required persistent facts |
| --- | --- |
| Sale and line identity | Stable sale/line/operation IDs; links to booking, customer, membership/cohort or other business record where applicable; stable product/category codes, human description, quantity, unit price, discounts and final line amounts. Do not infer categories from changeable labels or current prices. |
| Tax and fee components | Original currency, pricing/tax policy version, tax classification/rate, taxable and nontaxable bases, customer processing fee, taxable fee allocation, actual tax allocated to goods/services and to the fee, and actual charged total. Preserve deterministic cent allocations that sum to the existing approved combined tax total. Reporting must not silently change the tax formula/rounding. |
| Expected versus received | Estimates/amounts due and actual successful receipts are distinct. Record successful cash/check/verified Zelle, card and other approved tenders with their real amounts. Card setup, an authorization, failed/pending/outcome-unknown operations and unpaid amounts are not cash received. Refund/void outcomes must also be explicit. |
| Split payments | Each actual tender/operation and its allocation to the purchase and tax/fee components; preserve a received portion when another tender fails. Expected payment method does not establish actual tender. |
| Adjustments and refunds | Append linked refund, void, reversal, correction and conversion allocations rather than rewriting/deleting original financial records. Preserve affected original lines/receipts, amount, tax component, nonrefunded fee, reason/source, authorized actor, timestamps and provider references/outcomes. Partial and repeated operations must reconcile without exceeding paid/refundable balances. |
| Credits and conversions | Keep money refunded externally, customer credit issued/applied, gift-card tender and funds transferred to membership distinct. A conversion or credit redemption reallocates existing funds; it is not a second receipt of cash. Preserve application history and remaining obligations. Physical gift-card sale/redemption transactions do not create an unapproved digital gift-card balance/PIN ledger. |
| Dates and periods | Booking/service date and applicable membership/coverage period, transaction/request time, actual receipt/refund/void time and available settlement/payout dates are separate facts. Store timezone-aware instants and derive business periods in America/New_York. A later refund retains both its own date and its link to the original sale/date. |
| Provider and bank reconciliation | Retain safe provider charge/refund/operation references and available settlement/payout references. Customer's 3% processing fee is different from fees the processor charges MonkeyDo. Actual provider fees, chargebacks, reserves/adjustments and deposits require verified provider/statement data when available; preserve their source references, never fabricate them from the 3% customer fee. Missing provider data remains explicitly unknown. |
| Reliability and evidence | Stable operation identity, atomic posted allocations, deduplicated webhooks and reconciliation prevent retry/replay from duplicating receipts/refunds. Keep attempts/events separate from reportable financial effects. Preserve correction history; archive rather than cascade-delete associated financial facts. |
| Environment and access | Sandbox/test/legacy estimates never appear as live receipts. Preserve currency and environment identity. Financial history retains existing safe indefinite-retention/backup rules; no PAN/CVV/secrets in reports or logs. Owner-only accountant access/export by default; staff need existing explicit export permission. Do not create an accountant account or automatically send reports. |

Keeping tax components internally does not change the customer receipt's one
processing-fee total and one sales-tax total.

## What the later reports must be able to distinguish

- Sales by product/category and taxable/nontaxable treatment, with discounts,
  reversals and returns, preserving the original transaction detail.
- Money collected, external refunds and net receipts, with an explicit definition
  of which date/status is included. Total receipts including tax are different
  from sales income excluding tax.
- Sales tax charged/collected and tax reversed/refunded, including fee-tax
  reversals under the accountant's approved conversion rule.
- Customer processing fees charged/retained versus actual processor expenses.
  Neither net receipts nor a gateway payout alone establishes business profit.
- Outstanding balances, customer credits and gift-card-related movements without
  counting credit redemption or conversion as new cash receipts.
- Provider/bank deposits reconciled to successful payments/refunds and actual
  adjustments where corresponding evidence is available. Deposits can occur in a
  different period from the visit or charge.

The accountant can specify cash/accrual presentation, recognition treatment,
filing-period conventions, gift-card treatment, grouping and final file layout
before reports are built. Preserve underlying dates/service periods and movements
now; do not silently decide accounting policy or promise full accrual accounting,
profit-and-loss reporting or a general ledger from payment totals alone.

## Acceptance criteria for the payment foundation

1. A successful all-card or split-tender sale has reconcilable line, fee, tax,
   tender and received totals; failed/unknown attempts do not inflate receipts.
2. A later partial refund retains the original rate/rounding, records the refund
   date and original sale link, and reverses only the appropriate amounts.
3. Admission-to-membership conversion follows the accountant clarification:
   $16.47 original payment, $0.45 original fee retained, $0.99 admission tax and
   $0.03 fee tax reversed, $16.02 available toward membership. Preserve the linked
   reallocation; do not count it as a new payment or also refund it twice. A
   payment not applied toward membership retains its fee tax under that rule.
4. Credit issuance/redemption and physical gift-card tender remain distinguishable
   from cash received, with no fabricated digital gift-card balance tracking.
5. Duplicate submissions/webhook replays and restarts do not duplicate posted
   receipts, refunds or applications. Historical price/contact edits do not
   change accepted financial facts.
6. Sandbox records, old quotes and inactive drafts are excluded from live-money
   aggregates. New York month boundaries and cross-period refunds remain
   recoverable from the saved dates.
7. All figures trace to stable original/correction IDs; safe retention, restricted
   exports and restored-record reconciliation preserve the source history.

No application models, migrations, provider settings or report pages are changed
by this review. These are prerequisites for the next payment implementation and
later report acceptance, not evidence that a payment ledger/report exists today.
