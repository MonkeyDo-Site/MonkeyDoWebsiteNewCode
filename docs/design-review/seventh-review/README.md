# Seventh review — first review round

## Public capacity recovery — two actions

The capacity-error screen now offers **Adjust the amounts in my booking** and **Choose another session**. Adjust returns to the same selected session with the latest attempted play type, attendee counts, socks and payment method. Those amounts still require a fresh capacity/price check; no booking or capacity hold is created by recovery. Choose another session opens session selection. These v13 screenshots supersede the v12 public error screen below.

| State | Desktop | Phone |
|---|---|---|
| Capacity error with both buttons | [Full image](SEVENTH-v13-capacity-recovery-1440.png) | [Full image](SEVENTH-v13-capacity-recovery-390.png) |
| Returned form with attempted amounts | [Full image](SEVENTH-v13-restored-amounts-1440.png) | [Full image](SEVENTH-v13-restored-amounts-390.png) |

## Conditional supervised exception and public Continue

The owner-only supervised exception checkbox is absent on a regular edit screen, including when Supervised Play is first selected. It is rendered, unchecked, only after the server returns the relevant supervised-play warning. The approved booking-specific exception remains available after that warning. These v12 images replace the earlier supervised-exception example.

Public Continue currently returns a separate error page with the capacity message and a **Choose a session** link; attendee controls are not shown on that response. This is a capture of existing behavior, with no public-flow change in this follow-up.

| State | Desktop | Phone |
|---|---|---|
| Edit before warning — no exception checkbox | [Full image](SEVENTH-v12-edit-before-warning-1440.png) | [Full image](SEVENTH-v12-edit-before-warning-390.png) |
| Edit after warning — exception checkbox visible | [Full image](SEVENTH-v12-edit-after-warning-1440.png) | [Full image](SEVENTH-v12-edit-after-warning-390.png) |
| Public capacity error after Continue | [Full image](SEVENTH-v12-public-after-continue-1440.png) | [Full image](SEVENTH-v12-public-after-continue-390.png) |

## Backend capacity reminder

The owner’s edit screen uses a short reminder with actual capacity/booked counts: “The child capacity for this session is 35, of which 30 slots are already booked. Check the owner override checkbox to proceed.” Non-owner staff are directed to ask the owner. The existing owner-only override and public guidance remain enforced. Form-level errors span the edit form instead of a single narrow grid column. These v11 images replace the earlier v8/v10 edit-capacity examples. The special-price notice is shown only when a special admissions price is saved.

| Page | Desktop | Phone |
|---|---|---|
| Edit capacity reminder | [Full image](SEVENTH-v11-edit-capacity-reminder-1440.png) | [Full image](SEVENTH-v11-edit-capacity-reminder-390.png) |

## Completed-arrival payment total

After arrival, Payment shows **Total received: $42.30** above the existing **$32.30 cash** and **$10.00 Zelle** entries, replacing the Zelle-only received headline. Pending/failed operations are excluded; advance receipts count once. Unreturned overpayments remain included until their manual refund is actually recorded, after which the total is labelled “after refunds.”

| Page | Desktop | Phone |
|---|---|---|
| Booking after cash/Zelle arrival | [Full image](SEVENTH-v9-booking-total-received-1440.png) | [Full image](SEVENTH-v9-booking-total-received-390.png) |

## Capacity warnings and override controls

Actual application screens with fictional local records. Public customers see capacity warnings and alternatives; override controls are available only to authorized staff/owners. The arrival override applies to that arrival. The owner’s supervised exception applies only to the selected booking and does not itself override child/combined capacity.

| State | Desktop | Phone |
|---|---|---|
| Public child limit | [Full image](SEVENTH-v8-01-public-child-limit-1440.png) | [Full image](SEVENTH-v8-01-public-child-limit-390.png) |
| Public combined child/adult limit | [Full image](SEVENTH-v8-02-public-total-limit-1440.png) | [Full image](SEVENTH-v8-02-public-total-limit-390.png) |
| Public supervised limit | [Full image](SEVENTH-v8-03-public-supervised-limit-1440.png) | [Full image](SEVENTH-v8-03-public-supervised-limit-390.png) |
| Arrival capacity warning and override | [Full image](SEVENTH-v8-04-arrival-capacity-override-1440.png) | [Full image](SEVENTH-v8-04-arrival-capacity-override-390.png) |
| Edit booking capacity warning and owner override | [Full image](SEVENTH-v8-05-edit-capacity-override-1440.png) | [Full image](SEVENTH-v8-05-edit-capacity-override-390.png) |
| Owner supervised-play exception | [Full image](SEVENTH-v8-06-owner-supervised-exception-1440.png) | [Full image](SEVENTH-v8-06-owner-supervised-exception-390.png) |

All twelve desktop/phone captures passed overflow and JavaScript-error checks. Rejected edits left the example bookings unchanged; no successful override, arrival, payment or email was submitted.

## Price-adjustment summary

A comparison with the original booked amount appears below current line items and above received payments/balance. Each image shows the $55.29 → $42.30 example, with cancelled admission, existing cancellation fee and tax adjustment. The edit preview updates before Save; the saved booking uses accepted financial amounts.

| Page | Desktop | Phone |
|---|---|---|
| Arrival with original/adjusted comparison | [Full image](SEVENTH-v7-price-summary-arrival-1440.png) | [Full image](SEVENTH-v7-price-summary-arrival-390.png) |
| Edit booking before saving | [Full image](SEVENTH-v7-price-summary-edit-1440.png) | [Full image](SEVENTH-v7-price-summary-edit-390.png) |
| Saved adjusted booking | [Full image](SEVENTH-v7-price-summary-saved-booking-1440.png) | [Full image](SEVENTH-v7-price-summary-saved-booking-390.png) |


## Current arrival update — paper-waiver entry

The arrival waiver card includes **Paper waivers signed**. Checking it expands the actual signing date, adult name, relationship and covered minors on this page. Save updates the active-waiver list without losing attendee/payment changes. Arrival confirmation stays disabled until the paper details are saved or the checkbox is cleared.

| State | Desktop | Phone |
|---|---|---|
| Arrival, paper entry collapsed | [Full image](SEVENTH-v5-arrival-paper-collapsed-1440.png) | [Full image](SEVENTH-v5-arrival-paper-collapsed-390.png) |
| Arrival, paper entry expanded | [Full image](SEVENTH-v5-arrival-paper-expanded-1440.png) | [Full image](SEVENTH-v5-arrival-paper-expanded-390.png) |

These arrival images supersede the arrival images from the first review round below. Other page images remain applicable.


Actual application screenshots using fictional local records, at 1440px and 390px. Full pages, no cropping. No external payment, email or storage operation was sent. PR #33 remains draft during review.

| Page | Desktop | Phone |
|---|---|---|
| Arrival — cash | [Full image](SEVENTH-v3-01-arrival-1440.png) | [Full image](SEVENTH-v3-01-arrival-390.png) |
| Arrival — Zelle overpayment after fewer children arrive | [Full image](SEVENTH-v3-02-arrival-zelle-1440.png) | [Full image](SEVENTH-v3-02-arrival-zelle-390.png) |
| Booking — before arrival | [Full image](SEVENTH-v3-03-booking-upcoming-1440.png) | [Full image](SEVENTH-v3-03-booking-upcoming-390.png) |
| Booking — paid | [Full image](SEVENTH-v3-04-booking-paid-1440.png) | [Full image](SEVENTH-v3-04-booking-paid-390.png) |
| Booking — manual Zelle refund due | [Full image](SEVENTH-v3-05-booking-refund-1440.png) | [Full image](SEVENTH-v3-05-booking-refund-390.png) |
| Edit booking | [Full image](SEVENTH-v3-06-edit-booking-1440.png) | [Full image](SEVENTH-v3-06-edit-booking-390.png) |

The Zelle example reduces three children to two before confirming arrival: $55.29 previously received, $42.30 revised total including the existing $3 partial cancellation fee, and $12.99 manual refund due. Existing owner-special-price exceptions still omit automatic partial fees.

Screenshots show the local application; real provider-field behavior is a separate hosted check. Automatic month-to-year advancement remains pending the owner’s Banquest inquiry.
