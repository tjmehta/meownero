#!/usr/bin/python3 -I
"""Fixed no-argument custodian entry; no installed launch authority is supplied.

Only stdlib is imported before independent launch selection. The immutable
installer/ancestor/closure check must precede loading a qualified constructor.
This registry is deliberately empty; a file, hash or root UID cannot fill it.
"""
import hashlib
import json
from pathlib import Path
import sys

QUALIFIED_CUSTODIANS={}


def main(argv=None,*,qualified=None):
    args=sys.argv[1:] if argv is None else argv
    try:
        if args:raise ValueError('no arguments')
        table=QUALIFIED_CUSTODIANS if qualified is None else qualified
        source=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if source not in table:raise ValueError('independently qualified original launch unavailable')
        table[source].run_authenticated_inherited_entry()
        result='CUSTODIAN_RETURNED';status=0
    except Exception:
        result='REFUSED_UNQUALIFIED';status=3
    print(json.dumps(dict(result=result,native_execution='NOT_RUN',launch_ready=False)))
    return status


if __name__=='__main__':
    if not sys.flags.isolated or str(Path(__file__).resolve())!='/opt/meownero/TJS-2504/helper/profile-custodian.py':
        print('{"result":"REFUSED_UNQUALIFIED","native_execution":"NOT_RUN","launch_ready":false}')
        sys.exit(3)
    sys.exit(main())
