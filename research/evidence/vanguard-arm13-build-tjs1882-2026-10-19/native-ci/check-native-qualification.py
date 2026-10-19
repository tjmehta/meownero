"""Exercise ARM64 admission with synthetic PE files and mocked Win32 responses.

This is guard testing on Linux, never native Windows execution evidence.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile

p = argparse.ArgumentParser()
p.add_argument('--controller', type=Path, required=True)
p.add_argument('--scratch', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
ns = {'__file__': str(a.controller), '__name__': 'bound_guard_test'}
exec(compile(a.controller.read_text(), str(a.controller), 'exec'), ns)
cases = []

with tempfile.TemporaryDirectory(prefix='arm13-native-guard-', dir=a.scratch) as work:
    root = Path(work)
    package = root / 'package'
    (package / 'bin').mkdir(parents=True)

    def pe(machine=0xaa64, magic=b'\x0b\x02'):
        data = bytearray(90)
        data[:2] = b'MZ'
        data[60:64] = (64).to_bytes(4, 'little')
        data[64:68] = b'PE\0\0'
        data[68:70] = machine.to_bytes(2, 'little')
        data[88:90] = magic
        return bytes(data)

    names = ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')
    python = root / 'python.exe'
    programs = [package / 'bin' / (n + '.exe') for n in names]
    state = {}

    def reset():
        state.clear()
        state.update(process=0, native=0xaa64, crypto=True, query=True, arch='aarch64')
        for path in [python, *programs]:
            path.write_bytes(pe())
        ns['os'] = SimpleNamespace(name='nt')
        ns['platform'] = SimpleNamespace(python_implementation=lambda: 'CPython', machine=lambda: 'ARM64')
        ns['sys'] = SimpleNamespace(version_info=(3, 13, 16), executable=str(python))
        return {'program_sha256': {n: hashlib.sha256(pe()).hexdigest() for n in names}}

    def api(library, name, result, *arguments):
        if name == 'IsWow64Process2':
            def query(handle, process, native):
                assert handle == 123
                process._obj.value, native._obj.value = state['process'], state['native']
                return state['query']
            return query
        assert name == 'IsProcessorFeaturePresent'
        return lambda feature: state['crypto'] if feature == 30 else False

    def check(value):
        if not value:
            raise OSError('synthetic API failure')
        return value

    backend = SimpleNamespace(C=ctypes, W=wintypes, k=None, api=api, check=check,
        native_architecture=lambda: state['arch'], _winapi=SimpleNamespace(GetCurrentProcess=lambda: 123))

    row = reset()
    qualified = ns['windows_arm64_qualification'](backend, package, row)
    assert qualified['process_machine'] == 0 and qualified['native_machine'] == 0xaa64
    projected = ns['public_check']({'native_qualification': {**qualified, 'private': 'sentinel'}})
    assert projected['native_qualification'] == qualified and 'sentinel' not in json.dumps(projected)
    cases.append({'case': 'native-arm64-synthetic-admission-and-public-projection', 'result': 'PASS'})

    mutations = {
        'x64-python-process': lambda: state.update(process=0x8664),
        'x86-python-process': lambda: state.update(process=0x14c),
        'wrong-native-machine': lambda: state.update(native=0x8664),
        'wrong-backend-native': lambda: state.update(arch='x86_64'),
        'crypto-unavailable': lambda: state.update(crypto=False),
        'machine-query-fails': lambda: state.update(query=False),
        'python-x64-pe': lambda: python.write_bytes(pe(0x8664)),
        'python-arm64ec-pe': lambda: python.write_bytes(pe(0xa641)),
        'python-pe32': lambda: python.write_bytes(pe(magic=b'\x0b\x01')),
        'python-invalid-dos': lambda: python.write_bytes(b'bad'),
        'python-pe-offset-outside-file': lambda: python.write_bytes(pe()[:60] + (999999).to_bytes(4, 'little')),
        'old-python': lambda: setattr(ns['sys'], 'version_info', (3, 12, 0)),
        'non-cpython': lambda: setattr(ns['platform'], 'python_implementation', lambda: 'PyPy'),
        'wrong-process-platform': lambda: setattr(ns['platform'], 'machine', lambda: 'AMD64'),
        'non-windows': lambda: setattr(ns['os'], 'name', 'posix'),
    }
    for label, mutate in mutations.items():
        row = reset()
        mutate()
        try:
            ns['windows_arm64_qualification'](backend, package, row)
        except (AssertionError, OSError):
            cases.append({'case': label, 'result': 'PASS_REFUSAL'})
        else:
            raise AssertionError('guard accepted ' + label)
    for name, path in zip(names, programs):
        for mode in ('hash', 'machine'):
            row = reset()
            path.write_bytes(pe(0x8664))
            if mode == 'machine':
                row['program_sha256'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
            try:
                ns['windows_arm64_qualification'](backend, package, row)
            except AssertionError:
                cases.append({'case': name + '-' + mode, 'result': 'PASS_REFUSAL'})
            else:
                raise AssertionError('program guard accepted ' + name)

a.out.write_text(json.dumps({'result': 'PASS_MOCKED_ARM64_ADMISSION_GUARDS', 'count': len(cases),
    'cases': cases, 'controller_sha256': hashlib.sha256(a.controller.read_bytes()).hexdigest(),
    'native_windows_execution': 'UNTESTED', 'scope': 'SYNTHETIC_FILES_AND_MOCKED_APIS_ONLY'}, indent=2) + '\n')
print('PASS_MOCKED_ARM64_ADMISSION_GUARDS', len(cases))
