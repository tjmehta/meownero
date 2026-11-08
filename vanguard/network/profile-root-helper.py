#!/usr/bin/python3 -I
"""Proposed sole root entry. No arguments, plugins, installation or discovery.

The installed directory and complete source closure must be root-owned,
immutable and qualified. Isolated Python ignores caller PYTHONPATH and cwd.
This source candidate has no qualified OS constructor and refuses by default.
"""
import sys

# The fixed installed path is the only non-stdlib import path in isolated mode.
# Local source fixtures import main explicitly without invoking a root process.
if __name__=='__main__':
    from pathlib import Path
    if not sys.flags.isolated or str(Path(__file__).resolve())!='/opt/meownero/TJS-2504/helper/profile-root-helper.py':
        print('{"result":"REFUSED_UNQUALIFIED","native_execution":"NOT_RUN","launch_ready":false}')
        sys.exit(3)
    sys.path.insert(0,'/opt/meownero/TJS-2504/helper')

import hashlib
import json
from pathlib import Path
import profile_executor as e


def main(argv=None, *, qualified=None):
    args=sys.argv[1:] if argv is None else argv
    try:
        if args:raise ValueError('no arguments')
        table=e.QUALIFIED_ROOT if qualified is None else qualified
        # A hash selects only an independently reviewed compiled constructor;
        # it is never itself authority. No registry is loaded from disk/JSON.
        digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if digest not in table:raise ValueError('no qualified root constructor')
        table[digest].run_authenticated_inherited_entry()
        print(json.dumps(dict(result='HELPER_RETURNED',native_execution='NOT_RUN',launch_ready=False)))
        return 0
    except Exception:
        print(json.dumps(dict(result='REFUSED_UNQUALIFIED',native_execution='NOT_RUN',launch_ready=False)))
        return 3


if __name__=='__main__':sys.exit(main())
