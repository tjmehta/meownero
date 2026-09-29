#!/usr/bin/env python3
"""Build and run the bounded two-core Vanguard witness in isolated containers."""
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
SOURCE_FILES = [ROOT / p for p in ("vanguard/sync/CMakeLists.txt", "vanguard/sync/sync_tests.cpp", "vanguard/sync/fixture.cpp",
                                     "vanguard/run-sync.py", "vanguard/verify-sync.py")]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args):
    return subprocess.check_output(args, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=ROOT / "build/vanguard-src")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    src, out = args.src.resolve(), args.out.resolve()
    up = src / "monero-fcmp"
    if out.exists():
        raise SystemExit("refusing existing evidence directory")
    with open("/tmp/meownero-swarm-20260912-heavy.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
        if int(memory["MemAvailable"].split()[0]) * 1024 < 5 * 1024**3 or shutil.disk_usage(ROOT).free < 5 * 1024**3:
            raise SystemExit("requires 5 GiB available memory and disk")
        if command(["git", "-C", str(up), "rev-parse", "HEAD"]) != PIN["upstream"]["commit"]:
            raise SystemExit("upstream revision mismatch")
        if sha(up / "src/fcmp_pp/fcmp_pp_rust/Cargo.lock") != PIN["rust"]["cargo_lock_sha256"]:
            raise SystemExit("Cargo.lock mismatch")
        base = command(["git", "-C", str(up), "show", "HEAD:tests/CMakeLists.txt"]) + "\n"
        cmake = up / "tests/CMakeLists.txt"
        prior = cmake.read_text()
        accepted = base + "add_subdirectory(vanguard)\nadd_subdirectory(vanguard_boundary)\n"
        if prior != accepted:
            raise SystemExit("unexpected upstream test registration")
        target = up / "tests/vanguard_sync"
        if target.exists() and any(p.name not in {f.name for f in SOURCE_FILES[:3]} for p in target.iterdir()):
            raise SystemExit("unexpected injected source")
        target.mkdir(exist_ok=True)
        for path in SOURCE_FILES[:3]:
            shutil.copy2(path, target / path.name)
        rust = Path(os.environ.get("RUST_TOOLCHAIN_DIR", str(Path.home() / ".rustup/toolchains/stable-x86_64-unknown-linux-gnu")))
        if command([str(rust / "bin/rustc"), "-V"]) != PIN["builder"]["rustc"]:
            raise SystemExit("Rust toolchain mismatch")
        out.mkdir(parents=True)
        shutil.copy2(ROOT / "vanguard/source-lock.json", out / "source-lock.json")
        receipt = {"commit": command(["git", "rev-parse", "HEAD"]),
                   "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in SOURCE_FILES},
                   "upstream": PIN["upstream"]["commit"], "image": PIN["builder"]["image_id"],
                   "rustc": PIN["builder"]["rustc"], "binary": {}, "commands": [], "metrics": {}}

        def container(stage, script, readonly=False):
            name = f"vanguard-sync-{os.getpid()}-{stage}"
            argv = ["docker", "run", "--name", name, "--rm", "--pull=never", "--network=none", "--cpus=2",
                    "--memory=4g", "--memory-swap=4g", "--pids-limit=256", "--ulimit", "core=0",
                    "-u", f"{os.getuid()}:{os.getgid()}", "-v", f"{up}:/src" + (":ro" if readonly else ""),
                    "-v", f"{src / 'cargo-home'}:/cargo-home" + (":ro" if readonly else ""),
                    "-v", f"{rust}:/opt/rust:ro", "-v", f"{out}:/out", "-e", "CARGO_HOME=/cargo-home",
                    "-e", "CARGO_NET_OFFLINE=true", "-e", "PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    "-w", "/out", receipt["image"], "bash", "-euc",
                    f"trap 'cat /sys/fs/cgroup/memory.peak > /out/{stage}.memory; cat /sys/fs/cgroup/memory.events > /out/{stage}.memory-events; cat /sys/fs/cgroup/cpu.stat > /out/{stage}.cpu' EXIT\n" + script]
            receipt["commands"].append(argv)
            started = time.monotonic()
            try:
                with (out / (stage + ".docker.log")).open("w") as log:
                    code = subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=900).returncode
            except subprocess.TimeoutExpired:
                code = 124
                subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            receipt["metrics"][stage] = {"wall_seconds": time.monotonic() - started, "exit": code}
            (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            if code:
                raise SystemExit(f"{stage} failed: {out}")

        try:
            cmake.write_text(prior + "add_subdirectory(vanguard_sync)\n")
            (out / "upstream-injection.diff").write_text(command(["git", "-C", str(up), "diff", "HEAD", "--", "tests/CMakeLists.txt"]) + "\n")
            container("build", """
cd /src/build/vanguard
cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON ../.. > /out/cmake.log 2>&1
make -j1 vanguard_sync_tests > /out/make.log 2>&1
""")
            binary = up / "build/vanguard/tests/vanguard_sync/vanguard_sync_tests"
            receipt["binary"] = {"sha256": sha(binary), "bytes": binary.stat().st_size}
            for run in ("run1", "run2"):
                container(run, f"""
mkdir /out/{run}
cd /out/{run}
/src/build/vanguard/tests/vanguard_sync/vanguard_sync_tests /out/{run}/nodes > stdout.log 2> stderr.log
""", readonly=True)
        finally:
            cmake.write_text(prior)
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        (out / "MANIFEST.sha256").write_text("".join(f"{sha(p)}  {p.relative_to(out)}\n"
          for p in sorted(out.rglob("*")) if p.is_file()))
        subprocess.run(["python3", "-B", str(ROOT / "vanguard/verify-sync.py"), str(out)], check=True)


if __name__ == "__main__":
    main()
