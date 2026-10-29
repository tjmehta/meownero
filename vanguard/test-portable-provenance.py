#!/usr/bin/env python3
"""Regression checks for provenance-only successors and private-path refusal."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from portable_provenance import (PLACEHOLDER, digest, home_prefixes, recorded_receipt,
                                 refuse_private_paths, successor_archive)


def encoded(value):
    return (json.dumps(value, indent=2) + '\n').encode()


class ProvenanceTests(unittest.TestCase):
    def test_recording_removes_both_home_forms_without_changing_execution_arguments(self):
        argv = ['compiler', home_prefixes()[0] + 'source', home_prefixes()[-1] + 'output']
        receipt = {'commands': [{'argv': list(argv)}]}
        saved = recorded_receipt(receipt)
        self.assertEqual(receipt['commands'][0]['argv'], argv)
        self.assertEqual(saved['commands'][0]['argv'][1:], [PLACEHOLDER + 'source', PLACEHOLDER + 'output'])
        refuse_private_paths(encoded(saved))

    def test_recursive_scan_refuses_compressed_and_utf16_paths_but_allows_public_paths(self):
        for prefix in home_prefixes():
            for encoding in ('utf-8', 'utf-16-le', 'utf-16-be'):
                inner = io.BytesIO()
                with zipfile.ZipFile(inner, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('BUILD.json', (prefix + 'source').encode(encoding))
                outer = io.BytesIO()
                with zipfile.ZipFile(outer, 'w', zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('candidate.zip', inner.getvalue())
                with self.assertRaisesRegex(ValueError, 'PRIVATE_HOME_PREFIX'):
                    refuse_private_paths(outer.getvalue())
        refuse_private_paths(b'https://crates.io/crates/home/0.5.11 /home/runner/work/project /BUILD_HOME/source')

    def fixture(self, folder, extra_leak=False):
        prefix = 'package/'
        cached = encoded({'argv': [home_prefixes()[0] + 'build']})
        before = encoded({'cached_build': {'receipt_sha256': digest(cached)}})
        inputs = encoded({'source_build_receipt_sha256': digest(before), 'tar_sha256': 'historical-input-tar'})
        script = ('#!/usr/bin/env python3\npath = ' + repr(home_prefixes()[-1] + 'build') + '\n').encode()
        cross = encoded({'input_manifest_sha256': digest(inputs), 'script_sha256': digest(script),
                         'inputs_archive_sha256': 'historical-executed-tar'})
        build = encoded({'argv': [home_prefixes()[0] + 'compiler'],
                         'cached_build': {'receipt_sha256': digest(cached)},
                         'exception_probe': {'cross_receipt_sha256': digest(cross)}})
        files = {'bin/program.exe': b'IMMUTABLE_PROGRAM', 'tester.py': b'IMMUTABLE_CONTROLLER',
                 'licenses/COPYRIGHT': b'https://crates.io/crates/home/0.5.11',
                 'BUILD.json': build, 'build-evidence/cached-build-receipt.json': cached,
                 'build-evidence/pre-exception-probe-build-receipt.json': before,
                 'build-evidence/i686-exception-probe-input.json': inputs,
                 'build-evidence/i686-exception-probe-cross.py': script,
                 'build-evidence/i686-exception-probe-cross-receipt.json': cross}
        if extra_leak:
            files['bin/program.exe'] += home_prefixes()[0].encode()
        files['release.json'] = encoded({'files': {k: digest(v) for k, v in files.items()},
                                        'build_receipt': {'file': 'BUILD.json', 'sha256': digest(build)}})
        source = folder / 'original.zip'
        with zipfile.ZipFile(source, 'x', zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(prefix + name, data)
        return source, files

    def test_successor_preserves_program_controller_license_and_truthful_hash_chain(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, original = self.fixture(root)
            old_hash = digest(source.read_bytes())
            destination = root / 'successor.zip'
            report = successor_archive(source, destination)
            self.assertEqual(digest(source.read_bytes()), old_hash)
            with zipfile.ZipFile(destination) as archive:
                files = {name: archive.read('package/' + name) for name in original}
            for name in ['bin/program.exe', 'tester.py', 'licenses/COPYRIGHT']:
                self.assertEqual(files[name], original[name])
            values = {name: json.loads(data) for name, data in files.items() if name.endswith('.json')}
            self.assertEqual(values['BUILD.json']['cached_build']['receipt_sha256'], digest(files['build-evidence/cached-build-receipt.json']))
            self.assertEqual(values['build-evidence/i686-exception-probe-input.json']['source_build_receipt_sha256'], digest(files['build-evidence/pre-exception-probe-build-receipt.json']))
            self.assertEqual(values['build-evidence/i686-exception-probe-cross-receipt.json']['script_sha256'], digest(files['build-evidence/i686-exception-probe-cross.py']))
            self.assertEqual(values['build-evidence/i686-exception-probe-cross-receipt.json']['input_manifest_sha256'], digest(files['build-evidence/i686-exception-probe-input.json']))
            self.assertEqual(values['BUILD.json']['exception_probe']['cross_receipt_sha256'], digest(files['build-evidence/i686-exception-probe-cross-receipt.json']))
            for name, expected in values['release.json']['files'].items():
                self.assertEqual(digest(files[name]), expected)
            for name in report['rewritten_members']:
                self.assertIn(digest(original[name]).encode(), files[name])
                self.assertIn(old_hash.encode(), files[name])
                self.assertIn(b'DISTRIBUTION_COPY_NOT_ORIGINAL_EXECUTION_BYTES', files[name])
            self.assertEqual(values['build-evidence/i686-exception-probe-cross-receipt.json']['inputs_archive_sha256'], 'historical-executed-tar')
            self.assertEqual(values['build-evidence/i686-exception-probe-input.json']['tar_sha256'], 'historical-input-tar')
            refuse_private_paths(destination.read_bytes())
            saved = destination.read_bytes()
            with self.assertRaises(FileExistsError):
                successor_archive(source, destination)
            self.assertEqual(destination.read_bytes(), saved)

    def test_unrecognized_program_leak_refuses_output_instead_of_rewriting_program(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, _ = self.fixture(root, extra_leak=True)
            with self.assertRaisesRegex(ValueError, 'PRIVATE_HOME_PREFIX'):
                successor_archive(source, root / 'successor.zip')
            self.assertFalse((root / 'successor.zip').exists())


if __name__ == '__main__':
    unittest.main()
