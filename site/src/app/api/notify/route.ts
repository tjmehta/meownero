import { createHash } from "node:crypto";
import { put } from "@vercel/blob";

// Launch-notification signups. Two kinds: a Web Push subscription (no
// personal data, revocable from the browser) or, as a fallback, an email.
// Each record is one private blob keyed by a hash of the identifier, so
// re-submitting is idempotent and nothing is enumerable from the outside.

export const runtime = "nodejs";

const MAX_BODY = 4096;
const EMAIL_RE = /^[^\s@]{1,64}@[^\s@]{1,255}\.[^\s@]{2,}$/;

type PushSub = {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  expirationTime?: number | null;
};

function bad(message: string, status = 400) {
  return Response.json({ ok: false, error: message }, { status });
}

function key(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

function isPushSub(v: unknown): v is PushSub {
  if (!v || typeof v !== "object") return false;
  const s = v as Record<string, unknown>;
  const keys = s.keys as Record<string, unknown> | undefined;
  return (
    typeof s.endpoint === "string" &&
    s.endpoint.startsWith("https://") &&
    s.endpoint.length < 2048 &&
    !!keys &&
    typeof keys.p256dh === "string" &&
    typeof keys.auth === "string"
  );
}

export async function POST(req: Request) {
  const raw = await req.text();
  if (raw.length > MAX_BODY) return bad("Too large", 413);

  let body: Record<string, unknown>;
  try {
    body = JSON.parse(raw);
  } catch {
    return bad("Invalid JSON");
  }

  // Honeypot: real users never fill this.
  if (typeof body.website === "string" && body.website.length > 0) {
    return Response.json({ ok: true });
  }

  const createdAt = new Date().toISOString();

  if (body.type === "push") {
    if (!isPushSub(body.subscription)) return bad("Invalid subscription");
    const sub = body.subscription;
    await put(
      `push/${key(sub.endpoint)}.json`,
      JSON.stringify({
        endpoint: sub.endpoint,
        keys: { p256dh: sub.keys.p256dh, auth: sub.keys.auth },
        expirationTime: sub.expirationTime ?? null,
        createdAt,
      }),
      { access: "private", addRandomSuffix: false, allowOverwrite: true, contentType: "application/json" },
    );
    return Response.json({ ok: true });
  }

  if (body.type === "email") {
    const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
    if (!EMAIL_RE.test(email) || email.length > 254) return bad("Enter a valid email");
    await put(
      `email/${key(email)}.json`,
      JSON.stringify({ email, createdAt }),
      { access: "private", addRandomSuffix: false, allowOverwrite: true, contentType: "application/json" },
    );
    return Response.json({ ok: true });
  }

  return bad("Unknown type");
}
