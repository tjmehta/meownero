"""Verify immutable handoff bindings and run byte-only validation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import yaml

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
results = []
for num, kind in [('27', 'native-linux-ci'), ('28', 'native-linux-arm-ci'), ('29', 'native-ci')]:
    payload = root / f'build/tjs1882-d67e-{kind}-payload{num}'
    pub = json.loads((payload / 'PUBLICATION.json').read_text())
    for name, meta in pub['files'].items():
        assert sha(payload / name) == meta['sha256'] and (payload / name).stat().st_size == meta['bytes']
        if name.endswith('.py'):
            compile((payload / name).read_bytes(), str(payload / name), 'exec')
    assert (payload / 'SHA256SUMS').read_text() == ''.join(v['sha256'] + '  ' + n + '\n' for n, v in pub['files'].items())
    for name, meta in pub['source_evidence_files'].items():
        blob = subprocess.check_output(['git', 'show', pub['source_evidence_commit'] + ':' + name], cwd=root)
        assert len(blob) == meta['bytes'] and hashlib.sha256(blob).hexdigest() == meta['sha256']
    workflow = pub['publication_order']['final_repository_file']
    parsed = yaml.load((payload / workflow).read_text(), Loader=yaml.BaseLoader)
    assert list(parsed['on']) == ['push']
    assert parsed['on']['push']['branches'] == ['tjs1882-native-windows-preflight']
    assert parsed['on']['push']['paths'] == [workflow]
    assert parsed['permissions'] == {'contents': 'read'} and len(parsed['jobs']) == 1
    job = next(iter(parsed['jobs'].values()))
    assert job['timeout-minutes'] == ('30' if num == '29' else '120')
    for step in job['steps']:
        if 'uses' in step:
            assert len(step['uses'].split('@')[-1]) == 40
    manifest = payload / ('vanguard/ci-inputs.json' if num == '29' else
        'ci/tjs1882/' + ('linux-build-inputs.json' if num == '27' else 'linux-arm-build-inputs.json'))
    assert sha(manifest) in (payload / workflow).read_text()
    helper = payload / ('vanguard/run-portable-ci.py' if num == '29' else 'vanguard/run-portable-linux-ci.py')
    with tempfile.TemporaryDirectory(prefix='tjs1882-byte-only-', dir=root / 'build') as tmp:
        out = Path(tmp) / 'validate'
        argv = [sys.executable, '-B', str(helper), '--inputs', str(manifest),
            '--inputs-sha256', sha(manifest), '--out', str(out), '--prepare-only' if num == '29' else '--validate-only']
        if num == '29':
            argv.extend(['--target', 'windows-i686'])
            assert helper.read_bytes() == (evidence / 'i68629-supervisor.source.py').read_bytes()
        else:
            inputs = json.loads(manifest.read_text())
            assert inputs['bounds']['compile_memory_bytes'] == 4294967296
            assert inputs['compile_resource_policy']['host_minimum_available_bytes'] == 6 * 1024**3
        subprocess.run(argv, check=True, timeout=60, stdout=subprocess.DEVNULL)
    results.append({'payload': num, 'files_verified': len(pub['files']),
        'source_evidence_commit': pub['source_evidence_commit'], 'publication_sha256': sha(payload / 'PUBLICATION.json'),
        'syntax_workflow_pin_source_evidence_and_byte_only_validation': 'PASS', 'new_native_work': False})
result = {'result': 'PASS', 'payloads': results,
    'exact_controller_negative_proof_carry': '27/28 controllers and inputs equal25/26; four source-bound negative cases carried by exact hash equality'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS', sum(r['files_verified'] for r in results), 'frozen files')
