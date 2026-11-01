#!/usr/bin/env python3
"""Substitute only the two original write operations into current fixtures."""
import contextlib
import importlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
t = importlib.import_module('test_direct_profile')
r = t.r


def old_marker(staging):
    (staging/'BUILD_COMPLETE').write_text('runtime\n')


def old_publish(root, rows, receipt):
    for name,value in rows.items(): r.n.write_json(root/'public'/name,value)
    r.n.write_json(root/'public/receipt.json',receipt)


results = {}
for name,fn,method in [
    ('marker',old_marker,'test_runtime_marker_symlink_refuses_without_clobber_or_runtime'),
    ('public',old_publish,'test_readonly_public_root_cannot_redirect_finalization')]:
    case = t.Direct(method); case.setUp()
    try:
        with patch.object(r,'runtime_marker' if name == 'marker' else 'publish_evidence',fn), contextlib.redirect_stdout(io.StringIO()):
            try: getattr(case,method)(); error = None
            except Exception as ex: error = type(ex).__name__
        victims = [p for p in case.base.iterdir() if p.name.startswith('victim')]
        results[name] = dict(assertion_or_receipt_failure=error,victims=len(victims),
            victims_overwritten=sum(p.read_text() != 'unchanged' for p in victims))
    finally: case.doCleanups()
results['scope'] = 'Two baseline write operations in candidate actual-main fixtures; not a complete baseline installation. Docker/native effects substituted.'
assert results['marker']['victims_overwritten'] == 1
assert results['public']['victims_overwritten'] == 9
print(json.dumps(results,indent=2))
