# November design comments — implementation and review checkpoint

Source: owner's complete Design comments.docx, including ten embedded images. The owner clarified that the Weekday Club age line must be removed. Apply content through shared partials to Home and corresponding standalone pages. No booking, payment, membership eligibility or cancellation rules change.

Implemented: white circle behind booking monkey; About tiles reordered Climbing/Imaginative/Game/Toddler; Open Play line breaks and corrected capitalization/baby wording; supervised CTA arrow; photo scroll animation with reduced-motion support; membership heading/subheading, distinct cream/blue card colors and supplied balloons; individual club cards and requested copy; no Weekday Club age; party concept/photo, wording, bullets and numbered contact CTA; gift-card section copy and the owner-selected envelope/ribbon image; contact image placeholder and revised text/order.

The supplied photos/balloons extracted from the document are preserved byte-for-byte in `brand-assets/design-comments-originals`, with checksums. The three new WebP club/party images are AI-generated design concepts, not documentation of an actual club session or party. The club scenes edit the owner's supplied room photos; originals remain intact. The current site's original children/approved child edits are unchanged.

The owner selected the generated envelope/ribbon gift-card concept shown in chat to replace the first CSS mockup. It is included as a temporary gift-card presentation; the original master logo and header logo remain unchanged. The wall-logo photo is a branded placeholder awaiting the owner's photo. Temporary image concepts require owner review.

Owner requested an alternate text-color preview using the original logo's lighter green/pink. This palette is injected only into review screenshots, not enabled in site code. Default text colors remain dark green/berry pending review; compare readability before adopting lighter colors.

No pull request or deployment until the owner has seen all updated page screenshots, as requested. Screenshots and review artifacts are generated outside the application source.

## Second owner review

Move the party eyebrow and MonkeyDo Parties title outside the colored content card. Replace the CSS gift-card drawing with the specific generated gift-card/envelope/ribbon image selected by the owner. Move the contact logo outside the contact-details card, above We look forward to seeing you. Add alternating cream and pale-sage full-width homepage backgrounds, with separate bands for About, play, membership, clubs, parties, gift cards and contact. Shared standalone sections receive the same heading/image positioning changes. No pull request or deployment yet; prepare a fresh screenshot pack.

## Third owner review

Keep Room to explore and its cards on warm cream; start pale sage at About and alternate the remaining bands. Align Open/Supervised Play actions along the bottom when side by side, with more breathing room between supervised text groups. Lower the contact-details box to align with the welcome heading on desktop; keep the phone layout compact. Add the four photos from MonkeyDo4 images.docx in document order beneath the membership cards only on the standalone Memberships page. Keep them in one horizontal row; use an internally scrollable row on narrow screens. Preserve the supplied PNGs under membership-gallery-originals with checksums. No new generated imagery, pricing changes or backend changes.

## Fourth owner review

Use warm cream for the home membership, gift-card and contact sections; add a thin separator above membership. Add substantially more vertical breathing room and a fine divider before the standalone membership photo row. Provide both clubs-off launch and clubs-on homepage screenshot versions from the same template. Add an owner-only Website settings control using the existing clubs_visible field; changes are audited and stale saves are rejected. Hiding clubs also changes public navigation/page titles to Parties, without removing party content or deleting data. Existing database preferences remain intact: after deployment, the owner must switch clubs off for launch using Website settings. No database migration is required. Both screenshot variants are preserved; only local synthetic preview data is toggled during capture.
