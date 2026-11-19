# Fourth owner-feedback batch — implementation and review

Source: the complete Fourth Batch of comments.docx (seven numbered items,
Scenarios A–C and annotated layout), the revised Scenario B screenshot and all
subsequent owner answers. The original private attachments are not published.
The owner authorized implementing the whole batch, with screenshots only of the
redesigned public customer booking page. Other changes will receive owner
interactive acceptance after deployment. Use one draft PR and update that PR
with booking-page image comments; do not merge/deploy before that review.

## Coverage and scope

| Item | Implemented behavior |
| --- | --- |
| 1 | Omit Check the booking page to see which sessions offer it only from the booking-page Supervised Play information card. Preserve homepage/About wording. |
| 2 | Narrower green booking panel/inputs. Upper left Children/Adults, upper right Babies/Grip socks; lower left item-only estimate, lower right Payment method/Continue. Stack on phones. |
| 3 | Public form always shows Open/Supervised radios; unavailable choices are disabled/labelled. Open is default when available; supervised-only defaults to Supervised. Public Supervised selection resets adults/babies to zero and makes them read-only, with Supervised play is children only popup on attempted change. Restore prior Open values when switching back. Staff retain validation rather than locking. Estimate recalculates after the reset; server still rejects forged/nonzero supervised quantities. |
| 4 | Customers search input is narrower, with type selector and Search aligned on desktop; All types remains the initial selection. Responsive stacking retains usability. |
| 5 | Bookings, Today, Customers and Membership drafts have 10/25/50/100 rows, default 25, numbered/Previous/Next links, preserved filters/sort and page-one reset on size/filter change. Today totals/matching count remain independent of the displayed page. |
| 6 | Today/Bookings session checkbox selection filters immediately without Apply or closing the multi-select. Multiple choices remain usable; server validation/filters and no-JavaScript Apply fallback are retained. |
| 7A | Only the specified returning/current-phone entry gains Last Name or Email, allowing either/both, accurate success messages and the requested name-first/email-first failure copy. Partial-name confirmation remains. Unspecified new-customer, previous-phone and unmatched-phone paths retain their existing rules. |
| 7B | Distinct both-fields and email-first conflict branches, as clarified below; owner-only Dashboard notices. No customer phone update, reassignment or profile merge. |
| 7C | Referral remains optional. Clean new-customer tests pass; owner also reproduced a successful single-tab attempt. Step/flow markers now prevent stale/multi-tab/back submissions being interpreted as another step's form, preserving the current step and useful recovery text. This is not a claim that the original intermittent issue was definitively reproduced. |

## Matching branch matrix

| Entry and checks | Outcome | Other profile's phone |
| --- | --- | --- |
| Yes → matched current phone → correct name, current email, or both for that profile | Continue with the matched existing profile; show which details matched. Do not change saved spelling/contact data. | Not relevant |
| Name alone fails | Email-only retry names the entered name and phone; subsequent failure names the email/phone and removes obsolete introductory text. | Hidden |
| Email alone is not found | Name-only retry with requested red warning; subsequent name failure removes obsolete intro. Partial name goes through existing explicit family confirmation. | Hidden |
| Both supplied but neither matches | Keep both fields for correction with a clear error. | Hidden |
| Name verifies original phone profile, while simultaneously supplied email identifies another profile | Rare profile-choice exception. Original profile requires its existing email to continue; the other profile requires its own matching name before exposing/enabling Proceed using phone. Reuse an already matching name; possible spelling needs explicit family confirmation. Explicit selection changes the booking's chosen profile, not either customer's saved phone/email. | Revealed only after that profile's name/email verification |
| Email entered first identifies a different profile → requested name matches phone profile | Explain correct phone/name but different email profile; call/text assistance or restart with another email. | Hidden |
| Same email-first conflict → name matches email profile but not phone profile | Ask customer to restart using the phone they know for that customer. The saved number is not displayed. | Hidden |
| Same email-first conflict → name matches neither | Assistance message; no association. | Hidden |

Scenario B applies for the specified Yes/No phone-matched paths. It is not general
permission to switch profiles elsewhere. Verification proofs recheck profile
revision/contact and expire with the browser flow. Historical emails do not
identify a customer. Corrected-email verification is not a public contact edit.
The approved assistance number is 848-238-5147, correcting the screenshot typo.

Every detected different-profile conflict creates one owner Dashboard notice per
flow/profile pair, with protected profile links and audit. Retries do not create
repeated notices. No external alert email is added. Ordinary staff cannot read
or review these owner notices; existing historical-email notices retain their
own rendering. No customer profile is changed by verification.

## Review and validation

[Booking-page JPGs](design-review/owner-edits-batch-4/README.md) show desktop and
phone Open/Supervised/disabled variants only, as requested. Other screens were
exercised locally without adding screenshots to this gallery. Fixtures and
contacts are fictional. The local review clock is November 18, 2026, New York.

**428 tests passed locally on PostgreSQL 16.2**, including entry-scope boundaries, all requested success and
failure branches, hidden other-phone/explicit-choice restrictions, stale proofs,
owner-only notices, stale tabs/optional referral, forged unavailable play and
supervised quantity rejection, and all four paging lists/unpaged Today totals.
Chromium additionally checks actual quantity reset/popup/recalculation, restored
Open counts, 1440px/390px screenshots and 320px no overflow, immediate multi-session
filtering while keeping the chooser open, row-size navigation and separate real
browser conflict paths. Browser owner sessions are synthetic local test fixtures,
not new hosted MFA delivery evidence.

No model/schema change is required; the migration plan remains through 0026.
Routine deployment after approval uses the existing browser ZIP plus one
PowerShell block, without a reviewed schema flag. Existing compatible recovery
checks remain. No hosted change, payment/card/waiver integration, active benefits,
legacy-booking relabelling or next-phase operational development is included.
The prior next-phase documentation alignment is included in this branch; it
records plans, not implemented integrations. Homepage design remains unchanged.
