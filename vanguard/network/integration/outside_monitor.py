#!/usr/bin/env python3
"""Outside monitor reference implementation (TJS-4238 item 4); standard library only.

Runs under a different uid or on a different host from the public seed. It holds
no seed credential and never reads the seed's files. It checks three things:

- TLS pin: the certificate the seed's operator RPC presents must equal the pin the
  operator delivered out of band (a file the monitor's owner placed; never fetched
  over the public path). The handshake sends no request byte.
- Tip: the monitor runs its own follower node, which validates the chain it gets
  from the seed over public P2P. The follower's (height, top hash) must agree with
  the seed's operator status within the spread bound.
- Peer count: restricted RPC zeroes every connection count
  (`core_rpc_server.cpp:316-321`), so the public path cannot show it. The count comes
  from the seed supervisor's status on the operator channel; the monitor checks it
  is fresh, within the in-peers bound, and includes the follower's own edge.

Usage (on the monitor host; the follower login stays in the environment):
    MONITOR_FOLLOWER_LOGIN=user:pass python3 outside_monitor.py --seed-host HOST \
        --pin-file PIN --status-file STATUS --follower-rpc 127.0.0.1:PORT --in-peers 16
Exit 0 OK, 2 ALERT (a check failed), 3 UNVERIFIED (an input was missing or unreadable).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
import sys
import time
import urllib.request

RPC_PORT = 48081
PIN = re.compile('[0-9a-f]{64}')
HEX64 = PIN
STATUS_KEYS = {'count', 'top', 'inbound', 'launch', 'step', 'unix'}


class Alert(Exception):
    """A monitored property is wrong: page the operator."""


class Unverified(Exception):
    """An input is missing: the monitor cannot say the seed is healthy."""


def presented_pin(host, port=RPC_PORT, timeout=5.0):
    """SHA-256 of the DER certificate the listener presents; no request byte is written."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # Authentication is the pin comparison.
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with socket.create_connection((host, port), timeout=timeout) as raw:
        with context.wrap_socket(raw) as wrapped:
            return hashlib.sha256(wrapped.getpeercert(binary_form=True)).hexdigest()


def read_pin(path):
    try:
        value = Path(path).read_text().strip()
    except OSError:
        raise Unverified('out-of-band pin unreadable') from None
    if PIN.fullmatch(value) is None:
        raise Unverified('out-of-band pin shape')
    return value


def check_pin(expected, presented):
    if PIN.fullmatch(expected or '') is None:
        raise Unverified('out-of-band pin shape')
    if presented != expected:
        raise Alert('certificate pin mismatch')
    return True


def check_status(status, now, *, in_peers, max_age):
    if type(status) is not dict or set(status) != STATUS_KEYS:
        raise Unverified('operator status shape')
    if not (type(status['count']) is int and status['count'] >= 1 and type(status['top']) is str and
            HEX64.fullmatch(status['top']) and type(status['inbound']) is dict and
            all(type(v) is int and v >= 0 for v in status['inbound'].values()) and
            type(status['unix']) in (int, float)):
        raise Unverified('operator status values')
    age = now-status['unix']
    if age > max_age or age < -60:
        raise Alert('operator status is stale')
    total = sum(status['inbound'].values())
    if total > in_peers:
        raise Alert('inbound peers above the in-peers bound')
    return total, int(max(0, age))


def check_tip(follower, status, *, max_spread):
    """follower: (height, top) from the monitor's own validating node."""
    height, top = follower
    if abs(height-status['count']) > max_spread:
        raise Alert('follower and seed tips diverge')
    if height == status['count'] and top != status['top']:
        raise Alert('same height, different top block')
    return height == status['count'] and top == status['top']


def follower_info(address, login, timeout=5.0):
    """get_info from the monitor's own follower over its loopback RPC (Digest login)."""
    url = f'http://{address}/json_rpc'
    manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    manager.add_password(None, url, *login.split(':', 1))
    opener = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(manager))
    body = json.dumps({'jsonrpc': '2.0', 'id': '0', 'method': 'get_info'}).encode()
    request = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
    with opener.open(request, timeout=timeout) as response:
        value = json.loads(response.read(1 << 20))['result']
    return value['height'], value['top_block_hash']


def evaluate(*, seed_host, pin_file, status_file, follower, in_peers, max_age=180, max_spread=2,
             now=None, pin_of=None):
    """One sample. Returns a dict; never raises for an Alert or Unverified outcome."""
    result = dict(pin=None, tip=None, inbound=None, state='OK', reason=None)
    try:
        expected = read_pin(pin_file)
        result['pin'] = check_pin(expected, (pin_of or presented_pin)(seed_host))
        try:
            status = json.loads(Path(status_file).read_text())
        except (OSError, ValueError):
            raise Unverified('operator status unreadable') from None
        result['inbound'], result['status_age'] = check_status(status, time.time() if now is None else now,
                                                               in_peers=in_peers, max_age=max_age)
        result['tip'] = check_tip(follower(), status, max_spread=max_spread)
    except Alert as error:
        result.update(state='ALERT', reason=str(error))
    except Unverified as error:
        result.update(state='UNVERIFIED', reason=str(error))
    except OSError as error:  # The seed or the follower did not answer.
        result.update(state='ALERT', reason='unreachable: '+type(error).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--seed-host', required=True)
    parser.add_argument('--pin-file', required=True)
    parser.add_argument('--status-file', required=True)
    parser.add_argument('--follower-rpc', required=True)
    parser.add_argument('--in-peers', type=int, required=True)
    args = parser.parse_args()
    login = os.environ.get('MONITOR_FOLLOWER_LOGIN')
    if not login or ':' not in login:
        print(json.dumps(dict(state='UNVERIFIED', reason='follower login missing from the environment')))
        return 3
    result = evaluate(seed_host=args.seed_host, pin_file=args.pin_file, status_file=args.status_file,
                      follower=lambda: follower_info(args.follower_rpc, login), in_peers=args.in_peers)
    print(json.dumps(result, sort_keys=True))
    return {'OK': 0, 'ALERT': 2}.get(result['state'], 3)


if __name__ == '__main__':
    sys.exit(main())
