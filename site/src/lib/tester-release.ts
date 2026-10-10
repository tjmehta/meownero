type Artifact = Readonly<{
  url: string;
  filename: string;
  bytes: number;
  sha256: string;
}>;

type ReleaseIdentity = Readonly<{
  sourceCommit: string;
  imageId: string;
}>;

export type TesterRelease = ReleaseIdentity &
  (
    | Readonly<{ status: "unpublished" }>
    | Readonly<{
        status: "published";
        imageArchive: Artifact;
        sourceKit: Artifact;
      }>
  );

// Set status to published only after both public downloads have been retrieved
// and their exact transport bytes, sizes, filenames and checksums verified.
// The source kit must retain vanguard/docker/run.py and its support module.
const testerRelease: TesterRelease = {
  status: "unpublished",
  sourceCommit: "96aa5a836648153db7f2c3ef1e949b35b2f4bdff",
  imageId:
    "sha256:fd7256b13c90935782aedcebd23dcbd8dbe1e16853974ffb6722a116e32a13f9",
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

export function getTesterRelease(): TesterRelease {
  if (
    !/^[a-f0-9]{40}$/.test(testerRelease.sourceCommit) ||
    !/^sha256:[a-f0-9]{64}$/.test(testerRelease.imageId)
  ) {
    throw new Error("Invalid tester release identity");
  }
  if (testerRelease.status === "published") {
    validateArtifact(testerRelease.imageArchive);
    validateArtifact(testerRelease.sourceKit);
    if (testerRelease.imageArchive.filename === testerRelease.sourceKit.filename) {
      throw new Error("Tester artifact filenames must be distinct");
    }
  }
  return testerRelease;
}

export function getTesterCommands(
  release: Extract<TesterRelease, { status: "published" }>,
) {
  // Only validated local basenames and fixed release identifiers enter shell
  // examples. First-party download paths are links, never shell commands.
  validateArtifact(release.imageArchive);
  validateArtifact(release.sourceKit);
  if (!/^sha256:[a-f0-9]{64}$/.test(release.imageId)) {
    throw new Error("Invalid tester image ID");
  }
  return {
    checksum: `printf '%s  %s\\n' '${release.imageArchive.sha256}' '${release.imageArchive.filename}' '${release.sourceKit.sha256}' '${release.sourceKit.filename}' | sha256sum --check`,
    load: `docker load --input '${release.imageArchive.filename}'\ndocker image inspect --format '{{.Id}}' '${release.imageId}'`,
    run: `python3 vanguard/docker/run.py --image '${release.imageId}' --out "$PWD/journey-1"`,
  };
}
