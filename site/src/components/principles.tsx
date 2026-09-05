"use client";

import { motion, useReducedMotion } from "motion/react";

const principles = [
  {
    title: "Private by rule",
    body: "There is no transparent transaction type. Every transfer is shielded, always.",
  },
  {
    title: "Proof of work",
    body: "An independent chain with its own consensus and network. Not a token on someone else's.",
  },
  {
    title: "No premine",
    body: "Zero insider allocation. Public notice before genesis, then everyone mines.",
  },
];

// Scroll reveal. Storytelling: the three promises arrive one at a time after
// the teaser, in the order they matter. Once only, never re-triggers.
export function Principles() {
  const reduce = useReducedMotion();

  return (
    <section
      aria-labelledby="principles"
      className="mx-auto w-full max-w-6xl px-6 pt-4 pb-20 md:px-10 md:pt-0 md:pb-28"
    >
      <h2 id="principles" className="sr-only">
        What Meownero promises
      </h2>
      <ol className="grid grid-cols-1 gap-10 md:grid-cols-3 md:gap-8">
        {principles.map((p, i) => (
          <motion.li
            key={p.title}
            initial={reduce ? false : { opacity: 0, transform: "translateY(18px)" }}
            whileInView={{ opacity: 1, transform: "translateY(0px)" }}
            viewport={{ once: true, amount: 0.5 }}
            transition={{
              duration: 0.6,
              delay: i * 0.08,
              ease: [0.23, 1, 0.32, 1],
            }}
            className="border-t border-gold/30 pt-5"
          >
            <h3 className="text-xl font-medium tracking-tight">{p.title}</h3>
            <p className="mt-2 max-w-[36ch] text-base leading-relaxed text-muted-foreground text-pretty">
              {p.body}
            </p>
          </motion.li>
        ))}
      </ol>
    </section>
  );
}
