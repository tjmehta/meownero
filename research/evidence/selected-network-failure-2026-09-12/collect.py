"""One-shot read-only collection of the inherited failed selected-profile run."""
import json
from pathlib import Path
import runpy
import shutil
import xml.etree.ElementTree as ET

out = Path('/out')
base = Path('/selected')
run = base / 'selected-9-90'
m = runpy.run_path('/harness/clean15-provenance.py')
assert (base / 'driver.exit').read_text().strip() == '1'
assert (run / 'build.exit').read_text().strip() == '1'
assert not (run / 'result.json').exists()
assert not (base / 'fallback-12-120').exists()
assert not (run / 'p2p').exists()
for name in ('first', 'second'):
    m['verify_run'](Path('/historical/reproduction') / name, Path('/receipts') / name)
frozen = Path('/historical/frozen-inputs-15')
assert m['digest'](frozen / 'SHA256SUMS') == m['FROZEN']
m['verify_manifest'](frozen, m['read_manifest'](frozen / 'SHA256SUMS'))
for name in ('driver.sh', 'driver.pid', 'driver.log', 'driver.exit', 'phase.txt'):
    shutil.copyfile(base / name, out / name)
raw = out / 'selected-9-90'
raw.mkdir()
for path in sorted(run.iterdir()):
    if path.is_file():
        shutil.copyfile(path, raw / path.name)
results = {}
for name in ('consensus', 'difficulty', 'floor', 'full-native'):
    root = ET.parse(run / (name + '.xml')).getroot()
    results[name] = dict(root.attrib)
    results[name]['failed_tests'] = [
        {'name': suite.get('name') + '.' + test.get('name'),
         'assertions': [failure.text for failure in test.findall('failure')]}
        for suite in root for test in suite if test.findall('failure')]
assert results['full-native']['tests'] == '1237'
assert results['full-native']['failures'] == '7'
src = run / 'source'
artifacts = [src / 'build/release/bin' / name for name in
             ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')]
artifacts += [src / 'build/release/tests/unit_tests' / name for name in
              ('unit_tests', 'meow_difficulty_floor_tests')]
summary = {
    'status': 'FAIL_SELECTED_NATIVE_TESTS',
    'profile': 'selected-9-90',
    'compilation_targets_completed': True,
    'build_and_test_pipeline_exit': 1,
    'tests': results,
    'post_failure_binary_sha256': {str(p.relative_to(src)): m['digest'](p) for p in artifacts},
    'both_historical_source_build_inventories_preserved': True,
    'frozen_inputs_preserved': True,
    'p2p_run': False,
    'fallback_run': False,
    'limits': ['No test reruns or new exclusions; original failure retained.',
               'Post-failure hashes are not a passing build receipt.',
               'Incremental disposable build, not selected clean reproduction.',
               'No capacity normalization, FCMP, or launch-readiness claim.'],
}
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
(out / 'SHA256SUMS').write_text(''.join(
    f'{m["digest"](p)}  {p.relative_to(out)}\n'
    for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'))
print(json.dumps(summary, indent=2))
