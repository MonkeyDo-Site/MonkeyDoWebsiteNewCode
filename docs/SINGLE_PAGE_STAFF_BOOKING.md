# Single-page staff booking

The owner reported that backend booking still requires a reservation page followed by a separate setup page. Replace that create flow with one page containing customer/session/attendee controls, a live price estimate, an inline owner custom-admissions/complimentary control directly below the estimate, waiver details and secure payment details, and one final Confirm booking action.

Preserve ordinary admission collection at arrival, owner-only price/capacity permissions, special admissions with socks separate, full complimentary bookings without a card, named waivers and pending-waiver instructions, selected saved-card/new-card handling, separate staff future-use choice, uncertain-setup recovery and no automatic charge/retry. Do not change public booking or existing confirmed bookings.

Use private session drafts for the combined form. Previewing and changing choices must not create bookings or reserve places. An explicit final click may save/select the secure card, then atomically recheck capacity, create the booking, apply reviewed owner pricing and waiver details, bind the card and queue one confirmation. Preserve entered fields and a successfully saved card after validation failures. A repeated final request must not create another booking or confirmation. Card errors must not erase attendee entries. No ordinary admission charge occurs on confirmation.

Signing and paper-waiver details should be accessible from this page without losing the booking draft. Signed electronic evidence remains valid independently of a later booking failure. The current two-page setup route stays available for previously saved incomplete bookings until their setup is finished.

Build in a new draft PR because PR #35 is merged. Provide compact desktop/phone review images of standard, owner-priced/complimentary, waiver and error states. Merge/deployment follows owner review. Actual hosted Banquest rendering remains the deferred provider check; local provider frames/outcomes are simulated.
