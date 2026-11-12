"""Fail closed on private identifiers in gzip evidence, including nested tar files.

Run before recording or reviewing a milestone's evidence:
    python3 -B vanguard/network/integration/evidence/check_compressed_privacy.py
For the existing private tree, supply its explicit publication drop list with
--exclude-from. Every skipped gzip file is reported; nothing is skipped by default.
Run focused regression tests with --self-test. Diagnostics omit matched content.
"""

import argparse
import gzip
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zlib


EVIDENCE_PREFIX = Path('vanguard/network/integration/evidence')


def check_gzip(name, data, usernames):
    findings = []
    try:
        raw = gzip.decompress(data)
        if (b'/home/' in raw or b'/Users/' in raw
                or any(user.lower() in raw.lower() for user in usernames)):
            findings.append({'member': name, 'reason': 'private_identifier'})
        if name.endswith('.tar.gz'):
            with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
                for member in archive:
                    if member.isfile() and member.name.endswith('.gz'):
                        findings.extend(check_gzip(name + '!' + member.name,
                                                   archive.extractfile(member).read(), usernames))
    except (OSError, EOFError, tarfile.TarError, zlib.error) as error:
        findings.append({'member': name, 'reason': 'unreadable_' + type(error).__name__})
    return findings


def check_tree(root, usernames, excluded_paths=()):
    paths = sorted(root.rglob('*.gz'))
    findings = []
    skipped = []
    for path in paths:
        relative = str(path.relative_to(root))
        repository_path = str(EVIDENCE_PREFIX / relative)
        if repository_path in excluded_paths:
            skipped.append(repository_path)
            continue
        try:
            findings.extend(check_gzip(relative, path.read_bytes(), usernames))
        except OSError as error:
            findings.append({'member': relative,
                             'reason': 'unreadable_' + type(error).__name__})
    return {'gzip_files': len(paths), 'scanned_gzip_files': len(paths) - len(skipped),
            'skipped': skipped, 'findings': findings}


class PrivacyChecks(unittest.TestCase):
    def test_redacted_paths_pass(self):
        self.assertEqual(check_gzip('clean.log.gz', gzip.compress(b'<repo>/test.py ~/test.py'),
                                    [b'private-user']), [])

    def test_home_path_with_unknown_username_fails(self):
        self.assertTrue(check_gzip('new.log.gz', gzip.compress(b'/home/new-user/test.py'), []))

    def test_macos_home_path_fails(self):
        self.assertTrue(check_gzip('mac.log.gz', gzip.compress(b'/Users/x/test.py'), []))

    def test_excluded_path_is_skipped_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'private.gz').write_bytes(gzip.compress(b'/home/x/private'))
            excluded = str(EVIDENCE_PREFIX / 'private.gz')
            exclusions = root / 'drops.txt'
            exclusions.write_text('# Exact publication drop list\n\n' + excluded + '\n')
            process = subprocess.run([sys.executable, '-B', __file__, '--root', str(root),
                                      '--exclude-from', str(exclusions)],
                                     capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result['findings'], [])
            self.assertEqual(result['skipped'], [excluded])
            self.assertEqual(result['scanned_gzip_files'], 0)

    def test_leaky_sibling_of_excluded_path_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('private.gz', 'sibling.gz'):
                (root / name).write_bytes(gzip.compress(b'/home/x/private'))
            excluded = str(EVIDENCE_PREFIX / 'private.gz')
            result = check_tree(root, [], {excluded})
            self.assertEqual(result['skipped'], [excluded])
            self.assertEqual([x['member'] for x in result['findings']], ['sibling.gz'])

    def test_handle_passes_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'handle.gz').write_bytes(gzip.compress(b'tjmehta'))
            result = subprocess.run([sys.executable, '-B', __file__, '--root', str(root)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['findings'], [])

    def test_bare_username_fails(self):
        self.assertTrue(check_gzip('user.log.gz', gzip.compress(b'PRIVATE-USER ALL=(root)'),
                                   [b'private-user']))

    def test_public_reference_has_no_implicit_exception(self):
        self.assertTrue(check_gzip('reference.log.gz', gzip.compress(b'https://private-user.example'),
                                   [b'private-user']))

    def test_all_concatenated_gzip_members_are_checked(self):
        data = gzip.compress(b'clean') + gzip.compress(b'/home/another-user/secret')
        self.assertTrue(check_gzip('joined.log.gz', data, []))

    def test_invalid_gzip_fails(self):
        self.assertTrue(check_gzip('broken.log.gz', b'not gzip', []))

    def test_corrupt_gzip_trailer_fails(self):
        data = bytearray(gzip.compress(b'clean'))
        data[-8] ^= 1
        self.assertTrue(check_gzip('broken.log.gz', data, []))

    def test_corrupt_deflate_stream_fails(self):
        data = bytearray(gzip.compress(b'clean'))
        data[10] = 0x07  # Reserved DEFLATE block type.
        self.assertTrue(check_gzip('broken.log.gz', data, []))

    @staticmethod
    def archive(name, data, owner=''):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.uname = owner
            archive.addfile(member, io.BytesIO(data))
        return stream.getvalue()

    def test_nested_compressed_member_fails(self):
        data = self.archive('nested.log.gz', gzip.compress(b'/home/nested-user/secret'))
        self.assertTrue(check_gzip('packet.tar.gz', data, []))

    def test_tar_ownership_is_checked(self):
        data = self.archive('clean.log', b'clean', owner='private-user')
        self.assertTrue(check_gzip('packet.tar.gz', data, [b'private-user']))

    def test_nested_tree_is_scanned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'later').mkdir()
            (root / 'clean.gz').write_bytes(gzip.compress(b'clean'))
            (root / 'later' / 'bad.gz').write_bytes(gzip.compress(b'/home/unknown/secret'))
            result = check_tree(root, [])
            self.assertEqual(result['gzip_files'], 2)
            self.assertEqual([x['member'] for x in result['findings']], ['later/bad.gz'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--deny-user', action='append', default=[])
    parser.add_argument('--exclude-from', type=Path,
                        help='Exact repo-relative drop-listed paths, one per line; # comments allowed')
    parser.add_argument('--self-test', action='store_true')
    options = parser.parse_args()
    if options.self_test:
        unittest.main(argv=['check_compressed_privacy'], verbosity=2)
    else:
        if not options.root.is_dir():
            parser.error('--root must be an existing evidence directory')
        excluded_paths = set()
        if options.exclude_from is not None:
            try:
                excluded_paths = {line.strip() for line in options.exclude_from.read_text().splitlines()
                                  if line.strip() and not line.lstrip().startswith('#')}
            except OSError as error:
                parser.error('cannot read --exclude-from: ' + type(error).__name__)
        result = check_tree(options.root, [x.encode() for x in options.deny_user], excluded_paths)
        print(json.dumps(result, indent=2))
        raise SystemExit(bool(result['findings']))
