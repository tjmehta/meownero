"""Bounded Docker queries, exact ownership cleanup and terminal receipts."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import signal
import subprocess


def query(*argv, timeout=30):
    return subprocess.check_output(['docker', *argv], text=True, timeout=timeout).strip()


def save(path, receipt):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(receipt, indent=2) + '\n')
    os.replace(temporary, path)


@contextmanager
def cleanup_signals():
    previous = {s: signal.signal(s, signal.SIG_IGN) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for s, handler in previous.items():
            signal.signal(s, handler)


def retry_query(*argv, timeout=30):
    # One bounded retry for a lost CLI response. No unbounded cleanup polling.
    for attempt in range(2):
        try:
            return query(*argv, timeout=timeout)
        except (subprocess.SubprocessError, OSError):
            if attempt:
                raise


def proof(cid, label, invocation, *, name=None, image=None):
    item = json.loads(retry_query('inspect', cid))[0]
    assert re.fullmatch('[0-9a-f]{64}', cid) and item['Id'] == cid
    assert (item['Config'].get('Labels') or {}).get(label) == invocation
    if name is not None:
        assert item['Name'] == '/' + name
    if image is not None:
        assert item['Image'] == image
    return item


def cleanup_container(cid, label, invocation, *, name=None, image=None):
    row = {'cid': cid, 'removed': False, 'identity_verified': False}
    try:
        item = proof(cid, label, invocation, name=name, image=image)
        row.update(identity_verified=True, exit=item['State']['ExitCode'], oom_killed=item['State']['OOMKilled'])
        if item['State']['Running']:
            try:
                query('stop', '--time', '90', cid, timeout=120)
            except (subprocess.SubprocessError, OSError) as error:
                row['stop_failure_type'] = type(error).__name__
        # Revalidate after stopping. Never remove an unverified resource.
        proof(cid, label, invocation, name=name, image=image)
        try:
            query('rm', '-f', cid)
        except (subprocess.SubprocessError, OSError) as error:
            row['remove_failure_type'] = type(error).__name__
        row['removed'] = cid not in retry_query('ps', '-aq', '--no-trunc').splitlines()
    except (Exception, KeyboardInterrupt) as error:
        row['failure_type'] = type(error).__name__
    return row


def cleanup_named(name, image, invocation):
    """Recover a create that Docker accepted before the CLI registered its CID."""
    row = {'name': name, 'removed': False, 'discovery_complete': False}
    try:
        ids = retry_query('ps', '-aq', '--no-trunc', '--filter', 'name=^/' + name + '$').splitlines()
        assert len(ids) <= 1
        row['discovery_complete'] = True
        if not ids:
            row.update(removed=True, absent=True)
        else:
            row.update(cleanup_container(ids[0], 'meownero.invocation', invocation, name=name, image=image))
    except (Exception, KeyboardInterrupt) as error:
        row['failure_type'] = type(error).__name__
    return row


def cleanup_build(invocation, name, image):
    rows = []
    if image is not None:
        rows.append(cleanup_named(name, image, invocation))
    # Legacy builder intermediates are independently discovered and checked.
    # A failed named-resource query must not skip this separate cleanup path.
    try:
        ids = retry_query('ps', '-aq', '--no-trunc', '--filter', 'label=meownero.build-invocation=' + invocation).splitlines()
    except (Exception, KeyboardInterrupt) as error:
        rows.append({'scope': 'legacy-intermediates', 'removed': False, 'failure_type': type(error).__name__})
    else:
        rows.extend(cleanup_container(cid, 'meownero.build-invocation', invocation) for cid in sorted(set(ids)))
    return rows
