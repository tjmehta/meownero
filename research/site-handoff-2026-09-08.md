# Website handoff — 2026-09-08

## Latest user request and outcome

The iPhone signup misleadingly offered a browser notification, then revealed an email field after clicking. The user wants push-specific UI hidden entirely where push is unavailable, with email signup shown directly. No misleading flash before capability detection.

Fixed `site/src/components/notify.tsx`:
- The existing `supported` result was not used in the rendering condition.
- Email rendering now includes `!supported`.
- The server snapshot is now `null`; a noninteractive placeholder is rendered until the browser capability check completes.
- Capability detection remains API-based, not iPhone/iPad user-agent detection.

## Deployment and verification

User explicitly requested production deployment. Deployed local site files through Vercel CLI under `offln/meownero`.

- Live: https://meownero.com
- Deployment: https://meownero-4btdl7i2y-offln.vercel.app
- ID: `dpl_CVg1M68fvLwjUQaSz1ZYsqsQRJ5w`
- Inspector: https://vercel.com/offln/meownero/CVg1M68fvLwjUQaSz1ZYsqsQRJ5w
- Vercel inspect confirmed production Ready and apex/www aliases.
- Production HTTP smoke check returned 200.
- Targeted ESLint and local production build passed; Vercel production build also passed.
- After waiting 60 seconds, the CLI error-log query for the previous five minutes returned no logs. This is not proof of end-to-end notification delivery.
- Monitoring integrations/drains were not checked.
- Real iPhone behavior has NOT been verified. No live signup or notification send was performed during this fix.

## Git / workspace

The notification component change remains **uncommitted**, but was included in the production upload. Base HEAD at deployment: `d6084aa`. Do not describe that commit alone as containing the fix.

Unrelated untracked files were present (`.codex/`, `.mcp.json`, and `chain/test-authorities.sh.tmp.1647189.55b20b892d45`). Leave them untouched. Re-check current status before resuming; other work may be concurrent.

## Resume here

1. Verify on a real ordinary iPhone Safari tab: email form directly, no push CTA or browser-notification promise, including initial load.
2. Verify a supported desktop browser still shows the push CTA. Do not treat simulated API availability as actual Safari/device verification.
3. If pursuing iOS Home Screen push, verify installed-web-app eligibility and manifest requirements separately; normal Safari tabs and Home Screen web apps differ.
4. Commit the targeted fix only if requested. Deployment is already complete; do not redeploy merely because it is uncommitted.

## Other launch-notification follow-ups (not part of this completed fix)

- Real end-to-end push delivery testing remains pending; do not broadcast to subscribers without explicit approval.
- Review anti-abuse protection before driving significant traffic; current honeypot/body limit is not a rate limiter.
- Email delivery, double opt-in/removal workflow, and enforcement of deleting the list after the launch message need review before launch.
- Keep the promise: one launch message, no marketing newsletter or analytics. Email capture is explicitly allowed for that purpose.

Persistent UX preferences are also recorded in the existing `meownero-site` memory. Earlier conversation claims that unsupported-browser rendering was already fixed were incorrect; rely on the current diff and the verification limits above.
