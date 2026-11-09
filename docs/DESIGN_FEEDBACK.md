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
