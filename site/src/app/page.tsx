import Image from "next/image";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Principles } from "@/components/principles";
import { Notify } from "@/components/notify";
import { cn } from "cn";

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
        "Meownero is a proof-of-work cryptocurrency in development. Every payment is private. No premine or presale.",
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
      name: "Meownero | Private payments, proof of work",
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
      <section className="relative isolate flex items-center overflow-hidden md:min-h-[100dvh]">
        <div className="mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-6 px-6 pt-8 pb-16 md:grid-cols-[1.1fr_1fr] md:gap-8 md:px-10 md:py-24">
          <div className="order-2 flex flex-col items-start md:order-1">
            <Badge
              variant="outline"
              className="rise border-gold/40 bg-gold-soft px-3 text-gold"
              style={{ "--i": 0 } as React.CSSProperties}
            >
              In development
            </Badge>

            <h1
              className="rise mt-5 max-w-[14ch] text-[clamp(2.25rem,11vw,3rem)] leading-none font-semibold tracking-tighter text-balance md:text-6xl lg:text-7xl"
              style={{ "--i": 1 } as React.CSSProperties}
            >
              Every payment is private.
            </h1>

            <p
              className="rise mt-4 max-w-[42ch] text-lg leading-relaxed text-muted-foreground text-pretty md:text-xl"
              style={{ "--i": 2 } as React.CSSProperties}
            >
              A proof-of-work coin. No premine, no presale.
            </p>

            <div className="rise mt-6 w-full" style={{ "--i": 3 } as React.CSSProperties}>
              <Notify />
            </div>

            <div
              className="rise mt-5 w-full max-w-sm"
              style={{ "--i": 4 } as React.CSSProperties}
            >
              <Link
                href="/downloads"
                className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 w-full px-4 sm:w-auto")}
              >
                Try the Linux tester
              </Link>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                Local, valueless test coins on your own machine. Not a public
                testnet or mainnet.
              </p>
            </div>
          </div>

          <div className="order-1 flex justify-center md:order-2 md:justify-end">
            <div className="relative aspect-square w-[min(52vw,14rem)] md:w-[min(38vw,26rem)] lg:w-[28rem]">
              <div
                aria-hidden
                className="coin-glow pointer-events-none absolute -inset-[18%] rounded-full bg-[radial-gradient(closest-side,var(--gold-soft),transparent)]"
              />
              <div className="coin-in size-full">
                <div className="coin-float size-full">
                  <Image
                    src="/coin.png"
                    alt="Gold Meownero coin with a cat and MEOW lettering"
                    width={1024}
                    height={1024}
                    priority
                    sizes="(min-width: 1024px) 28rem, (min-width: 768px) 38vw, 52vw"
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
            MEOW isn&apos;t for sale. Anyone offering it now isn&apos;t us.
          </p>
        </div>
      </footer>
    </main>
  );
}
