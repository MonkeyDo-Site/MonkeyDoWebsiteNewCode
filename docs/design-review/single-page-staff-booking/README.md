# PR #36 — single-page backend booking review

[Draft PR #36](https://github.com/MonkeyDo-Site/MonkeyDoWebsiteNewCode/pull/36) · [Scope and agreed behavior](../../SINGLE_PAGE_STAFF_BOOKING.md)

Please refer to the screen number when commenting. This gallery has **9 screens**, each at **desktop 1440px** and **phone 390px**. All changes stay in the same draft PR until owner review is complete.

Customer search, session/date, visible child/total/supervised capacity, supervised play, attendee/sock counts, expected payment method, owner capacity override and closing the whole session remain available. The estimate, custom admissions/complimentary controls, waiver details, secure card details and one final Confirm booking action are on the same page.

**Backend reservation timing:** valid customer/session/count selections reserve places for 30 minutes. Changes to those selections update that reservation. Waiver/payment edits, polling and leaving the tab open do not extend it. Expired places become available automatically. The owner can explicitly reserve them again, subject to capacity. Confirmation replaces the temporary reservation with a permanent booking; ordinary admission is collected at arrival. **The public customer flow is unchanged**: its existing 20-minute form timeout and reservation at successful confirmation remain.

**Review fixtures:** customer details, signatures and card fields are fictional. Hosted card fields and provider outcomes are simulated. These images do not establish the actual Banquest iframe layout or auto-advance behavior; that provider check remains deferred. No external payment, email or storage provider was contacted.

## Screen index

| Screen | State | Desktop | Phone |
|---|---|---|---|
| **01** | All booking controls, live estimate, capacity counts and one confirmation button | [Desktop](STAFF-v1-01-standard-1440.png) | [Phone](STAFF-v1-01-standard-390.png) |
| **02** | Custom admissions price beneath the estimate; socks remain separate | [Desktop](STAFF-v1-02-custom-price-1440.png) | [Phone](STAFF-v1-02-custom-price-390.png) |
| **03** | Fully complimentary booking; no card or payment required | [Desktop](STAFF-v1-03-complimentary-1440.png) | [Phone](STAFF-v1-03-complimentary-390.png) |
| **04** | Record a named signed paper waiver on the booking page | [Desktop](STAFF-v1-04-paper-waiver-1440.png) | [Phone](STAFF-v1-04-paper-waiver-390.png) |
| **05** | Sign an electronic waiver without navigating away from the booking | [Desktop](STAFF-v1-05-electronic-waiver-1440.png) | [Phone](STAFF-v1-05-electronic-waiver-390.png) |
| **06** | Owner capacity reminder; previous reservation and entered counts retained | [Desktop](STAFF-v1-06-capacity-warning-1440.png) | [Phone](STAFF-v1-06-capacity-warning-390.png) |
| **07** | Card-entry error preserves the booking details and reserved places | [Desktop](STAFF-v1-07-card-error-1440.png) | [Phone](STAFF-v1-07-card-error-390.png) |
| **08** | Expired backend reservation with explicit renewal; entries preserved | [Desktop](STAFF-v1-08-expired-reservation-1440.png) | [Phone](STAFF-v1-08-expired-reservation-390.png) |
| **09** | Single final action opens the confirmed booking; admission remains due at arrival | [Desktop](STAFF-v1-09-confirmed-1440.png) | [Phone](STAFF-v1-09-confirmed-390.png) |

## 01 — All booking controls, live estimate, capacity counts and one confirmation button

[Open desktop image](STAFF-v1-01-standard-1440.png) · [Open phone image](STAFF-v1-01-standard-390.png)

![Screen 01: desktop](STAFF-v1-01-standard-1440.png)

<details>
<summary>Phone image</summary>

![Screen 01: phone](STAFF-v1-01-standard-390.png)

</details>

## 02 — Custom admissions price beneath the estimate; socks remain separate

[Open desktop image](STAFF-v1-02-custom-price-1440.png) · [Open phone image](STAFF-v1-02-custom-price-390.png)

![Screen 02: desktop](STAFF-v1-02-custom-price-1440.png)

<details>
<summary>Phone image</summary>

![Screen 02: phone](STAFF-v1-02-custom-price-390.png)

</details>

## 03 — Fully complimentary booking; no card or payment required

[Open desktop image](STAFF-v1-03-complimentary-1440.png) · [Open phone image](STAFF-v1-03-complimentary-390.png)

![Screen 03: desktop](STAFF-v1-03-complimentary-1440.png)

<details>
<summary>Phone image</summary>

![Screen 03: phone](STAFF-v1-03-complimentary-390.png)

</details>

## 04 — Record a named signed paper waiver on the booking page

[Open desktop image](STAFF-v1-04-paper-waiver-1440.png) · [Open phone image](STAFF-v1-04-paper-waiver-390.png)

![Screen 04: desktop](STAFF-v1-04-paper-waiver-1440.png)

<details>
<summary>Phone image</summary>

![Screen 04: phone](STAFF-v1-04-paper-waiver-390.png)

</details>

## 05 — Sign an electronic waiver without navigating away from the booking

[Open desktop image](STAFF-v1-05-electronic-waiver-1440.png) · [Open phone image](STAFF-v1-05-electronic-waiver-390.png)

![Screen 05: desktop](STAFF-v1-05-electronic-waiver-1440.png)

<details>
<summary>Phone image</summary>

![Screen 05: phone](STAFF-v1-05-electronic-waiver-390.png)

</details>

## 06 — Owner capacity reminder; previous reservation and entered counts retained

[Open desktop image](STAFF-v1-06-capacity-warning-1440.png) · [Open phone image](STAFF-v1-06-capacity-warning-390.png)

![Screen 06: desktop](STAFF-v1-06-capacity-warning-1440.png)

<details>
<summary>Phone image</summary>

![Screen 06: phone](STAFF-v1-06-capacity-warning-390.png)

</details>

## 07 — Card-entry error preserves the booking details and reserved places

[Open desktop image](STAFF-v1-07-card-error-1440.png) · [Open phone image](STAFF-v1-07-card-error-390.png)

![Screen 07: desktop](STAFF-v1-07-card-error-1440.png)

<details>
<summary>Phone image</summary>

![Screen 07: phone](STAFF-v1-07-card-error-390.png)

</details>

## 08 — Expired backend reservation with explicit renewal; entries preserved

[Open desktop image](STAFF-v1-08-expired-reservation-1440.png) · [Open phone image](STAFF-v1-08-expired-reservation-390.png)

![Screen 08: desktop](STAFF-v1-08-expired-reservation-1440.png)

<details>
<summary>Phone image</summary>

![Screen 08: phone](STAFF-v1-08-expired-reservation-390.png)

</details>

## 09 — Single final action opens the confirmed booking; admission remains due at arrival

[Open desktop image](STAFF-v1-09-confirmed-1440.png) · [Open phone image](STAFF-v1-09-confirmed-390.png)

![Screen 09: desktop](STAFF-v1-09-confirmed-1440.png)

<details>
<summary>Phone image</summary>

![Screen 09: phone](STAFF-v1-09-confirmed-390.png)

</details>
