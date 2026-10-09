#!/usr/bin/env python3
"""Instrument the unchanged short native gates without recording wallet secrets."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    gate = sys.argv[1]
    if gate == 'p2p':
        module = load('tester_p2p', '/harness/daemon-p2p.py')
        p2p = module
    elif gate == 'restore':
        module = load('tester_restore', '/harness/daemon-restore.py')
        p2p = module.p2p
    else:
        raise RuntimeError('unknown native gate')
    original_start, original_request = p2p.start, p2p.request
    processes = []
    rpc_lock = threading.Lock()
    # Colima shared folders cannot chmod Unix sockets. Reuse the accepted soak's
    # container-private tmpfs socket location; native Levin/scenario logic is unchanged.
    original_bridge = p2p.Bridge

    class ContainerBridge(original_bridge):
        def __init__(self):
            super().__init__()
            self.socket = Path('/run/vanguard/p2p.sock')

    p2p.Bridge = ContainerBridge

    def start(name, argv):
        original_start(name, argv)
        proc = p2p.PROCS[name]
        # Actual executable mapped by the running kernel process, not a receipt claim.
        path = Path(f'/proc/{proc.pid}/exe')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        processes.append({'name': name, 'pid': proc.pid, 'binary': Path(argv[0]).name, 'sha256': digest})
        (p2p.PUBLIC / 'process-hashes.json').write_text(json.dumps(processes, indent=2) + '\n')

    def request(port, path, body):
        response = original_request(port, path, body)
        # Capture native daemon observations and seed-free wallet methods only.
        method = body.get('method', path)
        allowed_wallet = {'transfer', 'get_address', 'get_balance', 'incoming_transfers',
                          'get_transfers', 'refresh', 'rescan_blockchain', 'restore_deterministic_wallet'}
        if port in (19081, 19181) or method in allowed_wallet:
            # A transfer may return an empty tx_key even when it was not requested.
            # Keep only public wallet result fields; node responses are native public data.
            public_response = response
            if port not in (19081, 19181) and 'result' in response:
                fields = {'tx_hash', 'tx_blob', 'amount', 'fee', 'spent_key_images',
                          'address', 'addresses', 'balance', 'unlocked_balance', 'transfers',
                          'in', 'out', 'pending', 'pool', 'failed', 'blocks_fetched',
                          'received_money', 'height', 'version', 'multisig_import_needed',
                          'per_subaddress', 'time_to_unlock', 'blocks_to_unlock'}
                public_response = {**response, 'result': {k: v for k, v in response['result'].items() if k in fields}}
            public_request = body
            if method == 'restore_deterministic_wallet':
                public_request = {**body, 'params': {k: v for k, v in body.get('params', {}).items()
                                                   if k in {'restore_height', 'filename', 'autosave_current'}}}
            row = {'port': port, 'path': path, 'method': method, 'request': public_request, 'response': public_response}
            with rpc_lock:
                with (p2p.PUBLIC / 'rpc-observations.jsonl').open('a') as stream:
                    stream.write(json.dumps(row, sort_keys=True) + '\n')
        return response

    p2p.start, p2p.request = start, request
    asyncio.run(module.main())


if __name__ == '__main__':
    main()
