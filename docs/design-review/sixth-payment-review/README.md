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
