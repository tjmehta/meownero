# ARM39 acceptance and ARM13 source review

Changed: Bound the original reviewer's `ACCEPT_SCOPED_EXACT_ARM39_ARTIFACT`
verdict into new delivery and seven-target manifests. The frozen ARM39 manifests,
archive and guide remain byte-preserved. The current count is four scoped native
target acceptances out of seven; the whole release remains OPEN.

The authoritative [independent verdict](/TJS/issues/TJS-1882#document-arm39-independent-review)
is revision `79710ac3-4e44-4175-9af8-70236f654ed6`. Its 26,937-byte attachment was
freshly downloaded and verified against SHA256
`cd660b889b4d1e55466f3d3c616b4a08ae43aed4bf76f8b8117fe65a4a709fd1`.
It accepts archive `b9f06ea78cf7da5c2272b998b48eed5a46dc404b721f32db7f09dc39407de1dc`,
72,731,614 bytes, with immutable release manifest
`d0b3c2d7a405d2ede1d07227ab90feb6d142afd6b3b15468af353d8800449d58`.
Fresh local hashing of the archive, all nine original parts and release manifest
also passed. No Meownero native journey was rerun by this writer.

The reviewer's independent witness is the exact archive's full 5/2
FCMP++ type7/CARROT receive, restore, later-spend and CLI journey plus all ten
controls in native ARM64 Ubuntu24.04.4 container userland on Colima. The writer's
Ubuntu22 HWE and Debian12 userland witnesses were reviewed, not independently
rerun. Debian12 is userland on an Ubuntu kernel. Other distributions remain
UNTESTED. This supplies no macOS, x64 or whole-release acceptance. Parent owns
actual group delivery after its checks using the unchanged nine documents.

Changed: Added a pinned compatibility patch to the existing Windows ARM64
cross-build branch. The ARM64 slow-hash branch unconditionally used POSIX mmap
and Linux getauxval on Windows. It now uses Windows VirtualAlloc/VirtualFree
and IsProcessorFeaturePresent for the Windows branch. Existing malloc fallback,
TLS state, hash arithmetic, AES rounds and non-Windows code remain unchanged.
The builder checks the source, patch and output hashes before proceeding and
records the patch and primary API references in provenance.

Affected callers: `portable-cross-build.py` applies this only to
`windows-aarch64` in the existing LLVM route. Windows x64/i686 use the unchanged
apt route. Linux38/ARM39 do not include this helper; all36 frozen Git bindings
and current frozen carriers passed, and both reviewed local Linux helpers remain
byte-identical to `b1af96d`. Existing accepted archives are untouched.

Verified: A fresh exact Git-object export of pinned crypto sources/headers
matches slow-hash SHA256
`886ae10164b0593e35df7419cd5834ce66a6db5a5f54a623a5364804f868fd83`.
Patch `38a310034b4ed0ee490aa2430d53f80866af83a8a769516b87720d8faa06cf80`
applies with zero fuzz and yields
`dae4f22d4034adc4d926f02f11b3cc6ab66b191384e31fd8b8e15656147221de`.
The retained LLVM distribution was checksum-verified and freshly extracted in
owned staging. Clang23.1.3 used exact ARM12 C flags/defines and pinned cached
Boost headers, with a separately checked `armv8-a` variant.

- Original source fails at slow-hash.c:1021, missing sys/mman.h.
- Corrected source compiles with `armv8-a+crypto` and without crypto to actual
  ARM64 COFF objects, machine0xaa64. See diagnostic02/result.json and logs.
- Native Darwin Clang preprocessing for ARM64 and x64 preserves every nonblank
  line. The initial byte comparison found one additional empty line after
  sys/mman.h; the exact difference is retained. This is a source regression check,
  not a Mac app build or journey.
- Python compilation, CLI help and diff whitespace checks pass. All six original
  dirty/untracked regular files remain byte-identical.

The local heavy-lock attempt refused before starting a workload. The fallback
used idle existing Colima and its pre-existing x64 compiler translation, with an
exclusively owned standard shared-lock inode. Both exact diagnostic containers
were offline/read-only, 1CPU/768MiB memory-and-swap/64PIDs, with child command
limits30s and a150s outer wait. Diagnostic02 peaked at362,844,160 bytes and had
zero OOM. Both exact containers and owned lock inodes were removed. Diagnostic01
stopped at an omitted Boost include path before observing the bug; its logs are
retained. Original included headers and ARM12 flags corrected that diagnostic.
The cleanup helper refused cached shared Virtualization handles. After captures,
a separate ownership check found only the existing filesystem holder and zero
diagnostic containers or compiler processes. The exact634,688,299-byte owned
staging tree was removed; shared Colima was preserved. See cleanup.json.
This is cross-compilation evidence only. No native Windows execution is claimed.

Primary contracts checked on October19:
[VirtualAlloc](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc),
[VirtualFree](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualfree),
and [IsProcessorFeaturePresent](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-isprocessorfeaturepresent).
VirtualAlloc reserves/commits writable pages; release uses the original base,
size0 and MEM_RELEASE. The OS feature query uses
PF_ARM_V8_CRYPTO_INSTRUCTIONS_AVAILABLE rather than assuming AES support.
Pinned source is [slow-hash.c at e151643c](https://github.com/seraphis-migration/monero/blob/e151643c5269c83bf24a83b2548e2493876026b2/src/crypto/slow-hash.c).

Unconfirmed/next: Original reviewer ec85048c should inspect this coherent ARM13
source delta by comment and return the same issue to writer92a7b4f2. No release
stage decision is requested. After source clearance, the writer owns a distinct
bounded ARM13 build and eventual exact-archive native Windows ARM qualification,
journey, controls and cleanup. ARM12 remains a failed attempt with no archive;
ARM13 has no full build or native journey yet. Runtime allocation/capacity still
needs qualification. Historical native acceptances and owner approval remain.

Linux38 is still blocked by the observed Ubuntu24 x64 host's lack of /dev/kvm,
vmx/svm flags and VM launchers. Studio lead38e398e0 and its existing parent route
own a qualified isolated Ubuntu22 x64 environment or fresh confirmation of
included Actions capacity/storage. The fresh billing API returns404/missing user
scope; there are zero active/queued runs and zero self-hosted runners. No quota
reset or spend authority is inferred. I68635 retains packet03d24579 and its
existing parent-owned capacity route; standalone32bit Windows remains UNTESTED.
The absent `/storage/data` staging is not a new payload-loss claim: committed
carriers and attached packets remain authoritative. No paid dispatch was made.

Needs TJ: None new.
