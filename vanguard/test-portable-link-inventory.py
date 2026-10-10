#!/usr/bin/env python3
"""Exercise pinned linker origins, dependency refusal and safe failure diagnostics."""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import portable_licenses as licenses

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / 'research/evidence/vanguard-portable-production-tjs1882-2026-10-09'
NAMES = ['libboost_filesystem.a', 'libssl.a', 'libcrypto.a', 'libsodium.a', 'libunbound.a', 'libzmq.a']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--vendored-header', type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.is_dir() and not args.out.exists()
    provenance = json.loads((ROOT / 'vanguard/licenses/easyloggingpp-9.96.7/provenance.json').read_text())
    assert licenses.sha(args.vendored_header) == provenance['vendored_header_sha256']
    cases = []
    with tempfile.TemporaryDirectory(prefix='PRIVATE_PATH_SENTINEL ', dir=args.out.parent) as directory:
        build = Path(directory) / 'build'
        source = build / 'monero-fcmp'
        binary_build = source / 'build/vanguard'
        depends = source / 'contrib/depends/x86_64-unknown-linux-gnu'
        links = []
        for name, folder in [('daemon', 'daemon'), ('simplewallet', 'simplewallet'), ('wallet_rpc_server', 'wallet')]:
            link = binary_build / 'src' / folder / 'CMakeFiles' / (name + '.dir/link.txt')
            link.parent.mkdir(parents=True)
            links.append(link)

        def configure(style, names=NAMES):
            for link in links:
                cwd = link.parent.parent.parent
                paths = [depends / 'lib' / name for name in names]
                if style == 'relative':
                    paths = [os.path.relpath(p, cwd) for p in paths]
                elif style == 'container':
                    paths = [Path('/src') / p.relative_to(source) for p in paths]
                elif style == 'mixed':
                    paths = [str(p) if n % 2 else os.path.relpath(p, cwd) for n, p in enumerate(paths)]
                tokens = [str(p) for p in paths]
                tokens += ['../common/libcommon.a', '../../contrib/epee/src/libepee.a', '../../external/randomx/librandomx.a']
                if style.startswith('response'):
                    response = link.with_name('libraries.rsp')
                    response.write_text(shlex.join([os.path.relpath(p, cwd) for p in paths]))
                    response_token = str(response.relative_to(cwd))
                    if style == 'response-absolute':
                        response_token = str(response)
                    elif style == 'response-container':
                        response_token = str(Path('/src') / response.relative_to(source))
                    tokens = ['@' + response_token, *tokens[len(paths):]]
                link.write_text(shlex.join(['c++', *tokens]))

        def inventory():
            return licenses.link_inventory(source, binary_build, depends, (Path('/src'),))

        for style in ('absolute', 'relative', 'container', 'mixed', 'response', 'response-absolute', 'response-container'):
            configure(style)
            commands, names, external, origins = inventory()
            assert names == set(NAMES)
            assert external == {'RandomX': ['librandomx.a'] * 3}
            assert origins == {(n, 'pinned_depends') for n in NAMES}
            assert len(commands) == (6 if style.startswith('response') else 3)
            cases.append({'case': style + '-equivalence', 'result': 'PASS'})

        def refuse(label, token, expected):
            configure('absolute')
            links[0].write_text(shlex.join(['c++', str(token)]))
            try:
                inventory()
            except AssertionError as error:
                assert expected in str(error), str(error)
            else:
                raise AssertionError('unsafe library origin accepted')
            cases.append({'case': label, 'result': 'PASS_REFUSAL'})

        cwd = links[0].parent.parent.parent
        refuse('wrong-depends-host', os.path.relpath(source / 'contrib/depends/wrong-host/lib/libboost_filesystem.a', cwd), 'non-pinned depends')
        refuse('wrong-depends-library-directory', depends / 'lib-other/libboost_filesystem.a', 'non-pinned depends')
        refuse('non-pinned-contrib', os.path.relpath(source / 'contrib/private/libboost_filesystem.a', cwd), 'non-pinned origin')
        for folder in ('src', 'contrib/epee'):
            configure('absolute')
            path = binary_build / folder / 'libcrypto.a'
            links[0].write_text(shlex.join(['c++', str(path)]) + ' ' + links[0].read_text())
            try:
                inventory()
            except AssertionError as error:
                assert 'non-pinned origin' in str(error)
                trace = error.__traceback__
                while trace.tb_next:
                    trace = trace.tb_next
                assert ('libcrypto.a', 'non_pinned_depends') in trace.tb_frame.f_locals['package_context']['libraries']
            else:
                raise AssertionError('project directory disguised pinned dependency')
            cases.append({'case': folder + '-pinned-basename-before-pinned-arguments', 'result': 'PASS_REFUSAL'})
        refuse('outside-project-src', os.path.relpath(source / 'outside/src/libcommon.a', cwd), 'unmapped source')
        refuse('absolute-untrusted-pinned-basename', '/opt/untrusted/libcrypto.a', 'non-pinned origin')
        configure('absolute')
        links[0].write_text(links[0].read_text() + ' /opt/untrusted/libcrypto.a')
        try:
            inventory()
        except AssertionError as error:
            assert 'non-pinned origin' in str(error)
        else:
            raise AssertionError('same basename from mixed origins accepted')
        cases.append({'case': 'mixed-pinned-and-untrusted-basename', 'result': 'PASS_REFUSAL'})
        refuse('response-escape', '@' + os.path.relpath(build / 'PRIVATE_RESPONSE_SENTINEL', cwd), 'unsafe linker response')
        refuse('response-container-escape', '@/src/build/../../../PRIVATE_RESPONSE_SENTINEL', 'unsafe linker response')
        cycle = links[0].with_name('cycle.rsp')
        token = '@' + str(cycle.relative_to(cwd))
        cycle.write_text(token)
        refuse('response-cycle', token, 'unsafe linker response')
        target = links[0].with_name('real.rsp')
        target.write_text('-lpthread')
        symlink = links[0].with_name('symlink.rsp')
        symlink.symlink_to(target)
        refuse('response-file-symlink', '@' + str(symlink.relative_to(cwd)), 'symlink linker response')
        parent_link = binary_build / 'symlink-parent'
        parent_link.symlink_to(target.parent, target_is_directory=True)
        refuse('response-parent-symlink', '@' + str(parent_link / target.name), 'symlink linker response')

        # Exercise the real missing-dependency assertion. Retained notice and Rust
        # seams isolate inventory behavior; this is not a native archive test.
        package = Path(directory) / 'package'
        notices = package / 'licenses/upstream'
        for relative in ['LICENSE', 'contrib/epee/LICENSE.txt', 'external/db_drivers/liblmdb/LICENSE',
                         'external/db_drivers/liblmdb/COPYRIGHT', 'external/randomx/LICENSE',
                         'external/mx25519/LICENSE', 'external/rapidjson/license.txt']:
            path = notices / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture notice\n')
        header = source / provenance['vendored_header_source']
        header.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.vendored_header, header)
        qr = source / 'external/qrcodegen/QrCode.hpp'
        qr.parent.mkdir(parents=True)
        qr.write_text('/* Project Nayuki. Permission is hereby granted */\n')
        (build / 'build-receipt.json').write_text(json.dumps({'target': 'linux-x86_64', 'builder_image': 'fixture'}))
        (build / 'dependencies.txt').write_text('')
        retained = []
        for component in licenses.DEPENDS:
            path = build / 'licenses' / component / 'LICENSE'
            path.parent.mkdir(parents=True)
            path.write_text('retained fixture notice\n')
            retained.append({'component': component, 'version': 'fixture', 'source': 'fixture',
                             'texts': {str(path.relative_to(build / 'licenses')): licenses.sha(path)},
                             'source_archive_sha256': '0' * 64, 'recipe_sha256': '1' * 64})

        for style in ('absolute', 'relative'):
            configure(style)
            with patch.object(licenses, 'retain_depends', return_value=retained), patch.object(licenses, 'rust_coverage', return_value=({}, [])):
                value = licenses.coverage(build, package, False, [], depends_static=True)
            assert value['result'] == 'PASS_LINKED_DEPENDENCY_COVERAGE'
            assert {c['component'] for c in value['components']} >= set(licenses.DEPENDS)
            cases.append({'case': style + '-full-missing-component-guard-positive', 'result': 'PASS', 'scope': 'NOTICE_AND_RUST_SEAMS'})

        configure('absolute')
        with patch.object(licenses, 'retain_depends', return_value=retained):
            try:
                licenses.coverage(build, package, False, ['libcrypto.a'], depends_static=True)
            except AssertionError as error:
                assert str(error) == 'pinned depends library has mixed/non-pinned origins'
            else:
                raise AssertionError('bundled basename replaced pinned provenance')
        cases.append({'case': 'coverage-mixed-bundled-origin-refusal', 'result': 'PASS_REFUSAL'})
        configure('absolute', ['libboost_filesystem.so', *NAMES[1:]])
        with patch.object(licenses, 'retain_depends', return_value=retained):
            try:
                licenses.coverage(build, package, False, [], depends_static=True)
            except AssertionError as error:
                assert str(error) == 'older baseline requires the pinned static dependency closure'
            else:
                raise AssertionError('shared dependency replaced static closure')
        cases.append({'case': 'static-closure-refusal-retained', 'result': 'PASS_REFUSAL'})

        def missing(style='relative'):
            configure(style, NAMES[1:])
            with patch.object(licenses, 'retain_depends', return_value=retained):
                licenses.coverage(build, package, False, [], depends_static=True)

        for prior, number in ((31, 33), (32, 34)):
            carrier = EVIDENCE / f'linux{number}-package-controller.source.py'
            spec = importlib.util.spec_from_file_location(f'controller{number}', carrier)
            ci = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(ci)
            ci.ROOT = ROOT
            inputs = {'target': 'linux-x86_64' if number == 33 else 'linux-aarch64',
                      'source_files': {'vanguard/portable_licenses.py': licenses.sha(Path(licenses.__file__))}}
            try:
                missing()
            except AssertionError as error:
                assert str(error) == 'depends component absent from linker inventory'
                diagnostic = ci.package_failure(error, inputs)
            else:
                raise AssertionError('missing Boost accepted')
            context = diagnostic['depends_inventory']
            assert context['component'] == 'boost'
            assert {row['basename'] for row in context['libraries']} == set(NAMES[1:])
            assert all(row['origin'] == 'pinned_depends' for row in context['libraries'])
            assert len(context['link_commands']) == 3
            assert 'PRIVATE_PATH_SENTINEL' not in json.dumps(diagnostic)
            assert not any('response_file' in row for row in context['link_commands'])
            old = ast.parse((EVIDENCE / f'linux{prior}-package-controller.source.py').read_text())
            new = ast.parse(carrier.read_text())
            functions = lambda tree: {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
            before, after = functions(old), functions(new)
            assert set(before) == set(after)
            assert [name for name in before if before[name] != after[name]] == ['package_failure']
            cases.append({'controller': number, 'case': 'missing-component-and-safe-source-bound-diagnostic', 'result': 'PASS'})

            try:
                missing('response')
            except AssertionError as error:
                value = ci.package_failure(error, inputs)
            commands = value['depends_inventory']['link_commands']
            assert len(commands) == 6
            assert {row['kind'] for row in commands} == {'link_command', 'response_file'}
            assert 'PRIVATE_PATH_SENTINEL' not in json.dumps(value)
            cases.append({'controller': number, 'case': 'safe-response-file-hash-context', 'result': 'PASS'})

            for origin, token in [('non_pinned_depends', source / 'contrib/depends/wrong-host/lib/libcrypto.a'),
                                  ('non_pinned_depends', Path('/opt/untrusted/libcrypto.a'))]:
                configure('relative')
                links[0].write_text(shlex.join(['c++', str(token)]))
                try:
                    inventory()
                except AssertionError as error:
                    value = ci.package_failure(error, inputs)
                else:
                    raise AssertionError('bad pinned origin accepted')
                assert value['depends_inventory']['component'] == 'openssl'
                assert value['depends_inventory']['libraries'] == [{'basename': 'libcrypto.a', 'origin': origin}]
                assert len(value['depends_inventory']['link_commands']) == 1
                assert 'PRIVATE_' not in json.dumps(value)
                cases.append({'controller': number, 'case': 'safe-origin-refusal-context-' + origin, 'result': 'PASS'})

            # Execute the preserved worker with the real license failure. A
            # secondary diagnostic write error must retain that primary error.
            out = Path(directory) / f'worker{number}'
            out.mkdir()
            (out / 'public').mkdir()
            for export_failure in (False, True):
                captured = []
                writes = []
                def actual_main():
                    try:
                        missing('response')
                    except AssertionError as error:
                        captured.append(error)
                        raise
                def write(path, value):
                    assert path == out / 'public/package-diagnostic.json'
                    assert 'PRIVATE_PATH_SENTINEL' not in json.dumps(value)
                    writes.append(value)
                    if export_failure:
                        raise OSError('PRIVATE_SECONDARY_SENTINEL')
                saved_argv = sys.argv
                try:
                    with patch.object(ci, 'load', return_value=SimpleNamespace(main=actual_main)), patch.object(ci, 'write', write):
                        try:
                            ci.worker('package', inputs, out)
                        except AssertionError as error:
                            assert error is captured[0]
                            assert str(error) == 'depends component absent from linker inventory'
                            assert getattr(error, '__notes__', []) == (['PACKAGE_DIAGNOSTIC_EXPORT_FAILED'] if export_failure else [])
                        else:
                            raise AssertionError('primary missing-component error lost')
                finally:
                    sys.argv = saved_argv
                assert len(writes) == 1 and writes[0]['depends_inventory']['component'] == 'boost'
                cases.append({'controller': number, 'case': 'worker-primary-error-secondary-export-' + str(export_failure),
                              'result': 'PASS', 'scope': 'REAL_LICENSE_FAILURE_WITH_PACKAGE_LOAD_SEAM'})

            # A spoofed context must not export private strings, path names,
            # exception text, invalid hashes, extra keys or arbitrary component names.
            code = compile("def fail():\n    package_context = context\n    raise AssertionError('PRIVATE_EXCEPTION_SENTINEL')\n",
                           str(ROOT / 'vanguard/portable_licenses.py'), 'exec')
            scope = {'context': {'component': 'PRIVATE_COMPONENT_SENTINEL',
                                'libraries': [('libboost_PRIVATE_NAME_SENTINEL.a', 'pinned_depends'), ('PRIVATE_NAME', 'PRIVATE_ORIGIN')],
                                'link_commands': [{'target': 'daemon', 'sha256': 'a' * 64, 'response_file': 'PRIVATE_RESPONSE_SENTINEL'},
                                                  {'target': 'PRIVATE_TARGET', 'sha256': 'PRIVATE_HASH'}]}}
            exec(code, scope)
            try:
                scope['fail']()
            except AssertionError as error:
                value = ci.package_failure(error, inputs)
            assert 'PRIVATE_' not in json.dumps(value)
            assert value['depends_inventory']['component'] == 'UNKNOWN'
            assert value['depends_inventory']['libraries'] == [{'basename': 'OTHER_LIBRARY', 'origin': 'pinned_depends'}]
            cases.append({'controller': number, 'case': 'spoofed-private-context-refusal', 'result': 'PASS'})

    receipt = {'schema': 'meownero-pinned-linker-inventory-fixtures/1', 'result': 'PASS',
               'source_sha256': licenses.sha(Path(licenses.__file__)),
               'controllers': {str(n): licenses.sha(EVIDENCE / f'linux{n}-package-controller.source.py') for n in (33, 34)},
               'fixture_source_sha256': licenses.sha(Path(__file__)), 'cases': cases,
               'native_archive_or_runtime_acceptance': False}
    args.out.write_text(json.dumps(receipt, indent=2) + '\n')
    print('PASS', len(cases), 'pinned inventory and privacy cases')


if __name__ == '__main__':
    main()
