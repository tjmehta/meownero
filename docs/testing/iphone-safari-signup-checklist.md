# iPhone Safari signup check: tester sheet (M1a)

One page. Deployed site as-is at https://meownero.com. Read the **Do not** box first.
Written 2026-09-18 for [TJS-14]; expected behavior comes from
`site/src/components/notify.tsx` and the local Chrome evidence in
[recovery-site-2026-09-13.md](../../research/recovery-site-2026-09-13.md).
It has not yet been run on any iPhone.

## Do not

- **Do not submit a real email address.** Anything you type into the email box and
  send is stored as-is in a private store with **no confirmation email and no double
  opt-in**, and there is currently **no way for you to remove it yourself**.
- The launch sender (`site/scripts/send-launch.ts`) has **no durable "already sent"
  marker**, so a stored address could be messaged more than once if the script is run
  twice. Delivery has never been tested. Real submissions wait for an approved test
  inbox and a written one-message/deletion procedure.
- Do not tap any button that says "Notify me at launch" or mentions browser
  notifications. On iPhone Safari that button should not appear at all; if it does,
  that is a finding (row 4), not something to try.
- Use one iPhone you own or have explicit permission to test on. Ordinary Safari tab,
  not a Home Screen web app, not Private Browsing, content blockers off for this site.

## Before you start

Note: iPhone model, iOS version (Settings > General > About), Safari version (same as
iOS), network (Wi-Fi or cellular, and carrier if cellular), time in your timezone.
Start **Screen Recording** from Control Center before opening Safari and keep it
running through row 8. Close all other Safari tabs for meownero.com first.

## Checklist

Record pass/fail plus one line of what you actually saw for every row.

| # | Do this | Expected |
|---|---------|----------|
| 1 | **Cold load.** Type `meownero.com` in a new tab and go. | Page loads over https; dark page, gold "Coming soon" badge, headline "Privacy that is not optional.", coin image. No error, no blank page. |
| 2 | **First paint to hydration.** Watch the space under the paragraph "Meownero is a proof-of-work coin..." for the first 3 seconds. | Empty gap, then the email box and "Notify me" button appear once. Nothing flashes and then swaps to something else. |
| 3 | **Direct email field.** Look at what appeared. | One email box with placeholder `you@example.com`, a gold "Notify me" button beside it, and the small text "Email only. One message at launch, then the list is deleted." |
| 4 | **No push CTA or promise.** Read every word in that area. | No "Notify me at launch" button, no "Use email instead" link, no text about browser notifications or "revocable from your browser". |
| 5 | **Keyboard.** Tap the email box. | Email keyboard appears (@ and . keys visible). Field and button stay visible above the keyboard; page does not zoom in or jump. |
| 6 | **Layout.** With the keyboard open, then closed, look at the row. | Box and button on one line, nothing cut off at the right edge, no sideways scrolling. Rotate to landscape and back: still readable, still no sideways scroll. |
| 7 | **Reload.** Dismiss the keyboard, leave the box empty, pull down to refresh. | Same as rows 2 to 4 again. Nothing you typed is remembered. No "You are on the list" text (that only appears after a real submission, which you are not doing). |
| 8 | **Optional: invalid address.** Type `test` (no @) and tap "Notify me". | Safari blocks the send and shows its own validation bubble, or the page shows "Enter a valid email." and keeps the form. Nothing is stored for an invalid address. Stop here; do not enter a real address. |

Expected done state, for reference only: after a real successful submission the form is
replaced by "You are on the list. One notification at launch, then it is gone." and a
reload shows that line again. Nobody should reach this state in this test.

## Send back

1. The screen recording (whole run, rows 1 to 8).
2. One screenshot of the signup area after row 2 and one with the keyboard open (row 5).
3. The device, iOS/Safari version, network type, and time from "Before you start".
4. The filled table: pass/fail and one line per row, including anything odd (slow load,
   layout jump, unexpected text, a permission prompt of any kind).

Return it privately to TJ, not to the group chat. The recording may show your address
bar and status bar; crop or blur anything you do not want shared.

## For the person filing the result

Compare against the deployed identity recorded on 2026-09-18 05:55 UTC: Vercel
deployment `dpl_CVg1M68fvLwjUQaSz1ZYsqsQRJ5w`, served with cache age 856569 s
(consistent with the September 8 deploy). Its server-rendered HTML matches the local
build `K7Uxh2PLHJzotyiXBqyTH` prerender (`site/.next/server/app/index.html`) after
normalizing chunk names, icon fingerprints and the `dpl` query; the signup slot is the
empty `h-16` placeholder in both. The deployed HTML does not expose a Next build ID,
so the `dpl` id is the build reference to record with the results. This is a fetch of
the HTML only, not device evidence; a device result is still the deliverable of M1b.
