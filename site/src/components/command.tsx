"use client";

import { useEffect, useRef } from "react";

// A terminal command that scrolls sideways on narrow screens. While more of
// the line is hidden to the right, data-more fades the right edge so touch
// users can see there is more to scroll (see .command in globals.css). The
// fade is an overlay, not a mask, so the focus outline stays visible.
export function Command({ children }: { children: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const ref = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const pre = ref.current;
    const box = wrap.current;
    if (!pre || !box) return;
    const update = () => {
      box.dataset.more = String(pre.scrollLeft + pre.clientWidth < pre.scrollWidth - 1);
    };
    update();
    pre.addEventListener("scroll", update, { passive: true });
    const observer = new ResizeObserver(update);
    observer.observe(pre);
    return () => {
      pre.removeEventListener("scroll", update);
      observer.disconnect();
    };
  }, []);

  return (
    <div ref={wrap} className="command relative mt-4">
      <pre
        ref={ref}
        tabIndex={0}
        aria-label="Terminal command, scroll horizontally if needed"
        className="overflow-x-auto rounded-lg border border-border bg-background p-4 text-sm leading-relaxed focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold"
      >
        <code className="font-mono">{children}</code>
      </pre>
    </div>
  );
}
