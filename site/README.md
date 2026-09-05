# meownero.com

Teaser site for Meownero. Next.js 16 (App Router), Tailwind v4, shadcn/ui, Motion. Deployed on Vercel (team `offln`, project `meownero`).

```sh
pnpm install
pnpm dev
NODE_ENV=production pnpm build   # the shell exports NODE_ENV=development globally; override it
```

Content rules: no chain claims beyond PLAN.md §1.1 (mandatory privacy, proof of work, fair launch, no premine). No lineage, no interop, no dates, no identities. See `research/traffic-playbook.md`.

## Launch notifications

"Notify me at launch" stores either a Web Push subscription (preferred, no personal data) or an email (fallback) as one private blob each in the Vercel Blob store `meownero-notify`. Records are keyed by SHA-256 of the endpoint or email, so re-submits are idempotent. A honeypot field drops bots.

Env (set on Vercel, pulled with `vercel env pull`): `BLOB_READ_WRITE_TOKEN`, `NEXT_PUBLIC_VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`.

Send the launch notification:

```sh
pnpm send:launch --dry-run
pnpm send:launch --title "Meownero genesis" --body "Binaries and genesis time are up." --url https://meownero.com
pnpm send:launch --print-emails   # for the one-time email send, then empty the store
```

Promise made on the page: one message at launch, then the list is deleted. Empty the store afterwards with `vercel blob empty-store`.
