"""Pure, reviewable lifecycle packet. Rendering never inspects the host.

UNBOUND is data, not a substituted execution value. Only a separately qualified
OS adapter can resolve a record; there is no shell or arbitrary-command RPC.
"""
import copy
import re

import profile_contract as c

GIB = 1024**3
MIB = 1024**2
SCHEMA = 'meownero-source-plan/3'
AUTHORIZATION = 'fdf10e5f-7009-466e-b0c5-3fa5dc70c537'
IDENTITIES = ('backing_inode', 'filesystem_device', 'loop', 'loop_device', 'mount_id', 'namespace_inode')
ALLOCATION = dict(control=GIB, workload=11*GIB, archive=2*GIB, other=GIB)
PREPARATION = dict(control=dict(seconds=300, cpu=1, memory=512*MIB, swap=0, pids=32, writes=1536*MIB),
    archive=dict(seconds=900, cpu=1, memory=GIB, swap=0, pids=64, writes=2*GIB, output=2*GIB),
    other_writes=512*MIB, seconds=1200, occupied=4*GIB, writes=4*GIB)
BINDINGS = ('operator', 'authentication_route', 'preparation_authority', 'runtime_grant',
    'platform_review', 'core_review', 'security_review', 'bootstrap_sha256', 'archive_sha256',
    'archive_provenance', 'producer_receipt', 'tool_versions', 'namespace_access',
    'pid1_custody_readback', 'hard_write_enforcement', 'overhead_qualification',
    'lifecycle_authority', 'retained_control_custodian', 'disposition_authority')


def source_plan():
    return dict(schema=SCHEMA, authorization_comment=AUTHORIZATION, attempt_id=None,
        source=dict(commit=None, inputs_sha256=None, artifact_sha256=None, helper_sha256=None),
        authority={key:None for key in BINDINGS}, original_lock=list(c.LOCK_ID), limits=c.LIMITS,
        allocation=ALLOCATION, preparation=PREPARATION,
        planned_storage={name:dict(bytes=size, backing_owner=[0,0], backing_mode=0o600,
            mount_owner=[0,0], mount_mode=0o700,
            observed={key:None for key in IDENTITIES}) for name,size in ALLOCATION.items()},
        ownership=dict(keeper=[0,0], deadline=[0,0], observer=[0,0], manager_slot=[0,0],
            outer=[1000,1000], controller=[1000,1000], native=[1000,1000],
            ledger_directory=[1000,1000], workload_directory=[1000,1000]),
        retained_control=dict(mount_disposition='independent_terminal_handoff_after_journal_and_observer_tail_close',
            storage='retain_backing_slot_tombstone_and_archive', expiry='explicit_separate_disposition_only'),
        overhead=dict(reserved_memory=16*MIB, reserved_pids=2, reserved_cpu_per_second=50_000, qualified=None,
            control_memory=240*MIB, control_pids=30, work_memory=3840*MIB, work_pids=224),
        native_execution='NOT_RUN', launch_ready=False)


def validate_plan(value):
    c.require(set(value) == set(source_plan()), 'exact plan fields')
    c.require(value['schema'] == SCHEMA and value['authorization_comment'] == AUTHORIZATION,
              'source plan schema/authorization')
    c.require(value['limits'] == c.LIMITS and value['original_lock'] == list(c.LOCK_ID), 'unchanged limits/lock')
    for key in ('allocation', 'preparation', 'ownership', 'retained_control', 'overhead'):
        c.require(value[key] == source_plan()[key], 'frozen plan policy: '+key)
    c.require(value['planned_storage'] == source_plan()['planned_storage'],
              'planned identities must remain UNBOUND; observed state is separate')
    c.require(set(value['authority']) == set(BINDINGS) and set(value['source']) == set(source_plan()['source']),
              'complete source/authority binding fields')
    c.require(value['attempt_id'] is None or bool(re.fullmatch('[0-9a-f]{32}',value['attempt_id'])), 'attempt id')
    c.require(value['native_execution'] == 'NOT_RUN' and value['launch_ready'] is False, 'source only')
    return value


def delivery_contract(role):
    modes=dict(prepare='prepare',keeper='serve',deadline='recover',observer='observe')
    c.require(role in modes, 'fixed bootstrap role')
    return dict(schema='meownero-helper-delivery/1', role=role, mode=modes[role],
        transport='unnamed_AF_UNIX_SOCK_SEQPACKET_SCM_RIGHTS_SCM_CREDENTIALS',
        property=['StandardInputFileDescriptor','h'], receiving_fd=0,
        descriptors=['authority','sealed_context']+([] if role=='prepare' else ['retained_namespace']),
        expectation='independently_authenticated_installed_unit_and_surviving_custodian',
        bind=['task','attempt_id','role','mode','invocation_id','source','spec_sha256',
            'contract_sha256','origin','deadlines','sender_credentials','sender_start',
            'delivery_deadline','namespace_identity'],
        one_use='separate_preparation_capability' if role=='prepare' else 'one_fresh_activation' if role=='keeper' else 'role_invocation',
        restart='independently_authenticated_installed_unit_two_named_stored_FDs_recovery_only'
            if role=='keeper' else 'new_role_bound_delivery_or_refuse',
        actual_transport='UNBOUND_NOT_QUALIFIED')


def dockerd_argv():
    """Frozen daemon argv; only its systemd ancestry changes in this pass."""
    return ['/usr/bin/dockerd','--host=unix://$W/root/exec/docker.sock',
        '--data-root=$W/root/docker','--exec-root=$W/root/exec','--pidfile=$W/root/exec/dockerd.pid',
        '--config-file=$C/manager/daemon.json','--exec-opt=native.cgroupdriver=cgroupfs',
        '--cgroup-parent=$WORK_CGROUP','--bridge=none','--iptables=false','--ip6tables=false',
        '--ip-forward=false','--ip-masq=false','--userland-proxy=false','--storage-driver=vfs']


def units(value):
    """Typed systemd255 D-Bus properties, not unit-file string interpolation."""
    validate_plan(value)
    stem = 'meowneroTJS2504'+(value['attempt_id'] or '$ATTEMPT')
    parent, work, control = stem+'.slice', stem+'-work.slice', stem+'-control.slice'
    props = lambda **kw: [[key,kind,val] for key,(kind,val) in kw.items()]
    limits = props(CPUQuotaPerSecUSec=('t',1_950_000), MemoryMax=('t',4080*MIB),
                   MemorySwapMax=('t',0), TasksMax=('t',254))
    rows = [(parent, limits), (work,props(CPUQuotaPerSecUSec=('t',1_900_000), MemoryMax=('t',3840*MIB),
            MemorySwapMax=('t',0), TasksMax=('t',224))),
        (control,props(CPUQuotaPerSecUSec=('t',50_000), MemoryMax=('t',240*MIB), MemorySwapMax=('t',0), TasksMax=('t',30)))]
    prefix = ['$BOUND_PYTHON','-B','$BOUND_HELPER']
    for role,mode in [('keeper','serve'),('deadline','recover'),('observer','observe'),('prepare','prepare')]:
        argv = prefix+[mode,'--bootstrap-role',role,'--spec','$ROOT_OWNED_SPEC','--spec-sha256','$SPEC_SHA256']
        if role == 'deadline': argv += ['--deadline-owner']
        service = props(Type=('s','notify' if role=='keeper' else 'exec'), User=('s','0'), Group=('s','0'),
            Slice=('s',control), ExecStart=('a(sasb)',[['$BOUND_PYTHON',argv,False]]),
            NoNewPrivileges=('b',True), ProtectSystem=('s','strict'), PrivateTmp=('b',False),
            PrivateMounts=('b',True), RestrictAddressFamilies=('(bas)',[True,['AF_UNIX','AF_NETLINK']]),
            CapabilityBoundingSet=('t',2**21 | 2**1 | 2**0 | 2**7 | 2**6),
            StandardInputFileDescriptor=('h','$BOOTSTRAP_'+role.upper()+'_RECEIVE_FD'),
            StandardOutput=('s','null'),StandardError=('s','null'), LimitCORE=('t',0),
            KillMode=('s','process'), TimeoutStopUSec=('t',300_000_000),
            ReadWritePaths=('as',['$C','$W','$O','$A']),
            InaccessiblePaths=('as',['-/run/docker.sock','-/var/run/docker.sock']))
        if role == 'prepare':
            service=[item for item in service if item[0]!='Slice']
            service+=props(Slice=('s',work),CPUQuotaPerSecUSec=('t',1_000_000),MemoryMax=('t',GIB),
                MemorySwapMax=('t',0),TasksMax=('t',64),RuntimeMaxUSec=('t',1_200_000_000))
        if role == 'keeper':
            service += props(FileDescriptorStoreMax=('u',2), FileDescriptorStorePreserve=('s','yes'),
                NotifyAccess=('s','main'), Restart=('s','on-failure'), RestartUSec=('t',1_000_000),
                OOMPolicy=('s','continue'))
        # Each child reenters the retained namespace using the named FD. The
        # initial PrivateMounts namespace alone never establishes shared custody.
        rows.append((stem+'-'+role+'.service',service))
    # PID1, not the keeper, starts dockerd. The keeper's inherited socket filter
    # must never become the workload's filter. Mount-view delivery still needs
    # exact authorized namespace/custody bindings and independent qualification.
    rows.append((stem+'-workload.service',props(Type=('s','exec'), User=('s','0'), Group=('s','0'),
        Slice=('s',work),ExecStart=('a(sasb)',[['/usr/bin/dockerd',dockerd_argv(),False]]),
        RestrictAddressFamilies=('(bas)',[True,['AF_UNIX','AF_NETLINK','AF_INET']]),
        KillMode=('s','control-group'),TimeoutStopUSec=('t',20_000_000),
        NoNewPrivileges=('b',True),ProtectSystem=('s','strict'),PrivateTmp=('b',False),
        PrivateMounts=('b',True),ReadWritePaths=('as',['$W']),ReadOnlyPaths=('as',['$C']),
        InaccessiblePaths=('as',['-/run/docker.sock','-/var/run/docker.sock']),
        StandardOutput=('s','null'),StandardError=('s','null'),LimitCORE=('t',0))))
    return [dict(stage=('work' if '-workload.service' in name else 'preparation_supervisor' if '-prepare.service' in name else
        'activation' if name.endswith('.service') else 'install'),bus='org.freedesktop.systemd1', path='/org/freedesktop/systemd1',
        interface='org.freedesktop.systemd1.Manager', member='StartTransientUnit',
        signature='ssa(sv)a(sa(sv))', args=[name,'fail',properties,[]],
        delivery=delivery_contract(name.rsplit('-',1)[-1].removesuffix('.service'))
            if name.endswith('.service') and '-workload.service' not in name else None) for name,properties in rows]


def operation_deadline(value,record,binding):
    """Original authenticated clocks, never a duration renewed at issuance.

    Preparation origins belong to the independently supplied launch binding.
    Active work cannot consume the exclusive cleanup reserve. The renderer's
    record limit and the enclosing phase limit both apply.
    """
    import math
    c.require(type(record) is int and 0<=record<54,'no automatic disposition deadline')
    c.require(set(binding)=={'contract_sha256','inputs_sha256','origin','deadlines','preparation'},
        'complete original operation clock binding')
    origin=binding['origin'];ends=binding['deadlines'];prep=binding['preparation']
    c.require(type(origin) in (int,float) and math.isfinite(origin) and
        ends==dict(build=origin+3600,work=origin+4200,end=origin+4500) and
        set(prep)=={'origin','archive_origin'} and
        all(type(x) in (int,float) and math.isfinite(x) for x in prep.values()) and
        prep['origin']<=prep['archive_origin']<=prep['origin']+1200,
        'unchanged original preparation and runtime clocks')
    row=render(value)['records'][record]
    limits={'prep_origin+1200':prep['origin']+1200,'prep_origin+300':prep['origin']+300,
        'archive_origin+900':min(prep['archive_origin']+900,prep['origin']+1200),
        'origin+3600':ends['build'],'origin+4200':ends['work'],'origin+4500':ends['end']}
    c.require(row['deadline'] in limits,'frozen record deadline')
    phase=row['phase']
    phase_end=(ends['end'] if phase in ('cleanup','completion') else
        ends['work'] if row['operation'] in ('outer','controller','start_and_wait') else
        limits[row['deadline']] if phase in ('install','preparation_supervisor','control','archive') else ends['build'])
    return min(limits[row['deadline']],phase_end,ends['end'])


def receiver_unit(value,record,endpoint_fd,*,operation_cutoff,now):
    """Source interface: one retained, non-restarting exact root receiver."""
    validate_plan(value)
    c.require(value['attempt_id'] is not None and type(record) is int and 0<=record<54 and
        type(endpoint_fd) is int and endpoint_fd>=0,'bound original receiver record/descriptor')
    import math
    c.require(all(type(x) in (int,float) and math.isfinite(x) for x in (operation_cutoff,now)) and
        now<operation_cutoff,'unexhausted original receiver operation cutoff')
    remaining=int((operation_cutoff-now)*1_000_000)
    c.require(0<remaining<2**64,'bounded supplementary relative receiver lifetime')
    stem='meowneroTJS2504'+value['attempt_id']
    properties=[['Type','s','exec'],['User','s','0'],['Group','s','0'],
        ['Slice','s',stem+'-control.slice'],['Restart','s','no'],['RemainAfterExit','b',True],['AddRef','b',True],
        ['ExecStart','a(sasb)',[['/usr/bin/python3',['/usr/bin/python3','-I','-B',
            '/opt/meownero/TJS-2504/helper/profile-root-helper.py'],False]]],
        ['StandardInputFileDescriptor','h',endpoint_fd],['StandardOutput','s','null'],
        ['StandardError','s','null'],['LimitCORE','t',0],['NoNewPrivileges','b',True],
        ['RestrictAddressFamilies','(bas)',[True,['AF_UNIX','AF_NETLINK']]],
        ['KillMode','s','control-group'],['RuntimeMaxUSec','t',remaining]]
    return dict(bus='org.freedesktop.systemd1',path='/org/freedesktop/systemd1',
        interface='org.freedesktop.systemd1.Manager',member='StartTransientUnit',
        signature='ssa(sv)a(sa(sv))',args=[stem+'-root'+str(record)+'.service','fail',properties,[]])


def render(value):
    validate_plan(value)
    records=[]
    def row(phase,kind,operation,args,*,uid=0,write=(),pre=(),identity=(),deadline=None):
        records.append(dict(sequence=len(records),phase=phase,kind=kind,operation=operation,args=args,
            uid=uid,gid=uid, writable=list(write), created_or_checked=list(identity),
            charge='C' if phase=='control' else 'A' if phase=='archive' else 'O' if phase in ('install','preparation_supervisor','dispose') else 'W+C',
            deadline=deadline or {'control':'prep_origin+300','archive':'archive_origin+900',
                'install':'prep_origin+1200','preparation_supervisor':'prep_origin+1200','dispose':'separate_authority.absolute_deadline'}.get(phase,'origin+4500'),
            environment={'LC_ALL':'C','PATH':'$PINNED_TOOL_PATH','MKE2FS_CONFIG':'$FROZEN_MKE2FS_CONFIG'},
            preconditions=list(pre), failure='durable_quarantine; bounded_failure_class; retain_owned_identities_and_custody',
            recovery='recover_only_original_deadlines; never_replace_slot_or_rearm'))
    row('install','syscall','verify_inherited_authority',[],pre=['exact_source_spec_hashes','independent_reviews',
        'noninteractive_task_only_authority','tool_hashes_versions','hard_C_W_A_O_limits_and_write_meter',
        'PID1_kernel_and_observer_tail_fit_reserved_16MiB_2PID_0.05CPU'])
    row('install','syscall','install_exact_owned_source',['openat(O_EXCL|O_NOFOLLOW)','$BOUND_HELPER_AND_SPEC_BYTES',
        'verify_hashes','fchown(0,0)','fchmod(0444)','fsync(file_and_directory)'],write=['O:installed_source_copies'],
        pre=['task_only_install_parent_fd','no_dependencies_or_shared_unit_changes'],identity=['installed_source_inodes_hashes'])
    for call in units(value):
        if call['args'][0].endswith('-workload.service'):
            continue  # W provisioning and namespace view must precede dockerd.
        if call['delivery'] is not None:
            row(call['stage'],'syscall','bootstrap_delivery',call['delivery'],
                pre=['authenticated_receiver_role_invocation_and_surviving_custodian',
                    'delivery_pair_receiver_SO_PASSCRED_sender_without_autobind_CLOEXEC',
                    'bounded_sendmsg_SCM_RIGHTS_exact_descriptor_order',
                    'independent_one_use_preparation_or_first_serve_or_role_capability',
                    'keeper_restart_uses_installed_recovery_never_packet_timeout_fallback'],
                identity=['sender_PID_start','role_invocation','original_contract_deadlines',
                    'receiving_endpoint_DBus_UnixFD_to_fd0'])
        row(call['stage'],'dbus',call['member'],call,write=['O:unit_metadata'],identity=['task_only_unit_name'])
    row('control','syscall','unshare',['CLONE_NEWNS'],identity=['mount_namespace_inode'])
    row('control','argv','mount',['/usr/bin/mount','--make-rprivate','/'],pre=['private_namespace'])
    for phase,area,blocks in [('control','C',GIB//4096),('work','W',11*GIB//4096)]:
        pre=['exact_owned_parent_dirfd','nonexistent_target','hard_write_and_capacity_meter']
        if area=='W': pre+=['first_admission_fresh_through_consumption','manager_QUARANTINED','local_CONSUMED']
        row(phase,'syscall','openat',['$'+area+'_PARENT_FD','$'+area+'_BASENAME',
            'O_CREAT|O_EXCL|O_NOFOLLOW|O_RDWR|O_CLOEXEC',0o600],write=[area],pre=pre,identity=[area+'_backing_dev_inode_nlink'])
        row(phase,'syscall','posix_fallocate',['$'+area+'_FD',0,blocks*4096],write=[area],
            pre=['identity_regular_nlink1_root0600','allocated_blocks_and_length_readback'],identity=[area+'_allocated_bytes'])
        row(phase,'argv','mke2fs',['/usr/sbin/mke2fs','-t','ext4','-b','4096','-m','0','-E',
            'lazy_itable_init=0,lazy_journal_init=0,nodiscard','/proc/self/fd/$'+area+'_FD',str(blocks)],
            write=[area],pre=['new_owned_verified_target','frozen_mke2fs_config_hash','pass_only_verified_backing_fd'],identity=[area+'_filesystem_uuid_capacity'])
        row(phase,'argv','losetup',['/usr/sbin/losetup','--sizelimit',str(blocks*4096),'$'+area+'_UNUSED_LOOP','$'+area+'_BACKING'],
            write=[area],pre=['explicit_loop_unused_no_find_or_reuse','backing_exact_identity'],identity=[area+'_loop_device_association'])
        row(phase,'argv','mount',['/usr/bin/mount','-t','ext4','-o','nosuid,nodev','$'+area+'_LOOP','$'+area],
            write=[area],identity=[area+'_mount_id_namespace_inode'])
        row(phase,'syscall','mkdirat_chown_fsync',['$'+area+'_FD',
            ['manager','ledger','log','export'] if area=='C' else ['root','user_bind_source'],
            [0,0] if area=='C' else {'root':[0,0],'user_bind_source':[1000,1000]}],write=[area],identity=[area+'_directory_identities'])
    row('work','syscall','bind_user_directory',['mount_bind_owned_user_subdirectory_to_task_accessible_mountpoint',
        'task_mount_namespace_contains_no_C_root_or_Docker_socket'],write=['W'],identity=['W_user_mount_dev_inode'],
        pre=['W_backing_root0600','W_private_mount_root0700','user_bind_endpoint_uid1000_mode0700'])
    row('control','syscall','ledger_dirfd_handoff',['openat(C,ledger); fchown(1000,1000); fchmod(0700); SCM_RIGHTS'],
        write=['C:ledger'],pre=['outer_has_no_C_path_traversal','ledger_FD_identity_in_authenticated_context'],identity=['ledger_directory_dev_inode_uid_mode'])
    row('control','syscall','reserve_slot',['openat(O_EXCL|O_NOFOLLOW,0600)','write RESERVED+source+activation_hash',
        'fsync(file)','fsync(directory)','readback_exact_identity_bytes'],write=['C:manager'],identity=['root_slot_dev_inode_digest'])
    row('archive','syscall','bounded_archive',['inherited_immutable_archive_fd_or_exact_authorized_producer',
        'exclusive_bounded_output_fd','independent_cumulative_write_meter','sha256+provenance+config+layers+linux/amd64',
        'fsync+readonly_custody'],write=['A'],pre=['payload_plus_metadata_and_copies<=2GiB',
            'producer_identity_and_hard_bound','no_shared_daemon_export'],identity=['archive_dev_inode_size_sha256'])
    row('custody','syscall','sd_notify',['FDSTORE=1; FDNAME=original-lock','SCM_RIGHTS(lock_fd)',
        'FDSTORE=1; FDNAME=mount-namespace','SCM_RIGHTS(namespace_fd)','BARRIER=1',
        'independent_PID1_fdinfo_same_flock_description_and_namespace_readback'],pre=['root_keeper_main_pid_start'],
        identity=['PID1_lock_witness','PID1_namespace_witness'])
    row('custody','syscall','arm_deadline',['independent_deadline_owner','original_origin+3600/+4200/+4500'],
        pre=['durable_original_origin','no_restart_time_reset'])
    row('admission','syscall','first_admission_quarantine_consume',['full_observation_started_at',
        'durable_manager_quarantine','task_uid1000_openat_ledger_dirfd_O_EXCL','fsync_file_directory_readback'],
        pre=['elapsed_from_first_observed_field_through_consumption<=5sec','before_build_deadline'])
    row('work','syscall','workload_namespace_view',['authenticated_retained_namespace_C_readonly_W_writable',
        'PID1_workload_unit_mount_view_before_ExecStart','no_keeper_child_exec'],
        pre=['exact_C_W_namespace_identities','independent_installed_binding_qualification'],
        identity=['workload_mount_view_C_W_devices_inodes'])
    workload_call=units(value)[-1]
    row('work','dbus','StartTransientUnit',workload_call,write=['O:unit_metadata','W:root'],
        pre=['manager_QUARANTINED','local_CONSUMED','W_mounted_exact_identity',
            'qualified_workload_namespace_view_before_ExecStart','frozen_config_log_none',
            'private_root_socket_0600','PID1_not_keeper_child_exec'],identity=['task_only_workload_unit'])
    row('work','syscall','place_before_exec',['work_slice_leaf.cgroup.procs','controller_children_only; dockerd_uses_workload_Slice'],
        pre=['work_memory3840MiB_pids224_OOMgroup1','control240MiB30PID','reserved16MiB2PID'])
    row('work','docker','load',['private_socket','image','load','--input','$SEALED_ARCHIVE'],write=['W:root'],
        pre=['sealed_archive_digest_provenance','hard_W_bound','no_pull_save'])
    row('work','docker','inspect_image',['private_socket','image','inspect','$FIXED_IMAGE'],pre=['exact_image_id_config_layers_linux_amd64'])
    row('activation','syscall','place_outer_before_exec',['task_uid1000_outer_leaf.cgroup.procs'],
        pre=['task_only_work_slice_exists','no_source_or_native_staging','no_supplementary_groups'])
    row('activation','argv','outer',['$BOUND_PYTHON','-B','$BOUND_RUN_OUTER','--inputs','$BOUND_INPUTS',
        '--capabilities','$BOUND_CAPABILITIES','--context-fd','$STARTUP_CONTEXT_FD',
        '--helper-fd','$HELPER_FD','--ledger-directory-fd','$LEDGER_DIRECTORY_FD'],uid=1000,write=['C:ledger'],
        pre=['sealed_authenticated_startup_context','uid1000_directory_FD_only_no_C_path','allowlisted_environment',
            'original_origin_from_context','no_activation_on_restart'],deadline='origin+4200')
    row('work','argv','controller',['$BOUND_PYTHON','-B','$BOUND_RUN_PROFILE','--inputs','$BOUND_INPUTS',
        '--grant-comment','$GRANT_ID','--artifact-sha256','$ARTIFACT_SHA256','--context-fd','$CONTEXT_FD',
        '--lock-fd','$LOCK_FD','--ledger-fd','$LEDGER_FD','--helper-fd','$HELPER_FD'],uid=1000,write=['W:user'],
        pre=['only_four_inherited_FDs','sealed_context','no_Docker_socket','allowlisted_environment','no_supplementary_groups'],
        deadline='origin+4200')
    row('work','docker','observe_and_create',['prevalidate_hash_fixed_CreateSpec',
        'burn_request','full_fresh_observe','create_with_remaining_absolute_timeout','record_CID_even_late_or_ambiguous'],
        write=['W:root','C:manager'],pre=['observation_start_to_create_completion<=5sec','completion<origin+3600'],deadline='origin+3600')
    row('work','docker','start_and_wait',['exact_owned_CID','build_then_runtime_sentinel_only','bounded_output'],write=['W'],deadline='origin+4200')
    row('cleanup','docker','remove_owned',['inspect_exact_CID_and_ownership','stop','rm','independent_absence_readback'],write=['W','C:log'])
    row('cleanup','syscall','terminate_owned',['PID_start_checked_signal_then_reap','work_subtree_cgroup.kill_only',
        'zero_recursive_population','close_owned_FDs'],write=['W','C:log'])
    workload=units(value)[-1]['args'][0]
    for member,signature,args in [('StopUnit','ss',[workload,'replace']),
            ('KillUnit','ssi',[workload,'all',9])]:
        row('cleanup','dbus',member,dict(bus='org.freedesktop.systemd1',path='/org/freedesktop/systemd1',
            interface='org.freedesktop.systemd1.Manager',member=member,signature=signature,args=args),
            pre=['exact_owned_workload_unit','keeper_or_independent_deadline_authority',
                'KillUnit_only_after_bounded_StopUnit_failure'] if member=='KillUnit' else
                ['exact_owned_workload_unit','keeper_or_independent_deadline_authority'],
            identity=['workload_cgroup_recursive_exit'])
    row('cleanup','syscall','export',['schema_allowlist_only','reserved_C_export_FD','byte_and_cumulative_write_limit',
        'ENOSPC_keeps_quarantine'],write=['C:export'])
    row('cleanup','argv','umount',['/usr/bin/umount','--','$W'],pre=['zero_population','no_open_owned_W_descriptors'])
    row('cleanup','argv','detach',['/usr/sbin/losetup','--detach','$W_LOOP'],pre=['normal_unmount_success'],identity=['W_loop_absence'])
    row('cleanup','syscall','unlinkat_owned_W',['verified_parent_fd','exact_backing_dev_inode','fsync_parent'],write=['W'],pre=['independent_detach_absence'])
    row('completion','syscall','final_custody',['durable_QUARANTINED','retain_C_slot_tombstone_and_A',
        'normal_unmount_C','close_namespace_after_all_workers_exit','release_named_PID1_FDs_and_all_lock_copies',
        'independent_original_inode_nonblocking_acquire_then_close'],write=['C:export'],pre=['work_cleanup_proven','C_backing_and_A_retention_receipt'])
    row('completion','syscall','observe',['keeper_and_cleanup_exit','W_absence','retained_C_and_A_exact_identities',
        'PENDING_OBSERVER_EXIT','lifecycle_authority_observes_observer_exit','charged_final_tail_and_metrics'],
        pre=['observer_cannot_attest_own_exit','everything<=origin+4500'])
    row('dispose','syscall','explicit_disposition',['export_receipt','irrevocably_expired_grant_tombstone',
        'StopUnit(task_only)','RemoveSubgroup_only_when_empty','unlinkat_exact_C_A_O_identities'],write=['C','A','O'],
        pre=['separate_disposition_authority','no_remaining_custody_obligations'])
    # Sort phases so preparation C/archive precede runtime W. Record numbers
    # describe the final traversable order, not loop generation order.
    order=['install','preparation_supervisor','control','archive','activation','custody','admission','work','cleanup','completion','dispose']
    records.sort(key=lambda r:order.index(r['phase']))
    for i,record in enumerate(records):record['sequence']=i
    # These objects must exist before the first C-bound journal entry. Keep the
    # exact creation commands in an independent, operator-authorized prefix;
    # ordinary root records only verify their original identities. In particular
    # no retained C state may be formatted, reserved or installed a second time.
    prerequisite=[1]+[r['sequence'] for r in records if r['phase']=='control']+[
        r['sequence'] for r in records if r['kind']=='dbus' and
        r['operation']=='StartTransientUnit' and r['args']['args'][0].endswith('.slice')]
    preparation=[copy.deepcopy(records[n]) for n in sorted(set(prerequisite))]
    for record in preparation:
        original=copy.deepcopy(record)
        records[record['sequence']].update(kind='syscall',operation='verify_prepared',
            args=dict(original_record_sha256=c.digest(c.canonical(original)),original_sequence=original['sequence'],
                expectation='independent_operator_prefix_receipt'),
            writable=[],preconditions=['original_prepared_identity_and_bytes',
                'no_create_format_overwrite_or_rearm','prefix_accounted_before_first_entry'])
    records[52]['args']=['durable_QUARANTINED','retain_C_slot_tombstone_and_A',
        'prepare_independent_terminal_handoff_only','keep_C_namespace_and_lock_custody',
        'NO_unmount_close_or_release_before_record53_completion_and_observer_tail']
    records[52]['preconditions']+=['independent_terminal_owner_retains_original_descriptors']
    prefix=dict(schema='meownero-operator-prefix/1',source_only=True,
        authority='independently_authenticated_outside_operator_not_root_record_ingress',
        operations=preparation,
        before_first_entry=['exact_immutable_installation_and_index','original_retained_namespace',
            'original_C_directory_record_order_and_all_role_capabilities',
            'parent_work_control_accounting_units','durable_operator_quarantine_and_startup_receipt'],
        command=['/usr/bin/python3','-I','-B','/opt/meownero/TJS-2504/helper/profile-custodian.py'],
        charge=dict(preparation=PREPARATION,allocation=ALLOCATION,overhead=value['overhead']),
        administrator_only=dict(schema='meownero-administrator-prefix/1',binding=None,
            implementation='UNBOUND_UNQUALIFIED',authentication='administrator_only_noninteractive_task_exact_source',
            preimport=['root_owned_immutable_opt_meownero_TJS2504_helper_and_all_ancestors',
                'exact_authority_bound_inputs_and_complete_installation_inventory',
                'fixed_isolated_no_argument_startup_before_any_project_import'],
            ordered=['immutable_preimport_publication','rootful_task_cgroup_accounting_before_workers',
                'original_private_mount_namespace_and_fixed_loop_ext4_C_W_A_O',
                'hard_occupied_bytes_and_separate_cumulative_write_reservations_for_every_writer',
                'original_PID1_two_named_FDs_and_independent_same_open_description_readback',
                'fourteen_original_prefix_operations_once','durable_bound_launch_receipt'],
            storage=dict(control_gib=1,workload_gib=11,archive_max_gib=2,other_max_gib=1,
                aggregate_max_gib=15,metadata_and_copy_accounting='inside_existing_C_W_A_O_caps'),
            manager_bus='independently_bound_system_or_user_for_launch_only',
            custody='PID1_only; user_manager_is_not_independent_pid1_readback',
            terminal='terminal_handoff_original_deadlines_normal_unmount_only',
            grant='separate_exact_administrator_authority; no_source_packet_authorization'),
        installed_implementation='UNIMPLEMENTED_UNQUALIFIED')
    terminal=dict(schema='meownero-terminal-handoff/1',source_only=True,
        owner='independent_outside_operator_not_a_C_bound_root_entry',
        ordered=['record52_intent_and_durable_completion','record53_pending_observer_and_durable_completion',
            'all_C_bound_entries_exit_and_close_journal_directory_descriptors',
            'independent_keeper_cleanup_and_observer_exit_witness','account_and_sync_final_C_export_tail',
            'retain_C_quarantine_tombstone_and_A','close_all_C_writers_and_descriptors',
            'normal_C_unmount_and_independent_absence','close_original_namespace_custody',
            'release_PID1_named_FDs_and_all_original_lock_copies',
            'independent_original_inode_nonblocking_acquire_then_close'],
        deadline='original_origin+4500',disposition='record54_separate_authority_only',
        implementation='UNIMPLEMENTED_UNQUALIFIED')
    return dict(schema='meownero-lifecycle-packet/4', spec_sha256=c.digest(c.canonical(value)),
        source_only=True, activation='REFUSED_UNQUALIFIED', plan=copy.deepcopy(value), records=records,
        operator_prefix=prefix,terminal_handoff=terminal,
        receiver_launch=dict(builder='profile_packet.receiver_unit',transport='profile_receiver.ManagerTransport',
            bus=None,record_range=[0,53],command=['/usr/bin/python3','-I','-B',
                '/opt/meownero/TJS-2504/helper/profile-root-helper.py'],
            unit='meowneroTJS2504$ATTEMPT-root$RECORD.service',
            deadline=dict(resolver='profile_packet.operation_deadline',
                authority='original protected record_binding including preparation.origin/archive_origin',
                operation='minimum original record, enclosing phase and absolute end cutoffs',
                active_phase='build except outer/controller/start_and_wait through work; cleanup reserve excluded',
                relative_runtime='floor remaining original cutoff at render; supplementary only, active-entry relative',
                delivery_and_rpc='separate short waits; never the operation lifetime',
                settlement='same original cutoff; late completion/exit/confirmation stays uncertain'),
            reference='AddRef=true_on_original_authenticated_connection_until_durable_settlement_confirmation',
            restart='no',charge='existing_control_slice_and_O_metadata_caps',qualification='UNBOUND_UNQUALIFIED'),
        units=units(value), unbound=[key for key,val in value['authority'].items() if val is None],
        observed_storage=None, native_execution='NOT_RUN', launch_ready=False)
