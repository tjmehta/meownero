"""Adverse source observations only; all command effects are injected."""
import json
import os
import time
from unittest.mock import patch
from test_supervisor import SupervisorTests
from profile_constructor import AuthorityClient
import profile_manager as m


def snapshot(case):
    m.send_packet(case.channel, dict(operation='snapshot'))
    return m.receive_packet(case.channel, case.server_credentials, 200, clock=lambda:100)[0]


def closed(case):
    until=time.monotonic()+3
    while time.monotonic()<until:
        result=snapshot(case)
        if result['entries_closed']:return result
        time.sleep(.01)
    return result


def cleanup_repeat(later=False):
    case=SupervisorTests();case.itinerary=[44,45];case.setUp()
    try:
        case.start();before=case.snapshot_local()
        marker=case.fixture.root/'markers'
        def effect(*args):
            with marker.open('ab') as stream:stream.write(b'effect\n')
            os._exit(9)
        if later:
            def settled(*args):
                with marker.open('ab') as stream:stream.write(b'settled44\n')
            case.fixture.backend.docker.side_effect=settled
            assert case.issue(44,recovered=True)==0
            case.fixture.backend.syscall.side_effect=effect
            first=case.issue(45,recovered=True)
        else:
            case.fixture.backend.docker.side_effect=effect
            first=case.issue(44,recovered=True)
        state=closed(case)
        case.restore_local(before)
        second=case.issue(44,recovered=True)
        return dict(first=first,second=second,markers=marker.read_text().splitlines(),snapshot=state)
    finally:case.doCleanups()


def post_close():
    case=SupervisorTests();case.setUp()
    try:
        case.start();original=AuthorityClient.call
        def crash(self,operation):
            result=original(self,operation)
            if operation=='close':os._exit(9)
            return result
        with patch.object(AuthorityClient,'call',crash):first=case.issue()
        return dict(first=first,snapshot=snapshot(case),cleanup=case.issue(44,recovered=True))
    finally:case.doCleanups()


print(json.dumps(dict(uncertain44=cleanup_repeat(),settled44_uncertain45=cleanup_repeat(True),
    post_close=post_close(),installed='NOT_RUN'),indent=2))
