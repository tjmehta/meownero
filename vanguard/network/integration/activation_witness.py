#!/usr/bin/env python3
"""Read-only live seed dial witness. Exit 0 OK, 2 ALERT, 3 UNVERIFIED.

Read the actual seed argv from /proc/PID/cmdline, its complete current-launch
default-format log, and the operator's checked plan. Banner timestamps are UTC,
regardless of the local timezone. Run in the seed's PID namespace. After log
rotation, preserve the logs and use the supervised planned restart to establish
a new launch banner in the running file. No daemon, network connection or host
rule is created by this command.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from integration import operator_contract as o
from integration import topology_contract as t


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--log-file', type=Path, required=True)
    parser.add_argument('--plan-file', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.pid <= 0:
            raise ValueError('pid must be positive')
        proc = Path(f'/proc/{args.pid}')
        stat = (proc/'stat').read_text()
        ticks = int(stat.rsplit(')', 1)[1].split()[19])  # proc_pid_stat(5), field 22.
        boot = time.clock_gettime(time.CLOCK_BOOTTIME)
        observed = time.time()
        # starttime is truncated to clock ticks. Use the upper edge, so an
        # earlier launch in the same tick cannot qualify; ambiguous logs fail closed.
        started = observed-boot+(ticks+1)/os.sysconf('SC_CLK_TCK')
        argv_raw = (proc/'cmdline').read_bytes()
        argv = argv_raw.rstrip(b'\0').decode().split('\0')
        plan = json.loads(args.plan_file.read_text())
        options = dict(o.check_public_seed(argv, plan,
                                           mining='--start-mining' in argv))
        if not args.log_file.samefile(options['--log-file']):
            raise ValueError('log file differs from running argv')
        raw = args.log_file.read_bytes()
        result = o.activation_seed_witness(raw, argv, plan, mining='--start-mining' in argv,
            launch_window=(started, time.time()))
        if ((proc/'stat').read_text().rsplit(')', 1)[1].split()[19] != str(ticks) or
                (proc/'cmdline').read_bytes() != argv_raw or
                abs((time.time()-observed)-(time.clock_gettime(time.CLOCK_BOOTTIME)-boot)) > 0.05):
            raise ValueError('process or wall clock changed during sample')
    except t.PolicyRefusal as error:
        result = dict(state='ALERT', reason=str(error))
    except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
        result = dict(state='UNVERIFIED', reason='witness input: '+type(error).__name__)
    print(json.dumps(result, sort_keys=True))
    return {'OK': 0, 'ALERT': 2}.get(result['state'], 3)


if __name__ == '__main__':
    sys.exit(main())
