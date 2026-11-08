"""Fixed runtime diagnostics for the frozen driver; no exception text is public.

Installed only at the driver's existing profile_contract import. Line ranges bind
this frozen source; source tests assert their anchors. This observes, never alters,
native calls. Only the main thread is traced; bridge-thread failures reach its
existing fixed c.require guard.
"""
import json
import os
import sys

REQUIRE_CODES = {'CLI exited before expected prompt': 'CLI_EXITED_BEFORE_EXPECTED_PROMPT',
 'CLI normal save/exit': 'CLI_NORMAL_SAVE_EXIT',
 'CLI remains': 'CLI_REMAINS',
 'Levin framing': 'LEVIN_FRAMING',
 'PID reuse; signal refused': 'PID_REUSE_SIGNAL_REFUSED',
 'UUID negative changed state': 'UUID_NEGATIVE_CHANGED_STATE',
 'aggregate limits/topology differ': 'AGGREGATE_LIMITS_TOPOLOGY_DIFFER',
 'chain negative changed state': 'CHAIN_NEGATIVE_CHANGED_STATE',
 'cold restore changed identity': 'COLD_RESTORE_CHANGED_IDENTITY',
 'cold restore state': 'COLD_RESTORE_STATE',
 'controller or Docker daemon outside aggregate parent': 'CONTROLLER_OR_DOCKER_DAEMON_OUTSIDE_AGGREGATE_PARENT',
 'daemon fork schedule': 'DAEMON_FORK_SCHEDULE',
 'denial matrix drift': 'DENIAL_MATRIX_DRIFT',
 'exact bootstrap hash required': 'EXACT_BOOTSTRAP_HASH_REQUIRED',
 'exact structured grant required': 'EXACT_STRUCTURED_GRANT_REQUIRED',
 'external input symlink': 'EXTERNAL_INPUT_SYMLINK',
 'foreign fixture itself invalid': 'FOREIGN_FIXTURE_ITSELF_INVALID',
 'foreign prefix accepted': 'FOREIGN_PREFIX_ACCEPTED',
 'genesis peer disagreement': 'GENESIS_PEER_DISAGREEMENT',
 'graceful save/exit failed': 'GRACEFUL_SAVE_EXIT_FAILED',
 'grant absent, premature or expired': 'GRANT_ABSENT_PREMATURE_OR_EXPIRED',
 'grant binding mismatch': 'GRANT_BINDING_MISMATCH',
 'healthy native handshake response': 'HEALTHY_NATIVE_HANDSHAKE_RESPONSE',
 'integrated roundtrip': 'INTEGRATED_ROUNDTRIP',
 'launcher manifest refusal': 'LAUNCHER_MANIFEST_REFUSAL',
 'listener remains': 'LISTENER_REMAINS',
 'load admission exceeds proposal': 'LOAD_ADMISSION_EXCEEDS_PROPOSAL',
 'missing/wrong/old credential accepted': 'MISSING_WRONG_OLD_CREDENTIAL_ACCEPTED',
 'native Levin frame': 'NATIVE_LEVIN_FRAME',
 'native RPC returned error': 'NATIVE_RPC_RETURNED_ERROR',
 'native frame ended': 'NATIVE_FRAME_ENDED',
 'native peer bridge failed': 'NATIVE_PEER_BRIDGE_FAILED',
 'no-counterpart state changed': 'NO_COUNTERPART_STATE_CHANGED',
 'non-genesis or wrong chain': 'NON_GENESIS_OR_WRONG_CHAIN',
 'non-loopback local socket': 'NON_LOOPBACK_LOCAL_SOCKET',
 'non-loopback remote socket': 'NON_LOOPBACK_REMOTE_SOCKET',
 'non-loopback route': 'NON_LOOPBACK_ROUTE',
 'nonempty pool': 'NONEMPTY_POOL',
 'not a new attributed Platform grant': 'NOT_A_NEW_ATTRIBUTED_PLATFORM_GRANT',
 'one native UUID field required': 'ONE_NATIVE_UUID_FIELD_REQUIRED',
 'original heavy-lock identity/owner/mode': 'ORIGINAL_HEAVY_LOCK_IDENTITY_OWNER_MODE',
 'original stopped bundle changed': 'ORIGINAL_STOPPED_BUNDLE_CHANGED',
 'overlapping owned process': 'OVERLAPPING_OWNED_PROCESS',
 'owned PID not absent': 'OWNED_PID_NOT_ABSENT',
 'path alias or symlink': 'PATH_ALIAS_OR_SYMLINK',
 'persisted CLI refresh height differs': 'PERSISTED_CLI_REFRESH_HEIGHT_DIFFERS',
 'portable length out of range': 'PORTABLE_LENGTH_OUT_OF_RANGE',
 'private regular file identity/mode': 'PRIVATE_REGULAR_FILE_IDENTITY_MODE',
 'repeated password prompt': 'REPEATED_PASSWORD_PROMPT',
 'requires 20 GiB free disk': 'REQUIRES_20_GIB_FREE_DISK',
 'requires 5 GiB available': 'REQUIRES_5_GIB_AVAILABLE',
 'restart identity/state': 'RESTART_IDENTITY_STATE',
 'restriction handler did not deny': 'RESTRICTION_HANDLER_DID_NOT_DENY',
 'retained root alias/type/owner': 'RETAINED_ROOT_ALIAS_TYPE_OWNER',
 'root owner/mode': 'ROOT_OWNER_MODE',
 'runtime deadline exhausted': 'RUNTIME_DEADLINE_EXHAUSTED',
 'runtime facts do not belong in authorization': 'RUNTIME_FACTS_DO_NOT_BELONG_IN_AUTHORIZATION',
 'same-profile address validation': 'SAME_PROFILE_ADDRESS_VALIDATION',
 'saved bundle digest or membership changed': 'SAVED_BUNDLE_DIGEST_OR_MEMBERSHIP_CHANGED',
 'special input file': 'SPECIAL_INPUT_FILE',
 'subaddress was not provisioned': 'SUBADDRESS_WAS_NOT_PROVISIONED',
 'unexpected native exit': 'UNEXPECTED_NATIVE_EXIT',
 'unknown public row': 'UNKNOWN_PUBLIC_ROW',
 'unsafe parent': 'UNSAFE_PARENT',
 'wallet inherited RPC_LOGIN': 'WALLET_INHERITED_RPC_LOGIN',
 'wallet reopen identity/rotation': 'WALLET_REOPEN_IDENTITY_ROTATION',
 'wallet/data file still open': 'WALLET_DATA_FILE_STILL_OPEN',
 'workload collision': 'WORKLOAD_COLLISION'}
EXCEPTIONS = frozenset(('NONE','OTHER_EXCEPTION','ValueError','RuntimeError','TimeoutError',
    'OSError','FileNotFoundError','PermissionError','ConnectionRefusedError',
    'ConnectionResetError','BrokenPipeError','KeyError','IndexError','TypeError',
    'AttributeError','StopIteration','JSONDecodeError','HTTPError','URLError','CalledProcessError'))
MAIN_STEPS = ((733,'SETUP'),(735,'WIRE_BRIDGE'),(737,'NODE1_START'),(738,'HANDSHAKE'),
    (740,'WIRE_BRIDGE'),(741,'HANDSHAKE'),(742,'SNAPSHOT_AGREEMENT'),
    (743,'NATIVE_HANDSHAKE'),(744,'GENESIS_STATE'),(745,'DAEMON_FORK_TABLE'),
    (752,'HTTP_AUTH'),(754,'DAEMON_SAVE'),(755,'UUID_GUARD'),(756,'NO_FALLBACK'),
    (762,'DAEMON_SAVE'),(764,'DAEMON_REOPEN_RESTORE'),(773,'LAUNCHER_REFUSALS'),
    (774,'DAEMON_REOPEN_RESTORE'),(775,'WALLET_SETUP'),(776,'PERSISTED_HEIGHT_ZERO'),
    (777,'SEVENTEEN_DENIALS'),(778,'ROTATED_LOGIN'),(779,'WALLET_SAVE_EXIT_RELEASE'),
    (780,'WALLET_COLD_RESTORE'),(781,'DAEMON_SAVE'))
WALLET_STEPS = ((689,'WALLET_SETUP'),(692,'PERSISTED_HEIGHT_ZERO'),(695,'HTTP_AUTH'),
    (696,'ADDRESS_ROUNDTRIP'),(702,'FOREIGN_PREFIX_REFUSAL'),(708,'SEVENTEEN_DENIALS'),
    (717,'WALLET_SAVE_EXIT_RELEASE'),(719,'ROTATED_LOGIN'),(723,'WALLET_COLD_RESTORE'))
STEPS = frozenset(code for _,code in MAIN_STEPS+WALLET_STEPS) | {
    'NODE0_START','NODE1_START','READINESS_RPC','CHAIN_GENESIS_GUARD','COMPLETE'}
LABELS = frozenset(REQUIRE_CODES.values()) | {'NONE','OTHER_REQUIRE'}
KEYS = {'step','exception_class','require_label'}
READINESS_KEYS = {'operation','exception_class','http_status','require_label','key_field','attempts'}
OPERATIONS = frozenset(('get_info','pool_hashes','pool_stats','OTHER_OPERATION'))
FIELDS = frozenset(('status','height','top_block_hash','wide_cumulative_difficulty',
    'tx_hashes','pool_stats','txs_total','NONE','OTHER_FIELD'))


def checked_readiness(value):
    return (isinstance(value,dict) and value.keys()==READINESS_KEYS and
        isinstance(value['operation'],str) and value['operation'] in OPERATIONS and
        isinstance(value['exception_class'],str) and value['exception_class'] in EXCEPTIONS and
        type(value['http_status']) is int and (value['http_status']==0 or 100<=value['http_status']<=599) and
        isinstance(value['require_label'],str) and value['require_label'] in LABELS and
        isinstance(value['key_field'],str) and value['key_field'] in FIELDS and
        type(value['attempts']) is int and 1<=value['attempts']<=1000000)


def readiness_failure(error, operation, require, http_status=0):
    """Attach only fixed tokens; keep the exception chain in private custody."""
    prior=getattr(error,'readiness',None)
    if checked_readiness(prior):return prior
    codes=exception_codes(error,require)
    cause=error.__cause__
    status=getattr(cause if cause is not None else error,'code',http_status)
    field=error.args[0] if isinstance(error,KeyError) and error.args else 'NONE'
    value=dict(operation=operation if operation in OPERATIONS else 'OTHER_OPERATION',
        exception_class=codes['exception_class'],require_label=codes['require_label'],
        http_status=status if type(status) is int and 100<=status<=599 else 0,
        key_field=field if isinstance(field,str) and field in FIELDS else 'OTHER_FIELD',attempts=1)
    error.readiness=value
    return value


def checked(value):
    return (isinstance(value,dict) and (value.keys()==KEYS or
        (value.keys()==KEYS|{'readiness'} and checked_readiness(value['readiness']))) and
        isinstance(value['step'],str) and value['step'] in STEPS and
        isinstance(value['exception_class'],str) and value['exception_class'] in EXCEPTIONS and
        isinstance(value['require_label'],str) and value['require_label'] in LABELS)


def exception_codes(error, require):
    label='NONE'
    tb=error.__traceback__
    while tb:
        if tb.tb_frame.f_code is require.__code__:
            message=tb.tb_frame.f_locals.get('message')
            label=REQUIRE_CODES.get(message,'OTHER_REQUIRE') if isinstance(message,str) else 'OTHER_REQUIRE'
        tb=tb.tb_next
    name=type(error).__name__
    result=dict(exception_class=name if name in EXCEPTIONS else 'OTHER_EXCEPTION',require_label=label)
    readiness=getattr(error,'readiness',None)
    if checked_readiness(readiness):result['readiness']=dict(readiness)
    return result


def install(driver, require):
    driver=str(driver)
    state=dict(step='SETUP',exception_class='NONE',require_label='NONE')
    emitted=False
    previous=sys.gettrace()
    def publish(frame):
        nonlocal emitted
        if emitted:return
        emitted=True
        public=frame.f_globals['PUBLIC']
        fd=os.open(public/'runtime-diagnostics.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as stream:stream.write(json.dumps(state)+'\n')
    def trace(frame,event,arg):
        if frame.f_code.co_filename != driver:return None
        name=frame.f_code.co_name
        if event=='line' and state['exception_class']=='NONE':
            line=frame.f_lineno
            table=MAIN_STEPS if name=='main' and line<792 else WALLET_STEPS if name=='wallet_controls' else ()
            for first,code in reversed(table):
                if line>=first:state['step']=code;break
            if name=='node' and state['step'] in {'NODE0_START','NODE1_START','READINESS_RPC'}:
                if line<=297:state['step']='NODE0_START' if frame.f_locals.get('index')==0 else 'NODE1_START'
                else:state['step']='READINESS_RPC'
            if name=='isolation' and line>=395:state['step']='CHAIN_GENESIS_GUARD'
        if name=='main' and event=='exception' and not emitted:
            state.update(exception_codes(arg[1],require));publish(frame)
        elif name=='main' and event=='return':
            if not emitted:
                state['step']='COMPLETE' if arg==0 else state['step'];publish(frame)
            sys.settrace(previous)
        return trace
    sys.settrace(trace)
    return trace
