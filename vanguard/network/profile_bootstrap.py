"""Generated helper entry over disposable/inherited descriptors.

The installed-unit/custodian expectation and atomic one-use consumption must be
implemented and qualified by the OS boundary. A packet cannot establish either.
No production boundary is registered. No path, environment or argv is authority.
"""
import fcntl
import json
import math
import os
import re
import socket
import stat
import time

import profile_contract as c
import profile_dispatch as d
import profile_manager as m
import profile_packet as p

FIELDS = {'schema','task','attempt_id','role','mode','invocation_id','source',
    'spec_sha256','contract_sha256','origin','deadlines','sender_credentials',
    'sender_start','delivery_deadline','namespace_identity'}
SEALS = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE


def delivery_pair():
    sender,receiver=m.private_pair()
    # SO_PASSCRED on the sending endpoint triggers Linux autobind on send.
    # Only the receiver needs it for per-packet SCM_CREDENTIALS authentication.
    sender.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,0)
    return sender,receiver


def socket_from_fd(fd):
    duplicate=os.dup(fd)
    try:return socket.socket(fileno=duplicate)
    except BaseException:
        os.close(duplicate)
        raise


def seqpacket(endpoint):
    c.require(endpoint.family == socket.AF_UNIX and
        endpoint.getsockopt(socket.SOL_SOCKET,socket.SO_TYPE) == socket.SOCK_SEQPACKET and
        endpoint.getsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED) == 1 and
        endpoint.getsockname() in ('',b'') and endpoint.getpeername() in ('',b''),
        'unnamed credentialed bootstrap endpoint')


def validate_delivery(value,role,plan,spec_sha256,now):
    c.require(type(value) is dict and set(value)==FIELDS, 'exact bootstrap delivery fields')
    c.require(value['schema']=='meownero-helper-bootstrap/1' and value['task']=='TJS-2504' and
        value['role']==role and value['mode']==p.delivery_contract(role)['mode'] and
        value['attempt_id']==plan['attempt_id'] and value['source']==plan['source'] and
        value['spec_sha256']==spec_sha256, 'role/task/attempt/source/spec bootstrap binding')
    for key,size in [('attempt_id',32),('invocation_id',32),('contract_sha256',64)]:
        c.require(type(value[key]) is str and bool(re.fullmatch('[0-9a-f]{'+str(size)+'}',value[key])),
            'bound bootstrap '+key)
    origin=value['origin'];end=value['delivery_deadline']
    c.require(type(origin) in (int,float) and math.isfinite(origin) and origin<=now and
        value['deadlines']==dict(build=origin+3600,work=origin+4200,end=origin+4500) and
        type(end) in (int,float) and math.isfinite(end) and now<end<=now+5 and
        end<=value['deadlines']['end'], 'bounded original bootstrap deadlines')
    creds=value['sender_credentials']
    c.require(type(creds) is list and len(creds)==3 and all(type(x) is int for x in creds) and
        creds[0]>0 and min(creds[1:])>=0 and type(value['sender_start']) is str and
        value['sender_start'].isdigit(), 'sender PID/uid/gid/start identity')
    c.require(value['namespace_identity'] is None if role=='prepare' else
        type(value['namespace_identity']) is int and value['namespace_identity']>0,
        'role-bound retained namespace identity')


def enter(mode,role,plan,spec_sha256,*,endpoint_fd=0,backend_table=None,clock=time.monotonic):
    """Consume generated entry through real authorization/lifecycle orchestration.

    The explicit table injection is for local source fixtures only. Installed
    execution uses the empty, exact-source registry. Recovery classification is
    independently authenticated; an absent packet never selects recovery.
    """
    c.require(p.delivery_contract(role)['mode']==mode, 'generated mode/role pair')
    table=d.QUALIFIED_OS if backend_table is None else backend_table
    adapter=d.qualified_adapter(mode,plan,spec_sha256,backend_table=table)
    expected=adapter.boundary.bootstrap_expectation(mode,role,plan,spec_sha256)
    c.require(type(expected) is dict and set(expected)=={'entry','delivery'}, 'installed entry classification')
    if expected['entry']=='stored-recovery':
        c.require(mode=='serve' and role=='keeper' and expected['delivery'] is None,
            'only independently authenticated keeper restart uses stored descriptors')
        try:
            adapter=d.authorize_mode(mode,plan,spec_sha256,None,None,backend_table=table)
            return adapter.enter(mode,plan)
        finally:adapter.authenticated=None
    c.require(expected['entry']=='fresh', 'missing or ambiguous installed entry refuses')
    expected=expected['delivery']
    validate_delivery(expected,role,plan,spec_sha256,clock())
    # This check authenticates the receiver invocation and surviving custodian,
    # including sender start ticks. It may not access private C/W before setns.
    adapter.boundary.check_bootstrap_sender(expected)
    fds=()
    endpoint=socket_from_fd(endpoint_fd)
    try:
        seqpacket(endpoint)
        packet,fds=m.receive_packet(endpoint,expected['sender_credentials'],expected['delivery_deadline'],
            fd_count=len(p.delivery_contract(role)['descriptors']),clock=clock)
        adapter.boundary.check_bootstrap_sender(expected)
        c.require(packet==expected, 'authenticated exact role/invocation delivery')
        authority,context=fds[:2]
        c.require(len({(os.fstat(fd).st_dev,os.fstat(fd).st_ino) for fd in fds})==len(fds),
            'distinct descriptor objects')
        with socket_from_fd(authority) as capability:
            seqpacket(capability)
        info=os.fstat(context)
        c.require(stat.S_ISREG(info.st_mode) and 0<info.st_size<=m.MAX_PACKET and
            fcntl.fcntl(context,fcntl.F_GET_SEALS)&SEALS==SEALS, 'bounded sealed context descriptor')
        raw=os.pread(context,info.st_size+1,0);value=json.loads(raw)
        c.require(c.canonical(value)==raw and set(value)=={'schema','delivery','contract'} and
            value['schema']=='meownero-helper-bootstrap-context/1' and value['delivery']==expected,
            'sealed context binds the exact delivery')
        contract=d.validate_contract(value['contract'])
        c.require(c.digest(c.canonical(contract))==expected['contract_sha256'] and
            contract['spec_sha256']==spec_sha256 and contract['attempt_id']==expected['attempt_id'] and
            contract['origin']==expected['origin'] and contract['deadlines']==expected['deadlines'],
            'original immutable contract and deadlines')
        # Atomic custodian-side burn survives fresh adapter/process instances.
        # Rejected/uncertain authentication must never restore this capability.
        c.require(adapter.boundary.consume_bootstrap_delivery(expected,authority,context) is True,
            'one-use role/invocation capability')
        adapter=d.authorize_mode(mode,plan,spec_sha256,authority,context,backend_table=table)
        adapter.bootstrap_delivery=expected
        adapter.bootstrap_namespace=fds[2] if len(fds)==3 else None
        return adapter.enter(mode,plan,deadline_owner=role=='deadline')
    finally:
        endpoint.close()
        adapter.bootstrap_delivery=None
        adapter.bootstrap_namespace=None
        adapter.authenticated=None
        for fd in fds:os.close(fd)
