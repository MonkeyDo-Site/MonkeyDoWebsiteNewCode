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

## V8: homepage booking button and age line

Owner requested moving the booking button slightly lower without shifting the
remaining page text, adding the original logo monkey to the button, and enlarging
the ages 1–10 line. Use a 10px relative button offset, a decorative extracted
original monkey, and an 18px age line. Verify spacing at desktop and phone widths.

## V9: homepage card wording

Come play link: “See available play sessions”. Celebrate together description:
“A private party filled with MonkeyDo fun, family and friends.” Earlier requested
card-number removal, photos, typography and motion remain in place. This is a
wording change only; party package inclusions and booking rules are unchanged.

## V10: restore approved membership marketing bullets

Restored the approved Subscription and Unlimited marketing copy from
MEMBERSHIPS.md and AG P20875–P20882: per-child/month prices, benefit bullets,
15% party discount wording, three-month minimum on each card, and the Unlimited
exclusion footnote. Removed the shortened paragraph paraphrases. This corrects
an implementation omission; no renewed owner approval of the copy is required.
Pricing and benefit calculation rules are unchanged.

## V11: separate program navigation and continuous homepage

Owner requested Memberships as a separate page from Clubs & Parties, and a
homepage continuing through About, Memberships, Clubs & Parties and Contact Us.
Implemented both dedicated routes/navigation and full scrolling homepage sections
from shared templates. Earlier combined route stays unlinked for old bookmarks.
Clubs visibility applies to dedicated and homepage sections. Latest owner request
supersedes the earlier combined-program page inventory; business rules unchanged.

## V12: play-session jump and separate homepage gift-card section

Come play now says “See play sessions” and links to #play-sessions on the same
homepage. The target contains both Open Play and Supervised Play and retains its
booking link. Gift Cards is its own homepage section after Clubs & Parties and
before Contact Us, using the approved in-person purchase notice. The notice also
remains on the dedicated Clubs & Parties page and in Contact information. No
digital gift-card checkout or balance ledger is added.

## V13: livelier play cards and membership headings

Added a thin divider before play options, eyebrow “Ready to play?” and full-size
heading “Open play or supervised play”. Open/Supervised Play now have sage/coral
card backgrounds and owner-supplied activity photos. Descriptions sit immediately
below titles, separated from the detail lists. Memberships has eyebrow “More ways
to go bananas” plus decorative original-monkey imagery. Removed the named-children
sentence from current public copy; anonymous membership allocation rules remain
unchanged internally. Earlier approved pricing and benefit bullets are preserved.

## V14: owner-selected play-card image subjects

Open Play uses a close crop of the child tossing green foam blocks. Supervised
Play uses the child climbing on the monkey bars. Both use the supplied original
photo without generative editing, with 4:3 display proportions to keep subjects
visible. Wording, card colors, spacing and other requested changes stay intact.

## V15: play-option booking buttons

Open Play button: “Book your session now →” with a decorative arrow.
Supervised Play now has a “See available sessions” button. Both point to the
booking schedule. Tightened button icon gap and constrained width for phones;
photo choices, copy and business rules remain unchanged.

## V16: age line before homepage booking button and arrow

Moved “Designed for little monkeys ages 1–10.” onto the next line of the hero
paragraph, before the booking button, using the paragraph's font and line spacing.
The button retains the original monkey and now ends with a decorative right arrow.
This later owner request supersedes the prior age-line/buton placement; all other
approved content, imagery and behavior remain unchanged.

## V17: scroll motion for the remaining homepage sections

Add gentle CSS view-timeline fade/slide effects to the intro and About, play,
Memberships, Clubs & Parties, Gift Cards and Contact headings/cards. Effects are
homepage-scoped, require browser support and no reduced-motion preference, and
stop on keyboard focus. Unsupported browsers and reduced-motion visitors retain
fully visible static content. No scripts, automatic scrolling, flashing or loops
are introduced; frozen preview script restrictions remain unchanged.

## V18: age-line gap and darker pink preview

Added 14px space before the homepage ages 1–10 line, keeping it above booking and
in the paragraph font. Preview a deeper rose-pink #AA405A on jungle/accent em text
and the eight requested area/play/club headings. This replaces the brown accent;
original logo and photographs remain unchanged. Calculated text contrast is 5.47:1
on cream, 4.82:1 on sage cards and 4.58:1 on coral cards. Color is proposed for
owner review, not independently marked approved.
