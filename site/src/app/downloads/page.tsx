import type { Metadata } from "next";
import Link from "next/link";
import { getTesterCommands, getTesterRelease } from "@/lib/tester-release";

const title = "Downloads | Meownero";
const description =
  "Run Meownero's wallet test offline with Docker on Linux x64. Test coins only. The graphical wallet isn't available yet.";

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
          Linux x64 · Docker
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tighter text-balance md:text-5xl">
          Test Meownero locally.
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
          Receive test coins, send a payment and restore a wallet. The test
          runs offline on your machine, not on a public testnet.
        </p>
      </header>

      <section aria-labelledby="download-heading" className="mt-10 rounded-xl border border-gold/30 bg-card p-6 md:p-8">
        <h2 id="download-heading" className="text-xl font-semibold">
          Linux x64 Docker tester
        </h2>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Command-line only. The graphical wallet isn&apos;t ready to download.
        </p>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Test coins have no value. Never use real funds or your own recovery phrase.
        </p>

        {release.status === "published" ? (
          <div className="mt-6">
            <a href={release.bundle.url} className={linkStyle} download={release.bundle.filename}>
              Download tester ZIP
            </a>
            <p className="mt-2 break-all text-sm text-muted-foreground">
              {Math.round(release.bundle.bytes / 1024 / 1024)} MiB · Docker image, launcher and setup guide
            </p>
          </div>
        ) : (
          <div className="mt-6 rounded-lg border border-border bg-background p-4">
            <p className="font-medium">The download isn&apos;t ready yet.</p>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              The ZIP and setup instructions will appear here once we verify the download.
            </p>
          </div>
        )}
      </section>

      <section aria-labelledby="requirements-heading" className="mt-10">
        <h2 id="requirements-heading" className="text-xl font-semibold">You&apos;ll need</h2>
        <ul className="mt-4 list-disc space-y-3 pl-5 leading-relaxed text-muted-foreground">
          <li>Linux x64 with local Docker Engine, cgroup v2 and a Unix socket. The Docker client and daemon must run on the same kernel.</li>
          <li>Python 3.11 or newer, sha256sum and unzip.</li>
          <li>5 GiB of available memory and 5 GiB free for test results. Keep extra disk space for the ZIP, extracted files and Docker image.</li>
        </ul>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Use a non-root account with Docker access. Docker Desktop, remote
          Docker, ARM, macOS and Windows are untested.
        </p>
      </section>

      {commands ? (
        <section aria-labelledby="setup-heading" className="mt-10 space-y-6">
          <h2 id="setup-heading" className="text-xl font-semibold">Run the test</h2>
          <p className="leading-relaxed text-muted-foreground">
            Save the ZIP in a new folder and open a terminal there. Keep that
            terminal open for all four steps. Stop if any command fails.
          </p>
          <div>
            <h3 className="font-medium">1. Check the download</h3>
            <p className="mt-2 leading-relaxed text-muted-foreground">
              Keep the original ZIP filename. The checksum should print OK.
            </p>
            <Command>{commands.checksum}</Command>
          </div>
          <div>
            <h3 className="font-medium">2. Unpack it</h3>
            <p className="mt-2 leading-relaxed text-muted-foreground">
              This checks the files inside and moves into the kit folder. It
              refuses to overwrite an existing folder.
            </p>
            <Command>{commands.unpack}</Command>
          </div>
          <div>
            <h3 className="font-medium">3. Load the Docker image</h3>
            <Command>{commands.load}</Command>
            <p className="mt-3 leading-relaxed text-muted-foreground">
              Continue only if it prints &quot;Exact image verified: linux/amd64&quot;.
            </p>
          </div>
          <div>
            <h3 className="font-medium">4. Run it</h3>
            <p className="mt-2 leading-relaxed text-muted-foreground">
              Run this from the kit folder. It creates receipts/journey01 for
              the results. Use a new output folder for each run, with no symlinks
              in its parent path.
            </p>
            <Command>{commands.run}</Command>
            <p className="mt-3 leading-relaxed text-muted-foreground">
              In receipts/journey01, result.json must say PASS_NATIVE_JOURNEY.
              Check runtime.json for cleanup.removed set to true.
              Keep the results if a run fails.
            </p>
            <p className="mt-3 leading-relaxed text-muted-foreground">
              The tester removes its container and disposable wallets when it
              finishes. Only the test results stay on disk.
            </p>
          </div>
        </section>
      ) : null}

      <details className="mt-10 rounded-xl border border-border p-6">
        <summary className="cursor-pointer rounded-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold">
          Build details
        </summary>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          Tested on Ubuntu 24.04.4 LTS, Docker Engine 29.5.3, cgroup v2 and
          Python 3.14.7. Other hosts and versions are untested.
          This is an accelerated FCMP++/CARROT regtest in an Ubuntu container.
          The wallet test passed, along with timeout and interruption checks.
        </p>
        <dl className="mt-4 space-y-4 text-sm">
          {release.status === "published" ? (
            <>
              <div>
                <dt className="text-muted-foreground">ZIP filename</dt>
                <dd className="mt-1 break-all font-mono leading-relaxed">{release.bundle.filename}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">SHA256</dt>
                <dd className="mt-1 break-all font-mono leading-relaxed">{release.bundle.sha256}</dd>
              </div>
            </>
          ) : null}
          <div>
            <dt className="text-muted-foreground">Source commit</dt>
            <dd className="mt-1 break-all font-mono leading-relaxed">{release.sourceCommit}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Docker image ID</dt>
            <dd className="mt-1 break-all font-mono leading-relaxed">{release.imageId}</dd>
          </div>
        </dl>
      </details>
    </main>
  );
}
