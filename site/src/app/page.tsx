import Image from "next/image";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Principles } from "@/components/principles";
import { Notify } from "@/components/notify";

// Entity data for search and AI answer engines. Deliberately no founder,
// address, or contact fields: the project has no public identities yet.
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://meownero.com/#org",
      name: "Meownero",
      alternateName: "MEOW",
      url: "https://meownero.com",
      logo: "https://meownero.com/icon-512.png",
      description:
        "Meownero (MEOW) is an independent proof-of-work cryptocurrency in development where every transaction is private by rule. Fair launch, no premine, no presale.",
    },
    {
      "@type": "WebSite",
      "@id": "https://meownero.com/#site",
      url: "https://meownero.com",
      name: "Meownero",
      publisher: { "@id": "https://meownero.com/#org" },
      inLanguage: "en",
    },
    {
      "@type": "WebPage",
      "@id": "https://meownero.com/",
      url: "https://meownero.com",
      name: "Meownero: fair-launch privacy coin, proof of work, no premine",
      isPartOf: { "@id": "https://meownero.com/#site" },
      about: { "@id": "https://meownero.com/#org" },
      primaryImageOfPage: "https://meownero.com/coin.png",
    },
  ],
};

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <section className="relative isolate flex min-h-[100dvh] items-center overflow-hidden">
        <div className="mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-12 px-6 pt-20 pb-16 md:grid-cols-[1.1fr_1fr] md:gap-8 md:px-10 md:py-24">
          <div className="order-2 flex flex-col items-start md:order-1">
            <Badge
              variant="outline"
              className="rise border-gold/40 bg-gold-soft px-3 text-gold"
              style={{ "--i": 0 } as React.CSSProperties}
            >
              Coming soon
            </Badge>

            <h1
              className="rise mt-6 max-w-[14ch] text-5xl font-semibold tracking-tighter text-balance md:text-6xl lg:text-7xl"
              style={{ "--i": 1 } as React.CSSProperties}
            >
              Privacy that is not optional.
            </h1>

            <p
              className="rise mt-6 max-w-[42ch] text-lg leading-relaxed text-muted-foreground text-pretty md:text-xl"
              style={{ "--i": 2 } as React.CSSProperties}
            >
              Meownero is a proof-of-work coin where every transaction is
              private by rule. Fair launch. No premine.
            </p>

            <div className="rise mt-8" style={{ "--i": 3 } as React.CSSProperties}>
              <Notify />
            </div>

            <Link
              href="/downloads"
              className="mt-5 rounded-sm text-sm text-gold underline underline-offset-4 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold"
            >
              Local tester downloads
            </Link>
          </div>

          <div className="order-1 flex justify-center md:order-2 md:justify-end">
            <div className="relative aspect-square w-[min(72vw,20rem)] md:w-[min(38vw,26rem)] lg:w-[28rem]">
              <div
                aria-hidden
                className="coin-glow pointer-events-none absolute -inset-[18%] rounded-full bg-[radial-gradient(closest-side,var(--gold-soft),transparent)]"
              />
              <div className="coin-in size-full">
                <div className="coin-float size-full">
                  <Image
                    src="/coin.png"
                    alt="The Meownero coin: a gold coin with a serious cat and the word MEOW."
                    width={1024}
                    height={1024}
                    priority
                    sizes="(min-width: 1024px) 28rem, (min-width: 768px) 38vw, 72vw"
                    className="size-full"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <Principles />

      <footer className="mx-auto w-full max-w-6xl px-6 pb-10 md:px-10">
        <div className="border-t border-border pt-6 text-sm text-muted-foreground">
          <p className="max-w-[60ch] text-pretty">
            Meownero is in development. Nothing is for sale, there is no token,
            and there is no presale. Anyone offering MEOW today is not us.
          </p>
        </div>
      </footer>
    </main>
  );
}
