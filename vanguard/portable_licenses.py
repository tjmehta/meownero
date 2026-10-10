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


def rust_coverage(build, package):
    """Require every locked external crate, including build/target-only inputs.

    This deliberately covers a superset of the linked crates. Cache discovery
    supplies locations, never the required set, so an absent cache cannot pass.
    """
    pin = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
    lock_path = build / 'monero-fcmp' / pin['rust']['cargo_lock_path']
    assert sha(lock_path) == pin['rust']['cargo_lock_sha256'], 'Cargo.lock pin mismatch'
    lock = tomllib.loads(lock_path.read_text())
    local = [p for p in lock['package'] if 'source' not in p]
    assert [(p['name'], p['version']) for p in local] == [('fcmp_pp_rust', '0.0.0')], \
        'unmapped local Rust package'
    required = {(p['name'], p['version'], p['source']): p
                for p in lock['package'] if 'source' in p}
    assert required, 'empty required Rust coverage'
    found = {}
    for kind, relative, prefix in [('registry', 'registry/src', 'rust-registry'),
                                   ('git', 'git/checkouts', 'rust-git')]:
        tree = build / 'cargo-home' / relative
        exported = package / 'licenses' / prefix
        assert tree.is_dir() and not tree.is_symlink(), 'missing Rust source tree: ' + relative
        assert exported.is_dir() and not exported.is_symlink(), 'missing Rust notice tree: ' + prefix
        for cargo in sorted(tree.rglob('Cargo.toml')):
            if any(p in {'.git', 'target'} for p in cargo.relative_to(tree).parts):
                continue
            metadata = tomllib.loads(cargo.read_text()).get('package', {})
            for key in required:
                if key[:2] != (metadata.get('name'), metadata.get('version')):
                    continue
                source = key[2]
                if kind == 'registry':
                    assert source == 'registry+https://github.com/rust-lang/crates.io-index', \
                        'unsupported Rust registry: ' + source
                else:
                    assert source.startswith('git+') and '#' in source, 'Rust source kind mismatch'
                    revision = source.rsplit('#', 1)[1]
                    assert re.fullmatch(r'[0-9a-f]{40}', revision), 'unresolved Rust git revision'
                    assert cargo.relative_to(tree).parts[1] == revision[:7], 'Rust git revision mismatch'
                assert key not in found, 'ambiguous Rust crate: ' + str(key)
                originals = sorted(p for p in cargo.parent.iterdir() if p.is_file() and
                    p.name.upper().startswith(('LICENSE', 'COPYING', 'COPYRIGHT')))
                assert originals, 'Rust crate notices missing: ' + key[0] + '@' + key[1]
                texts = {}
                for original in originals:
                    retained = exported / original.relative_to(tree)
                    digest = sha(original)
                    assert sha(retained) == digest, 'Rust notice content mismatch: ' + str(retained)
                    texts[str(retained.relative_to(package))] = digest
                row = {'component': 'Rust crate ' + key[0], 'version': key[1], 'source': source,
                       'libraries': [], 'texts': texts, 'cargo_toml_sha256': sha(cargo)}
                if 'checksum' in required[key]:
                    row['locked_source_archive_sha256'] = required[key]['checksum']
                found[key] = row
    missing = sorted(set(required) - set(found))
    assert not missing, 'required Rust crate missing: ' + str(missing)
    summary = {'policy': 'all external Cargo.lock packages, including build and target-only crates',
               'cargo_lock_sha256': sha(lock_path), 'required_count': len(required),
               'covered_count': len(found), 'local_wrapper': 'fcmp_pp_rust 0.0.0 covered by upstream LICENSE'}
    return summary, [found[key] for key in sorted(required)]


def link_inventory(source, binary_build, depends_root, container_sources=(), windows=False):
    """Resolve library and response paths from each actual linker working directory."""
    source, binary_build = source.resolve(), binary_build.resolve()
    depends_root = depends_root.resolve() if depends_root else None
    link_files, libraries, origins = [], set(), set()
    package_context = {'component': None, 'libraries': origins, 'link_commands': link_files}
    external_libraries = {}
    external = {'liblmdb.a': 'LMDB', 'libmx25519.a': 'mx25519', 'librandomx.a': 'RandomX',
                'libeasylogging.a': 'Easylogging++', 'libqrcodegen.a': 'qrcodegen'}
    for target in ['daemon', 'simplewallet', 'wallet_rpc_server']:
        matches = list(binary_build.rglob('CMakeFiles/' + target + '.dir/link.txt'))
        assert len(matches) == 1, 'missing/ambiguous linker inventory: ' + target
        link = matches[0]
        cwd = link.parent.parent.parent
        link_files.append({'target': target, 'sha256': sha(link)})

        def input_path(path):
            if path.is_absolute():
                for alias in container_sources:
                    if path.is_relative_to(alias):
                        return source / path.relative_to(alias)
            return cwd / path

        def arguments(text, seen=()):
            for token in shlex.split(text):
                if token.startswith('@'):
                    package_context['component'] = None
                    candidate = input_path(Path(token[1:]))
                    response = candidate.resolve()
                    assert response.is_relative_to(binary_build) and response not in seen, 'unsafe linker response file'
                    assert response.is_file() and not any(p.is_symlink() for p in (candidate, *candidate.parents)), 'missing/symlink linker response file'
                    link_files.append({'target': target, 'response_file': str(response.relative_to(binary_build)), 'sha256': sha(response)})
                    yield from arguments(response.read_text(), (*seen, response))
                else:
                    yield token

        for token in arguments(link.read_text()):
            if token.startswith('-l'):
                allowed = {'-lc', '-lm', '-ldl', '-lrt', '-lpthread', '-lstdc++'}
                if windows:
                    allowed |= {'-lws2_32', '-lmswsock', '-lwinhttp', '-lcrypt32', '-liphlpapi',
                                '-lshlwapi', '-ldnsapi', '-lbcrypt', '-ladvapi32', '-luserenv',
                                '-lkernel32', '-luser32', '-lshell32', '-lole32', '-lversion', '-lrpcrt4', '-lntdll', '-ldbghelp'}
                    allowed |= {'-lsynchronization', '-lgdi32', '-lwinspool', '-loleaut32', '-luuid', '-lcomdlg32'}
                assert token in allowed, 'unmapped linker library: ' + token
            if not re.search(r'\.(?:a|so(?:\.\d+)*)$', token):
                continue
            path = Path(token)
            normalized = input_path(path).resolve()
            component = next((name for name, prefix in DEPENDS.items() if path.name.startswith(prefix)), None)
            package_context['component'] = component
            if depends_root and normalized.is_relative_to(depends_root):
                if normalized.parent != depends_root / 'lib':
                    origins.add((path.name, 'non_pinned_depends'))
                assert normalized.parent == depends_root / 'lib', 'non-pinned depends library origin'
                libraries.add(path.name)
                origins.add((path.name, 'pinned_depends'))
            elif ('contrib' in normalized.parts and 'depends' in normalized.parts) or ('contrib' in path.parts and 'depends' in path.parts):
                origins.add((path.name, 'non_pinned_depends'))
                raise AssertionError('non-pinned depends library origin')
            elif depends_root and component:
                # A dependency basename cannot become a project library just
                # because it sits under src, epee or external build output.
                origins.add((path.name, 'non_pinned_depends'))
                raise AssertionError('pinned depends library has non-pinned origin')
            elif normalized.is_relative_to(binary_build / 'external'):
                assert path.name in external, 'unmapped static dependency: ' + token
                external_libraries.setdefault(external[path.name], []).append(path.name)
            elif normalized.is_relative_to(binary_build / 'src') or normalized.is_relative_to(binary_build / 'contrib/epee') or normalized == binary_build / 'lib/libwallet.a':
                pass
            elif 'contrib' in normalized.parts or 'contrib' in path.parts:
                origins.add((path.name, 'unmapped_contrib'))
                raise AssertionError('unmapped contrib library origin')
            elif path.is_absolute():
                libraries.add(path.name)
                origins.add((path.name, 'system'))
                assert not (depends_root and component), 'pinned depends library has non-pinned origin'
            else:
                origins.add((path.name, 'unmapped_relative'))
                raise AssertionError('unmapped source library: ' + token)
    return link_files, libraries, external_libraries, origins


def coverage(build, package, mac, bundled, windows=False, depends_static=False):
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
    receipt = json.loads((build / 'build-receipt.json').read_text())
    depends_root = None
    if mac or depends_static:
        target = receipt.get('target', 'macos-aarch64')
        host = {'linux-x86_64': 'x86_64-unknown-linux-gnu', 'linux-aarch64': 'aarch64-unknown-linux-gnu',
                'windows-x86_64': 'x86_64-w64-mingw32', 'windows-i686': 'i686-w64-mingw32',
                'windows-aarch64': 'aarch64-w64-mingw32', 'macos-aarch64': 'arm64-apple-darwin',
                'macos-x86_64': 'x86_64-apple-darwin'}[target]
        depends_root = source / 'contrib/depends' / host
    container_sources = (Path('/out/monero-fcmp'),) if windows else (() if mac else (Path('/src'), Path('/work/monero-fcmp')))
    link_files, libraries, external_libraries, origins = link_inventory(source, binary_build, depends_root, container_sources, windows)
    libraries.update(bundled)
    origins.update((name, 'bundled') for name in bundled)
    for component, names in external_libraries.items():
        next(c for c in components if c['component'] == component)['libraries'].extend(names)

    if mac or depends_static:
        dependency_libraries = set()
        for c in retain_depends(build):
            names = [n for n in libraries if n.startswith(DEPENDS[c['component']])]
            package_context = {'component': c['component'], 'libraries': sorted(origins), 'link_commands': link_files}
            assert all({origin for name, origin in origins if name == n} == {'pinned_depends'} for n in names), 'pinned depends library has mixed/non-pinned origins'
            if depends_static:
                assert all(n.endswith('.a') for n in names), 'older baseline requires the pinned static dependency closure'
            dependency_libraries.update(names)
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
        if mac:
            assert all(any(n.startswith(prefix) for prefix in DEPENDS.values()) for n in libraries), \
                'unmapped native depends library'
        else:
            libraries -= dependency_libraries
    if not mac:
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

    rust, crates = rust_coverage(build, package)
    components.extend(crates)
    return {'schema': 'meownero-license-coverage/1', 'result': 'PASS_LINKED_DEPENDENCY_COVERAGE',
            'link_commands': link_files, 'rust_coverage': rust, 'components': components}
