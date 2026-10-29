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


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('plan','prepare','serve','recover','observe','dispose'))
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--spec-sha256')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--authority-fd',type=int)
    parser.add_argument('--context-fd',type=int)
    parser.add_argument('--deadline-owner',action='store_true')
    args=parser.parse_args(argv)
    try:
        value=json.loads(args.spec.read_bytes())
        if args.mode=='plan':
            c.require(not args.deadline_owner and args.authority_fd is None and args.context_fd is None,
                'plan accepts source data only')
            packet=p.render(value)
            raw=json.dumps(packet,indent=2)+'\n'
            if args.out:args.out.write_text(raw)
            else:print(raw,end='')
            return 0
        c.require(args.out is None, 'mutation has no arbitrary output path')
        adapter=d.authorize_mode(args.mode,value,args.spec_sha256,args.authority_fd,args.context_fd)
        # This static table has no entries. Only reviewed source can supply an
        # adapter; a filename, environment variable or JSON cannot load code.
        return adapter.enter(args.mode,value,deadline_owner=args.deadline_owner)
    except (ValueError,KeyError,OSError,TypeError) as error:
        print(json.dumps(dict(result='REFUSED_BEFORE_HOST_OPERATIONS',failure_class=type(error).__name__,
            native_execution='NOT_RUN',launch_ready=False)))
        return 3


if __name__=='__main__':sys.exit(main())
