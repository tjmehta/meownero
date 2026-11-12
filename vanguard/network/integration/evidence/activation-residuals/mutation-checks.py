"""In-memory faults; run through guarded-source-tests.py --mutations only."""
import gzip
import hashlib
import inspect
import io
import json
from pathlib import Path
import textwrap
import unittest
from unittest import mock

from integration import test_operator as tests

HERE = Path(__file__).resolve().parent.parent/'activation-residuals-f3'
HERE.mkdir(exist_ok=True)
PREFIX = 'integration.test_operator.'


def run_test(name, path):
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromName(PREFIX+name))
    path.write_bytes(gzip.compress(stream.getvalue().encode(), mtime=0))
    return dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                skipped=len(result.skipped))


function_cases = [
    ('dial-utc-parsing-removed', tests.o, 'activation_seed_witness',
     '.replace(tzinfo=timezone.utc)', '',
     'ActivationWitness.test_utc_banners_work_in_explicit_non_utc_zones'),
    ('dial-debug-list-exemption-removed', tests.o, 'activation_seed_witness',
     "seed_list=SEED_LIST+(b'Seed node: ', b'Fallback seed node: ')", 'seed_list=SEED_LIST',
     'ActivationWitness.test_info_and_debug_seed_list_loading_are_not_dials'),
    ('dial-upstream-check-removed', tests.o, 'activation_seed_witness',
     'if upstream or maker:', 'if maker:',
     'ActivationWitness.test_upstream_dials_alert_for_each_seed_on_failure_or_success'),
    ('dial-argv-gate-removed', tests.o, 'activation_seed_witness',
     "options = dict(check_public_seed(argv, value, mining=mining))", "options = {'--log-level': '1'}",
     'ActivationWitness.test_connections_maker_gate_and_activity_alert'),
    ('dial-maker-check-removed', tests.o, 'activation_seed_witness',
     'if upstream or maker:', 'if upstream:',
     'ActivationWitness.test_connections_maker_gate_and_activity_alert'),
    ('dial-rehearsal-zero-rule-reused', tests.o, 'activation_seed_witness',
     'if upstream or maker:', 'if upstream or maker or attempted:',
     'ActivationWitness.test_housekeeping_and_ping_back_lines_do_not_alert'),
    ('dial-seed-pass-required-again', tests.o, 'activation_seed_witness',
     "return dict(result, state='OK', reason=None)",
     "return dict(result, state='OK' if passes else 'UNVERIFIED', reason=None)",
     'ActivationWitness.test_restart_without_seed_pass_is_ok'),
    ('dial-info-check-removed', tests.o, 'activation_seed_witness',
     "if options.get('--log-level') not in ('1', '2', '3', '4'):", 'if False:',
     'ActivationWitness.test_warning_only_or_missing_logging_never_reaches_ok'),
    ('dial-earlier-banner-accepted', tests.o, 'activation_seed_witness',
     'if launch_window[0] <= stamp <= launch_window[1]:', 'if stamp <= launch_window[1]:',
     'ActivationWitness.test_old_launch_cannot_supply_current_coverage_or_dials'),
    ('dial-launch-slice-removed', tests.o, 'activation_seed_witness',
     'raw = raw[starts[0]:]', 'raw = raw',
     'ActivationWitness.test_old_launch_cannot_supply_current_coverage_or_dials'),
    ('monitor-overflow-handler-removed', tests.om, 'check_status',
     'except OverflowError:', 'except ZeroDivisionError:',
     'OutsideMonitor.test_out_of_float_range_integer_timestamp_is_unverified_with_cli_exit_3'),
]
rule = tests.o.OBJECT_CLASSES['port-rule']['rule']
backstop = next(line for line in rule.splitlines(True) if 'ct state new ip saddr !=' in line)
template_cases = [
    ('meter-size-removed', 'size 65535', ''),
    ('meter-size-unbounded', 'size 65535', 'size 0'),
    ('meter-key-wrong', '{ ip saddr limit', '{ ip daddr limit'),
    ('backstop-removed', backstop, ''),
    ('backstop-unconditional', 'ip saddr != @seed_sources ', ''),
    ('backstop-tracked-only', 'ip saddr != @seed_sources ', 'ip saddr @seed_sources '),
    ('backstop-wrong-verdict', backstop, backstop.replace('drop;', 'accept;')),
    ('backstop-wrong-order', backstop, ''),
]
paths = [Path(inspect.getfile(tests.o)), Path(inspect.getfile(tests.om)), Path(inspect.getfile(tests))]
hashes = lambda: {str(path.relative_to(Path.cwd())): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in paths}
before, rows = hashes(), []


def record(label, test, old, new, patch):
    control = run_test(test, HERE/(label+'-control.log.gz'))
    assert control == dict(tests=1, failures=0, errors=0, skipped=0), (label, control)
    with patch:
        mutant = run_test(test, HERE/(label+'-mutant.log.gz'))
    assert mutant['tests'] == 1 and not mutant['skipped'] and mutant['failures']+mutant['errors'], (label, mutant)
    rows.append(dict(mutation=label, test=PREFIX+test, control=control, mutant=mutant,
                     result='DETECTED', original=old, replacement=new))


for label, owner, name, old, new, test in function_cases:
    function = getattr(owner, name)
    source = textwrap.dedent(inspect.getsource(function))
    assert source.count(old) == 1, (label, 'fault must match once')
    namespace = dict(function.__globals__)
    exec(compile(source.replace(old, new, 1), '<'+label+'>', 'exec'), namespace)
    record(label, test, old, new, mock.patch.object(owner, name, namespace[name]))

for label, old, new in template_cases:
    assert rule.count(old) == 1, (label, 'fault must match once')
    changed = rule.replace(old, new, 1)
    if label == 'backstop-wrong-order':
        accept = next(line for line in changed.splitlines(True) if 'ct state new accept;' in line)
        changed = changed.replace(accept, accept+backstop, 1)
    record(label, 'PublicSeedShape.test_port_rule_parses_to_only_planned_ports_with_per_source_limits',
           old, new, mock.patch.dict(tests.o.OBJECT_CLASSES['port-rule'], rule=changed))

assert hashes() == before, 'mutation changed on-disk source'
summary = dict(result='PASS_MUTATION_SENSITIVITY_ONLY', cases=rows, source_sha256=before,
               source_bytes_unchanged=True, native='NOT_RUN')
(HERE/'mutations.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary))
