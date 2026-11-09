# Design review V3

[Open review](index.html) · [Home desktop](01-home-desktop.jpg) · [Home phone](01-home-phone.jpg)

V3 adds the five owner-uploaded child/activity photos to V2's Nunito typography
and framed ad hero. Homepage cards now each have a photo. About uses matching
photos for Imaginative Play, Climbing Area and Toddler Zone; Game Room retains
its original matching image. Original uploaded files and logo remain unchanged.
V1 and V2 artifacts are preserved in their own folders.

Verified all 16 read-only screens at 1440px and 390px in Chromium: images load,
no horizontal overflow or JavaScript errors. Extra checks confirm Nunito loads
and all three card images keep a 4:3 display ratio. All 246 regression tests pass
on PostgreSQL 17. Existing deployment helper validates all three review bundles.
This is prepared source, not a deployed release or functional booking site.
