"""Closed command executor for the frozen lifecycle records.

No shell, arbitrary argv, dynamic import, sudo or host discovery. The root
entry has no qualified constructor. Every syscall/D-Bus/Docker primitive and
external-writer limiter is an explicit injected, UNQUALIFIED OS boundary.
"""
import copy
import math
from pathlib import Path
import re
import subprocess
import time

import profile_contract as c
import profile_packet as p

ROOT_DIRECTORY='/opt/meownero/TJS-2504/helper'
ROOT_ENTRY=ROOT_DIRECTORY+'/profile-root-helper.py'
CHILD_DIRECTORY=ROOT_DIRECTORY+'/runtime/vanguard/network'
ROOT_COMMAND=['/usr/bin/python3','-I','-B',ROOT_ENTRY]
QUALIFIED_ROOT={}  # Never populated by bindings, argv, environment or tests.
# This is the complete low-level record protocol, distinct from the existing
# outer/controller Dispatcher protocol. No free-form operation is accepted.
OPERATIONS=('verify_inherited_authority','install_exact_owned_source','bootstrap_delivery',
    'StartTransientUnit','unshare','mount','openat','posix_fallocate','mke2fs','losetup',
    'mkdirat_chown_fsync','bind_user_directory','ledger_dirfd_handoff','reserve_slot',
    'bounded_archive','sd_notify','arm_deadline','first_admission_quarantine_consume',
    'workload_namespace_view','place_before_exec','load','inspect_image','place_outer_before_exec',
    'outer','controller','observe_and_create','start_and_wait','remove_owned','terminate_owned',
    'StopUnit','KillUnit','export','umount','detach','unlinkat_owned_W','final_custody',
    'observe','explicit_disposition')
TOKEN=re.compile(r'\$[A-Z][A-Z0-9_]*')


def verify_installation(root, inputs_raw):
    """Check declared bytes before dispatch; authority authenticates inputs_raw.

    This read-only source check neither installs files nor qualifies ownership,
    immutability or an OS adapter. The index's own hash comes from the exact
    artifact-bound authority, avoiding a recursive manifest hash.
    """
    root=Path(root)
    import json
    inputs=json.loads(inputs_raw)
    sources=dict(inputs['reference']['repository_files'])
    for name,sha in inputs['candidate_files'].items():
        c.require(name not in sources or sources[name]==sha, 'conflicting source bindings')
        sources[name]=sha
    inventory_path='vanguard/network/integration/installation-inventory.json'
    raw=(root/'installation-inventory.json').read_bytes()
    c.require(c.digest(raw)==sources[inventory_path], 'installation inventory binding')
    inventory=json.loads(raw)
    c.require(inventory['schema']=='meownero-installation-inventory/1', 'installation schema')
    groups=inventory['groups']
    c.require(set(groups)=={'root_helper','child_runtime','validation_data'}, 'installation groups')
    child={**groups['child_runtime'],**groups['validation_data']}
    c.require(set(child)==set(sources) and len(child)==len(groups['child_runtime'])+
        len(groups['validation_data']), 'complete disjoint child source inventory')
    destinations=set()
    for group,members in groups.items():
        for source,destination in members.items():
            path=Path(destination)
            c.require(not path.is_absolute() and '..' not in path.parts and str(path)==destination,
                'canonical relative installed path')
            c.require(destination not in destinations, 'duplicate installed destination')
            destinations.add(destination)
            target=root/path
            c.require(target==target.resolve(strict=True) and target.is_file() and
                c.digest(target.read_bytes())==sources[source], 'missing/altered installed member: '+destination)
    c.require((root/'runtime/vanguard/network/integration/inputs.json').read_bytes()==inputs_raw,
        'installed authority index bytes')
    return inventory


def templates(plan):
    records=p.render(plan)['records']
    c.require(set(r['operation'] for r in records)==set(OPERATIONS), 'closed complete record operation table')
    return records


def substitute(value, bindings):
    """Replace only separately authenticated scalar tokens; preserve argv shape."""
    if type(value) is str:
        if TOKEN.fullmatch(value):
            c.require(value[1:] in bindings, 'missing bound token')
            return bindings[value[1:]]
        def replace(match):
            bound=bindings.get(match[0][1:])
            c.require(type(bound) in (str,int), 'string template needs scalar binding')
            return str(bound)
        result=TOKEN.sub(replace,value)
        c.require('$' not in result, 'unresolved template')
        return result
    if type(value) is list:return [substitute(x,bindings) for x in value]
    if type(value) is dict:return {k:substitute(v,bindings) for k,v in value.items()}
    return value


class RecordExecutor:
    """Run only a rendered record after independent authority and IO admission.

    The boundary authenticates bindings and source before construction; each
    call rechecks original deadlines, one-use record order, owned identities,
    hard enforcement and a durable worst-case write reservation. It must deny
    execution when ANY such facility is missing. Samples are not enforcement.
    """
    def __init__(self,plan,boundary,*,clock=time.monotonic,run=subprocess.run):
        self.plan=copy.deepcopy(p.validate_plan(plan))
        self.records=templates(plan)
        self.boundary,self.clock,self.run=boundary,clock,run
        self.used=set();self.failed=False
        # No caller-supplied substitutions. Only the independently authenticated
        # root custody/authority implementation returns bound values.
        self.bindings=boundary.authenticate_executor(self.plan)
        c.require(type(self.bindings) is dict, 'authenticated binding map')

    def execute(self,request):
        c.require(type(request) is dict and set(request)=={'operation','record','deadline'} and
            request['operation'] in OPERATIONS and type(request['record']) is int and
            0<=request['record']<len(self.records), 'closed record request; no argv')
        record=self.records[request['record']]
        c.require(record['operation']==request['operation'], 'exact operation/record pair')
        c.require(not self.failed or record['phase'] in ('cleanup','completion'), 'uncertainty is recovery only')
        c.require(record['sequence'] not in self.used, 'one-use record')
        self.used.add(record['sequence'])
        try:
            deadline=request['deadline']
            c.require(type(deadline) in (int,float) and math.isfinite(deadline) and
                self.clock()<deadline, 'future finite absolute deadline')
            # This independent guard enforces phase order and deadlines as well
            # as hard meters before an effect, including after process restart.
            self.boundary.admit_record(record,deadline)
            exact=copy.deepcopy(record)
            # Descriptive preconditions/environment templates are review data;
            # only the actual typed arguments are expanded for execution.
            exact['args']=substitute(record['args'],self.bindings)
            self.boundary.verify_bound_record(record,exact,deadline)
            if record['kind']=='argv':
                argv=exact['args']
                c.require(type(argv) is list and argv and all(type(x) is str and
                    '\x00' not in x and '\n' not in x and '$' not in x for x in argv), 'bound argv only')
                c.require(argv[0].startswith('/') and record['operation'] in
                    ('mount','mke2fs','losetup','outer','controller','umount','detach'), 'enumerated program')
                c.require(argv[0]==('/usr/bin/python3' if record['args'][0]=='$BOUND_PYTHON' else
                    record['args'][0]), 'fixed program identity; no command substitution')
                if record['operation'] in ('outer','controller'):
                    script='run-outer.py' if record['operation']=='outer' else 'run-profile.py'
                    c.require(argv[1:3]==['-B',CHILD_DIRECTORY+'/'+script], 'fixed owned Python entry')
                # FDs, private cwd and per-child environment come only from the
                # guard. No inherited environment or serialized output.
                execution=self.boundary.execution_context(record,exact,deadline)
                c.require(set(execution)=={'env','cwd','pass_fds','uid','gid','extra_groups'} and
                    execution['uid']==execution['gid']==record['uid'] and execution['extra_groups']==[],
                    'exact child identity/context')
                result=self.run(argv,shell=False,check=True,stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True,
                    timeout=deadline-self.clock(),env=execution['env'],cwd=execution['cwd'],
                    pass_fds=tuple(execution['pass_fds']),user=execution['uid'],group=execution['gid'],
                    extra_groups=[],umask=0o077)
                c.require(result.returncode==0, 'fixed command failed')
            elif record['kind']=='dbus':
                c.require(record['operation'] in ('StartTransientUnit','StopUnit','KillUnit'), 'fixed bus method')
                self.boundary.dbus(exact['args'],deadline)
            elif record['kind']=='syscall':
                self.boundary.syscall(record['operation'],exact['args'],deadline)
            else:
                c.require(record['kind']=='docker' and record['operation'] in
                    ('load','inspect_image','observe_and_create','start_and_wait','remove_owned'), 'fixed private Docker method')
                self.boundary.docker(record['operation'],exact['args'],deadline)
            self.boundary.complete_record(record,deadline)
            c.require(self.clock()<deadline, 'late operation consumes record and keeps recovery ownership')
            return dict(result='RECORD_RETURNED',record=record['sequence'],native_execution='NOT_RUN')
        except BaseException:
            self.failed=True
            self.boundary.quarantine_record_uncertainty(record)
            raise


class RootEntry:
    """Connect the sole root CLI to the closed record executor.

    Only an exact-source registered installed boundary can construct this. Its
    inherited-channel authentication is deliberately not derived from JSON.
    """
    def __init__(self,boundary,*,clock=time.monotonic,run=subprocess.run):
        self.boundary,self.clock,self.run=boundary,clock,run

    def run_authenticated_inherited_entry(self):
        try:
            plan=self.boundary.authenticate_root_entry()
            # Only the independently authenticated boundary supplies the frozen
            # index bytes; request JSON and the local index cannot grant authority.
            verify_installation(c.HERE,self.boundary.authenticated_installation_inputs())
            executor=RecordExecutor(plan,self.boundary,clock=self.clock,run=self.run)
            request=self.boundary.receive_authenticated_record_request()
            return executor.execute(request)
        finally:
            close=getattr(self.boundary,'close_authenticated_entry',None)
            if close is not None:close()


def proposal(plan):
    """Review data only. This must never be installed from a source proposal."""
    records=templates(plan)
    return dict(schema='meownero-root-executor-proposal/1',root_entry=ROOT_ENTRY,
        root_command=ROOT_COMMAND,arguments='none; authenticated inherited role/request only',
        sudoers_proposal='tjmehta ALL=(root) NOPASSWD: /usr/bin/python3 -I -B '+ROOT_ENTRY,
        source_closure=dict(inventory='integration/installation-inventory.json',
            hashes='exact authority-bound inputs.json candidate_files and reference.repository_files',
            root=ROOT_DIRECTORY,child=CHILD_DIRECTORY,
            authority_index='runtime/vanguard/network/integration/inputs.json; exact grant-bound bytes',
            installation='root-owned immutable files and ancestors; UNQUALIFIED'),
        operations=list(OPERATIONS),command_allowlist=[dict(record=r['sequence'],phase=r['phase'],
            kind=r['kind'],operation=r['operation'],args=r['args'],uid=r['uid'],gid=r['gid'],
            preconditions=r['preconditions'],deadline=r['deadline']) for r in records],
        substitution_authority='independent_installed_custodian_only_not_request_JSON',
        teardown=[r for r in records if r['phase'] in ('cleanup','completion')],
        rollback=[r for r in records if r['phase']=='dispose'],
        never_rollback='control quarantine, grant consumption or uncertain attempt eligibility',
        ingress=dict(source='profile_ingress.InstalledIngress',transport='existing unnamed seqpacket/SCM_RIGHTS',
            trust='independently supplied constructor anchor, never packet/seals/hash/local JSON',
            state='existing CapabilityStore/GrantJournal plus original record-order file; no create/rearm',
            qualification='UNQUALIFIED; no installed constructor or surviving trust anchor supplied'),
        unqualified=['installed authority/receiver','syscall/D-Bus/Docker adapters',
            'PID1 same-description readback','workload C/W namespace view','external writer mediation',
            'surviving deadline owner','observer exit/tail sensors','archive producer/custody'],
        activation='REFUSED_UNQUALIFIED',native_execution='NOT_RUN',launch_ready=False)
