"""Narrow privileged helper COMMAND INTERFACE, not an installed host service.

Command construction and binding validation only. No shell, sudo, installation,
host probing, original-lock acquisition, subprocess or activation in this module.
The operator must bind identities and qualify the server before these plans can
be executed. Missing bindings cannot be replaced with caller-provided commands.
"""
import re
from pathlib import PurePosixPath

import profile_contract as c
import profile_manager as m

GIB = 1024**3
OPERATIONS = ('retain', 'first_admission', 'quarantine', 'provision', 'recover', 'observe_after_exit')
CONTROL_PATHS = {'manager', 'ledger', 'log', 'export'}
WORK_PATHS = {'docker', 'exec', 'tmp', 'private', 'attempt', 'public'}


def absolute(value):
    c.require(type(value) is str and value.startswith('/') and
              not any(x in value for x in ('\n', '\x00', '%', ' ', '\t')) and
              str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts,
              'canonical absolute bound path required')
    return PurePosixPath(value)


def fixed_disk(disk, allowance):
    """Check a frozen identity declaration; actual host enforcement is unqualified."""
    root, backing = absolute(disk['mount']), absolute(disk['backing'])
    c.require(root != PurePosixPath('/') and root != backing and not backing.is_relative_to(root),
              'backing must be separately bound on root ext4')
    for key in ('backing_inode', 'length', 'allocated_bytes', 'filesystem_capacity',
                'filesystem_device', 'loop_device', 'mount_id', 'namespace_inode'):
        c.require(type(disk[key]) is int and disk[key] > 0, 'positive fixed disk identity/capacity')
    for key in ('owner_uid', 'owner_gid', 'backing_mode', 'mount_mode', 'nlink', 'backing_device'):
        c.require(type(disk[key]) is int, 'integer disk ownership/mode/identity')
    c.require(disk['backing_filesystem'] == 'ext4' and disk['backing_device'] == 66306 and
              disk['filesystem'] == 'ext4' and disk['fully_allocated'] is True and
              disk['length'] == allowance and disk['allocated_bytes'] == allowance and
              disk['filesystem_capacity'] <= allowance and disk['nlink'] == 1,
              'fixed fully allocated ext4 backing required')
    c.require(bool(re.fullmatch(r'/dev/loop[0-9]+', disk['loop'])), 'explicit owned loop required')
    c.require(disk['owner_uid'] == 0 and disk['owner_gid'] == 0 and
              disk['backing_mode'] == 0o600 and disk['mount_mode'] == 0o700 and
              disk['identity_mutable'] is False, 'private immutable operator-bound disk identity')
    return root


def storage_fit(value):
    """Pure fit/refusal check, with no allocation, host discovery or authority."""
    allocation = value.get('allocation')
    c.require(type(allocation) is dict and set(allocation) == {'control', 'workload', 'archive', 'other'},
              'complete charged storage split required')
    c.require(all(type(x) is int and 0 <= x <= c.LIMITS['disk_hard_bytes'] for x in allocation.values()) and
              allocation['control'] > 0 and allocation['workload'] > 0,
              'positive bounded control/workload allocations required')
    residual = c.LIMITS['disk_hard_bytes'] - sum(allocation[x] for x in ('control', 'archive', 'other'))
    c.require(0 < allocation['workload'] <= residual, 'combined storage exceeds 15 GiB')
    c.require('control_disk' in value, 'independent persistent control identity required')
    control, work = value['control_disk'], value['disk']
    control_root = fixed_disk(control, allocation['control'])
    work_root = fixed_disk(work, allocation['workload'])
    c.require(not control_root.is_relative_to(work_root) and not work_root.is_relative_to(control_root),
              'control and workload mounts must be disjoint')
    for key in ('backing', 'backing_inode', 'filesystem_device', 'loop', 'loop_device', 'mount_id'):
        c.require(control[key] != work[key], 'control and workload identities must be distinct')
    c.require(control['namespace_inode'] == work['namespace_inode'], 'one bound private namespace')
    for disk in (control, work):
        c.require(not any(absolute(disk['backing']).is_relative_to(root) for root in (control_root, work_root)),
                  'backing cannot be writable through either task mount')
    c.require(value.get('control_identity_sha256') == c.digest(c.canonical(control)),
              'control identity differs from frozen custody binding')
    c.require(control['writable_by_workload'] is False and control['prepared_before_first_admission'] is True and
              control['retention'] == 'explicit_authorized_disposition_only' and
              control['restart'] == 'recovery_only' and control['missing_or_corrupt'] == 'quarantine_never_rearm' and
              all(type(control.get(k)) is str and control[k] for k in ('custodian', 'custody_receipt')),
              'persistent independent control custody and quarantine policy required')
    reserves = value.get('control_reserves')
    c.require(type(reserves) is dict and set(reserves) == {'state', 'log', 'export', 'overhead'} and
              all(type(x) is int and x > 0 for x in reserves.values()), 'bounded control reserves required')
    c.require(sum(reserves.values()) <= allocation['control'] and
              sum(reserves[x] for x in ('state', 'log', 'export')) <= control['filesystem_capacity'],
              'control payload/metadata reserves do not fit')
    c.require(set(value['writes']) == CONTROL_PATHS | WORK_PATHS, 'all writable locations must be bound')
    for name, path in value['writes'].items():
        root = control_root if name in CONTROL_PATHS else work_root
        c.require(absolute(path) == root/name, 'writable task path outside its charged allocation')
    c.require(0 < value['offline_image']['length'] <= allocation['archive'], 'archive exceeds charged allowance')
    archive = absolute(value['offline_image']['path'])
    c.require(not any(archive.is_relative_to(root) for root in (control_root, work_root)) and
              str(archive) not in (control['backing'], work['backing']), 'separate sealed archive required')
    return dict(charged_bytes=sum(allocation.values()), residual_workload_bytes=residual,
                control_identity_sha256=value['control_identity_sha256'])


def validate_binding(value):
    c.require(value['schema'] == 'meownero-rootful-helper-binding/2', 'helper binding schema')
    attempt = value['attempt_id']
    c.require(bool(re.fullmatch(r'[0-9a-f]{32}', attempt)), 'fixed task attempt id')
    for key in ('operator', 'authority_comment', 'systemd_version', 'helper_source_sha256', 'preparation_receipt'):
        c.require(type(value[key]) is str and bool(value[key]), 'missing operator/source/preparation binding')
    c.require(bool(re.fullmatch(r'[0-9a-f]{64}', value['helper_source_sha256'])), 'helper source digest')
    c.require(value['original_lock'] == list(c.LOCK_ID) and value['limits'] == c.LIMITS,
              'original lock or aggregate limits changed')
    storage_fit(value)
    c.require(value['writable_escape'] is False and value['shared_sockets_visible'] is False,
              'no writable host or shared socket escape')
    image = value['offline_image']
    c.require(image['image_id'] == m.IMAGE and image['architecture'] == 'amd64' and
              image['os'] == 'linux' and image['read_only'] is True and image['immutable'] is True and
              image['length'] > 0 and image['device'] > 0 and image['inode'] > 0 and
              bool(image['provenance']) and bool(re.fullmatch(r'[0-9a-f]{64}',image['sha256'])),
              'exact immutable offline image identity/provenance required')
    parent = str(absolute(value['cgroup_parent']))
    c.require(parent.endswith('/meownero-TJS2504-'+attempt) and parent != '/' and
              value['existing_delegation'] is True, 'task-only existing delegation required')
    return value


def command_manifest(value, *, consumption):
    """Exact argv and cgroup writes for review; never execute this return value."""
    validate_binding(value)
    c.require(consumption['attempt_id'] == value['attempt_id'] and consumption['bindings'] == value['bindings'] and
              consumption['control_identity_sha256'] == value['control_identity_sha256'] and
              consumption['first_admission'] == 'PASS' and consumption['manager_state'] == 'QUARANTINED' and
              consumption['local_state'] == 'CONSUMED', 'durable admission/quarantine/consumption before workload provisioning')
    disk, writes = value['disk'], value['writes']
    root, loop = disk['mount'], disk['loop']
    parent = '/sys/fs/cgroup'+value['cgroup_parent']
    # These are post-consumption WORKLOAD commands. Preparing the separate
    # control mount/slot needs an operator interface this source does not supply.
    return dict(schema='meownero-helper-command-manifest/2', source_only=True,
        operations=list(OPERATIONS), activation='REFUSED_UNQUALIFIED',
        storage_fit=storage_fit(value), control_retained=value['control_disk'],
        setup=[['/usr/bin/mount','--make-rprivate','/'],
               ['/usr/sbin/losetup','--sizelimit',str(disk['length']),loop,disk['backing']],
               ['/usr/bin/mount','-t','ext4','-o','nosuid,nodev',loop,root]],
        cgroup_writes={parent+'/cpu.max':'200000 100000', parent+'/memory.max':str(4*GIB),
            parent+'/memory.swap.max':'0', parent+'/pids.max':'256',parent+'/memory.oom.group':'0',
            parent+'/cgroup.subtree_control':'+cpu +memory +pids',
            parent+'/work/memory.max':str(3840*1024**2), parent+'/work/memory.oom.group':'1',
            parent+'/work/pids.max':'224',parent+'/work/memory.swap.max':'0',
            parent+'/recovery/memory.max':str(256*1024**2),parent+'/recovery/pids.max':'32',
            parent+'/recovery/memory.swap.max':'0',parent+'/recovery/memory.oom.group':'0'},
        daemon=['/usr/bin/dockerd','--host=unix://'+writes['exec']+'/docker.sock',
            '--data-root='+writes['docker'],'--exec-root='+writes['exec'],
            '--pidfile='+writes['exec']+'/dockerd.pid','--config-file='+writes['manager']+'/daemon.json',
            '--exec-opt=native.cgroupdriver=cgroupfs','--cgroup-parent='+value['cgroup_parent']+'/work',
            '--bridge=none','--iptables=false','--ip6tables=false','--ip-forward=false',
            '--ip-masq=false','--userland-proxy=false','--storage-driver=vfs'],
        import_image=['/usr/bin/docker','--host=unix://'+writes['exec']+'/docker.sock',
                      'image','load','--input',value['offline_image']['path']],
        daemon_config={'log-driver':'none','features':{'containerd-snapshotter':False}},
        environment={'HOME':writes['private'],'TMPDIR':writes['tmp'],'XDG_RUNTIME_DIR':writes['exec'],
                     'PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'C','DOCKER_CONFIG':writes['private']+'/docker-client'},
        work_abort_write={parent+'/work/cgroup.kill':'1'},
        cleanup=[['/usr/bin/umount','--',root],['/usr/sbin/losetup','--detach',loop]],
        forbidden=['shared_docker_socket','shared_caller_unit_changes','pull','save','shell',
                   'lazy_unmount','force_unmount','bulk_process_kill','delete_backing_or_manager_slot'],
        setup_preconditions=['private_namespace_identity_checked', 'exact_loop_unused',
            'backing_not_associated_with_any_other_loop', 'backing_identity_and_full_allocation_checked',
            'no_automatic_find_or_reuse_of_an_existing_loop'],
        detach_postcondition='independently_observe_owned_loop_backing_association_absent_within_deadline',
        ordering=['bounded_control_preparation_and_reserved_slot_receipt','authenticate_grant_and_reviews','retain_and_pid1_readback',
            'first_fresh_admission','durable_manager_quarantine','local_consumed_ledger',
            'setup_and_image_import','controller','atomic_second_admission_and_create',
            'stop_exact_cid_and_owned_pid_start_pairs','work_population_zero','export_allowlist',
            'recovery_exit','independent_observer','unmount_and_detach','release_all_lock_copies',
            'independent_original_inode_acquire_then_close'],
        limitations=['A command list is not a helper server, authority, installation or host qualification.',
                     'Control preparation and workload allocation/formatting need the absent operator-bound server.',
                     'Retained control capacity and archive/preparation copies remain charged after workload cleanup.',
                     'The v3 controller uses only the typed helper channel; host qualification remains absent.'])


def unit_contract(value):
    """Task-specific properties for operator review, not an installable unit."""
    validate_binding(value)
    return {'unit':'meownero-TJS2504-'+value['attempt_id']+'.service',
        'aggregate_slice':{'CPUQuota':'200%','MemoryMax':str(4*GIB),'MemorySwapMax':'0','TasksMax':'256'},
        'keeper_service':{'FileDescriptorStoreMax':'2','FileDescriptorStorePreserve':'yes',
            'NotifyAccess':'main','Restart':'on-failure','RestartSec':'1', 'OOMPolicy':'continue',
            'MemoryMax':str(256*1024**2),'MemorySwapMax':'0','TasksMax':'32',
            'ProtectSystem':'strict','PrivateMounts':'yes','PrivateTmp':'no',
            'StandardOutput':'null','StandardError':'null','LimitCORE':'0'},
        'unresolved':['exact ExecStart/server and independent deadline owner',
            'surviving namespace custody and recovery reentry',
            'bounded PID1 FD-store/kernel overhead accounting and actual retain readback',
            'root helper capability/seccomp/mount confinement and denial of shared Unix sockets',
            'final observer accounting and original-lock release witness after recovery exit'],
        'native_execution':'NOT_RUN'}


def validate_recovery(witness, binding):
    """Reject cleanup claims that omit or act on unowned resources."""
    validate_binding(binding)
    c.require(witness['attempt_id'] == binding['attempt_id'] and
              witness['namespace_inode'] == binding['disk']['namespace_inode'] and
              witness['loop_device'] == binding['disk']['loop_device'] and
              witness['mount_id'] == binding['disk']['mount_id'], 'recovery identity changed')
    c.require(witness['work_population'] == 0 and witness['daemon_helpers'] == [] and
              witness['remaining_cids'] == [] and witness['remaining_owned_pid_start_pairs'] == [],
              'owned recovery incomplete')
    c.require(witness['local_ledger_removed'] is False and witness['manager_slot_removed'] is False and
              witness['lock_still_held'] is True and witness['control_retained'] is True and
              witness['control_identity_sha256'] == binding['control_identity_sha256'],
              'recovery must preserve independent control journal and lock custody')
    return witness


if __name__ == '__main__':
    # No execute/install option: even a root caller cannot activate via this
    # source artifact. No environment-supplied command or privilege discovery.
    import json
    print(json.dumps(m.source_status(), indent=2))
    raise SystemExit(3)
