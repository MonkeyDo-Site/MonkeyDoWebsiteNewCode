# November design comments — implementation and review checkpoint

Source: owner's complete Design comments.docx, including ten embedded images. The owner clarified that the Weekday Club age line must be removed. Apply content through shared partials to Home and corresponding standalone pages. No booking, payment, membership eligibility or cancellation rules change.

Implemented: white circle behind booking monkey; About tiles reordered Climbing/Imaginative/Game/Toddler; Open Play line breaks and corrected capitalization/baby wording; supervised CTA arrow; photo scroll animation with reduced-motion support; membership heading/subheading, distinct cream/blue card colors and supplied balloons; individual club cards and requested copy; no Weekday Club age; party concept/photo, wording, bullets and numbered contact CTA; gift-card section copy and exact-logo CSS mockup; contact image placeholder and revised text/order.

The supplied photos/balloons extracted from the document are preserved byte-for-byte in `brand-assets/design-comments-originals`, with checksums. The three new WebP club/party images are AI-generated design concepts, not documentation of an actual club session or party. The club scenes edit the owner's supplied room photos; originals remain intact. The current site's original children/approved child edits are unchanged.

The physical gift-card concept is composed in HTML/CSS around the unchanged original logo; it does not regenerate the official logo. The wall-logo photo is a branded placeholder awaiting the owner's photo. Temporary image concepts require owner review.

Owner requested an alternate text-color preview using the original logo's lighter green/pink. This palette is injected only into review screenshots, not enabled in site code. Default text colors remain dark green/berry pending review; compare readability before adopting lighter colors.

No pull request or deployment until the owner has seen all updated page screenshots, as requested. Screenshots and review artifacts are generated outside the application source.
