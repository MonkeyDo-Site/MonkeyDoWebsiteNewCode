# MonkeyDo Waiver Sources

This directory documents waiver source provenance. Waiver files themselves belong in private Cloudflare R2 storage and must not be committed to Git.

## Draft source

- Original filename: `MD Waiver (1).pdf`
- SHA-256: `f159515b1c1c531bc57fce6a8813aa63f38f25da014459807759495f028ccdb6`
- Status: Draft/reference only; not approved for production or legal reliance.
- HTML transcription: [`../../waiver.html`](../../waiver.html)

The original draft and every future approved source must be stored as a distinct, immutable object in the private Cloudflare R2 waiver bucket. The application database on DigitalOcean should record each object's secure reference, checksum, version, and status. Signed customer waivers and source waiver documents must never be stored in this directory or committed to Git.
