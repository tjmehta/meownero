"use client";

import { useState, useSyncExternalStore, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// "Notify me at launch". Push first: the browser issues an anonymous
// subscription and the user can revoke it from the browser. Email is the
// fallback for browsers without push or when permission is declined.

type Mode = "idle" | "working" | "email" | "done";

const STORAGE_KEY = "meownero:notify";
const VAPID = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;

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
  const res = await fetch("/api/notify", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = (await res.json().catch(() => ({}))) as { ok?: boolean; error?: string };
  if (!res.ok || !data.ok) throw new Error(data.error || "Something went wrong");
}

export function Notify() {
  const [mode, setMode] = useState<Mode>("idle");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Remembered per browser only, so a returning visitor sees the done state
  // without a round trip. Server snapshot is false to avoid hydration drift.
  const stored = useSyncExternalStore(noop, readStored, () => false);
  // Feature detection only. iOS Safari tabs have no PushManager (Apple limits
  // push to Home Screen web apps), so they get the email form directly.
  // Unknown during SSR: do not advertise push before checking the browser.
  const supported = useSyncExternalStore<boolean | null>(noop, pushSupported, () => null);

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
      setError(err instanceof Error ? err.message : "Something went wrong");
      setMode("email");
    }
  }

  async function submitEmail(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const website = (form.elements.namedItem("website") as HTMLInputElement | null)?.value ?? "";
    setMode("working");
    setError(null);
    try {
      await post({ type: "email", email, website });
      finish();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setMode("email");
    }
  }

  if (mode === "done" || stored) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        You are on the list. One notification at launch, then it is gone.
      </p>
    );
  }

  if (supported === null) {
    return <div className="h-16" aria-hidden="true" />;
  }

  if (!supported || mode === "email" || (mode === "working" && email)) {
    return (
      <form onSubmit={submitEmail} className="flex w-full max-w-sm flex-col gap-2">
        <div className="flex gap-2">
          <Input
            type="email"
            name="email"
            required
            autoComplete="email"
            inputMode="email"
            placeholder="you@example.com"
            aria-label="Email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={mode === "working"}
            className="h-10 md:text-base"
          />
          <Button type="submit" size="lg" className="h-10 px-4" disabled={mode === "working"}>
            {mode === "working" ? "Saving" : "Notify me"}
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
        <p className="text-xs text-muted-foreground">
          {error ? `${error}. ` : ""}Email only. One message at launch, then the list is deleted.
        </p>
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <Button size="lg" className="h-10 px-4" onClick={subscribePush} disabled={mode === "working"}>
          {mode === "working" ? "One moment" : "Notify me at launch"}
        </Button>
        <button
          type="button"
          onClick={() => setMode("email")}
          className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Use email instead
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        A browser notification. No account, no email, revocable from your browser.
      </p>
    </div>
  );
}
