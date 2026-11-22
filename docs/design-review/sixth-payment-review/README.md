# Payment Details — sixth batch review

Full-page Chromium captures of the actual local application at 1440px and 390px. Nothing is cropped. Open an image to inspect it at full size.

| Payment choice | Desktop | Phone |
| --- | --- | --- |
| Credit card | [Open](card-1440.jpg) | [Open](card-390.jpg) |
| Cash | [Open](cash-1440.jpg) | [Open](cash-390.jpg) |
| Check | [Open](check-1440.jpg) | [Open](check-390.jpg) |
| Zelle | [Open](zelle-1440.jpg) | [Open](zelle-390.jpg) |

[Credit card saved — Confirm booking enabled](card-saved-1440.jpg).

Fixtures are fictional. Provider card fields and external storage/gateway operations are simulated; these images demonstrate layout and local state transitions, not actual merchant card-brand acceptance or provider iframe rendering. No external payment was sent. Only the requested payment-page images are included.

The browser check also exercised an actual local new-customer flow: Back/Forward, required signing, separate coverage confirmation, payment-method change without another signature, save card, confirm once, and Back resolving to the saved receipt. All four payment choices were checked at both widths with no browser JavaScript errors or horizontal page overflow. The five progress steps occupy one row on desktop.

## Updated after image feedback

These images now show one Save card button, consolidated lower-page instructions, more separation below Switch payment method, and no public payment-policy checkbox or booking-only-card disclaimer. Saving the card enables a rose Confirm booking button and the explicit completion instruction. The sandbox acknowledgment remains staging-only.

[Short animation preview](confirm-booking-animation.webm) shows the actual local page changing to the rose button and three gentle pulses. Phone saved-card re-entry, focus/visibility and reduced-motion behavior were also verified. No booking is automatically confirmed by saving the card.
