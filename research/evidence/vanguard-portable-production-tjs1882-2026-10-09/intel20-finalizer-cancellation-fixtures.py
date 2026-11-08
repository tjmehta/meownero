"""Deliver real repeated TERM/INT inside source-bound lock/receipt finalizers."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile

root = Path(__file__).resolve().parents[3]
source = root / 'build/tjs1882-3175-intel20-supervisor.py'
spec = importlib.util.spec_from_file_location('ci14', source)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
main = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
lock_body = next(n.finalbody for n in ast.walk(main) if isinstance(n, ast.Try) and
                 any(isinstance(q, ast.Call) and getattr(q.func, 'attr', None) == 'unlink'
                     for q in ast.walk(ast.Module(body=n.finalbody, type_ignores=[]))))
receipt_body = next(n.finalbody for n in main.body if isinstance(n, ast.Try) and n.finalbody)
cases = []
with tempfile.TemporaryDirectory(prefix='tjs1882-intel20-finalizer-') as tmp:
    for case in ('verified-lock', 'identity-refused-lock', 'public-receipts'):
        out = Path(tmp) / case
        out.mkdir(mode=0o700)
        public = out / 'public'
        public.mkdir(mode=0o700)
        callbacks = []

        def cancelled(number, frame):
            callbacks.append(int(number))
            if len(callbacks) == 1:
                raise RuntimeError('fixture caller cancellation')

        saved = {n: signal.signal(n, cancelled) for n in (signal.SIGTERM, signal.SIGINT)}
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        delivered = []

        def repeated_cancel():
            if not delivered:
                delivered.append(True)
                assert {signal.SIGTERM, signal.SIGINT} <= signal.pthread_sigmask(signal.SIG_BLOCK, set())
                for number in (signal.SIGTERM, signal.SIGINT, signal.SIGTERM, signal.SIGINT):
                    os.kill(os.getpid(), number)

        proof = {'result': 'FAIL', 'failure_type': 'FIXTURE_CANCELLATION'}
        lock = out / 'owned.lock'
        lock.touch(mode=0o600)
        supervision = {'wrapper_reaped': True, 'cleanup': [{'pid': os.getpid(), 'removed': True}],
                       'rejected_observation_cleanup': []}
        ci.write(public / 'supervision.json', supervision)

        class ReceiptPath:
            def __init__(self, path):
                self.path = path

            def read_text(self):
                repeated_cancel()
                return self.path.read_text()

        class PublicPaths:
            def __truediv__(self, name):
                return ReceiptPath(public / name)

        def write(path, value):
            repeated_cancel()
            ci.write(path, value)

        namespace = dict(json=json, signal=signal, os=os, lock=lock, proof=proof,
                         lock_identity=lock.stat().st_ino + int(case == 'identity-refused-lock'),
                         public=PublicPaths() if case != 'public-receipts' else public,
                         check_root=None, write=write)
        try:
            body = receipt_body if case == 'public-receipts' else lock_body
            try:
                exec(compile(ast.Module(body=body, type_ignores=[]), str(source), 'exec'), namespace)
            except RuntimeError:
                pass
            assert delivered and callbacks
            assert all(signal.getsignal(n) is cancelled for n in saved)
            assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == mask
            if case == 'verified-lock':
                assert not lock.exists() and proof['owned_lock_removed']
            elif case == 'identity-refused-lock':
                assert lock.exists() and 'owned_lock_removed' not in proof
            else:
                assert json.loads((public / 'ci-receipt.json').read_text()) == proof
            cases.append({'case': case, 'actual_repeated_TERM_INT': True,
                          'protected_finalizer_completed': True,
                          'identity_failure_preserves_lock': case == 'identity-refused-lock' and lock.exists(),
                          'original_caller_handlers_and_mask_restored': True})
        finally:
            # Keep the fixture owner alive while draining any second pending signal.
            signal.pthread_sigmask(signal.SIG_BLOCK, set(saved))
            for number in saved:
                signal.signal(number, lambda number, frame: None)
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            for number, handler in saved.items():
                signal.signal(number, handler)
result = {'schema': 'meownero-intel20-finalizer-repeated-cancel-fixtures/1',
          'result': 'PASS_REAL_CANCEL_LOCK_RECEIPT_PROTECTION_AND_RESTORATION',
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'cases': cases,
          'native_journeys': 'UNTESTED_BY_FIXTURES'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
