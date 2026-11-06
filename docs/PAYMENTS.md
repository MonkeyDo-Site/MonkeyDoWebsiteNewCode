# Payments, tax, card lifecycle, and Banquest evidence

Consolidated November 5, 2026. Business rules are owner decisions; provider findings below are public documentation observations, not authenticated account tests. No integration, credential installation, verification or charge is performed by this checkpoint.

## 1. Payment timing, consent, and arrival

| Purchase | Timing |
|---|---|
| Ordinary/supervised visit and booking-selected socks | After staff arrival review and explicit final confirmation, not online booking creation |
| New membership/prepayment/first installment | At purchase; later installments on approved schedule |
| Membership bought with future visit | Membership at purchase; visit at arrival; one combined email accurately separates paid/due |
| In-person membership/visit conversion | Final adjusted transaction(s) based on already-paid versus unpaid amounts |
| Club card enrollment | At enrollment |
| Club cash/check or Zelle | First attended session for cash/check; Zelle before; contacted-customer backup charge only explicit |
| Party | No deposit; booking/card setup followed by agreed arrival/payment flow |
| Physical gift-card sale | In-person sale, separately recorded from any booking payment |
| Owner-comped $0 booking | No payment attempt or required card; waiver still needed |

Use cash, check, verified Zelle, card, physical gift-card tender and eligible customer credit as specified by product. No ACH bank-debit integration. Nonmember ordinary bookings require a backup card for alternate tenders. Member-benefit $0 visits still have membership/cancellation obligations; do not treat them as owner-comped bookings.

Customer payment disclosure supplied during history:

> You're almost done with your booking. Please enter your payment method. Please note: Payment will be processed after you arrive. For cash, check, or zelle, please enter a backup credit card. This card will be charged only in the event that another form of payment is not received. Once the payment is received upon arrival, the backup credit card information will be automatically deleted from our system.

**Later consent distinction governs implementation:** the deletion sentence describes booking-only backup methods, not a customer method explicitly retained for future use. Present that exception clearly with the separate future-use choice; do not falsely promise deletion of a retained reusable method. Owner approved safe display label **Saved payment method ending in 1234**. Membership and club immediate-charge timing must be explained in their own flows, not misrepresented by the ordinary-arrival disclosure.

Accept versioned applicable payment/cancellation terms each booking, even with a reusable card. Store consent source/time/version and audit. Phone/admin flow uses the policy-reviewed checkbox, not a mandatory scripted phone-consent screen. Secure provider-controlled card fields for both customer and staff, never raw PAN/CVV through MonkeyDo. Record genuine consent; a policy-reviewed checkbox is not a waiver signature.

### Final arrival operation

Start arrival opens review only. Confirm actual counts, revised price and any pending partial cancellation, coverage for everyone, and actual payment. Card replacement available before charge. Alternate choices:

- Cash received.
- Check received.
- Zelle received (verify in business bank account; screenshot not proof).
- **No alternate payment received — charge card on file.**

Use clear final action such as **Confirm arrival and charge $45**, **Confirm arrival and record cash**, or applicable check/Zelle wording. Do not charge from a mere Arrived checkbox, from appointment time passing, or redundant booking-detail payment buttons. Record actual tender and sensitive-action audit. No extra “Credit card instead” duplicate choice; replace card first if necessary.

Zelle account **monkeydoplay@gmail.com**. At choice ask which account/name payment comes from. Confirmation says **You selected Zelle as your form of payment. Please Zelle payment to monkeydoplay@gmail.com.** Record verified received or resolve backup card. No old confirmation-number-in-memo requirement and no invented online Zelle collection or auto-expiry deadline.

## 2. Card retention and history

- Card details stay with Banquest; MonkeyDo keeps necessary provider references/consent and limited display metadata, never PAN/CVV or locally persisted expiry.
- Booking-only provider method remains until applicable booking payment/fee responsibilities resolved, then remove from permitted application charging sources and request provider deletion where supported. Final alternate-payment confirmation triggers automatic removal, not a separate scheduled/manual early-removal operation.
- Optional future-use consent retains reusable customer method after arrival/alternate payment. A booking-specific replacement can differ from reusable method: Yes to replacing saved method updates future use; No keeps old reusable method and uses new method for booking only.
- Do not invalidate another outstanding booking or installment obligation accidentally when replacing/removing shared provider references. Resolve dependencies/replacement before detaching.
- Owner approved **indefinite safe transaction history**: amount/date/status/card brand/last four/provider transaction reference/correction/refund history. Historical last four remain visible after method removal or replacement. Do not retain a method solely to display old last four.
- Provider deletion's effect on underlying saved-card/derived tokens and previous-transaction charging references remains technical verification; do not assert every historical provider reference is irrevocably unchargeable without evidence. Application authorization must forbid deleted sources regardless.
- No issuer holds/authorization-only verification wanted. Token storage reported free by owner. Saving a token does not prove issuer validity; expiry metadata check without deliberate verification is approved. Later declines use the established issue flow.
- Known expiry message: **Your saved card has expired and needs to be updated before this booking can be completed.** Other unusability must not be mislabeled expiry: **Your saved payment method could not be used. Please enter a payment method for this booking.**

## 3. Cancellation, no-show, corrections, and failures

Ordinary policy supplied by owner:

> If the booking is cancelled, or the customer doesn't arrive, the customer's credit card will be charged $3 per each $15 admission.

Before payment details require unchecked **I understand the Monkey Do cancellation policy**. Later membership/supervised rules extend **$3 per child admission** to free member, $5.99 member, $14.24 discounted supervised and $18.99 supervised visits, not a percentage of their price. Baby-only/adult-only required admission also has $3 fee; extra $5 adult has none. No fee on explicitly owner-comped $0 booking.

- Any ordinary cancellation timing, customer calls/texts rather than self-service cancellation. Staff/owner chooses charge/no-charge, no mandatory reason. Use **No show**, not “didn't arrive.” Show fee and explicit **Confirm no show and charge $amount** / **Confirm no show without a fee**; $0 comped no-show just confirms. Cancel closes without acting.
- Fewer actual children: remove absent child's admission, restore applicable benefit, add itemized $3 partial-cancellation fee, collect with remaining arrival payment. Three ordinary children booked/two arrive -> $30 admission+$3 pending fee before tax/card fee. Remove absent extra adult's $5, no fee.
- Avoid stacking/double-collecting already-recorded partial fees when a whole booking later cancels; ledger must reconcile the approved per-admission obligations rather than create duplicate charges.
- Party has **$50** cancellation/no-show fee and owner waiver, not ordinary per-child calculation. Club first no-show has enrollment-payment follow-up, no ordinary $3 club fee.
- Phone cancellation without presented/verified physical gift card charges backup card; gift-card use requires actual verification.
- No ordinary customer refund program. Accidental duplicate/wrong charges: **Payment correction required**, alert owner, owner corrects via provider dashboard, record/sync original and correction, preserve history. Staff may see but not issue owner-only correction. Membership/club owner exceptions are separate.
- Member/club refunds do not return original processing fee. Cancellation membership email may include refund processed then; no later refund-only email or monthly installment receipt. Club exception refund notice optional.
- Failed/authentication-required charge: current screen, unresolved Dashboard and owner email to business address. Safe alert includes customer, appointment/internal reference, phone, amount and protected admin link, not card/waiver/comment contents.
- Staff/owner records customer will authenticate / provide another card / leave unpaid for follow-up. Do not falsely mark paid/arrived-and-paid on an unsuccessful charge. Payment and attendance states remain distinct.
- **No automatic payment retries initially.** Contact customer and explicitly resolve. Future optional owner review after operating experience can authorize a new retry policy.
- Timeout is **outcome unknown**, not automatically declined. Reconcile provider records/events before another charge. Unique operation identities, database protections, webhook deduplication and explicit recovery must be tested before functional sandbox-payment readiness.
- Split failure preserves received funds: $75 due/$40 cash received/$35 card fails -> $40 received/$35 unpaid. Retry/reconcile only remaining operation; never charge full $75 again or fabricate cash reversal.

## 4. Tax categories and fee formula

| Taxable | Nontaxable |
|---|---|
| Ordinary admission; supervised play; party package and extra children/adults | Subscription/Unlimited fees/installments; Sunday/Weekday clubs; ordinary/partial/no-show cancellation fees; gift-card sale; grip socks |

Gift-card/credit tender does not remove tax on underlying taxable purchases. Owner can change future global tax rate and processing percentage; historical transactions retain their original categories/rate/calculations. **6.6% is staging-only**. Production UEZ rate remains pending; do not silently use staging rate in production.

- Default **3% processing fee**, on card-funded **pretax subtotal after discounts**, never on sales tax. No fee on cash/check/Zelle/gift-card/credit portion. Includes applicable card-funded membership installments, cancellation charges and gift-card sales. No owner-specified maximum or debit exclusion was requested; owner reports provider/network allowance, not independently verified merchant terms.
- Banquest automatic surcharge is owner-reported **disabled**. Confirm settings during integration to prevent duplicate fee.
- Tax applies to taxable items **and the processing fee attributable to those taxable items**. Nontaxable-item fee is not taxed. Latest owner formula supersedes earlier fee-on-tax-inclusive-total recommendations.
- Customer/email displays **one Credit-card processing fee** total and **one Sales tax** total; internal taxable/nontaxable fee allocation is not two fees.
- For full card payment, let B=pretax subtotal, T=taxable subtotal, r=card-fee rate, s=sales-tax rate. Fee=B×r; tax=T×s+(taxable allocated fee)×s; total=B+fee+tax.
- Split methods: owner approved proportional allocation of card-funded purchase across taxable/nontaxable components, without staff assigning individual items. Preserve exact allocated cents, actual tender amounts and reconciliation. Fixed cash/gift-card amounts are actual payment amounts, not automatically pretax allocations.
- Example arithmetic uses decimal amounts, fee rounded to cents, combined tax rounded to cents. Establish deterministic line allocation/rounding and test sum reconciliation in implementation; do not introduce binary floating-point money drift.

Approved checkout sentence (render configured percentage):

> A credit-card processing fee of 3% will be added to any amount charged to a credit card. This fee does not apply to amounts paid by cash, check, Zelle, or gift card.

### Regression examples — 6.6% staging, all card unless stated

| Purchase | Pretax | Fee | Combined sales tax | Total |
|---|---:|---:|---:|---:|
| 2 ordinary children | $30.00 | $0.90 | $2.04 | **$32.94** |
| 1 Subscription place, first month | $17.99 | $0.54 | $0.00 | **$18.53** |
| 1 ordinary child+1sock | $16.99 | $0.51 | $1.02 | **$18.52** |
| 3 children total+2adults; purchase2Subscription places;1ordinary admission remains | $50.98 | $1.53 | $1.02 | **$53.53** |
| 5 children total+2adults; purchase2Subscription places;3ordinary admissions remain | $80.98 | $2.43 | $3.06 | **$86.47** |
| $100 gift-card sale | $100.00 | $3.00 | $0.00 | **$103.00** |
| $289 party less15% | $245.65 | $7.37 | $16.70 | **$269.72** |

Three-child example: membership35.98+ordinary15=50.98; fee50.98×3%=1.53; taxable admission fee15×3%=.45; tax(15+.45)×6.6%=1.02. Five-child example is35.98+45, not a pricing-rule change. Never use $5.98 as adjusted total from an admission that was not paid.

Online combined purchase: three-child case collects membership **$37.06 now**, visit **$16.47 at arrival**; five-child case membership **$37.06 now**, visit **$49.41 at arrival**. One combined email does not mean one immediate charge for a future visit. At in-person finalization the adjusted purchase may be collected together. Actual per-charge rounding must reconcile displayed totals.

Proportional split example:30taxable+20nontaxable=50pretax. Each method covers **half the pretax purchase** (25base=15taxable+10nontaxable):

| Allocation | Cash | Card |
|---|---:|---:|
| Pretax base | $25.00 | $25.00 |
| Fee | $0.00 | $0.75 |
| Combined tax on share+applicable fee | $0.99 | $1.02 |
| Actual payment | **$25.99** | **$26.77** |

Summary50subtotal+.75fee+2.01tax=**52.76**. This is not a customer handing over exactly$25cash; actual-tender input needs consistent inclusive allocation.

Already-paid cash conversions at6.6%:1child+1adult15+.99tax=15.99paid ->17.99Subscription, reverse replaced admission/tax,2.00additional before any new card fee.2children+2adults ordinary35+2.31=37.31paid ->35.98Subscription,1.33customer credit. For original card payment keep original fee nonrefundable; new card charge has its own fee, not waived.

**Still open:** tax on retained original processing fee after conversion. Example15admission+.45fee+.99admission tax+.03fee tax=16.47. Admission and .99 reverse; .45 fee remains. Whether .03 remains/reverses awaits owner/accountant. Do not silently decide or call it resolved.

## 5. Banquest documented capabilities and limits

Reviewed public specifications in the reconstruction task:

- [API v2 specification](https://docs.banquestgateway.com/api/v2/spec)
- [Hosted Tokenization v0.3](https://docs.banquestgateway.com/tokenization/v0.3)
- [Webhook specification](https://docs.banquestgateway.com/schemas/webhooks/webhooks-v1.yml)
- [Banquest API landing page](https://banquest.com/api/)

Direct documentation routes returned HTTP404 with a browser-application shell, but root/assets and underlying specifications loaded. Earlier proxy403 failures were resolved by allowing the documented hosts. Successful public GET is not authenticated account readiness.

| Observed specification | Implementation consequence |
|---|---|
| HostedTokenization uses gateway iframe and public Tokenization key beginning `pk_` | Raw card fields stay provider-side. Private API source key/PIN never go to browser. |
| API Basic authentication source-key:PIN; User-Agent identifies application | Server-only authentication and environment-specific endpoints; no actual values in docs. |
| Nonce one-use, expires after15minutes | Exchange at booking for durable stored provider method; do not save nonce until next-day arrival. |
| Payment-method creation from nonce/token/reference; source charge supports `pm-`/`tkn-`/`ref-`/`nonce-` and separate amount | Delayed charging and changed final quantities are documented; fraud/account/3DS rules still need sandbox verification. |
| Payment-method GET returns expiry/brand/last4; PATCH/DELETE available | Read metadata without deliberately authorizing; do not persist expiry/CVV locally. Removal scope needs verification. |
| Saved-card creation explicitly does not verify validity; Verification is a distinct request | No automatic issuer verification/hold; owner accepts later decline possibility. Public docs do not establish all lookup/verification fees. |
| Source charges ignore extra CVV fields | Do not pretend adding CVV to an old source validates it; new secure entry/provider-supported flow required. |
| Flags for recurring/installment/customer-initiated/cardholder presence | Map actual purchase type correctly; fixed-term membership classification and processor capabilities require validation. |
| Recurring schedules exist; documented statuses include next-day retries | Need no-retry and exact New York/month-end behavior; do not blindly use defaults. App-managed due jobs are an implementation option. Omit provider receipt emails. |
| `ignore_duplicates` false by default | Duplicate detection is not proof of client-key idempotency. No explicit idempotency-key contract found in reviewed spec; design reconciliation. |
| HTTPS webhooks have unique event ID; `X-Signature`, raw-body HMAC-SHA256 endpoint key | Verify authenticity, constant-time comparison, deduplicate repeated deliveries; acknowledgement is not successful business processing. |
| Refund by original reference after settlement; void/reversal alternatives before settlement | Select correct operation and exact amount; don't default to refunding nonrefundable fee. |
| Optional3DS through Paay | Account enablement/cost/authentication-required recovery unverified, not automatically mandatory or configured. |
| Gateway can auto-add mandatory surcharge and return revised amounts | Owner reports disabled; ensure no duplicate3% and reconcile actual returned charge. Gateway reporting descriptions do not override owner's accountant-directed tax policy. |

Sandbox/production bases: `https://api.sandbox.banquestgateway.com/api/v2/` and `https://api.banquestgateway.com/api/v2/`. Source/key permissions, webhook key, tokens, API PIN and test-card PDF must be transferred securely when integration is authorized; never put values here. Examples of environment variable names are not proof installed configuration. No API/provider operations are authorized by this document.

## 6. Owner-supplied sandbox instructions

Owner has test-card PDF; card numbers are deliberately not committed. Provider states sandbox normally Fiserv unless alternate processor requested. **Actual account processor remains unidentified**; establish from configuration/provider before claiming processor-specific tests passed. This does not block general staging development.

| Fiserv test amount | Expected supplied result |
|---|---|
| $1.00–$100.00 | Generally approval, subject to specific exceptions/processor |
| **$45.67** | No Host Response, timeout-reversal test |
| **$105.00** | Generic decline |
| **$101.31** | Invalid account number decline |
| **$101.06** | Response106 |
| **$109.02** | Error902 |

Fiserv allows any AVS/CVV test values; TSYS needs supplied specific test CVVs and often declines below$1. Do not reduce instructions to “all below100approve” or “all above100error.” Changing amount to explore sandbox responses is test activity only, never a production billing workaround.

Sandbox transactions **cannot move to live**. Separate credentials/data/endpoints; verify production settings before eventual separately approved launch. Functional staging must test duplicate submission, network timeout/outcome unknown, webhook replay, insufficient/declined/invalid card, card replacement/removal, tax/split allocation, membership due dates/no retries, and refund/void behavior. Public specification review alone does not pass these checks.
