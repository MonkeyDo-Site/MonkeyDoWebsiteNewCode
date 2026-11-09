# Design review V17

[Open review](index.html) · [Full homepage JPG](01-home-desktop.jpg)

The remaining homepage sections now fade/slide gently as they enter the viewport:
intro, About, play options, Memberships, Clubs & Parties, Gift Cards and Contact.
This uses progressive CSS view timelines with no scripts or hidden-content state.
Browsers without support retain fully visible static content. Reduced-motion
visitors get no scroll animation; keyboard focus also stops motion on that card.
Standalone pages remain static. Images, wording and operating rules are unchanged.

Chromium checks verified actual scroll progress, reduced motion, focus visibility
and no overflow at desktop and phone widths across 22 section elements. All 17
review screens passed reduced-motion image/layout checks. JPGs are static and do
not show animation. Earlier reviews remain preserved. Nothing has been deployed.
