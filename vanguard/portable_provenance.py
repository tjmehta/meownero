"""Keep local home paths out of portable provenance and distribution ZIPs."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import zipfile

PLACEHOLDER = '/BUILD_HOME/'


def home_prefixes():
    home = Path.home()
    # Include both build-host platforms, even when assembling on the other one.
    return tuple(sorted({home.as_posix().rstrip('/') + '/',
                         '/home/' + home.name + '/', '/Users/' + home.name + '/'}))


def replace_home(text):
    for prefix in home_prefixes():
        text = text.replace(prefix, PLACEHOLDER)
    return text


def recorded_receipt(value):
    """Sanitize the saved copy; the actual command arguments stay untouched."""
    result = json.loads(replace_home(json.dumps(value)))
    result['path_recording'] = {'home_prefix_placeholder': PLACEHOLDER,
                                'command_paths': 'HOME_PREFIX_REPLACED_AT_RECORDING'}
    return result


def refuse_private_paths(data):
    """Scan bytes, archive metadata and nested members; never echo a private value."""
    for prefix in home_prefixes():
        for encoding in ('utf-8', 'utf-16-le', 'utf-16-be'):
            if prefix.encode(encoding) in data:
                raise ValueError('PRIVATE_HOME_PREFIX_IN_DISTRIBUTABLE')
    stream = io.BytesIO(data)
    if zipfile.is_zipfile(stream):
        with zipfile.ZipFile(stream) as archive:
            refuse_private_paths(archive.comment)
            for info in archive.infolist():
                refuse_private_paths(info.filename.encode())
                refuse_private_paths(info.comment)
                refuse_private_paths(info.extra)
                refuse_private_paths(archive.read(info))
    elif data.startswith((b'\x1f\x8b', b'BZh', b'\xfd7zXZ\x00')) or data[257:262] == b'ustar':
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as archive:
            for info in archive.getmembers():
                refuse_private_paths(info.name.encode())
                refuse_private_paths(info.linkname.encode())
                refuse_private_paths(json.dumps(info.pax_headers).encode())
                if info.isfile():
                    refuse_private_paths(archive.extractfile(info).read())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def successor_archive(source, destination):
    """Rewrite only known provenance, then refresh its transitive hash bindings.

    Original execution hashes remain in each changed member's rewrite record.
    Program, helper, controller, license and all other member bytes are immutable.
    """
    original_archive_sha256 = digest(source.read_bytes())
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        original = {info.filename: archive.read(info) for info in infos}
        if len(original) != len(infos):
            raise ValueError('DUPLICATE_ARCHIVE_MEMBER')
        root = infos[0].filename.split('/')[0] + '/'
        members = dict(original)
        rewrites, bindings = {}, {}

        def rewrite(name):
            key = root + name
            if key not in original:
                return
            before = original[key]
            replaced = replace_home(before.decode())
            record = {'original_member_sha256': digest(before),
                      'original_archive_sha256': original_archive_sha256,
                      'home_prefix_placeholder': PLACEHOLDER,
                      'meaning': 'DISTRIBUTION_COPY_NOT_ORIGINAL_EXECUTION_BYTES',
                      'binding_updates': []}
            if name.endswith('.json'):
                value = json.loads(replaced)

                def rebind(item, field=''):
                    if isinstance(item, dict):
                        return {k: rebind(v, field + '/' + k) for k, v in item.items()}
                    if isinstance(item, list):
                        return [rebind(v, field + '/' + str(i)) for i, v in enumerate(item)]
                    if isinstance(item, str) and item in bindings:
                        record['binding_updates'].append({'field': field,
                            'original_sha256': item, 'successor_sha256': bindings[item]})
                        return bindings[item]
                    return item

                value = rebind(value)
                if replaced == before.decode() and not record['binding_updates']:
                    return
                value['distribution_rewrite'] = record
                after = (json.dumps(value, indent=2) + '\n').encode()
            else:
                if replaced == before.decode():
                    return
                lines = replaced.splitlines(keepends=True)
                lines.insert(1 if lines[0].startswith('#!') else 0,
                             '# distribution_rewrite: ' + json.dumps(record) + '\n')
                after = ''.join(lines).encode()
            members[key] = after
            bindings[digest(before)] = digest(after)
            rewrites[name] = {'original_sha256': digest(before), 'successor_sha256': digest(after),
                              'binding_updates': record['binding_updates']}

        # Dependency order: cached -> pre-probe -> inputs/script -> cross -> build -> release.
        for name in ('build-evidence/cached-build-receipt.json',
                     'build-evidence/pre-exception-probe-build-receipt.json',
                     'build-evidence/i686-exception-probe-input.json',
                     'build-evidence/i686-exception-probe-cross.py',
                     'build-evidence/i686-exception-probe-cross-receipt.json',
                     'BUILD.json', 'release.json'):
            rewrite(name)
        if not rewrites:
            raise ValueError('NO_PROVENANCE_CORRECTION')
        release = json.loads(members[root + 'release.json'])
        for name, expected in release['files'].items():
            if digest(members[root + name]) != expected:
                raise ValueError('SUCCESSOR_RELEASE_BINDING_MISMATCH')
        if digest(members[root + 'BUILD.json']) != release['build_receipt']['sha256']:
            raise ValueError('SUCCESSOR_BUILD_BINDING_MISMATCH')
        # Inspect every member before writing an output. Unknown leaks fail closed.
        for name, data in members.items():
            refuse_private_paths(name.encode())
            refuse_private_paths(data)
        with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for info in infos:
                archive.writestr(info, members[info.filename])
        refuse_private_paths(destination.read_bytes())
        return {'original_archive_sha256': original_archive_sha256,
                'successor_archive_sha256': digest(destination.read_bytes()),
                'home_prefix_placeholder': PLACEHOLDER, 'rewritten_members': rewrites,
                'unchanged_members': {name[len(root):]: digest(data) for name, data in original.items()
                                      if data == members[name]},
                'historical_execution': 'ORIGINAL_HASHES_ONLY; SUCCESSOR_PROVENANCE_WAS_NOT_EXECUTED',
                'native_acceptance': 'NOT_GRANTED_BY_SANITIZATION'}
