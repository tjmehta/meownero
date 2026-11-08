#!/usr/bin/env python3
"""Inspect source-only capability bindings; unqualified execution always refuses."""
import argparse
import json
from pathlib import Path

import profile_contract as c
import profile_outer as outer
import profile_dispatch as dispatcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capabilities', type=Path, default=c.HERE/'integration/outer-capabilities.json')
    parser.add_argument('--inputs', type=Path, default=c.HERE/'integration/inputs.json')
    parser.add_argument('--check', action='store_true', help='read source JSON only; never inspect the host')
    parser.add_argument('--context-fd',type=int)
    parser.add_argument('--helper-fd',type=int)
    parser.add_argument('--ledger-directory-fd',type=int)
    args = parser.parse_args()
    capabilities = c.json_file(args.capabilities)
    if args.check:
        print(json.dumps(outer.capability_check(capabilities), indent=2))
        return 0
    try:
        outer.require_runtime(c.json_file(args.inputs), capabilities)
        result=dispatcher.launch_outer(args.context_fd,args.helper_fd,args.ledger_directory_fd,c.json_file(args.inputs))
        print(json.dumps(result))
        return 0 if result['result']=='PENDING_MANAGER_COMPLETION' else 1
    except (ValueError,KeyError,OSError,TypeError) as error:
        print(json.dumps(dict(result='REFUSED_BEFORE_HOST_OPERATIONS', failure_class=type(error).__name__,
                              native_execution='NOT_RUN', launch_ready=False)))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
