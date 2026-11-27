# Active memberships — owner testing guide in progress

Draft [PR #37](https://github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/pull/37) remains under development. The [gallery](reviews/active-memberships/README.md) uses fictional records and simulated card outcomes; no live payment or email delivery was performed. Review images now. The steps below are for a later authorized staging release, with test customers and Banquest test cards. This is not a deployment or live-payment instruction.

## Current functional scenarios

| Scenario | Actions | Expected result |
| --- | --- | --- |
| New purchase | Select a customer, type, places, whole-month term and monthly/prepaid billing. Review the amount and accepted terms. Change the count before confirming. | The price and schedule update together. A changed selection requires accepting the current terms again. Only final confirmation saves the purchase and requests/records payment. |
| New membership card | On purchase/renew/add, choose Enter a new card and record the customer's Yes/No future-visit choice. Accept the current terms and use the final confirmation. | Secure storage happens first, followed by one explicit purchase. Unknown storage outcomes stop the purchase and survive reload without another exchange. No unrelated booking policy consent is recorded. Actual provider fields still require separate verification. |
| Actual payment truth | Compare pending and paid purchase overviews. | Pending/unknown card outcomes add no money and activate no benefits. Confirmed receipts appear separately from the next installment. |
| Combined member booking | Create a booking for a verified member, change counts and review price, waiver and card controls. | Member prices appear on the existing combined screen. Capacity counts, 30-minute backend holds, closure and owner-price controls remain. Benefit reservations occur only on confirmed booking. |
| Member arrival | Review actual counts, waivers and payment, then confirm arrival. | Included visits create no fabricated receipt. Paid remaining admissions/socks and cancellation fees retain their correct separate treatment. Usage is saved on confirmation. |
| Edit or move | Change attendees or session, including a move to another membership month. | The new estimate appears before saving. Saving transfers benefit reservations and preserves the old quote/history. No silent changes to already paid attendance. |
| Released Unlimited place | Cancel the first same-day booking, then open another already-confirmed booking. | The existing price stays until Apply available Unlimited benefit is explicitly selected and saved. |
| Renewal | Open Renew from an existing membership. Renew fewer places or change type. | Early renewal starts after expiry. Renewal within seven days after expiry starts on the actual date with a one-month minimum; later renewal normally requires three months. Original dates/prices/history remain intact. |
| Addition | Open Add membership places. | Additional places have their own term, accepted price, schedule and ordinary three-month initial minimum. |
| Failed installment | Open Resolve payment or update membership card. Choose the installment and card/cash/check/Zelle/verified physical gift card. | Preview creates no payment. The final button states the action and amount. Noncard requires verified receipt and removes only the unused card fee for that balance. |
| Uncertain installment | Open payment controls while an existing outcome is unknown or processing. | A replacement charge and manual receipt are blocked. Open the previous payment for review. Changing a card does not bypass this block. |
| Card update | Select an available customer-owned card, record authorization and save. | A new mandate is retained in history. No charge is requested; scheduled dates and earlier payment outcomes remain unchanged. New hosted-card entry for an existing membership's replacement source is still being connected; purchase/renew/add support new entry. |
| Owner attention | Resolve an overdue installment, then return to the overview and Dashboard. | Actual funds increase once, benefits become available when all required dues are current, and the settled installment notice clears. No successful-installment customer email is sent. |

## Known unfinished areas

Public secure-card purchase/renewal and private links; new replacement-card entry for an existing membership; combined purchase-and-visit checkout/email; combined multi-cohort renewal checkout; scheduled installment execution; direct owner membership cancellation/refunds/consolidation/grants and booking exceptions; visit conversion/customer credit; expiry/grace notices and booking renewal prompts; full filters/exports and final provider validation remain in progress. The release feature switch stays off by default.

Actual Banquest hosted fields and installment processor flags are not verified by the fictional gallery. Two policy answers about later installments after failure and parent arrears after prepaid early renewal remain pending in the [implementation record](ACTIVE_MEMBERSHIP_IMPLEMENTATION.md). Neither disputed automatic branch is enabled.

The final guide will add those completed flows, exact release prerequisites and the approved deployment handoff. Merging, deployment and live financial actions require separate explicit release authorization.
