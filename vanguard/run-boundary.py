#!/usr/bin/env python3
"""Build and reproduce VG-F1/VG-F2 plus the local boundary, offline and bounded."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
PIN = json.loads((ROOT / "vanguard/source-lock.json").read_text())


def command(args, **kw):
    return subprocess.check_output(args, text=True, **kw).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=ROOT / "build/vanguard-src")
    parser.add_argument("--out", type=Path, required=True, help="new evidence directory")
    args = parser.parse_args()
    src = args.src.resolve()
    up = src / "monero-fcmp"
    out = args.out.resolve()
    if out.exists():
        raise SystemExit("refusing existing output directory")
    # Use the established project-wide lock. Never steal a held lock.
    with open("/tmp/meownero-swarm-20260912-heavy.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        if int(mem["MemAvailable"].split()[0]) * 1024 < 5 * 1024**3 or shutil.disk_usage(ROOT).free < 5 * 1024**3:
            raise SystemExit("requires 5 GiB available memory and disk")
        if command(["git", "-C", str(up), "rev-parse", "HEAD"]) != PIN["upstream"]["commit"]:
            raise SystemExit("upstream pin mismatch; prepare with vanguard/build.sh prepare")
        base_cmake = command(["git", "-C", str(up), "show", "HEAD:tests/CMakeLists.txt"]) + "\n"
        cmake = up / "tests/CMakeLists.txt"
        allowed = [base_cmake + "add_subdirectory(vanguard)\n",
                   base_cmake + "add_subdirectory(vanguard)\nadd_subdirectory(vanguard_boundary)\n"]
        if cmake.read_text() not in allowed:
            raise SystemExit("unexpected upstream CMake injection")
        changed = command(["git", "-C", str(up), "diff", "HEAD", "--name-only"]).splitlines()
        if changed != ["tests/CMakeLists.txt"]:
            raise SystemExit("unexpected upstream tracked changes")
        for path, sha in PIN["upstream"]["submodules"].items():
            sub = up / path
            if command(["git", "-C", str(sub), "rev-parse", "HEAD"]) != sha or command(["git", "-C", str(sub), "status", "--porcelain"]):
                raise SystemExit("submodule mismatch: " + path)
        if digest(up / "src/fcmp_pp/fcmp_pp_rust/Cargo.lock") != PIN["rust"]["cargo_lock_sha256"]:
            raise SystemExit("Cargo.lock mismatch")
        oxide = list((src / "cargo-home/git/checkouts").glob("monero-oxide-*/31c26d9"))
        if len(oxide) != 1 or command(["git", "-C", str(oxide[0]), "rev-parse", "HEAD"]) != PIN["rust"]["monero_oxide_rev"] or command(["git", "-C", str(oxide[0]), "diff", "HEAD"]):
            raise SystemExit("monero-oxide source mismatch")
        rust = Path(os.environ.get("RUST_TOOLCHAIN_DIR", str(Path.home() / ".rustup/toolchains/stable-x86_64-unknown-linux-gnu")))
        if command([str(rust / "bin/rustc"), "-V"]) != PIN["builder"]["rustc"]:
            raise SystemExit("Rust toolchain mismatch")
        out.mkdir(parents=True)
        target = up / "tests/vanguard_boundary"
        target.mkdir(exist_ok=True)
        owned = sorted((ROOT / "vanguard/boundary").iterdir())
        if any(p.name not in {f.name for f in owned} for p in target.iterdir()):
            raise SystemExit("unexpected file in owned boundary injection")
        for path in owned:
            shutil.copy2(path, target / path.name)
        cmake.write_text(allowed[-1])
        shutil.copy2(ROOT / "vanguard/source-lock.json", out / "source-lock.json")
        source_hashes = {str(p.relative_to(ROOT)): digest(p) for p in owned + [ROOT / "vanguard/run-boundary.py", ROOT / "vanguard/verify-boundary.py"]}
        fixtures = {p.name: digest(p) for p in sorted((up / "tests/data").glob("fcmp_pp_verify_inputs_*in.bin"))}
        receipt = {"base_commit": command(["git", "rev-parse", "HEAD"], cwd=ROOT), "source_sha256": source_hashes,
                   "fixture_sha256": fixtures, "upstream": PIN["upstream"]["commit"], "monero_oxide": PIN["rust"]["monero_oxide_rev"],
                   "image": PIN["builder"]["image_id"], "rustc": PIN["builder"]["rustc"], "commands": [], "metrics": {}}
        (out / "upstream-injection.diff").write_text(command(["git", "-C", str(up), "diff", "HEAD"]) + "\n")

        def container(stage, script, memory, readonly=False):
            argv = ["docker", "run", "--rm", "--pull=never", "--network=none", "--cpus=2", "--memory=" + memory,
                    "--memory-swap=" + memory, "--pids-limit=256", "--ulimit", "core=0", "-u", f"{os.getuid()}:{os.getgid()}",
                    "-v", f"{up}:/src" + (":ro" if readonly else ""), "-v", f"{src / 'cargo-home'}:/cargo-home" + (":ro" if readonly else ""),
                    "-v", f"{rust}:/opt/rust:ro", "-v", f"{out}:/out", "-e", "CARGO_HOME=/cargo-home", "-e", "CARGO_NET_OFFLINE=true",
                    "-e", "HOME=/tmp", "-e", "PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "-w", "/src", receipt["image"], "bash", "-euc", script]
            receipt["commands"].append(argv)
            start = time.monotonic()
            with (out / (stage + ".docker.log")).open("w") as log:
                result = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
            receipt["metrics"][stage] = {"wall_seconds": time.monotonic() - start, "exit": result.returncode}
            (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            if result.returncode:
                raise SystemExit(f"{stage} failed; see {out}")

        container("build", """
mkdir -p build/vanguard
cd build/vanguard
cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON ../.. > /out/cmake.log 2>&1
make -j1 vanguard_boundary_tests > /out/make.log 2>&1
cat /sys/fs/cgroup/memory.peak > /out/build.memory
cat /sys/fs/cgroup/memory.events > /out/build.memory-events
g++ --version > /out/gxx.txt
cmake --version > /out/cmake.txt
rustc -vV > /out/rustc.txt
cargo -V > /out/cargo.txt
""", "4g")
        binary = up / "build/vanguard/tests/vanguard_boundary/vanguard_boundary_tests"
        receipt["binary"] = {"sha256": digest(binary), "bytes": binary.stat().st_size}
        for name in ("run1", "run2"):
            container(name, f"""
/src/build/vanguard/tests/vanguard_boundary/vanguard_boundary_tests /src/tests/data > /out/{name}.tsv 2> /out/{name}.stderr
cat /sys/fs/cgroup/memory.peak > /out/{name}.memory
cat /sys/fs/cgroup/memory.events > /out/{name}.memory-events
""", "512m", readonly=True)
        if (out / "run1.tsv").read_bytes() != (out / "run2.tsv").read_bytes():
            raise SystemExit("deterministic results differ")
        (out / "MANIFEST.sha256").write_text("".join(f"{digest(p)}  {p.name}\n" for p in sorted(out.iterdir()) if p.is_file()))
        subprocess.run(["python3", str(ROOT / "vanguard/verify-boundary.py"), str(out)], check=True)


if __name__ == "__main__":
    main()
