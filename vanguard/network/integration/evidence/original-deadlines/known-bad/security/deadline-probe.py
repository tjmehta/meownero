"""Disposable connected source probe; all privileged effects remain injected."""
import json
import multiprocessing
from pathlib import Path
import sys
import types
from unittest.mock import patch

REPOSITORY = Path('<repo>/.paperclip/worktrees/TJS-2504-meownero-isolated-shared-testnet-profile-and-bootstrap-launch-candidate')
sys.path.insert(0, str(REPOSITORY / 'vanguard/network'))
import profile_constructor as constructor
import profile_packet as packet
import test_lifecycle_source
import test_supervisor


def exercise(duration):
    now = multiprocessing.Value('d', 100)
    original = constructor.SurvivingAuthority
    case = test_supervisor.SupervisorTests()
    case.itinerary = [25, 44]  # Valid activation route plus its required cleanup route.
    case.setUp()
    fixture = case.fixture
    fixture.backend.authenticate_executor = lambda unused: test_lifecycle_source.bindings(fixture.plan)
    fixture.backend.execution_context = lambda record, exact, deadline: dict(
        env={'LC_ALL': 'C'}, cwd='/fixture/W', pass_fds=[],
        uid=record['uid'], gid=record['gid'], extra_groups=[])
    effect_path = fixture.root / 'probe-effects'

    def effect(*args, **kwargs):
        with effect_path.open('ab') as stream:
            stream.write(b'effect\n')
        now.value = 100 + duration
        return types.SimpleNamespace(returncode=0)

    def authority(*args, **kwargs):
        kwargs['clock'] = lambda: now.value
        return original(*args, **kwargs)

    case.command_effect = effect
    original_entry = constructor.OperatorConstructor.run_authenticated_inherited_entry

    def observed_entry(entry):
        try:
            return original_entry(entry)
        except Exception as error:
            with Path(__file__).with_name('probe-entry-errors.log').open('a') as stream:
                stream.write(type(error).__name__ + ': ' + str(error) + '\n')
            raise

    try:
        with patch.object(constructor, 'SurvivingAuthority', side_effect=authority):
            case.start()
        with patch.object(constructor.OperatorConstructor, 'run_authenticated_inherited_entry', observed_entry):
            status = case.issue(25)
        state = case.wait_closed()['state']
        result = dict(modeled_duration=duration, exit_status=status,
                      effects=effect_path.read_bytes().count(b'effect\n'),
                      mode=state['mode'], disposition=state['dispositions']['25'],
                      original_deadlines=state['binding']['record_binding']['deadlines'])
        assert result['effects'] == 1
        assert status == (0 if duration == 29 else 3)
        assert state['mode'] == ('LIVE' if duration == 29 else 'RECOVERY_ONLY')
        return result
    finally:
        case.doCleanups()
        assert not fixture.root.exists(), 'owned fixture scratch must be removed'


results = [exercise(29), exercise(31)]
plan = test_lifecycle_source.p.source_plan()
plan['attempt_id'] = '1' * 32
properties = {name: value for name, kind, value in packet.receiver_unit(plan, 25, 17)['args'][2]}
output = dict(source_only=True, privileged_effects='INJECTED', tests=results,
              receiver_runtime_max_usec=properties['RuntimeMaxUSec'],
              conclusion='producer request deadline also caps a valid longer phase at 30 seconds')
Path(__file__).with_suffix('.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps(output, indent=2))
