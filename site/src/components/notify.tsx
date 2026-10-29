"use client";

import { useEffect, useId, useRef, useState, useSyncExternalStore, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// "Notify me at launch". Push first: the browser issues an anonymous
// subscription and the user can revoke it from the browser. Email is the
// fallback for browsers without push or when permission is declined.

type Mode = "idle" | "working" | "email" | "done";

const STORAGE_KEY = "meownero:notify";
const VAPID = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;

const NETWORK_ERROR = "Could not reach the server. Check your connection and try again.";
const SERVER_ERROR = "Something went wrong on our side. Try again in a minute.";
const PUSH_ERROR = "Browser notifications did not work here. Use email instead.";

// Errors whose message is already a sentence a visitor can act on.
class NotifyError extends Error {}

function readStored() {
  try {
    return !!localStorage.getItem(STORAGE_KEY);
  } catch {
    return false;
  }
}
const noop = () => () => {};

function pushSupported() {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window &&
    !!VAPID
  );
}

function toKey(base64: string) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function post(payload: Record<string, unknown>) {
  let res: Response;
  try {
    res = await fetch("/api/notify", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new NotifyError(NETWORK_ERROR);
  }
  let data: { ok?: boolean; error?: string };
  try {
    data = await res.json();
  } catch {
    throw new NotifyError(SERVER_ERROR);
  }
  if (!res.ok || !data.ok) throw new NotifyError(data.error || SERVER_ERROR);
}

const message = (err: unknown, fallback: string) =>
  err instanceof NotifyError ? err.message : fallback;

// Same 2px gold outline as the site's text links.
const focusRing = "focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-4 focus-visible:outline-gold";

export function Notify() {
  const [mode, setMode] = useState<Mode>("idle");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const statusRef = useRef<HTMLParagraphElement>(null);
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;

  // Remembered per browser only, so a returning visitor sees the done state
  // without a round trip. Server snapshot is false to avoid hydration drift.
  const stored = useSyncExternalStore(noop, readStored, () => false);
  // Feature detection only. iOS Safari tabs have no PushManager (Apple limits
  // push to Home Screen web apps), so they get the email form directly.
  // Unknown during SSR: do not advertise push before checking the browser.
  const supported = useSyncExternalStore<boolean | null>(noop, pushSupported, () => null);

  // Keep keyboard and screen reader users in place: into the field when the
  // email form replaces the push button or shows an error, onto the
  // confirmation after success. Mode only becomes "email" after a user action.
  useEffect(() => {
    if (mode === "done") statusRef.current?.focus();
    else if (mode === "email") inputRef.current?.focus();
  }, [mode, error]);

  function finish() {
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {}
    setMode("done");
  }

  async function subscribePush() {
    if (!pushSupported()) {
      setMode("email");
      return;
    }
    setMode("working");
    setError(null);
    try {
      const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      await navigator.serviceWorker.ready;
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setMode("email");
        return;
      }
      const existing = await reg.pushManager.getSubscription();
      const sub =
        existing ??
        (await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: toKey(VAPID as string) as BufferSource,
        }));
      await post({ type: "push", subscription: sub.toJSON() });
      finish();
    } catch (err) {
      setError(message(err, PUSH_ERROR));
      setMode("email");
    }
  }

  async function submitEmail(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // The button stays focusable while saving, and Enter in the field also
    // submits, so ignore repeat submits here.
    if (mode === "working") return;
    const form = e.currentTarget;
    const website = (form.elements.namedItem("website") as HTMLInputElement | null)?.value ?? "";
    setMode("working");
    setError(null);
    try {
      await post({ type: "email", email, website });
      finish();
    } catch (err) {
      setError(message(err, SERVER_ERROR));
      setMode("email");
    }
  }

  const done = mode === "done" || stored;
  let body: ReactNode = null;

  if (done) {
    // Only the status line below.
  } else if (supported === null) {
    // Same height as the email form, to avoid a jump on hydration.
    body = <div className="h-[9.25rem] min-[360px]:h-24" aria-hidden="true" />;
  } else if (!supported || mode === "email" || (mode === "working" && email)) {
    const working = mode === "working";
    body = (
      <form
        onSubmit={submitEmail}
        aria-busy={working}
        className="flex w-full flex-col gap-2"
      >
        <label htmlFor={`${id}-email`} className="text-sm font-medium">
          Email for the launch notice
        </label>
        <div className="flex flex-wrap gap-2">
          <Input
            ref={inputRef}
            id={`${id}-email`}
            type="email"
            name="email"
            required
            autoComplete="email"
            inputMode="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            readOnly={working}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${hintId} ${errorId}` : hintId}
            className={`h-11 min-w-0 flex-[1_1_12rem] focus-visible:ring-0 md:text-base ${focusRing}`}
          />
          <Button
            type="submit"
            size="lg"
            className="h-11 grow px-4 min-[360px]:grow-0"
            disabled={working}
            focusableWhenDisabled
          >
            {working ? "Saving…" : "Notify me"}
          </Button>
        </div>
        {/* Honeypot: hidden from people, filled by bots. */}
        <input
          type="text"
          name="website"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          className="absolute -left-[9999px] h-0 w-0 opacity-0"
        />
        <div>
          <p id={hintId} className="text-xs text-muted-foreground">
            One email at launch. Then we delete the list.
          </p>
          <p
            id={errorId}
            role="alert"
            className="text-sm font-medium text-destructive [&:not(:empty)]:mt-1"
          >
            {error}
          </p>
        </div>
      </form>
    );
  } else {
    body = (
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Button
            size="lg"
            className="h-11 px-4"
            onClick={subscribePush}
            disabled={mode === "working"}
            focusableWhenDisabled
          >
            {mode === "working" ? "Saving…" : "Notify me at launch"}
          </Button>
          <button
            type="button"
            onClick={() => setMode("email")}
            className={`inline-flex min-h-11 items-center rounded-sm px-2 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline ${focusRing}`}
          >
            Use email instead
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          One browser notification at launch. Turn it off in your browser settings.
        </p>
      </div>
    );
  }

  // The status line stays mounted, empty, in every branch, so its text is
  // announced when signup finishes.
  return (
    <div className="w-full max-w-sm">
      {body}
      <p
        ref={statusRef}
        role="status"
        tabIndex={-1}
        className="rounded-sm text-sm text-muted-foreground outline-none focus-visible:outline-2 focus-visible:outline-solid focus-visible:outline-offset-4 focus-visible:outline-gold"
      >
        {done
          ? "You're on the list. We'll notify you at launch, then delete your signup."
          : null}
      </p>
    </div>
  );
}
