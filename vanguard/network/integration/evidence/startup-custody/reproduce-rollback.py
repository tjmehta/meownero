"""Run from vanguard/network. Exit 1 records the unmet rollback criterion."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import test_constructor

case = test_constructor.ConstructorTests()
case.setUp()
try:
    fixture = case.fixture
    paths = [fixture.order, *[fixture.control / name for name in fixture.identities]]
    before = {path: (path.read_bytes(), (path.stat().st_dev, path.stat().st_ino)) for path in paths}
    crash = case.invoke(fresh=True, crash=True)
    pending = fixture.state()['pending']
    for path, (raw, identity) in before.items():
        path.write_bytes(raw)
        assert (path.stat().st_dev, path.stat().st_ino) == identity
    replay = case.invoke(fresh=True)
    print(json.dumps(dict(child_exit=crash, pending_before_rollback=pending,
        original_same_inode_state_restored=True, fresh_fixture_authorized_entry_exit=replay,
        result='REQUIRED_ROLLBACK_ACCEPTANCE_NOT_MET' if replay == 0 else 'REFUSED')))
    assert crash == 9 and pending == 0
    sys.exit(1 if replay == 0 else 0)
finally:
    case.doCleanups()
