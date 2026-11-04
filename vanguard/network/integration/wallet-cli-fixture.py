#!/usr/bin/env python3
"""Disposable source fixture, never a wallet. Strings bind pinned e151643c.

Only options used by the audited driver are modeled. Like wallet_args.cpp:167,
unknown config keys refuse before log setup. No native binary/data is accessed.
"""
import os
from pathlib import Path
import sys
import time

COMMON = {'testnet', 'config-file', 'password-file', 'daemon-address', 'log-file'}
CLI = COMMON | {'generate-new-wallet', 'mnemonic-language', 'wallet-file'}
RPC = COMMON | {'wallet-file', 'rpc-bind-ip', 'rpc-bind-port', 'rpc-ssl', 'restricted-rpc'}
CONFIG = {'daemon-login', 'daemon-ssl'}
PROMPT = '[wallet 123ABC]: '
PASSWORD = 'Wallet password: '


def main():
    args = iter(sys.argv[1:]); values = {}
    for arg in args:
        if not arg.startswith('--') or arg[2:] not in CLI:
            return 1
        key = arg[2:]
        values[key] = True if key == 'testnet' else next(args)
    for line in Path(values['config-file']).read_text().splitlines():
        key, value = line.split('=', 1)
        if key not in CONFIG:
            return 1
        if key == 'daemon-ssl' and value != 'disabled':
            return 1
    Path(values['log-file']).write_text('FIXTURE_OPTIONS_ACCEPTED\n')
    mode = os.environ.get('WALLET_CLI_FIXTURE_MODE', 'normal')
    if mode == 'early-exit':
        return 23
    create = 'generate-new-wallet' in values
    expected = ['set refresh-from-block-height 0', 'set', 'address new', 'refresh 0', 'save', 'exit'] if create else ['set', 'exit']

    def emit(text):
        # Deliberately split prompt tokens, as a PTY may do.
        for part in (text[:4], text[4:]):
            sys.stdout.write(part); sys.stdout.flush(); time.sleep(.002)

    emit(PROMPT if mode != 'out-of-sync' else '[wallet 123ABC (out of sync)]: ')
    for command in expected:
        if sys.stdin.readline().rstrip('\n') != command:
            return 24
        if mode == 'command-exit':
            return 25
        if command == 'exit':
            return 0
        if command == 'set refresh-from-block-height 0':
            emit(PASSWORD if mode != 'unknown-password' else 'Enter password (unexpected): ')
            if sys.stdin.readline().rstrip('\n') != Path(values['password-file']).read_text().strip():
                return 26
            if mode == 'repeated-password':
                emit(PASSWORD)
                sys.stdin.readline()
                return 27
        if command == 'set':
            emit('refresh-from-block-height = 0\n')
        if mode == 'confirmation':
            emit('Is this okay? [y/N]: ')
            sys.stdin.readline()
            return 28
        emit(PROMPT)
    return 29


if __name__ == '__main__':
    raise SystemExit(main())
