"""Retain pinned depends notices and bind shipped libraries to packaged texts."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parent.parent
DEPENDS = {'boost': 'libboost_', 'openssl': ('libssl', 'libcrypto'),
           'sodium': 'libsodium', 'unbound': 'libunbound', 'zeromq': 'libzmq'}
SYSTEM = {'libbsd': 'libbsd0', 'libcap': 'libcap2', 'libcom_err': 'libcom-err2',
          'libcrypto': 'libssl3t64', 'libssl': 'libssl3t64', 'libevent-2.1': 'libevent-2.1-7t64',
          'libgcc_s': 'libgcc-s1', 'libgssapi_krb5': 'libgssapi-krb5-2',
          'libhidapi-libusb': 'libhidapi-libusb0', 'libk5crypto': 'libk5crypto3',
          'libkeyutils': 'libkeyutils1', 'libkrb5support': 'libkrb5support0',
          'libkrb5': 'libkrb5-3', 'libmd': 'libmd0', 'libnorm': 'libnorm1t64',
          'libpgm-5.3': 'libpgm-5.3-0t64', 'libresolv': 'libc6', 'librt': 'libc6',
          'libsodium': 'libsodium23', 'libstdc++': 'libstdc++6', 'libudev': 'libudev1',
          'libunbound': 'libunbound8', 'libusb-1.0': 'libusb-1.0-0', 'libzmq': 'libzmq5',
          'libz': 'zlib1g'}


def sha(path):
    assert path.is_file() and not path.is_symlink(), 'missing/unsafe license input: ' + str(path)
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def retain_depends(build):
    """Read only notice members from archives checked against the locked recipes."""
    depends = build / 'monero-fcmp/contrib/depends'
    out = build / 'licenses/depends'
    out.mkdir(parents=True, exist_ok=True)
    components = []
    for name in DEPENDS:
        recipe = depends / 'packages' / (name + '.mk')
        text = recipe.read_text()
        def field(key):
            return re.search(r'^\$\(package\)_' + key + r'=(.+)$', text, re.M)[1]
        version = field('version')
        filename = field('file_name').replace('$($(package)_version)', version).replace('$(package)', name)
        archive = depends / 'sources' / filename
        assert sha(archive) == field('sha256_hash'), 'depends source checksum mismatch: ' + name
        texts = {}
        with tarfile.open(archive) as stream:
            for member in stream:
                path = Path(member.name)
                if not re.fullmatch(r'(?:LICENSE|COPYING|COPYRIGHT|NOTICE|AUTHORS)(?:[._-].*)?', path.name, re.I):
                    continue
                if path.suffix in {'.cpp', '.hpp', '.pm'}:
                    continue
                assert member.isfile() and not path.is_absolute() and '..' not in path.parts
                assert member.size < 2 * 1024**2, 'oversized notice'
                target = out / name / path
                target.parent.mkdir(parents=True, exist_ok=True)
                data = stream.extractfile(member).read()
                if target.exists():
                    assert target.read_bytes() == data, 'retained notice changed'
                else:
                    target.write_bytes(data)
                texts[str(target.relative_to(build / 'licenses'))] = sha(target)
        assert any(Path(p).name.upper().startswith('LICENSE') for p in texts), 'missing depends license: ' + name
        components.append({'component': name, 'version': version, 'source_archive': filename,
                           'source_archive_sha256': sha(archive), 'recipe_sha256': sha(recipe),
                           'source': field('download_path').replace('$($(package)_version)', version).replace('$(package)', name),
                           'texts': texts})
    (out / 'inventory.json').write_text(json.dumps(components, indent=2) + '\n')
    return components


def coverage(build, package, mac, bundled):
    source = build / 'monero-fcmp'
    licenses = package / 'licenses'
    components = []
    def add(name, version, origin, texts, libraries=()):
        assert texts, 'license coverage missing: ' + name
        hashes = {str(p.relative_to(package)): sha(p) for p in texts}
        components.append({'component': name, 'version': version, 'source': origin,
                           'libraries': sorted(libraries), 'texts': hashes})

    pin = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
    origin = pin['upstream']['url'] + '@' + pin['upstream']['commit']
    add('Monero', pin['upstream']['commit'], origin, [licenses / 'upstream/LICENSE'])
    for name, rel, version in [
        ('epee', 'contrib/epee/LICENSE.txt', pin['upstream']['commit']),
        ('LMDB', 'external/db_drivers/liblmdb/LICENSE', '0.9.70'),
        ('RandomX', 'external/randomx/LICENSE', pin['upstream']['submodules']['external/randomx']),
        ('mx25519', 'external/mx25519/LICENSE', pin['upstream']['submodules']['external/mx25519']),
        ('RapidJSON', 'external/rapidjson/license.txt', pin['upstream']['submodules']['external/rapidjson'])]:
        texts = [licenses / 'upstream' / rel]
        if name == 'LMDB':
            texts.append(licenses / 'upstream/external/db_drivers/liblmdb/COPYRIGHT')
        add(name, version, origin, texts)

    easy = ROOT / 'vanguard/licenses/easyloggingpp-9.96.7'
    provenance = json.loads((easy / 'provenance.json').read_text())
    assert sha(source / provenance['vendored_header_source']) == provenance['vendored_header_sha256']
    assert sha(easy / 'LICENSE') == provenance['license_sha256']
    dest = licenses / 'upstream/external/easylogging++'
    dest.mkdir(parents=True, exist_ok=True)
    for name in ['LICENSE', 'COPYRIGHT-header.txt', 'provenance.json']:
        shutil.copyfile(easy / name, dest / name)
    add('Easylogging++', '9.96.7', provenance['license_url'], [dest / 'LICENSE', dest / 'COPYRIGHT-header.txt'])
    qr = source / 'external/qrcodegen/QrCode.hpp'
    notice = qr.read_text().split('*/', 1)[0] + '*/\n'
    assert 'Permission is hereby granted' in notice and 'Project Nayuki' in notice
    dest = licenses / 'upstream/external/qrcodegen/COPYRIGHT-header.txt'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(notice)
    add('qrcodegen', pin['upstream']['commit'], origin + '/external/qrcodegen', [dest])

    # Inventory the actual three linker commands, including static libraries
    # invisible to otool/readelf. Unknown external libraries stop packaging.
    binary_build = source / ('build/portable' if mac else 'build/vanguard')
    link_files = []
    libraries = set(bundled)
    external = {'liblmdb.a': 'LMDB', 'libmx25519.a': 'mx25519', 'librandomx.a': 'RandomX',
                'libeasylogging.a': 'Easylogging++', 'libqrcodegen.a': 'qrcodegen'}
    for target in ['daemon', 'simplewallet', 'wallet_rpc_server']:
        matches = list(binary_build.rglob('CMakeFiles/' + target + '.dir/link.txt'))
        assert len(matches) == 1, 'missing/ambiguous linker inventory: ' + target
        link = matches[0]
        link_files.append({'target': target, 'sha256': sha(link)})
        for token in shlex.split(link.read_text()):
            if token.startswith('-l'):
                assert token in {'-lc', '-lm', '-ldl', '-lrt', '-lpthread', '-lstdc++'}, \
                    'unmapped linker library: ' + token
            if not re.search(r'\.(?:a|so(?:\.\d+)*)$', token):
                continue
            path = Path(token)
            if path.is_absolute():
                libraries.add(path.name)
            elif 'external' in path.parts:
                assert path.name in external, 'unmapped static dependency: ' + token
                next(c for c in components if c['component'] == external[path.name])['libraries'].append(path.name)
            else:
                assert 'src' in (link.parent / path).resolve().parts or 'contrib' in path.parts or path.name == 'libwallet.a', \
                    'unmapped source library: ' + token

    if mac:
        for c in retain_depends(build):
            names = [n for n in libraries if n.startswith(DEPENDS[c['component']])]
            assert names, 'depends component absent from linker inventory'
            for rel, digest in c['texts'].items():
                p = licenses / 'system' / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(build / 'licenses' / rel, p)
                assert sha(p) == digest
            add(c['component'], c['version'], c['source'],
                [licenses / 'system' / p for p in c['texts']], names)
            components[-1]['source_archive_sha256'] = c['source_archive_sha256']
            components[-1]['recipe_sha256'] = c['recipe_sha256']
        assert all(any(n.startswith(prefix) for prefix in DEPENDS.values()) for n in libraries), \
            'unmapped native depends library'
    else:
        installed = dict(line.split('=', 1) for line in (build / 'dependencies.txt').read_text().splitlines())
        installed = {k.split(':')[0]: v for k, v in installed.items()}
        by_package = {}
        for name in libraries:
            stem = name.split('.so')[0].removesuffix('.a')
            if stem.startswith('libboost_'):
                base = 'libboost-' + stem.removeprefix('libboost_').replace('_', '-')
                candidates = [p for p in installed if re.fullmatch(re.escape(base) + r'\d+\.\d+\.\d+(?:t64)?', p)]
                assert len(candidates) == 1, 'unknown Boost package: ' + name
                pkg = candidates[0]
            else:
                assert stem in SYSTEM, 'unmapped shipped dependency: ' + name
                pkg = SYSTEM[stem]
            assert pkg in installed, 'dependency version missing: ' + pkg
            by_package.setdefault(pkg, []).append(name)
        for pkg, names in sorted(by_package.items()):
            text = licenses / 'system' / ('COPYRIGHT-' + pkg)
            referenced = {name.rstrip('.') for name in re.findall(r'/usr/share/common-licenses/([A-Za-z0-9.-]+)', text.read_text())}
            texts = [text] + [licenses / 'system' / ('COPYING-common-' + name) for name in sorted(referenced)]
            add(pkg, installed[pkg], 'Ubuntu package inventory at builder ' + str(json.loads((build / 'build-receipt.json').read_text())['builder_image']), texts, names)

    # Retain crate name/version/source mappings for the Cargo.lock dependencies.
    lock = tomllib.loads((source / pin['rust']['cargo_lock_path']).read_text())
    locked = {(p['name'], p['version']): p for p in lock['package']}
    for tree, prefix in [(build / 'cargo-home/registry/src', 'rust-registry'),
                         (build / 'cargo-home/git/checkouts', 'rust-git')]:
        for cargo in sorted(tree.rglob('Cargo.toml')):
            if any(p in {'.git', 'target'} for p in cargo.relative_to(tree).parts):
                continue
            metadata = tomllib.loads(cargo.read_text()).get('package', {})
            key = metadata.get('name'), metadata.get('version')
            if key not in locked:
                continue
            texts = [p for p in (licenses / prefix / cargo.parent.relative_to(tree)).glob('*')
                     if p.is_file() and p.name.upper().startswith(('LICENSE', 'COPYING', 'COPYRIGHT'))]
            add('Rust crate ' + key[0], key[1], locked[key].get('source', origin), texts)
    return {'schema': 'meownero-license-coverage/1', 'result': 'PASS_LINKED_DEPENDENCY_COVERAGE',
            'link_commands': link_files, 'components': components}
