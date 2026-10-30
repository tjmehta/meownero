type Artifact = Readonly<{
  url: string;
  filename: string;
  bytes: number;
  sha256: string;
}>;

type ReleaseIdentity = Readonly<{
  sourceCommit: string;
  imageId: string;
  bundleRoot: string;
  imageArchiveFilename: string;
}>;

export type TesterRelease = ReleaseIdentity &
  (
    | Readonly<{ status: "unpublished" }>
    | Readonly<{
        status: "published";
        bundle: Artifact;
      }>
  );

// Hosted ZIP bytes, size and checksum verified before staging this download.
// The ZIP has one root containing the image, reviewed launcher and notices.
const testerRelease: TesterRelease = {
  status: "published",
  bundle: {
    url: "/downloads/artifacts/meownero-vanguard-linux-x64-docker-96aa5a8.zip",
    filename: "meownero-vanguard-linux-x64-docker-96aa5a8.zip",
    bytes: 190475713,
    sha256: "0b72d59fba8bd01b1ba45e72016c4e5c36176026918c1152c1e75d3e01030978",
  },
  sourceCommit: "96aa5a836648153db7f2c3ef1e949b35b2f4bdff",
  imageId:
    "sha256:fd7256b13c90935782aedcebd23dcbd8dbe1e16853974ffb6722a116e32a13f9",
  bundleRoot: "meownero-vanguard-linux-x64-docker-96aa5a8",
  imageArchiveFilename: "meownero-vanguard-linux-x64-fd7256b1.docker.tar.gz",
};

export type NativeTesterRelease = Readonly<{
  archive: Artifact;
  archiveRoot: string;
  sourceCommit: string;
}>;

// Hosted archive bytes, size and checksum verified before staging this
// download. They match the independently accepted Linux38 archive; its root
// folder holds the launcher, native programs and license notices.
const nativeTesterRelease: NativeTesterRelease = {
  archive: {
    url: "/downloads/artifacts/meownero-vanguard-linux38-x86_64.tar.gz",
    filename: "meownero-vanguard-linux38-x86_64.tar.gz",
    bytes: 76582444,
    sha256: "fc4bde3b0a665bebcd22140fbc67fad2f15b5c841252a18dff0d5c5d79d56743",
  },
  archiveRoot: "meownero-vanguard-x86_64",
  sourceCommit: "be5e7b161a08bbb396a00c46905b3ade6eec21aa",
};

// Exact reviewed packaging successor. This is a test-and-report handoff,
// not native Windows execution acceptance or a release.
const windowsTestBundle: Artifact = {
  url: "/downloads/artifacts/meownero-windows-test-sanitized-v1.zip",
  filename: "meownero-windows-test-sanitized-v1.zip",
  bytes: 164091051,
  sha256: "eb6b76d387f26e5b4a9f849d8e7de2fbf11e9ce06a221cb16b3f5dbd0502da46",
};

export function getWindowsTestBundle(): Artifact {
  validateArtifact(windowsTestBundle);
  return windowsTestBundle;
}

const sha256Pattern = /^[a-f0-9]{64}$/;
const filenamePattern = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

function validateArtifact(artifact: Artifact): void {
  if (
    !filenamePattern.test(artifact.filename) ||
    artifact.url !== `/downloads/artifacts/${artifact.filename}` ||
    !Number.isSafeInteger(artifact.bytes) ||
    artifact.bytes <= 0 ||
    !sha256Pattern.test(artifact.sha256)
  ) {
    throw new Error("Invalid published tester artifact metadata");
  }
}

function validateIdentity(release: ReleaseIdentity): void {
  if (
    !/^[a-f0-9]{40}$/.test(release.sourceCommit) ||
    !/^sha256:[a-f0-9]{64}$/.test(release.imageId) ||
    !filenamePattern.test(release.bundleRoot) ||
    !filenamePattern.test(release.imageArchiveFilename)
  ) {
    throw new Error("Invalid tester release identity");
  }
}

function validateBundle(release: Extract<TesterRelease, { status: "published" }>) {
  validateIdentity(release);
  validateArtifact(release.bundle);
  if (release.bundle.filename !== `${release.bundleRoot}.zip`) {
    throw new Error("Tester ZIP must match its verified root directory");
  }
}

export function getTesterRelease(): TesterRelease {
  validateIdentity(testerRelease);
  if (testerRelease.status === "published") {
    validateBundle(testerRelease);
  }
  return testerRelease;
}

export function getTesterCommands(
  release: Extract<TesterRelease, { status: "published" }>,
) {
  // Only validated local basenames and fixed release identifiers enter shell
  // examples. First-party download paths are links, never shell commands.
  validateBundle(release);
  return {
    checksum: `printf '%s  %s\\n' '${release.bundle.sha256}' '${release.bundle.filename}' | sha256sum --check`,
    unpack: `test ! -e '${release.bundleRoot}' && test ! -L '${release.bundleRoot}' &&\nunzip '${release.bundle.filename}' &&\ncd '${release.bundleRoot}' &&\nsha256sum --check SHA256SUMS`,
    load: `docker load --input '${release.imageArchiveFilename}' &&\ntest "$(docker image inspect --format '{{.Id}}' '${release.imageId}')" = '${release.imageId}' &&\ntest "$(docker image inspect --format '{{.Os}}/{{.Architecture}}' '${release.imageId}')" = 'linux/amd64' &&\nprintf '%s\\n' 'Exact image verified: linux/amd64'`,
    run: `mkdir -m 700 receipts &&\npython3 -B vanguard/docker/run.py --image '${release.imageId}' --out ./receipts/journey01`,
  };
}

function validateNativeRelease(release: NativeTesterRelease): void {
  validateArtifact(release.archive);
  if (
    !/^[a-f0-9]{40}$/.test(release.sourceCommit) ||
    !filenamePattern.test(release.archiveRoot) ||
    !release.archive.filename.endsWith(".tar.gz")
  ) {
    throw new Error("Invalid native tester release metadata");
  }
}

export function getNativeTesterRelease(): NativeTesterRelease {
  validateNativeRelease(nativeTesterRelease);
  return nativeTesterRelease;
}

export function getNativeTesterCommands(release: NativeTesterRelease) {
  // Same rule as the Docker commands: only validated basenames and fixed
  // identifiers enter shell examples.
  validateNativeRelease(release);
  return {
    checksum: `printf '%s  %s\\n' '${release.archive.sha256}' '${release.archive.filename}' | sha256sum --check`,
    unpack: `test ! -e '${release.archiveRoot}' && test ! -L '${release.archiveRoot}' &&\ntar -xzf '${release.archive.filename}' &&\ncd '${release.archiveRoot}'`,
    run: `./launch.sh preflight &&\n./launch.sh run --out ../journey01`,
  };
}
