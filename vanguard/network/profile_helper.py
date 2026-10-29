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


def absolute(value):
    c.require(type(value) is str and value.startswith('/') and
              not any(x in value for x in ('\n', '\x00', '%', ' ', '\t')) and
              str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts,
              'canonical absolute bound path required')
    return PurePosixPath(value)


def validate_binding(value):
    c.require(value['schema'] == 'meownero-rootful-helper-binding/1', 'helper binding schema')
    attempt = value['attempt_id']
    c.require(bool(re.fullmatch(r'[0-9a-f]{32}', attempt)), 'fixed task attempt id')
    for key in ('operator', 'authority_comment', 'systemd_version', 'helper_source_sha256', 'preparation_receipt'):
        c.require(type(value[key]) is str and bool(value[key]), 'missing operator/source/preparation binding')
    c.require(bool(re.fullmatch(r'[0-9a-f]{64}', value['helper_source_sha256'])), 'helper source digest')
    c.require(value['original_lock'] == list(c.LOCK_ID) and value['limits'] == c.LIMITS,
              'original lock or aggregate limits changed')
    disk = value['disk']
    root = absolute(disk['mount'])
    backing = absolute(disk['backing'])
    c.require(root != backing and root != PurePosixPath('/') and not backing.is_relative_to(root),
              'backing must be separately bound on root ext4')
    c.require(disk['backing_filesystem'] == 'ext4' and disk['backing_device'] == 66306 and
              type(disk['backing_inode']) is int and disk['backing_inode'] > 0 and
              disk['fully_allocated'] is True and 0 < disk['length'] <= 15*GIB and
              disk['allocated_bytes'] >= disk['length'], 'fixed fully allocated ext4 backing required')
    c.require(disk['filesystem'] == 'ext4' and disk['filesystem_capacity'] <= disk['length'] and
              disk['filesystem_capacity'] > 0 and disk['nlink'] == 1,
              'fixed filesystem hard limit or identity differs')
    c.require(bool(re.fullmatch(r'/dev/loop[0-9]+', disk['loop'])) and
              type(disk['loop_device']) is int and disk['loop_device'] > 0 and
              type(disk['mount_id']) is int and disk['mount_id'] > 0 and
              type(disk['namespace_inode']) is int and disk['namespace_inode'] > 0,
              'owned loop/mount/private namespace identities required')
    expected_paths = {'manager','ledger','log','export','docker','exec','tmp','private','attempt','public'}
    c.require(set(value['writes']) == expected_paths, 'all writable locations must be bound')
    for name, path in value['writes'].items():
        c.require(absolute(path) == root/name, 'writable task path outside fixed disk')
    c.require(value['writable_escape'] is False and value['shared_sockets_visible'] is False,
              'no writable host or shared socket escape')
    image = value['offline_image']
    c.require(image['image_id'] == m.IMAGE and image['architecture'] == 'amd64' and
              image['os'] == 'linux' and image['read_only'] is True and image['immutable'] is True and
              image['length'] > 0 and image['device'] > 0 and image['inode'] > 0 and
              bool(image['provenance']) and bool(re.fullmatch(r'[0-9a-f]{64}',image['sha256'])),
              'exact immutable offline image identity/provenance required')
    c.require(not absolute(image['path']).is_relative_to(root), 'immutable image is a separate read-only input')
    parent = str(absolute(value['cgroup_parent']))
    c.require(parent.endswith('/meownero-TJS2504-'+attempt) and parent != '/' and
              value['existing_delegation'] is True, 'task-only existing delegation required')
    return value


def command_manifest(value):
    """Exact argv and cgroup writes for review; never execute this return value."""
    validate_binding(value)
    disk, writes = value['disk'], value['writes']
    root, loop = disk['mount'], disk['loop']
    parent = '/sys/fs/cgroup'+value['cgroup_parent']
    # Fixed pid1 FD retention is a kernel descriptor, never another writable
    # ledger. All variable manager/log/export data is on the fixed filesystem.
    return dict(schema='meownero-helper-command-manifest/1', source_only=True,
        operations=list(OPERATIONS), activation='REFUSED_UNQUALIFIED',
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
        environment={'HOME':writes['manager'],'TMPDIR':writes['tmp'],'XDG_RUNTIME_DIR':writes['exec'],
                     'PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'C','DOCKER_CONFIG':writes['manager']+'/docker-client'},
        work_abort_write={parent+'/work/cgroup.kill':'1'},
        cleanup=[['/usr/bin/umount','--',root],['/usr/sbin/losetup','--detach',loop]],
        forbidden=['shared_docker_socket','shared_caller_unit_changes','pull','save','shell',
                   'lazy_unmount','force_unmount','bulk_process_kill','delete_backing_or_manager_slot'],
        setup_preconditions=['private_namespace_identity_checked', 'exact_loop_unused',
            'backing_not_associated_with_any_other_loop', 'backing_identity_and_full_allocation_checked',
            'no_automatic_find_or_reuse_of_an_existing_loop'],
        detach_postcondition='independently_observe_owned_loop_backing_association_absent_within_deadline',
        ordering=['operator_preparation_receipt','authenticate_grant_and_reviews','retain_and_pid1_readback',
            'first_fresh_admission','durable_manager_quarantine','local_consumed_ledger',
            'setup_and_image_import','controller','atomic_second_admission_and_create',
            'stop_exact_cid_and_owned_pid_start_pairs','work_population_zero','export_allowlist',
            'recovery_exit','independent_observer','unmount_and_detach','release_all_lock_copies',
            'independent_original_inode_acquire_then_close'],
        limitations=['A command list is not a helper server, authority, installation or host qualification.',
                     'The legacy inner still refuses the unqualified atomic-create channel.'])


def unit_contract(value):
    """Task-specific properties for operator review, not an installable unit."""
    validate_binding(value)
    return {'unit':'meownero-TJS2504-'+value['attempt_id']+'.service',
        'aggregate_slice':{'CPUQuota':'200%','MemoryMax':str(4*GIB),'MemorySwapMax':'0','TasksMax':'256'},
        'keeper_service':{'FileDescriptorStoreMax':'1','FileDescriptorStorePreserve':'yes',
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
              witness['lock_still_held'] is True, 'recovery must preserve journal and lock custody')
    return witness


if __name__ == '__main__':
    # No execute/install option: even a root caller cannot activate via this
    # source artifact. No environment-supplied command or privilege discovery.
    import json
    print(json.dumps(m.source_status(), indent=2))
    raise SystemExit(3)
