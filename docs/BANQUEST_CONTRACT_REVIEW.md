# Banquest public contract review for the booking stage

Read-only public documentation checked November 19, 2026. No credentials,
merchant-account request or transaction was sent during this review.

The older docs URL https://docs.banquestgateway.com/api/v2/spec currently returned
404. The current v2 specification was obtained successfully from the public
sandbox API host: https://api.sandbox.banquestgateway.com/api/v2/spec.
The v1 schema is different and was not used as a substitute v2 request contract.

Contracts used:
- v2 Basic authentication is source-key:PIN, with an identifying User-Agent.
- POST transactions/charge accepts pm-ID source, exact amount, capture true,
  ignore_duplicates false, transaction flags, tax amount and custom_fields.
  Mandatory gateway surcharges can change returned amounts; verify the returned
  transaction identity/actual amount rather than silently accepting a mismatch.
- GET transactions/ID provides captured/settled state, actual amount and metadata,
  created_at, settled_date and available batch identity. Auth-only/approved,
  partial/submitted/unknown states are not confirmed captured receipts.
- Refund takes original reference_number and an explicit amount. Void references
  the original and does not have a separate guaranteed transaction ID. Their
  financial effects remain distinct and linked to original paid amounts.
- Creating customers/ID/payment-methods from nonce requires transient expiration
  month/year; card saving does not verify issuer validity or authorize a hold.
  Do not persist expiry or nonce as tomorrow's charging source.
- Hosted Tokenization v0.3 exposes provider-hosted fields, getNonceToken(), nonce
  and transient expiryMonth/expiryYear. Only the public pk_ key belongs in the
  browser. The published documentation computes the sandbox host as
  tokenization.sandbox.banquestgateway.com; its sample-code bundle includes a
  developer accept.blue host, which must not replace the configured Banquest
  sandbox domain in application code.
- Webhook spec: https://docs.banquestgateway.com/schemas/webhooks/webhooks-v1.yml.
  Verify hexadecimal X-Signature with HMAC-SHA256 over the raw body, deduplicate
  stable event IDs, distinguish response notification types, and acknowledge
  durable receipt separately from completed financial reconciliation.

This establishes public request shapes only. Private account source permissions,
processor, 3DS enablement/authentication handling, deletion semantics, provider
amounts/fees, webhook delivery and actual nonce lifecycle remain sandbox acceptance
work. No exactly-once gateway guarantee, issuer verification, live-payment
readiness or bank-deposit reconciliation is claimed from reading documentation.
