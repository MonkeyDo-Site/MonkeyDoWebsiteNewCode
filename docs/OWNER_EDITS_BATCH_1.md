# First batch of owner edits

Implements the twelve items in the owner's Word document and the four subsequent clarifications. The source document's screenshots are not published: review images use fictional local customers and session records only.

## Scheduling screens

1. Every owner scheduling screen includes a sticky **Owner scheduling** link. The daily page uses **Choose a date:**, **Edit the default weekly schedule**, and **Edit booking horizon**.
2. Confirmation and date-setting checkboxes appear before their labels, on the same line. The date-closure label ends with a period and the Chol Hamoed checkbox has no trailing colon.
3. Daily sessions appear in a table with session time, session label, play mode, blocked status, child/total/supervised reserved counts and limits, visibility, and an Edit session action. Ordinary play is omitted from the display (the internal data classification is retained). Displayed clock labels use 12-hour time without rewriting stored owner labels.
4. Existing sessions have time-only edit fields and a fixed displayed date. The service also rejects date movement. Booked-session timing and play-mode changes remain prohibited. Date settings disable the date field and use the loaded date server-side; a posted replacement date cannot redirect the edit.
5. The weekly page links to its Owner scheduling parent rather than directly to the horizon and dated calendar. It uses the owner's revised instructions and **Add a weekly default session** action.
6. Only active, non-deleted defaults can be selected or submitted for generation. The update checkbox reads **Also apply changes to existing unbooked sessions**, with help distinguishing creation of missing sessions from updating previously generated sessions.

## Defaults and existing reservations

- **Deactivate:** immediately hides all linked sessions from public booking and blocks new reservations through public, staff, and internal reservation services. Existing bookings, quotes, session times and individually edited session values are retained. The default remains in the weekly list and can be reactivated.
- **Reactivate:** restores eligibility according to each dated session's own visibility, closure, capacity, date and time rules. It does not reopen a manually closed session. Generate with updates selected to apply changed template times/capacities to eligible dates.
- **Delete:** an owner-only confirmation page displays the count of all associated bookings, including historical records. Deletion archives the weekly default, removes it from the working weekly list and generation options, and blocks its linked sessions from new bookings immediately. It removes only unused future generated sessions with no booking history, allowing that timing to be recreated. Removal details are audited. Booked, past and individually edited records remain; it does not erase or cancel bookings or change their times. There is no deletion through GET and confirmation requires CSRF, current revision, current booking count, and an explicit checkbox.
- The shared calendar lock serializes these changes with reservation creation. If another booking arrives after the delete warning, the owner must review the updated count before confirming again.
- Retained dated sessions still participate in the existing no-overlap and unique-start protections. A replacement default can generate dates cleared of unused sessions, but a conflict with a retained booked or individually edited session is reported as preserved; deletion cannot bypass booking-history protections.
- Weekly edits do not move existing bookings. For an 11:30-to-11:40 template change, booked dates remain at 11:30; eligible unbooked generated dates can update to 11:40. One-time sessions and individually edited sessions remain unchanged.

## Booking tables and search

Bookings use a table with Family name, Session date/time, Children, Adults, Babies, Play type, Status and Open booking. Waiver and membership columns are deferred to their planned functional work.

Authorized customer and booking searches retain exact/partial/phone matching and add conservative surname spelling suggestions, with exact names first, direct matches next and possible spelling matches clearly labeled. The comparison handles a small number of edits, including adjacent transpositions; very short surnames do not use fuzzy matching. The current implementation streams customer names for staff suggestions and requires no PostgreSQL extension. Larger customer volumes may justify a dedicated search index later.

Public booking checks a possible spelling only against the one customer selected by the submitted phone number. Greenfield entered for Greenfeld opens a confirmation step; it does not search or list other customers, reveal the stored surname/email before confirmation, rename the customer or merge records. Confirmation rechecks the profile revision and is subject to the existing session expiry, CSRF and throttling. The existing previous-phone flow is unchanged. This remains the existing test booking identity workflow, not a replacement for production account verification.

## Validation and review

Desktop (1440px) and phone (390px) screenshots cover daily scheduling, session/date edits, weekly defaults and editing, horizon, deletion warning, booking list/search, customer search and the public spelling confirmation. Browser checks cover parent-link stickiness, fixed dates, inline controls, table output, no page overflow, hidden inactive generation choices and the public confirmation transition. Owner screenshots use a synthetic local fixture session; they are not hosted MFA acceptance evidence.

See the review gallery in `docs/design-review/owner-edits-batch-1/` for JPG downloads and the recorded browser checks. Automated coverage includes archive/deactivation behavior, existing booking/quote preservation, direct service and forged-form checks, stale booking counts/revisions, owner-only access, CSRF, audit rollback, deletion-versus-booking concurrency, exact/possible search ordering, phone-specific public matching, profile changes and completion of a spelling-variant booking against the original customer record.

Final automated verification: **308 PostgreSQL-backed tests passed**. Ruff lint and formatting, Django system checks, and migration-drift checks passed.

## Deployment handoff

This branch requires **core.0022_weekly_default_archive**, an additive nullable `archived_at` column on WeeklySlot. It does not backfill, delete, rename or reprice existing data. Apply this reviewed migration to the existing functional database using the separate migration role before running the Functional deployment helper. The ordinary runtime role should not receive schema privileges. The existing helper intentionally stops on pending migrations and must not be bypassed.

This release therefore needs one schema-preparation step before the usual single deployment command. The installed Functional helper and existing staged deployment/rollback workflow are reused; no DNS, email transport, payment or site-mode change is required. The live club visibility preference remains untouched.

A code rollback does not reverse this migration or data changes. In particular, the older release did not enforce the inactive/deleted weekly-default gate: after using those controls, rolling back to that older version requires checking those dated sessions' visibility/closure before reopening customer booking. The archive column can remain present during a code rollback; do not reverse the migration or erase retained scheduling history as part of a routine rollback.

No PR, migration on the Droplet or hosted deployment has been performed for this batch. Screenshots are provided for review first.
