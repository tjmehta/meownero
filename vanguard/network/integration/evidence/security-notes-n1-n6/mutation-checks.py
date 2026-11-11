"""Focused mutations in memory, run only through guarded-source-tests.py --mutations."""
import contextlib
import hashlib
import inspect
import io
import json
from pathlib import Path
import textwrap
import unittest
from unittest import mock

from integration import test_operator as tests

HERE = Path(__file__).resolve().parent
PREFIX = 'integration.test_operator.'
CASES = [
    ('N1-updates-gate-removed', tests.o, 'check_public_seed',
     "    _require(values['--check-updates'] == 'disabled', 'public seed updates must be disabled')\n", '',
     'PublicSeedShape.test_updates_must_be_explicitly_disabled'),
    ('N5-proxy-handler-removed', tests.om, 'follower_info', 'urllib.request.ProxyHandler({}),', '',
     'OutsideMonitor.test_follower_ignores_environment_http_proxy'),
    ('N5-finite-timestamp-check-removed', tests.om, 'check_status', " and math.isfinite(status['unix'])", '',
     'OutsideMonitor.test_nonfinite_status_timestamp_is_unverified_even_when_tips_agree'),
    ('N6-nofollow-removed', tests.m, 'read_relayed', ' | os.O_NOFOLLOW', '',
     'OperatorManager.test_relay_refuses_symlink_to_valid_owner_only_file'),
    ('N6-pin-change-check-removed', tests.od.Operator, 'open_public',
     "    c.require(self.pins['S'] != before, 'seed certificate did not change')\n", '',
     'OperatorManager.test_public_reopen_refuses_reused_pin_before_publishing'),
]


def run_test(name, logfile):
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromName(PREFIX+name)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    logfile.write_text(stream.getvalue())
    logfile.chmod(0o600)
    return dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                skipped=len(result.skipped))


paths = [Path(inspect.getfile(getattr(owner, name))) for _, owner, name, *_ in CASES]
hashes = lambda: {str(p.relative_to(Path.cwd())): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before = hashes()
rows = []
for label, owner, name, old, new, test in CASES:
    control = run_test(test, HERE/(label+'-control.log'))
    assert control == dict(tests=1, failures=0, errors=0, skipped=0), (label, control)
    function = getattr(owner, name)
    source = textwrap.dedent(inspect.getsource(function))
    assert source.count(old) == 1, (label, 'mutation does not match exactly once')
    namespace = dict(function.__globals__)
    if label.startswith('N1'):
        # Revert both halves of the requirement: presence and disabled-only value.
        namespace['PUBLIC_REQUIRED'] = tuple(n for n in tests.o.PUBLIC_REQUIRED if n != '--check-updates')
    changed = source.replace(old, new, 1)
    exec(compile(changed, '<'+label+'>', 'exec'), namespace)
    with mock.patch.object(owner, name, namespace[name]):
        mutant = run_test(test, HERE/(label+'-mutant.log'))
    assert mutant['tests'] == 1 and not mutant['skipped'] and mutant['failures']+mutant['errors'] > 0, (label, mutant)
    rows.append(dict(mutation=label, test=PREFIX+test, control=control, mutant=mutant, result='DETECTED',
                     removed=old.strip(), replacement=new))
assert hashes() == before, 'mutation altered an on-disk source'
summary = dict(result='PASS_MUTATION_SENSITIVITY_ONLY', cases=rows, source_sha256=before,
               source_bytes_unchanged=True, native='NOT_RUN',
               qualification='In-memory faults prove regression sensitivity; no runtime source was rewritten.')
(HERE/'mutations.json').write_text(json.dumps(summary, indent=2)+'\n')
(HERE/'mutations.json').chmod(0o600)
print(json.dumps(summary))
