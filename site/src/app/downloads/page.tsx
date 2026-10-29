import type { Metadata } from "next";
import Link from "next/link";
import { cn } from "cn";
import { Command } from "@/components/command";
import { buttonVariants } from "@/components/ui/button";
import {
  getNativeTesterCommands,
  getNativeTesterRelease,
  getTesterCommands,
  getTesterRelease,
} from "@/lib/tester-release";

const title = "Downloads | Meownero";
const description =
  "Run Meownero's wallet test offline on Linux x64, natively or with Docker. Test coins only. The graphical wallet isn't available yet.";

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

// The primary action on each tester card: a real link with download, styled
// as the site's gold button. Full width on phones.
const downloadStyle = cn(buttonVariants({ size: "lg" }), "h-11 w-full px-4 text-base md:w-auto");

export default function Downloads() {
  const release = getTesterRelease();
  const commands =
    release.status === "published" ? getTesterCommands(release) : null;
  const native = getNativeTesterRelease();
  const nativeCommands = getNativeTesterCommands(native);

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10 wrap-break-word md:px-10 md:py-16">
      <nav aria-label="Site">
        <Link href="/" className={cn(linkStyle, "-mx-2 inline-flex min-h-11 items-center px-2")}>
          ← Meownero
        </Link>
      </nav>

      <header className="mt-8 max-w-2xl md:mt-12">
        <p className="text-sm font-medium tracking-wide text-gold">
          Test-only · Linux x64
        </p>
        <h1 className="mt-4 text-[clamp(1.75rem,11vw,2.25rem)] leading-[1.1] font-semibold tracking-tighter text-balance md:text-5xl md:leading-none">
          Test Meownero locally.
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
          Receive test coins, send a payment and restore a wallet. The test
          runs offline on your machine, not on a public testnet.
        </p>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Two testers run the same kind of journey: a native archive that runs
          the programs directly, and a Docker bundle that runs them in a
          container.
        </p>
      </header>

      <section aria-labelledby="native-heading" className="mt-10">
        <div className="rounded-xl border border-gold/30 bg-card p-4 md:p-8">
          <h2 id="native-heading" className="text-xl font-semibold">
            Linux x64 native tester
          </h2>
          <p className="mt-3 leading-relaxed text-muted-foreground">
            Native Linux programs with a command-line launcher. No Docker, and
            it installs nothing. Not a graphical wallet.
          </p>
          <div className="mt-6">
            <a href={native.archive.url} className={downloadStyle} download={native.archive.filename}>
              Download native tester
            </a>
            <p className="mt-2 text-sm wrap-anywhere text-muted-foreground">
              {native.archive.filename} · {native.archive.bytes.toLocaleString("en-US")} bytes
            </p>
            <p className="mt-2 text-xs text-muted-foreground">SHA256</p>
            <code className="mt-1 block break-all font-mono text-sm leading-relaxed">
              {native.archive.sha256}
            </code>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Unsigned. Tested on an Ubuntu 22.04 userland (glibc 2.35) running
              on an Ubuntu 24.04 x64 kernel. Bare-metal Ubuntu 22.04, Debian 12
              and other distributions are untested.
            </p>
          </div>
        </div>

        <h2 className="mt-10 text-xl font-semibold">Before you start</h2>
        <ul className="mt-4 list-disc space-y-3 pl-5 leading-relaxed text-muted-foreground">
          <li>Linux x64 with glibc 2.35 or newer, Python 3.8 or newer, tar and sha256sum.</li>
          <li>Two CPU cores, at least 5 GiB of available memory and 5 GiB of free disk space.</li>
          <li>Run as a non-root user. Use only disposable test wallets, never a personal recovery phrase.</li>
        </ul>

        <h2 className="mt-10 text-xl font-semibold">Verify, extract, then run</h2>
        <h3 className="mt-6 font-medium">1. Check the archive before extraction</h3>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          Save the archive with the name shown above in a new folder and open a
          terminal there. The checksum must report OK. Stop if any check or
          command below fails.
        </p>
        <Command>{nativeCommands.checksum}</Command>

        <h3 className="mt-6 font-medium">2. Extract it</h3>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          The extracted folder must not already exist. Stay in this terminal
          inside it.
        </p>
        <Command>{nativeCommands.unpack}</Command>

        <h3 className="mt-6 font-medium">3. Check the package, then run the local journey</h3>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          The preflight checks every packaged file, the source pins, the
          architecture and your glibc version. The run writes to a new
          journey01 folder beside the package; use a fresh name for every
          later run.
        </p>
        <Command>{nativeCommands.run}</Command>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Require PASS_NATIVE_JOURNEY in journey01/result.json. That receipt is
          the only file to share. Keep journey01/private unshared: it holds the
          disposable wallets, chain data and logs. Read TESTER.md in the package
          for manual wallet commands.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          The package&apos;s own release.json still says BUILT_UNTESTED because it
          was frozen at build time. The later native journey and independent
          review are bound to the SHA256 above.
        </p>

        <h2 className="mt-10 text-xl font-semibold">What it checks</h2>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Mine test coins, send five to a new wallet, confirm the private
          FCMP++/CARROT payment, recover that wallet from its seed, then spend
          two coins back and confirm receipt. Programs listen only on
          loopback, each attempt has a twenty-minute deadline, and the launcher
          stops only its own processes.
        </p>

        <dl className="mt-6 text-sm">
          <dt className="text-muted-foreground">Source commit</dt>
          <dd className="mt-1 break-all font-mono leading-relaxed">{native.sourceCommit}</dd>
        </dl>
      </section>

      <section aria-labelledby="download-heading" className="mt-10 rounded-xl border border-gold/30 bg-card p-4 md:p-8">
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
            <a href={release.bundle.url} className={downloadStyle} download={release.bundle.filename}>
              Download tester ZIP
            </a>
            <p className="mt-2 text-sm wrap-anywhere text-muted-foreground">
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
        <h2 id="requirements-heading" className="text-xl font-semibold">Before you start with Docker</h2>
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
          <h2 id="setup-heading" className="text-xl font-semibold">Run the Docker test</h2>
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

      <details className="mt-10 rounded-xl border border-border p-4 md:p-6">
        <summary className="-my-2.5 cursor-pointer rounded-sm py-2.5 font-medium focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-gold">
          Docker build details
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
