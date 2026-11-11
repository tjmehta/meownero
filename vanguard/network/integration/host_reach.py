#!/usr/bin/env python3
"""Read-only host-namespace reach probe (TJS-4238 item 5, Security note 1).

Run as the host owner in the host network namespace, with no root:
    python3 host_reach.py 10.231.77.2 48080 48081
For each port it opens one TCP connection, sends no byte, optionally holds it for
--hold seconds (so the seed's own socket census can witness the edge) and closes
it. It prints one JSON object. "connected" means a host-originated connection
reaches the seed's listener: the host namespace is inside the same-uid boundary,
not outside it, and a public firewall rule must bind the listener's interface.
"""
import argparse
import errno
import json
import socket
import time

OUTCOMES = ('connected', 'refused', 'unreachable', 'timeout')


def probe(host, port, *, timeout=3.0, hold=0.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        code = sock.connect_ex((host, port))
        if code == 0:
            if hold:
                time.sleep(hold)
            return 'connected'
        if code == errno.ECONNREFUSED:
            return 'refused'
        if code in (errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EHOSTDOWN):
            return 'unreachable'
        return 'timeout'  # EAGAIN/ETIMEDOUT/EINPROGRESS: no answer inside the timeout.
    except socket.timeout:
        return 'timeout'
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('host')
    parser.add_argument('ports', type=int, nargs='+')
    parser.add_argument('--hold', type=float, default=0.0)
    args = parser.parse_args()
    result = {str(port): probe(args.host, port, hold=args.hold) for port in args.ports}
    print(json.dumps(dict(host=args.host, outcomes=result, bytes_sent=0,
                          same_uid_boundary=any(v == 'connected' for v in result.values()))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
