#!/usr/bin/env python3
"""Portable checks of selection, export containment and collision preservation.

These do not execute Windows programs or qualify the Win32 architecture query.
"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('bundle', Path(__file__).with_name('windows-test-bundle.py'))
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class BundleTests(unittest.TestCase):
    def test_native_lane_selection_and_emulation_refusal(self):
        self.assertEqual(bundle.choose_target(0, 0x8664), 'windows-i686')
        self.assertEqual(bundle.choose_target(0, 0xaa64), 'windows-aarch64')
        for process, native in ((0x8664, 0xaa64), (0x14c, 0x8664), (0, 0x14c)):
            with self.assertRaises(bundle.Refused):
                bundle.choose_target(process, native)

    def test_report_does_not_export_wallets_logs_or_unlisted_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            public = root / 'public'
            public.mkdir()
            (public / 'ci-receipt.json').write_text(json.dumps({'result': 'FAIL'}))
            for path in (public / 'wallet.keys', public / 'seed.txt', public / 'private.log', root / 'private.log'):
                path.write_text('PRIVATE_SENTINEL_DO_NOT_EXPORT')
            bundle.export_report(root / 'report.zip', {'result': 'FAIL'}, public)
            with zipfile.ZipFile(root / 'report.zip') as report:
                self.assertEqual(set(report.namelist()), {'bundle-receipt.json', 'public/ci-receipt.json'})
                self.assertNotIn(b'PRIVATE_SENTINEL', b''.join(report.read(n) for n in report.namelist()))

    def test_report_collision_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.zip'
            path.write_bytes(b'KEEP_EXISTING_REPORT')
            with self.assertRaises(FileExistsError):
                bundle.export_report(path, {}, Path(folder))
            self.assertEqual(path.read_bytes(), b'KEEP_EXISTING_REPORT')

    def test_public_receipt_symlink_and_hardlink_refused(self):
        for link_type in ('symlink', 'hardlink'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root / 'private.json').write_text('{"seed": "PRIVATE"}')
                public = root / 'public'
                public.mkdir()
                path = public / 'ci-receipt.json'
                if link_type == 'symlink':
                    path.symlink_to(root / 'private.json')
                else:
                    os.link(root / 'private.json', path)
                with self.assertRaises(bundle.Refused):
                    bundle.export_report(root / 'report.zip', {}, public)

    def test_manifest_path_cannot_escape_bundle(self):
        for name in ('../wallet', '/wallet', 'C:/wallet', 'a\\wallet'):
            with self.assertRaises(bundle.Refused):
                bundle.relative(Path('/bundle'), name)


if __name__ == '__main__':
    unittest.main()
