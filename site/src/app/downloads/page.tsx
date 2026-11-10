import type { Metadata } from "next";
import Link from "next/link";
import { cn } from "cn";
import { Command } from "@/components/command";
import { buttonVariants } from "@/components/ui/button";
import {
  getMacTesterRelease,
  getNativeTesterCommands,
  getNativeTesterRelease,
  getPreviousWindowsTestBundle,
  getTesterCommands,
  getTesterRelease,
  getWindowsTestBundle,
} from "@/lib/tester-release";

const title = "Downloads | Meownero";
const description =
  "Run Meownero's wallet test offline on Apple Silicon Mac, Windows or Linux x64. Test coins only. The graphical wallet isn't available yet.";

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
  const windows = getWindowsTestBundle();
  const previousWindows = getPreviousWindowsTestBundle();
  const mac = getMacTesterRelease();

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10 wrap-break-word md:px-10 md:py-16">
      <nav aria-label="Site">
        <Link href="/" className={cn(linkStyle, "-mx-2 inline-flex min-h-11 items-center px-2")}>
          ← Meownero
        </Link>
      </nav>

      <header className="mt-8 max-w-2xl md:mt-12">
        <p className="text-sm font-medium tracking-wide text-gold">
          Test-only · Mac, Windows and Linux
        </p>
        <h1 className="mt-4 text-[clamp(1.75rem,11vw,2.25rem)] leading-[1.1] font-semibold tracking-tighter text-balance md:text-5xl md:leading-none">
          Test Meownero locally.
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-muted-foreground">
          Receive test coins, send a payment and restore a wallet. The test
          runs offline on your machine, not on a public testnet.
        </p>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Apple Silicon Mac testers can try the native archive below.
          Windows testers can run the experimental test-and-report bundle.
          Linux x64 testers can choose a native archive or a Docker bundle.
        </p>
      </header>

      <section id="macos" aria-labelledby="macos-heading" className="mt-10 rounded-xl border border-gold/30 bg-card p-4 md:p-8">
        <h2 id="macos-heading" className="text-xl font-semibold">
          Apple Silicon Mac tester
        </h2>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          This file replaces the October 10 Apple Silicon archive. It runs
          private, valueless test coins on your own machine only. It is a
          command-line tester, not a graphical wallet or public network.
        </p>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Independently tested natively on one Apple Silicon Mac with macOS
          26.5.1: receive test coins, restore the wallet, spend from the restored
          wallet, and all ten refusal and cleanup checks passed.
        </p>
        <div className="mt-6">
          <a href={mac.archive.url} className={downloadStyle} download={mac.archive.filename}>
            Download Apple Silicon tester
          </a>
          <p className="mt-2 text-sm wrap-anywhere text-muted-foreground">
            {mac.archive.filename} · {mac.archive.bytes.toLocaleString("en-US")} bytes
          </p>
          <p className="mt-2 text-xs text-muted-foreground">SHA256</p>
          <code className="mt-1 block break-all font-mono text-sm leading-relaxed">
            {mac.archive.sha256}
          </code>
        </div>
        <h3 className="mt-6 font-medium">Before you start</h3>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          Apple Silicon only, Python 3.8 or later, two CPU cores, 5 GiB available
          memory and 5 GiB free disk. The programs declare macOS 11.0 as their
          minimum; older macOS versions and a fresh macOS install are untested.
          Use only disposable wallets, never a personal recovery phrase.
        </p>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Ad hoc signatures only: not Developer ID signed or notarized. macOS
          download approval (Gatekeeper) has not been tested. A browser download
          may be quarantined and macOS may refuse to run the programs; neither
          outcome has been observed. TESTER.md treats download approval as a
          separate check and gives no workaround.
        </p>
        <h3 className="mt-6 font-medium">Check, extract, then run</h3>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          Suggested alternative: download in Terminal with curl. This download
          route is also untested; it does not establish macOS approval.
          In a new folder, run:
        </p>
        <Command>{`curl --fail --location --output '${mac.archive.filename}' 'https://meownero.com${mac.archive.url}'`}</Command>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Whether downloaded in your browser or Terminal, check the file before
          extracting. Compare the output below with the SHA256 above. Stop if
          they differ.
        </p>
        <Command>{`shasum -a 256 '${mac.archive.filename}'`}</Command>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          After the hash matches, extract into a new folder and open the package:
        </p>
        <Command>{`test ! -e '${mac.archiveRoot}' && test ! -L '${mac.archiveRoot}' &&\ntar xzf '${mac.archive.filename}' &&\ncd '${mac.archiveRoot}'`}</Command>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Read TESTER.md, then run preflight and the journey. The output folder
          must not already exist; choose a fresh name for every run.
        </p>
        <Command>{`./launch.sh preflight &&\n./launch.sh run --out ../my-disposable-journey`}</Command>
        <p className="mt-4 leading-relaxed text-muted-foreground">
          Share only my-disposable-journey/result.json, including a failed
          receipt. Never share private/ or the whole output folder: it holds
          disposable wallets, chain data and logs.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          The unchanged package says BUILT_UNTESTED because that status was
          frozen at build time. The later independent native acceptance applies
          to the exact SHA256 above, not other Macs or download methods.
        </p>
        <dl className="mt-6 text-sm">
          <dt className="text-muted-foreground">Source commit</dt>
          <dd className="mt-1 break-all font-mono leading-relaxed">{mac.sourceCommit}</dd>
        </dl>
      </section>

      <section id="windows" aria-labelledby="windows-heading" className="mt-10 rounded-xl border border-gold/30 bg-card p-4 md:p-8">
        <p className="text-sm font-medium text-gold">Experimental Windows diagnostics · v2</p>
        <h2 id="windows-heading" className="mt-2 text-xl font-semibold">
          Run the Windows tests and send back a report.
        </h2>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          This unsigned experimental diagnostic bundle needs fresh native
          Windows checks. The earlier ARM wallet, restore, later-spend and CLI
          checks passed, but control coverage was incomplete. The earlier
          Intel funding attempt timed out; its cause is still unknown.
          This is not a wallet fix or a verified Windows release.
        </p>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          It is designed to test startup, test-coin payments, wallet recovery,
          refusal cases and process cleanup on your own computer. No real
          funds, personal recovery phrases or public network are involved.
        </p>
        <div className="mt-6">
          <a href={windows.url} className={downloadStyle} download={windows.filename}>
            Download Windows diagnostics v2
          </a>
          <p className="mt-2 text-sm wrap-anywhere text-muted-foreground">
            {windows.filename} · {windows.bytes.toLocaleString("en-US")} bytes
          </p>
          <p className="mt-2 text-xs text-muted-foreground">SHA256</p>
          <code className="mt-1 block break-all font-mono text-sm leading-relaxed">
            {windows.sha256}
          </code>
        </div>
        <h3 className="mt-6 font-medium">Before you start</h3>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          Use Intel/AMD x64 Windows or Windows on ARM64, with at least 10 GiB
          free disk space and 5 GiB available RAM. Standalone 32-bit Windows is
          not supported. Close any other Meownero tester first; do not run as
          administrator.
        </p>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          The existing requirements remain native 64-bit CPython 3.13 or later
          with the Python launcher: x64 CPython on Intel/AMD, native ARM64
          CPython on ARM Windows. Emulated x64 Python on ARM is refused.
          Follow READ-ME.md for the launcher and Windows requirements; this
          rerun does not call for new packages, elevation or policy changes.
        </p>
        <h3 className="mt-6 font-medium">Check, extract, then run</h3>
        <p className="mt-2 leading-relaxed text-muted-foreground">
          Save the ZIP, open PowerShell in its folder and compare this command&apos;s
          output with the SHA256 above. Stop if they differ.
        </p>
        <Command>{`(Get-FileHash -Algorithm SHA256 '.\\${windows.filename}').Hash`}</Command>
        <ol className="mt-4 list-decimal space-y-3 pl-5 leading-relaxed text-muted-foreground">
          <li>Extract the entire ZIP into a new writable local folder. Keep all files together.</li>
          <li>Open the extracted meownero-windows-test folder and double-click RUN-TEST.cmd. Leave the window open and allow up to 25 minutes.</li>
          <li>Let owned-process cleanup finish. Send back only the generated report.zip, including incomplete, FAIL or NOT_RUN results. Read it before sharing.</li>
        </ol>
        <p className="mt-3 leading-relaxed text-muted-foreground">
          Do not share the whole run folder: it can contain disposable wallets,
          seeds and private logs. If cancelling, press Ctrl+C once and allow
          cleanup to finish. Force-closing the window may prevent a report.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          On ARM, symlink-fixture error 1314 alone must record NOT_EXECUTED,
          continue later controls, and finish INCOMPLETE_NATIVE_ARCHIVE_CONTROLS
          with exit 2, never PASS. If symlink creation works, actual rejection
          and all ten controls are required. Other fixture and refusal errors
          remain failures. Do not elevate or change Windows policy.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Intel funding failures now report generateblocks, refresh or
          get_balance and elapsed/budget/deadline values. The 90-second socket,
          1200-second journey and 1500-second controller budgets are unchanged.
          A timeout identifies the operation, not the underlying engine cause.
          Please return the report whether the full journey passes or fails.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Intel/AMD x64 PCs run the i68635 programs through WoW64; ARM64 PCs run
          ARM13 and require ARMv8 crypto support. These are not native x64
          programs, and standalone 32-bit Windows support is not established.
          Source and this exact bundle have scoped independent acceptance;
          that supersedes only the unchanged ZIP&apos;s review-pending wording.
          Native successor execution remains unverified. Optional
          native_cli_event NOT_REQUESTED is informational. A report is evidence
          for that machine, not whole-release acceptance.
        </p>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          Previous bundle, retained for reference (use v2 for this rerun):{" "}
          <a href={previousWindows.url} className={linkStyle} download={previousWindows.filename}>
            {previousWindows.filename}
          </a>
        </p>
      </section>

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
