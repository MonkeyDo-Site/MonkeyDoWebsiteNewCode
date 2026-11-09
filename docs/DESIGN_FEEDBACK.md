# Design feedback tracker

Previous review: **V1**, frozen application source `7a7b674`, November 8, 2026 (New York). [Open review gallery](design-review/v1/README.md).

The owner authorized a stable design preview and separate continuing backend work. No page design is marked approved by that authorization. The owner has now requested the first design updates; V2 is prepared below.

| ID | Review version | Page / screen | Device | Owner comment | Status | Change PR / review evidence |
| --- | --- | --- | --- | --- | --- | --- |
| D01 | V2 | All pages | Both | Rounded ad body/button font; similar font permitted for now | Ready for owner review | Locally hosted Nunito; original logo unchanged |
| D02 | V2 | Home hero | Both | Use the photo in the ad; cropping with the original border is permitted | Ready for owner review | Original photo composition and sage frame isolated; promotional text omitted |
| D03 | V2 | About and home cards | Both | Use five new child/activity photos to liven up the pages | Ready for owner review | ZIP originals now preserved; photos added to all three homepage cards and matching About areas in V3 |

Statuses: **Pending** (recorded); **In progress**; **Ready for owner review**; **Approved** (explicit owner approval); **Deferred** (include reason).

## Working agreement

- Keep V1 screenshots and HTML fixed throughout its review. Reference version, page and phone/computer for every comment. Preserve original wording when recording feedback.
- Link each change to its implementation PR. Make design changes separately from backend work where practical; run the relevant responsive checks before marking ready for review.
- Record approval only after the owner reviews the change. Clarify materially conflicting comments instead of silently dropping earlier approved decisions.
- Existing unfinished requirements stay on the build plan. Active membership data, waiver coverage and payment workflows are not omissions requiring the owner to request them again.
- Create V2 at an agreed checkpoint. Pin its source/review commits and keep V1 accessible. Never regenerate an already published version in place.
- Backend work continues on its own branches/PRs. The review host must serve a pinned release from a separate directory, never the moving development checkout.

## Preview access

The read-only GitHub gallery is ready. A hosted browser URL remains blocked on secure server access: the environment reports no DigitalOcean/SSH credential binding. Obtain the Droplet IP/SSH username and arrange a protected SSH credential through environment settings; never put passwords or private keys in chat, repository files or screenshots. No server or DNS changes have occurred.

Owner-guided setup is now underway on replacement host 107.170.1.143. The owner runs server commands in their own SSH session; cloud-agent SSH remains unconfigured. See [HOSTED_DESIGN_PREVIEW.md](HOSTED_DESIGN_PREVIEW.md) for the installation checkpoint. V1 design files remain unchanged.

## V2 review

First typography/hero revision is in [V2](design-review/v2/index.html). V1
files remain unchanged. The hosted source now selects V2 when this release is
explicitly deployed; no server update has occurred during preparation.

V3 adds the newly uploaded activity photos to V2 typography/hero changes. V1 and
V2 remain preserved. Original source photos are used without retouching.

## V4: homepage motion and card labels

The owner asked to remove decorative card numbers and add animations. Labels
01/02/03 are removed. Hero text/photo use one brief entrance; cards lift on mouse
hover or keyboard focus; hero button and intro link have slight hover/focus
movement. Motion is disabled for prefers-reduced-motion. V4 preserves previous
review folders. These changes are ready for owner review, not owner-approved.

## V5: clarify the two play-session choices

Added the owner's line “Choose open play or supervised play, when available.”
immediately above the two About-page options. The first option is titled
“Open play” to match that wording. Prices, ages and attendance rules are unchanged.
Prepared for owner review; earlier review versions remain preserved.

## V6: Open Play line-by-line wording

Replaced the Open Play paragraph with the owner's requested lines: Play
accompanied by an adult; Children ages 1-11: $15 each; 1 free adult; additional
adults ages 12 and up: $5 each; Babies under one are free. Separate paragraph:
“if you are coming just with a baby, there is a $15 admission.” Heading: Open Play.
This is customer-facing copy/layout; established pricing rules are unchanged.

## V7: Supervised Play wording

Used the owner's exact Supervised Play heading and lines: “Your child plays and
our capable staff supervises”; “For children ages 3-11”; “$18.99 per child”;
“Subscription members enjoy 25% off supervised play”. Separate paragraph:
“Supervised play is available for select sessions. Check the booking page to see
which sessions offer it.” This replaces the earlier public description; the
established booking cutoff remains an operational rule.
