#!/usr/bin/env python3
"""Render the source packet or enter one exact-source qualified lifecycle mode.

No adapter is qualified in this candidate. All mutation modes refuse before
resource access. No shell, privilege discovery, generic argv or plugin path.
"""
import argparse
import json
from pathlib import Path
import sys

import profile_contract as c
import profile_dispatch as d
import profile_packet as p
import profile_bootstrap as b


def main(argv=None, *, backend_table=None, clock=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('plan','prepare','serve','recover','observe','dispose'))
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--spec-sha256')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--authority-fd',type=int)
    parser.add_argument('--context-fd',type=int)
    parser.add_argument('--deadline-owner',action='store_true')
    parser.add_argument('--bootstrap-role',choices=('prepare','keeper','deadline','observer'))
    args=parser.parse_args(argv)
    try:
        value=json.loads(args.spec.read_bytes())
        if args.mode=='plan':
            c.require(not args.bootstrap_role and not args.deadline_owner and args.authority_fd is None and args.context_fd is None,
                'plan accepts source data only')
            packet=p.render(value)
            raw=json.dumps(packet,indent=2)+'\n'
            if args.out:args.out.write_text(raw)
            else:print(raw,end='')
            return 0
        c.require(args.out is None, 'mutation has no arbitrary output path')
        if args.bootstrap_role:
            c.require(args.authority_fd is None and args.context_fd is None and
                args.deadline_owner==(args.bootstrap_role=='deadline'), 'one generated bootstrap entry')
            kwargs={} if clock is None else dict(clock=clock)
            result=b.enter(args.mode,args.bootstrap_role,value,args.spec_sha256,
                backend_table=backend_table,**kwargs)
        else:
            # Installed first-start/recovery roles must use the generated entry.
            c.require(args.mode=='dispose' and not args.deadline_owner, 'generated bootstrap entry required')
            table=d.QUALIFIED_OS if backend_table is None else backend_table
            adapter=d.authorize_mode(args.mode,value,args.spec_sha256,args.authority_fd,args.context_fd,backend_table=table)
            result=adapter.enter(args.mode,value)
        labels=dict(prepare='PREPARED_UNACTIVATED',observe='PENDING_OBSERVER_EXIT',
            serve='SERVICE_RETURNED',recover='RECOVERY_RETURNED',dispose='DISPOSITION_RETURNED')
        if args.mode in ('prepare','observe'):
            c.require(type(result) is dict and result.get('result')==labels[args.mode], 'expected lifecycle result')
        else:
            c.require(type(result) is dict or type(result) is int and result==0, 'successful lifecycle return')
        # Never forward receipts/context/exception messages to process output.
        print(json.dumps(dict(result=labels[args.mode],native_execution='NOT_RUN',launch_ready=False)))
        return 0
    except (ValueError,KeyError,OSError,TypeError) as error:
        print(json.dumps(dict(result='REFUSED_BEFORE_HOST_OPERATIONS',failure_class=type(error).__name__,
            native_execution='NOT_RUN',launch_ready=False)))
        return 3


def run(argv=None, **fixture):
    sys.exit(main(argv, **fixture))


if __name__=='__main__':run()
