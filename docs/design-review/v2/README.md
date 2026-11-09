# Design review V2

First owner-requested typography and homepage hero revision. [Open index](index.html).
Nunito is a temporary match for the ad's rounded body/button lettering. The hero
retains the ad's actual photo composition and sage border. V1 is preserved in its
own folder. Existing program copy, original logo and operational restrictions
remain unchanged. Five newly supplied inline child/activity images are pending
file upload; About and homepage card photo placement is not completed.

[Desktop homepage](01-home-desktop.jpg) · [Phone homepage](01-home-phone.jpg)

The source commit is recorded in manifest.json. All 16 read-only pages were
checked in Chromium at 1440px and 390px, with images loaded, no horizontal
overflow and no JavaScript errors. Controls remain disabled. Deployment requires
an explicit pinned release update through the existing helper; nothing here
sends emails, charges cards, or changes the database schema.
