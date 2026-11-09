# Design review V4

[Open review](index.html) · [Home desktop](01-home-desktop.jpg) · [Home phone](01-home-phone.jpg)

Removes decorative 01/02/03 labels from the homepage cards. Adds a brief hero
entrance, card lift/shadow for mouse hover and keyboard focus, and small hero
button/intro link movement. No looping animation or JavaScript dependency.
Reduced-motion visitors receive none of these animations and no smooth scrolling.
All photos, wording and original logo from V3 are preserved. V1–V3 remain on disk.

All 16 pages passed Chromium desktop/phone layout and asset checks. Separate
browser checks verified hero animation, hover and keyboard focus with both normal
and reduced motion. Screenshots use reduced motion and cannot demonstrate motion;
open the HTML review or the eventual deployed preview to see the effects.
Deployment-bundle validation, Ruff lint/format and whitespace checks passed.
No database migration or hosted deployment occurred.
