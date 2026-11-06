# Reconstruction evidence, approval boundaries, and validation plan

Consolidated November 5, 2026. This records what can be substantiated from the supplied history, baseline Git objects and later reconstruction conversation. It does not claim original-task recovery, application implementation, legal review by counsel, live provider configuration or deployment.

## 1. Sources and complete review coverage

Owner supplied **VoikyCodexHistory.docx**, approximately1.38million text characters, **21,213 body paragraphs**, **28 tables**, **33 prompts A–AG**. Entire available document was read chronologically in covered sections, including repeated/copy-pasted answers and italic command/output passages. Italics sometimes also mark ordinary emphasis. Paragraph references below are one-based `//w:body//w:p` in `word/document.xml`, including tables, rather than layout-dependent Word page numbers.

| Range | Prompts |
|---|---|
| P1–2802 | A |
| P2803–5113 | B–H |
| P5114–8116 | I–L |
| P8117–11159 | M–S |
| P11160–14547 | T–Z |
| P14548–18723 | AA–AE |
| P18724–21213 | AF–AG |

Original DOCX remains a private task attachment, not committed wholesale: it may contain personal and operational context. The current repository plus this decision/trace record is the reviewable specification. Later direct owner answers in this reconstruction chat govern where they change the history. A local scratch summary is a continuation aid, not authority over the original answers.

### Source limitations

- Literal masked text P3498/P3507, duplicated P3641/P3648, cannot be reconstructed from asterisks. Later phone/contact answers resolve much associated behavior; do not invent original strings.
- P2348 and P19723 contain cut-off command-output lines. Complete available text was reviewed; related material appears more fully elsewhere and current files were inspected.
- DOCX contains no embedded original image binaries/other attachments. At initial consolidation, the reattached images were visible in chat but original files were unavailable locally. Subsequently, the owner uploaded `monkeydo.zip`; its 12 original images are now preserved unchanged with checksums in [brand-assets/README.md](brand-assets/README.md). This resolves image availability, not recovery of code from the original task.
- **AG is the last user prompt and contains inline answers to a copied assistant response. There is no assistant response to AG**: owner confirmed this is the prompt that stuck. Copied final blocker lists are stale, not a later assessment.
- Historical public Banquest requests failed. Later permitted public specification retrieval succeeded; neither establishes authenticated account behavior or transaction test results.
- OpenAI Support is investigating original task. Do not operate on it, reset its history, or assume its files are recovered.

## 2. Baseline verified against actual checkout

Before this documentation update local `work` and read-only remote `main` were both **0bcc571ef493b79ca1f88e0ff09c2952cb4e30ab**. All nine tracked text files matched Prompt A's displayed contents after normalizing Word numbered-list formatting. Source PDF checksum matched its documented hash. No extra local unreachable commits were found in the initial object inspection.

| Verified present | Not implemented in baseline |
|---|---|
| README and planning/decision/hosting/open-documents | Functional application/backend/database schema/migrations |
| Waiver source PDF and standalone HTML prototype | Persistent signatures/booking integration/provider transactions |
| Brand asset handling notes | Original image files at the initial baseline (subsequently supplied; see above) |
| Prior requirements prose | Memberships/programs/admin/auth/jobs/payment/email/export/deployment code |

`waiver.html` added in `a5b5f5e`, merged PR#3. It deliberately prevents form submission and reports that no signature was saved. Existing conversion is preserved; calling it a prototype refers to missing persistence, not missing HTML. PDF and HTML stay byte-for-byte unchanged in this documentation PR, including historical draft labels. Wording approval and later implementation status are separate.

## 3. Historical local commits versus remote evidence

History records more than read-only review even though that was intended:

| Evidence | Historical action | Current evidentiary limit |
|---|---|---|
| S P10916–11009,11149–11150 | `299136e` Document encrypted database backup plan; three docs +46/-3; PR metadata | Local creation output, not verified push/PR URL |
| T P11269 | Assistant admits premature documentation commit/PR metadata | Does not authorize later changes |
| V P11888–11908 | `git revert --no-edit 299136e` -> `5e3505b`, +3/-46; revert PR-tool metadata | No verified numbered GitHub PR |
| Z P14225–14229 | `f132f22` Document encrypted PostgreSQL backup plan atop baseline | Creation/relation to earlier commit and revert unexplained |
| AA–AF output | Backup requirements again visible in three historical files | Not working backup infrastructure |

Affected historical files: `docs/DECISION_LOG.md`, `docs/DIGITALOCEAN_VPS_PLAN.md`, `docs/OPEN_DECISIONS.md`. `299136e`, `5e3505b`, `f132f22` did not resolve as local commit objects; not advertised remote branch/PR tips in initial review. This is not proof absence from every GitHub object or original environment. Metadata titled “Document encrypted PostgreSQL backup plan” / “Revert premature backup requirements documentation” is not an actual verified PR number/URL. Advertised baseline PR refs were#1–#5.

This update reconstructs current documentation with **new** Git history. It does not replay unexplained local commits, assert app-code recovery, or disturb original task. If Support supplies artifacts later, preserve and compare before merging.

### Available commit references recorded in history

| Short | Verified full local commit |
|---|---|
|0bcc571|0bcc571ef493b79ca1f88e0ff09c2952cb4e30ab|
|5017e51|5017e519c6601f0d794f0f565bf2d70d97cc1363|
|dc861fd|dc861fd78cdfde407fa7d837639d0ae9b75b33f5|
|a5b5f5e|a5b5f5e4d7c0e46b9b07d83f29030113cc7a2955|
|f32f89c|f32f89c59f7b2e1038e1efe98ab078c13003ca54|
|582c98b|582c98b306479216a482d8d49418d96c089b401c|
|415f92d|415f92dfbb220f4ac22608e3226e9c77d5b098ad|
|f2a8ac3|f2a8ac37bb0fd1c6fee2c3c5bcb15d8969188dfb|
|cae77fa|cae77faad612548447213cf277262c99164e2c4a|
|72c4fa1|72c4fa14663e48331b48195c934834a3ca5afef4|
|5597333|5597333c2ee592e75781ce21c3973f4cf1be53db|

Recorded branch references: `main`, `work`, `refs/heads/main`, `refs/heads/work`, `codex/add-waiver-storage-and-access-requirements`, `codex/create-html-waiver-from-pdf`, `codex/create-website-for-monkeydo-indoor-playspace`, and its `-o6r98u` variant. Remote also advertised HTML branch `-skx6vg` for PR#4; its contents were **excluded** as unapproved.

Diff identifiers `f94d76c..0808875`, `06aa80e..0ccfd4a`, `450c6a8..949c84a` are blob IDs, not commits. Old side resolved locally, new side did not. Do not interpret phone numbers or 64-character PDF SHA-256 as commit IDs.

## 4. Decision trace map

This map locates material supersessions; full current rules belong in subject documents, not copied historical lists.

| Source | Material current effect | Current document |
|---|---|---|
|A P3–50|Read-only original review, current main, exclude PR#4|This evidence record|
|B P2804–2815; C/E; N P8897|Purchased domain, Cloudflare proxy/strict HTTPS, DO/staging direction|Hosting plan|
|C–H P2856–3959|Brand copy, unavailable slots, manual closures, owner exclusive group/overrides, contact corrections, waiver sharing, staff roles/cancellation/arrival|Main requirements / payments / emails|
|I–L P5114–8116|Last Name only, About copy, cards not tabs, exports, optional reusable card, sender, universal waiver arrival check|Main requirements / payments|
|M–O P8117–9581|Editable customer type, failure/bounce workflow, Start arrival priority/today vs future row actions|Main requirements / emails|
|P–S P9582–11159|R2 backup destination, key model, seven nightly/twelve monthly, historical doc mutation|Hosting / evidence|
|U–Z P11290–14547|Subscription, explicit billing calendars, supervised play, clubs/participants/overlap, Banquest, party rename|Memberships / programs / payments|
|AA P14549; AF P19030–19058; AG P20995–21005|Owner waiver wording/e-sign approval, two-year-from-signing deletion, metadata retained, next-booking version change|Main requirements / waiver provenance|
|AB–AE P15524–18723; AF P18726–18733|Unlimited, benefit order, Subscription independence, date-only Chol Hamoed, four mixed-type free adults|Memberships|
|AG P20903/20911 vs copied P20912|Actual renewal-date grace anchor, no lapse benefits; specific answer outranks broad copied yes|Memberships|
|AG P20923/P20925/P20929/P20937/P20943|No unpaid phantom credit; paid tax reversal/credit; eligible extra uses; staff conversion|Memberships / payments|
|AG P20994/P21009/P21028/P21036–37|No installment receipts, club audit/export/refund conditions|Programs / emails|
|AG P21041–21086|Party details, no gift-card ledger/PIN, socks questions/answers|Programs|
|AG P21089/P21115/P21132–57|No Play page, preserve About areas, security/log/export decisions|Main requirements|
|Later reconstruction chat|No counsel gate, leap Jan29Feb29 reset, credit eligibility/expiration alert, split preservation/proportions, socks35online, attendance warning/leaveblank, email edits, fee **before** tax and taxable fee portion|All current subject documents|
|Owner's present request|Authorize documentation update/commit/PR, not application development|README / decision log|

Late reconstruction clarification confirms80.98pretax is **five total children** buying two Subscriptions;50.98 is **three total children** buying two. Both follow same rule, no new price change. Production rate and retained-fee tax remain pending despite “everything resolved” authorization to consolidate.

## 5. Phased future reconstruction/build

1. Review this coordinated documentation PR, preserving existing source/code. No original-task history changes.
2. After separate development authorization, verify the supplied original image inventory and select implementation stack/auth/ORM/jobs. Preserve approved source PDF/logo and document environment setup.
3. Shared foundation: identities/permissions/audit, versioned settings/pricing/tax, PostgreSQL transactions, capacity and benefit/credit ledgers, durable operations.
4. Public responsive content and ordinary booking/customer/waiver/admin arrival workflows.
5. Membership cohorts/cycles/renewals/conversions/failures plus supervised mode.
6. Club programs/participants/enrollment/occurrences; parties; physical gift-card sales/manual tender; socks.
7. Verified Banquest sandbox, Resend/R2, signature storage, webhook/reconciliation/retention jobs and actual isolated backup restore.
8. Owner WCAG/browser/mobile/operational acceptance; approved costs and separate deployment/DNS/live-payment/customer-opening gates. No production secrets/data in staging.

## 6. Required acceptance scenarios for implementation

These are future meaningful tests, **not tests executed by this documentation PR**:

- Horizon1–10/reset, Friday opening of Sunday, DST, Saturday visibility, ordinary-after-start versus supervised cutoff, private closure reason, gray full/party labels.
- Concurrent ordinary last-space bookings, owner exclusive group/public block, staff arrival-only override versus forbidden advance override, atomic reschedule with audit.
- Customer silent new lookup/current+previous phone branches, unique IDs, Last Name-only and camp type, displaced contact history, no unrelated history leakage; shared-minor waiver link privacy/expiry/reschedule and version/year/leap validity.
- Waiver persisted/hash verified/private retrieval authorized, two-year deletion and post-restore retention, paper fallback versus electronic evidence, universal arrival gate preserving form state.
- Ordinary child/baby/adult-only minimum; actual-attendee edits; absent child partial fee and benefit release; extra adult no cancellation fee; $0 comped versus member-free distinction; party50fee and discount-before-tax; no group discounts online.
- All [membership numerical/calendar examples](MEMBERSHIPS.md), per-place/per-booking limits, four-adult stacking, Subscription independence after Unlimited use, date-only exclusions, no rollover, concurrent benefit reservation, reschedule/cancel release without silent repricing.
- Jan29leap reset, short-month return to anchor, early/grace/lapsed renewal/type conversion/count reductions/cohorts, failed installment owner alerts/no automatic retry, no silent future booking repricing, original accepted prices preserved.
- Paid/unpaid visit conversions, tax reversal/fee retention pending decision, credit use/concurrency/installment application/expiry alert; three-child50.98 and five-child80.98 examples.
- Fee/tax/split/rounding [PAYMENTS.md](PAYMENTS.md) examples; actual inclusive tender amounts, preserved first payment when second fails, physical gift-card manual verification/no digital ledger, card removal/history, new fee on actual card portion only.
- Club term generation/exclusions/overlap decisions, named participant DOB/age corrections/waiver match audit, leave-blank roster warning, no auto3clubfee, first no-show follow-up/contact-before-charge, no duplicate collection each occurrence; correct rosters/exports.
- Banquest source conversion before15minute nonce expiry, no automatic holds, authentication failure paths, duplicate submit/network unknown/webhook replay, sandbox processor-specific responses including45.67, settled refund versus void, no double gateway surcharge, no automatic retries/receipts.
- Accurate paid/due one combined email, package exclusions, optional waiver/PDF, no Book a visit CTA there, edited renewal wording/plurals, no appointment reminders/receipts; Failed/Bounced/unknown delivery, corrected-address booking-only resend, Dashboard fallback during email outage.
- Permission matrix/server enforcement, password hashing/reset/MFA/recovery, five-failure delays,12hour idle, session revocation, archival/nonreused IDs, no export reauthentication, secret-safe logs/exports.
- WCAG2.2AA, keyboard/screen-reader labels/focus/errors/contrast/resize across current browsers and mobile/tablet/desktop, owner-approved final admin/navigation/layout.
- Genuine encrypted nightly upload/checksum/retention, isolated monthly restore without illicit key storage, manual two-copy dated desktop download, owner-only production restore and investigation preservation.

For this PR validate Markdown links/whitespace, financial example arithmetic, approved-rule coverage and unchanged PDF/HTML. Do not invent passing application tests where no application exists.
