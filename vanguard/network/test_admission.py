#!/usr/bin/env python3
"""Adverse provenance checks for the reuse boundary; no Docker/native process."""
import argparse
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('admission_driver', Path(__file__).with_name('run-admission.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class ReuseBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH, prefix='admission-refusal-')
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.here, self.reuse = root / 'vanguard/network', root / 'reuse'
        self.source = self.reuse / 'source'
        self.here.mkdir(parents=True)
        self.source.mkdir(parents=True)
        self.pin = {'upstream': {'commit': 'fixture-commit'}, 'builder': {'image_id': 'fixture-image'},
                    'rust': {'cargo_lock_path': 'Cargo.lock', 'cargo_lock_sha256': a.network.sha(b'locked')}}
        (self.here.parent / 'source-lock.json').write_text(json.dumps(self.pin))
        members = {'Cargo.lock': b'locked', 'tests/CMakeLists.txt': b'# original\n', 'src/unit.cpp': b'original'}
        archive = self.reuse / 'source-root.tar'
        with tarfile.open(archive, 'w') as stream:
            for name, raw in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                stream.addfile(info, io.BytesIO(raw))
                dest = self.source / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw + (b'\nadd_subdirectory(vanguard-network)\n' if name == 'tests/CMakeLists.txt' else b''))
        target = self.source / 'tests/vanguard-network'
        target.mkdir()
        for name in ('CMakeLists.txt', 'README.md', 'genesis.cpp'):
            (target / name).write_text('helper fixture ' + name)
        binary = self.source / 'build/network/tests/vanguard-network/vanguard_network_genesis'
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b'fixture binary, never executed')
        (self.reuse / 'binary.sha256').write_text(a.g.digest(binary) + ' fixture\n')
        cache = self.reuse / 'cargo-home/registry/input'
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b'cached fixture')
        self.old = {'result': 'PASS_NATIVE_RECIPE_HELPERS_ONLY',
            'source_lock_sha256': a.g.digest(self.here.parent / 'source-lock.json'),
            'upstream_commit': 'fixture-commit', 'builder_image': 'fixture-image',
            'archives': {'.': {'revision': 'fixture-commit', 'sha256': a.g.digest(archive)}},
            'helper_sources': {n: a.g.digest(target / n) for n in ('CMakeLists.txt', 'genesis.cpp')},
            'tests_cmake_changed_sha256': a.g.digest(self.source / 'tests/CMakeLists.txt'),
            'cargo_cache_files': {'registry/input': a.g.digest(cache)}, 'cargo_checkout_heads': {},
            'telemetry_padding': 'x' * 70000}
        self.save_receipt()
        for obj, name, value in ((a, 'REUSE', self.reuse), (a.network, 'HERE', self.here)):
            mocked = patch.object(obj, name, value)
            mocked.start()
            self.addCleanup(mocked.stop)

    def save_receipt(self):
        raw = json.dumps(self.old)
        (self.reuse / 'receipt.json').write_text(raw)
        bound = self.here / 'evidence/native-genesis-attempt01/receipt.json'
        bound.parent.mkdir(parents=True, exist_ok=True)
        bound.write_text(raw)

    def validate(self):
        receipt = {}
        a.validate_reuse(self.pin, receipt)
        return receipt

    def test_hash_bound_large_receipt_and_valid_export(self):
        self.assertGreater((self.reuse / 'receipt.json').stat().st_size, 65536)
        self.assertEqual(self.validate()['reuse']['cargo_files_verified'], 1)

    def test_changed_receipt_refused(self):
        with (self.reuse / 'receipt.json').open('a') as stream:
            stream.write(' ')
        with self.assertRaisesRegex(ValueError, 'prior receipt changed'):
            self.validate()

    def test_changed_original_source_refused(self):
        (self.source / 'src/unit.cpp').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'export differs'):
            self.validate()

    def test_extra_header_refused(self):
        (self.source / 'src/shadow.h').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'unexpected or missing'):
            self.validate()

    def test_changed_cargo_input_refused(self):
        (self.reuse / 'cargo-home/registry/input').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'copied Cargo input changed'):
            self.validate()

    def test_changed_prior_binary_refused(self):
        (self.source / 'build/network/tests/vanguard-network/vanguard_network_genesis').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'prior helper binary changed'):
            self.validate()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    SCRATCH = args.scratch
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReuseBoundary))
    raise SystemExit(0 if result.wasSuccessful() else 1)
