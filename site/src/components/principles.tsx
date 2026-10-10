"use client";

import { motion, useReducedMotion } from "motion/react";

const principles = [
  {
    title: "Private payments",
    body: "Every transaction is shielded. There is no public transaction option.",
  },
  {
    title: "Proof of work",
    body: "Miners secure Meownero's own blockchain. It isn't a token on another chain.",
  },
  {
    title: "No premine",
    body: "No coins set aside for insiders. Mining starts after public notice.",
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
        How Meownero works
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
