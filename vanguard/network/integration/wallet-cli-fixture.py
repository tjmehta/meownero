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
BACKGROUND = ('The daemon is not set up to background mine.\n'
    'With background mining enabled, the daemon will mine when idle and not on battery.\n'
    'Enabling this supports the network you are using, and makes you eligible for receiving new monero\n'
    'Do you want to do it now? [y/N]: ')


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
    readline = mode.startswith('readline-')
    if readline:
        mode = mode.removeprefix('readline-')
    if mode == 'early-exit':
        return 23
    create = 'generate-new-wallet' in values
    expected = ['set refresh-from-block-height 0', 'set', 'address new', 'refresh 0', 'save', 'exit'] if create else ['set', 'exit']

    def emit(text):
        if readline:
            # console_handler.h markers + readline_buffer.cpp blank/real redisplay.
            sys.stdout.write('\x1b]0;fixture title\x07\x1b[?2004h\r\x01\x1b[1;33m\x02')
            sys.stdout.flush(); time.sleep(.004)
            text = '\r\x1b]0;fixture title\x1b\\\x01\x1b[1;33m\x02'+text.replace(
                '123ABC', '123ABZ\bC')+'\x01\x1b[0m\x02\x1b[?2004l'
        # Deliberately split prompt tokens, as a PTY may do.
        for part in (text[:4], text[4:]):
            sys.stdout.write(part); sys.stdout.flush(); time.sleep(.002)

    def background(text=BACKGROUND):
        emit(text)
        if sys.stdin.readline().rstrip('\n') != 'n':
            raise SystemExit(30)
        with Path(values['log-file']).with_name('background-refused.fixture').open('a') as record:
            record.write('n\n')

    if mode in ('background-mining', 'background-repeated', 'background-altered'):
        background(BACKGROUND.replace('The daemon', 'Another daemon') if mode=='background-altered' else BACKGROUND)
        if mode=='background-repeated':
            background()
    if mode == 'skeleton-failure':
        emit('abbey abducts ability\n'+Path(values['password-file']).read_text()+
             'Q' * 95+'\n'+'0123456789abcdef' * 4+'\n'+
             'abbey\rready\nabbey\bx\naces\x00acidic\n[wallet 123ABC]: \x1b[?2004h\n')
        emit('Is this okay? [y/N]: ')
        sys.stdin.readline()
        return 31
    if mode == 'altered-wallet':
        emit('[wallet 123ABC altered]: ')
        sys.stdin.readline()
        return 32
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
        if mode=='background-during-command':
            background()
        emit(PROMPT)
    return 29


if __name__ == '__main__':
    raise SystemExit(main())
