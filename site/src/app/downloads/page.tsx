import type { Metadata } from "next";
import Link from "next/link";
import {
  getNativeTesterCommands,
  getNativeTesterRelease,
  getTesterCommands,
  getTesterRelease,
} from "@/lib/tester-release";

const title = "Local tester downloads | Meownero";
const description =
  "Disposable Linux x64 testers for Meownero's local, valueless FCMP++/CARROT regtest: a native archive and a Docker bundle. No mainnet, public testnet or GUI wallet download.";

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
  const native = getNativeTesterRelease();
  const nativeCommands = getNativeTesterCommands(native);

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10 md:px-10 md:py-16">
      <nav aria-label="Site">
        <Link href="/" className={linkStyle}>
          ← Meownero
        </Link>
      </nav>

      <header className="mt-12 max-w-2xl">
        <p className="text-sm font-medium tracking-wide text-gold">
          Test-only · Linux x64
        </p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tighter text-balance md:text-5xl">
          Try a local wallet journey.
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
          A disposable, accelerated FCMP++/CARROT regtest with valueless test
          coins. Everything stays on your own machine. This is not a shared
          public testnet or mainnet, and it must not be used with real funds.
        </p>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Two testers run the same kind of journey: a native archive that runs
          the programs directly, and a Docker bundle that runs them in a
          container.
        </p>
      </header>

      <section aria-labelledby="native-heading" className="mt-10">
        <div className="rounded-xl border border-gold/30 bg-card p-6 md:p-8">
          <h2 id="native-heading" className="text-xl font-semibold">
            Linux x64 native tester
          </h2>
          <p className="mt-3 leading-relaxed text-muted-foreground">
            Native Linux programs with a command-line launcher. No Docker, and
            it installs nothing. Not a graphical wallet.
          </p>
          <div className="mt-6">
            <a href={native.archive.url} className={linkStyle} download={native.archive.filename}>
              Download native tester
            </a>
            <p className="mt-2 break-all text-sm text-muted-foreground">
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

      <section aria-labelledby="download-heading" className="mt-10 rounded-xl border border-gold/30 bg-card p-6 md:p-8">
        <h2 id="download-heading" className="text-xl font-semibold">
          Linux x64 Docker tester
        </h2>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Native Linux programs in an Ubuntu container, with a command-line
          launcher. Not a graphical wallet.
        </p>

        {release.status === "published" ? (
          <div className="mt-6">
            <a href={release.bundle.url} className={linkStyle} download={release.bundle.filename}>
              Download tester ZIP
            </a>
            <p className="mt-2 break-all text-sm text-muted-foreground">
              {release.bundle.filename} · {release.bundle.bytes.toLocaleString("en-US")} bytes
            </p>
            <p className="mt-2 text-xs text-muted-foreground">SHA256</p>
            <code className="mt-1 block break-all font-mono text-sm leading-relaxed">
              {release.bundle.sha256}
            </code>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              One bundle includes the Docker image, launcher, verification guide
              and license notices.
            </p>
          </div>
        ) : (
          <div className="mt-6 rounded-lg border border-border bg-background p-4">
            <p className="font-medium">Downloads are not published yet.</p>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              The local tester has been verified. A ZIP download and setup
              instructions will appear here when the published bundle and its
              checksum are ready.
            </p>
          </div>
        )}
      </section>

      <section aria-labelledby="requirements-heading" className="mt-10">
        <h2 id="requirements-heading" className="text-xl font-semibold">Before you start with Docker</h2>
        <ul className="mt-4 list-disc space-y-3 pl-5 leading-relaxed text-muted-foreground">
          <li>Tested on Ubuntu 24.04.4 LTS, Linux x64, Docker Engine 29.5.3, cgroup v2 and Python 3.14.7. Python 3.11 or newer is the baseline; other hosts and versions are untested.</li>
          <li>Docker client and daemon on the same Linux kernel, using a local Unix socket. This tester makes no support claim for remote Docker, Docker Desktop, ARM, macOS or Windows.</li>
          <li>At least 5 GiB of available host memory and 5 GiB free on the receipt filesystem. Allow extra disk space for the ZIP download, extraction and loaded image.</li>
          <li>Python, sha256sum and unzip must already be installed.</li>
          <li>Run as a non-root user with Docker access. Use only disposable test wallets, never a personal recovery phrase.</li>
        </ul>
      </section>

      <section aria-labelledby="journey-heading" className="mt-10">
        <h2 id="journey-heading" className="text-xl font-semibold">What the Docker tester checks</h2>
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
          <h2 id="setup-heading" className="text-xl font-semibold">Docker: verify, load, then run</h2>
          <div>
            <h3 className="font-medium">1. Check the ZIP before extraction</h3>
            <p className="mt-2 leading-relaxed text-muted-foreground">
              Save the ZIP with the name shown above in a new folder and open a
              terminal there. The checksum must report OK. Stop if any check or
              command below fails.
            </p>
            <Command>{commands.checksum}</Command>
          </div>
          <div>
            <h3 className="font-medium">2. Extract and check the bundle contents</h3>
            <p className="mt-2 leading-relaxed text-muted-foreground">
              The extracted kit folder must not already exist. Check all included
              files with SHA256SUMS, then stay in this same terminal at the kit root.
            </p>
            <Command>{commands.unpack}</Command>
          </div>
          <div>
            <h3 className="font-medium">3. Load and verify the exact Linux x64 image</h3>
            <Command>{commands.load}</Command>
            <p className="mt-3 leading-relaxed text-muted-foreground">
              Continue only when the checks print &ldquo;Exact image verified:
              linux/amd64&rdquo;. They require both the full image ID below and
              the Linux x64 platform to match.
            </p>
          </div>
          <div>
            <h3 className="font-medium">4. Run the local journey</h3>
            <p className="mt-2 leading-relaxed text-muted-foreground">
              Run as a non-root user from the kit root. This creates a fresh
              receipts folder and a new journey01 output directory. The output
              parent must exist and contain no symlinks. Use a fresh output name
              for every later run.
            </p>
            <Command>{commands.run}</Command>
            <p className="mt-3 leading-relaxed text-muted-foreground">
              Require PASS_NATIVE_JOURNEY in result.json, and confirm in
              runtime.json that cleanup removed the run&apos;s own container.
              Both files are in receipts/journey01. Keep failed receipts for
              diagnosis. No public network connection or real coins are needed.
            </p>
          </div>
        </section>
      ) : null}

      <section aria-labelledby="identity-heading" className="mt-10 rounded-xl border border-border p-6">
        <h2 id="identity-heading" className="text-xl font-semibold">Exact Docker tester identity</h2>
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
