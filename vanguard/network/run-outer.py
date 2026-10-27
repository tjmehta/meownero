#!/usr/bin/env python3
"""Inspect source-only capability bindings; unqualified execution always refuses."""
import argparse
import json
from pathlib import Path

import profile_contract as c
import profile_outer as outer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capabilities', type=Path, default=c.HERE/'integration/outer-capabilities.json')
    parser.add_argument('--inputs', type=Path, default=c.HERE/'integration/inputs.json')
    parser.add_argument('--check', action='store_true', help='read source JSON only; never inspect the host')
    args = parser.parse_args()
    capabilities = c.json_file(args.capabilities)
    if args.check:
        print(json.dumps(outer.capability_check(capabilities), indent=2))
        return 0
    try:
        outer.require_runtime(c.json_file(args.inputs), capabilities)
        # A later reviewed source delta must implement a real qualified manager
        # adapter, grant authentication and the private channel. There is no
        # dynamic plugin/command lookup and no executable supplied by JSON.
        raise ValueError('qualified manager adapter and reviewed grant entry are not supplied')
    except ValueError as error:
        print(json.dumps(dict(result='REFUSED_BEFORE_HOST_OPERATIONS', reason=str(error),
                              native_execution='NOT_RUN', launch_ready=False)))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
