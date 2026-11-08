"""Owned tiny real compiler failure and static private-safe diagnostic cases."""
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'vanguard'))
def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), root / 'vanguard' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
builder = load('portable-build.py')
controller = load('run-portable-linux-ci.py')
cases = []
with tempfile.TemporaryDirectory(prefix='tjs1882-linux23-diagnostic-') as tmp:
    base = Path(tmp)
    compiler = shutil.which('g++')
    assert compiler
    work = base / 'actual-compiler'
    work.mkdir(mode=0o700)
    source = work / 'PRIVATE_SOURCE_SENTINEL.cpp'
    source.write_text('int main(){return MEOWNERO_UNDECLARED_DIAGNOSTIC_FIXTURE;}\n')
    (work / 'build.phase').write_text('COMPILE\n')
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))
    with (work / 'build.log').open('wb') as stream:
        result = subprocess.run([compiler, '-fsyntax-only', str(source)], stdout=stream,
                                stderr=subprocess.STDOUT, timeout=5, preexec_fn=limits)
    assert result.returncode != 0
    diagnostic = builder.build_diagnostics(work)
    assert diagnostic['phase'] == 'COMPILE' and diagnostic['reason'] == 'COMPILER_ERROR_RECORDED'
    assert 'PRIVATE_SOURCE_SENTINEL' not in json.dumps(diagnostic)
    cases.append({'case': 'actual-owned-compiler-failure', 'exit': result.returncode,
                  'bounds': {'seconds': 5, 'address_space_bytes': 256 * 1024**2}, 'diagnostic': diagnostic})
    for number, (text, reason) in enumerate([
        ('fatal error: Killed signal terminated program cc1plus', 'COMPILER_PROCESS_KILLED'),
        ('internal compiler error: Segmentation fault', 'COMPILER_INTERNAL_SEGMENTATION_FAILURE'),
        ("error: 'nothrow' is not a member of 'std'", 'STD_NOTHROW_DECLARATION_MISSING'),
        ("error: use of undeclared identifier 'posix_memalign'", 'POSIX_MEMALIGN_DECLARATION_MISSING'),
        ('fatal error: PRIVATE_PATH: No space left on device', 'COMPILER_DISK_FULL'),
        ('PRIVATE_EXCEPTION_SENTINEL', 'BUILD_FAILURE_UNCLASSIFIED')]):
        work = base / str(number)
        work.mkdir(mode=0o700)
        (work / 'build.phase').write_text('DEPENDENCIES\n')
        (work / 'build.log').write_text('PRIVATE_SOURCE_SENTINEL\n' + text + '\n')
        (work / 'build.memory').write_text('12345678\n')
        (work / 'build.memory-events').write_text('oom 0\noom_kill 0\nPRIVATE_KEY 42\n')
        diagnostic = builder.build_diagnostics(work)
        assert diagnostic['reason'] == reason and diagnostic['peak_memory_bytes'] == 12345678
        assert not diagnostic['cgroup_oom_kill_observed'] and 'PRIVATE' not in json.dumps(diagnostic)
        cases.append({'case': reason, 'fixture': 'STATIC_CLASSIFIER_INPUT_NOT_NATIVE_BUILD', 'diagnostic': diagnostic})
    (work / 'build.log').unlink()
    (work / 'build.log').symlink_to(source)
    (work / 'build.memory-events').write_text('oom_kill 1\n')
    diagnostic = builder.build_diagnostics(work)
    assert diagnostic['reason'] == 'BUILD_FAILURE_UNCLASSIFIED' and diagnostic['cgroup_oom_kill_observed']
    cases.append({'case': 'symlink-refused-oom-fact-not-cause-inference', 'diagnostic': diagnostic})
    value = {'schema': 'meownero-portable-build/1', 'result': 'FAILED_ATTEMPT',
             'failure': 'PRIVATE_WALLET_KEY_SENTINEL', 'failure_type': 'PRIVATE_EXCEPTION',
             'commands': [{'label': 'build', 'argv': ['PRIVATE_PATH_SENTINEL'], 'exit': 2}],
             'build_diagnostic': {**diagnostic, 'private_extra': 'PRIVATE_WALLET_KEY_SENTINEL'}}
    projected = controller.public_worker_receipt(value)
    assert 'PRIVATE' not in json.dumps(projected) and 'argv' not in json.dumps(projected)
    assert projected['failure_type'] == 'OTHER_EXCEPTION'
    cases.append({'case': 'public-worker-projection-private-text-exclusion', 'result': 'PASS'})
result = {'schema': 'meownero-linux23-build-diagnostic-source-fixtures/1',
          'result': 'PASS_REAL_TINY_COMPILER_FAILURE_STATIC_REASON_RESOURCE_PRIVACY',
          'source_sha256': {name: hashlib.sha256((root / 'vanguard' / name).read_bytes()).hexdigest()
                            for name in ('portable-build.py', 'run-portable-linux-ci.py')},
          'cases': cases, 'actual_Linux08_failure_reason': 'UNKNOWN',
          'native_Ubuntu22_or_ARM_production_build': 'UNTESTED_BY_FIXTURES'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
