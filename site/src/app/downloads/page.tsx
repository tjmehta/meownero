import type { Metadata } from "next";
import Link from "next/link";
import { getTesterCommands, getTesterRelease } from "@/lib/tester-release";

const title = "Local tester downloads | Meownero";
const description =
  "A disposable Linux x64 Docker tester for Meownero's local, valueless FCMP++/CARROT regtest. No mainnet, public testnet or GUI wallet download.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: "/downloads" },
  openGraph: {
    title,
    description,
    url: "/downloads",
    siteName: "Meownero",
    type: "website",
  },
  twitter: { card: "summary_large_image", title, description },
};

const linkStyle =
  "rounded-sm text-gold underline underline-offset-4 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold";

function Command({ children }: { children: string }) {
  return (
    <pre
      tabIndex={0}
      aria-label="Terminal command, scroll horizontally if needed"
      className="mt-4 overflow-x-auto rounded-lg border border-border bg-background p-4 text-sm leading-relaxed focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold"
    >
      <code className="font-mono">{children}</code>
    </pre>
  );
}

export default function Downloads() {
  const release = getTesterRelease();
  const commands =
    release.status === "published" ? getTesterCommands(release) : null;

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10 md:px-10 md:py-16">
      <nav aria-label="Site">
        <Link href="/" className={linkStyle}>
          ← Meownero
        </Link>
      </nav>

      <header className="mt-12 max-w-2xl">
        <p className="text-sm font-medium tracking-wide text-gold">
          Test-only · Linux x64 · Docker
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tighter text-balance md:text-5xl">
          Try a local wallet journey.
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
          A disposable, accelerated FCMP++/CARROT regtest with valueless test
          coins. Everything stays on your own machine. This is not a shared
          public testnet or mainnet, and it must not be used with real funds.
        </p>
      </header>

      <section aria-labelledby="download-heading" className="mt-10 rounded-xl border border-gold/30 bg-card p-6 md:p-8">
        <h2 id="download-heading" className="text-xl font-semibold">
          Linux x64 Docker tester
        </h2>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Native Linux programs in an Ubuntu container, with a command-line
          launcher. Not a graphical wallet.
        </p>

        {release.status === "published" ? (
          <div className="mt-6 space-y-6">
            {[
              { label: "Docker image archive", artifact: release.imageArchive },
              { label: "Launcher and source kit", artifact: release.sourceKit },
            ].map(({ label, artifact }) => (
              <div key={artifact.filename}>
                <a href={artifact.url} className={linkStyle} download={artifact.filename}>
                  Download {label.toLowerCase()}
                </a>
                <p className="mt-2 break-all text-sm text-muted-foreground">
                  {artifact.filename} · {artifact.bytes.toLocaleString("en-US")} bytes
                </p>
                <p className="mt-2 text-xs text-muted-foreground">SHA256</p>
                <code className="mt-1 block break-all font-mono text-sm leading-relaxed">
                  {artifact.sha256}
                </code>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-6 rounded-lg border border-border bg-background p-4">
            <p className="font-medium">Downloads are not published yet.</p>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              The local tester has been verified. Download links and setup
              instructions will appear here when the published files and their
              checksums are ready.
            </p>
          </div>
        )}
      </section>

      <section aria-labelledby="requirements-heading" className="mt-10">
        <h2 id="requirements-heading" className="text-xl font-semibold">Before you start</h2>
        <ul className="mt-4 list-disc space-y-3 pl-5 leading-relaxed text-muted-foreground">
          <li>A local Linux x64 machine, Docker with cgroup v2, and Python 3.11 or newer.</li>
          <li>Docker client and daemon on the same Linux kernel, using a local Unix socket. Remote Docker, Docker Desktop, ARM, macOS and Windows are not supported by this tester.</li>
          <li>At least 5 GiB of actually available memory, plus 10 GiB of free space at the output location and at the Docker data location.</li>
          <li>Run as a non-root user with Docker access. Use only disposable test wallets, never a personal recovery phrase.</li>
        </ul>
      </section>

      <section aria-labelledby="journey-heading" className="mt-10">
        <h2 id="journey-heading" className="text-xl font-semibold">What it checks</h2>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Receive test coins, make a private payment, recover a test wallet,
          spend again, and open the recovered wallet in the CLI. A full journey
          has passed, along with deadline and live-interruption checks that
          confirmed the tester cleans up its processes and container.
        </p>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          The run is offline. Disposable wallet data is removed when its
          container is cleaned up; only public test results are kept in your
          chosen output folder.
        </p>
      </section>

      {commands ? (
        <section aria-labelledby="setup-heading" className="mt-10 space-y-6">
          <h2 id="setup-heading" className="text-xl font-semibold">Verify, load, then run</h2>
          <div>
            <h3 className="font-medium">1. Check both downloads</h3>
            <p className="mt-2 leading-relaxed text-muted-foreground">
              Save both files with the names shown above and open a terminal in
              that folder. Both checksum checks must report OK. Stop if either fails.
            </p>
            <Command>{commands.checksum}</Command>
          </div>
          <div>
            <h3 className="font-medium">2. Load the image and confirm its identity</h3>
            <Command>{commands.load}</Command>
            <p className="mt-3 leading-relaxed text-muted-foreground">
              The printed image ID must match the exact image below. Stop if it
              does not match.
            </p>
          </div>
          <div>
            <h3 className="font-medium">3. Run the local journey</h3>
            <p className="mt-2 leading-relaxed text-muted-foreground">
              Unpack the launcher and source kit into its own folder. Open a
              terminal at the kit root, where vanguard/docker/run.py is present.
              The output folder must not already exist; choose a new name for
              every run. The launcher uses the existing current folder as its parent.
            </p>
            <Command>{commands.run}</Command>
            <p className="mt-3 leading-relaxed text-muted-foreground">
              Look for PASS_NATIVE_JOURNEY in result.json and runtime.json in
              your output folder. No public network connection or real coins are needed.
            </p>
          </div>
        </section>
      ) : null}

      <section aria-labelledby="identity-heading" className="mt-10 rounded-xl border border-border p-6">
        <h2 id="identity-heading" className="text-xl font-semibold">Exact tester identity</h2>
        <dl className="mt-4 space-y-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Source commit</dt>
            <dd className="mt-1 break-all font-mono leading-relaxed">{release.sourceCommit}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Docker image ID</dt>
            <dd className="mt-1 break-all font-mono leading-relaxed">{release.imageId}</dd>
          </div>
        </dl>
      </section>

      <footer className="mt-10 border-t border-border pt-6 text-sm leading-relaxed text-muted-foreground">
        <p>
          No graphical wallet is available to download. The current UI is a
          separate, simulated prototype, not a working wallet. Meownero remains
          in development; there is no token sale or presale.
        </p>
      </footer>
    </main>
  );
}
