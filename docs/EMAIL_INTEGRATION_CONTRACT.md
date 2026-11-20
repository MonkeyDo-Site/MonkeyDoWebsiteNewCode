# Customer mail delivery contract review

Reviewed November 19, 2026 against the official SDK source:

- [Resend webhook event types and payloads](https://github.com/resend/resend-node/blob/main/src/webhooks/interfaces/webhook-event.interface.ts)
- [Svix Python header adaptation](https://github.com/svix/svix-webhooks/blob/main/python/svix/webhooks.py)
- [Standard Webhooks Python signature implementation](https://github.com/standard-webhooks/standard-webhooks/blob/main/libraries/python/standardwebhooks/webhooks.py)

Resend email events carry a top-level type/created_at, data.email_id and optional
string-to-string tags. Delivery, bounce, complaint and failure statuses are
separate from successful API submission. The application sends a nonsecret local
message UUID tag and verifies the expected sender/recipient before using that tag
to reconcile a sending/unknown local attempt. Untagged unrelated account emails
are not associated with customer booking messages.

Verify the raw body with Svix's whsec_ base64-decoded key, HMAC-SHA256 of
`svix-id.svix-timestamp.body`, constant-time v1/base64 signature comparison and a
five-minute timestamp tolerance. Deduplicate signed event IDs and reject a
changed body for an existing ID. Retain only allowlisted reference/type/hash/time
facts, not raw provider/customer message contents. Only the exact enabled POST
callback bypasses the browser staging gate; signature validation still applies.
No opens/click tracking feature is introduced.

Contract and local cryptographic tests do not constitute configured Resend
acceptance. The private webhook signing secret, endpoint registration, delivered
mail and repeat-bounce acceptance still require verification in the actual
staging account. No credential belongs in this document or the PR.
