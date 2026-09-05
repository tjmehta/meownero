// Send the launch notification to every push subscriber and print the email
// list for a separate, one-time send. Run from site/ with the Vercel env
// pulled into .env.local:
//
//   pnpm send:launch --title "Meownero genesis" --body "..." --url https://meownero.com
//   pnpm send:launch --dry-run
//
// Expired or gone subscriptions (404/410) are deleted as they are found.

import { get, list, del } from "@vercel/blob";
import webpush from "web-push";

const args = new Map<string, string>();
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith("--")) {
    const next = process.argv[i + 1];
    if (next && !next.startsWith("--")) {
      args.set(a.slice(2), next);
      i++;
    } else {
      args.set(a.slice(2), "true");
    }
  }
}

const dryRun = args.get("dry-run") === "true";
const payload = JSON.stringify({
  title: args.get("title") ?? "Meownero",
  body: args.get("body") ?? "Meownero has news.",
  url: args.get("url") ?? "https://meownero.com",
  tag: "meownero-launch",
});

async function readJson<T>(pathname: string): Promise<T | null> {
  const res = await get(pathname, { access: "private", useCache: false });
  if (!res || res.statusCode !== 200 || !res.stream) return null;
  const text = await new Response(res.stream).text();
  return JSON.parse(text) as T;
}

async function* all(prefix: string) {
  let cursor: string | undefined;
  do {
    const page = await list({ prefix, cursor, limit: 1000 });
    for (const b of page.blobs) yield b.pathname;
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
}

async function main() {
  const { VAPID_PRIVATE_KEY, NEXT_PUBLIC_VAPID_PUBLIC_KEY, VAPID_SUBJECT } = process.env;
  if (!VAPID_PRIVATE_KEY || !NEXT_PUBLIC_VAPID_PUBLIC_KEY) throw new Error("VAPID keys missing");
  webpush.setVapidDetails(VAPID_SUBJECT ?? "mailto:security@meownero.com", NEXT_PUBLIC_VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);

  let sent = 0;
  let removed = 0;
  let failed = 0;
  for await (const pathname of all("push/")) {
    const sub = await readJson<{ endpoint: string; keys: { p256dh: string; auth: string } }>(pathname);
    if (!sub) continue;
    if (dryRun) {
      sent++;
      continue;
    }
    try {
      await webpush.sendNotification(sub, payload, { TTL: 60 * 60 * 24 * 7 });
      sent++;
    } catch (err) {
      const status = (err as { statusCode?: number }).statusCode;
      if (status === 404 || status === 410) {
        await del(pathname);
        removed++;
      } else {
        failed++;
        console.error("push failed", pathname, status);
      }
    }
  }

  const emails: string[] = [];
  for await (const pathname of all("email/")) {
    const rec = await readJson<{ email: string }>(pathname);
    if (rec) emails.push(rec.email);
  }

  console.log(JSON.stringify({ dryRun, push: { sent, removed, failed }, emails: emails.length }, null, 2));
  if (emails.length && args.get("print-emails") === "true") console.log(emails.join("\n"));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
