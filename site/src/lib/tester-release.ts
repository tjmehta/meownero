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

// Publish only after the actual public ZIP bytes, size and checksum are verified.
// The ZIP has one root containing the image, reviewed launcher and notices.
const testerRelease: TesterRelease = {
  status: "unpublished",
  sourceCommit: "96aa5a836648153db7f2c3ef1e949b35b2f4bdff",
  imageId:
    "sha256:fd7256b13c90935782aedcebd23dcbd8dbe1e16853974ffb6722a116e32a13f9",
  bundleRoot: "meownero-vanguard-linux-x64-docker-96aa5a8",
  imageArchiveFilename: "meownero-vanguard-linux-x64-fd7256b1.docker.tar.gz",
};

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
