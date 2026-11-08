"""Bound launch and exact-receiver exit interfaces. No installed bus is supplied.

Manager calls use an independently authenticated injected connection. The parent
alternative uses real pidfd/waitid only for its own original child. Neither
interface establishes protected installation, PID1 custody or terminal cleanup.
"""
import copy
import math
import os
import re
import time

import profile_contract as c
import profile_ingress as i
import profile_packet as p


def boot_id():
    with open('/proc/sys/kernel/random/boot_id',encoding='ascii') as stream:
        return stream.read().strip()


def scope(launch,record,receiver):
    return copy.deepcopy(dict(task='TJS-2504',attempt_id=launch['plan']['attempt_id'],source=launch['plan']['source'],
        record=record,record_binding=launch['record_binding'],receiver=receiver,
        operation_deadline=p.operation_deadline(launch['plan'],record,launch['record_binding'])))


def exit_status(code,status):
    if code is None and status is None:return None
    c.require(type(code) is int and type(status) is int,'terminal code/status pair')
    if code==os.CLD_EXITED:
        c.require(0<=status<=255,'normal exit status range')
        return status
    c.require(code in (os.CLD_KILLED,os.CLD_DUMPED) and 0<status<128,'terminal signal event only')
    return -status


def validate_witness(value,expected,observer,method,now):
    c.require(type(value) is dict and set(value)=={'schema','method','scope','observer','boot_id',
        'observed_at','code','status','detail'} and value['schema']=='meownero-receiver-exit/1',
        'complete exact-receiver exit witness')
    c.require(value['method']==method and value['scope']==expected and value['observer']==observer and
        value['boot_id']==boot_id(),'original independently authenticated exit observer and binding')
    at=value['observed_at'];binding=expected['record_binding']
    c.require(type(at) in (int,float) and math.isfinite(at) and
        binding['origin']<=at<=now<binding['deadlines']['end'],'original exit observation/deadline')
    result=exit_status(value['code'],value['status'])
    c.require(result is not None,'missing terminal status retains custody')
    if method=='parent_pidfd':
        c.require(value['detail']==dict(reaped=True),'exact child reaped before settlement')
    else:
        c.require(method=='manager_reaper' and type(value['detail']) is dict,'fixed exit witness method')
    return result


class ChildExitWitness:
    """Pin a live original child before delivery; never accept a supplied status.

    The independent parent persists siginfo before reaping. ECHILD, no event,
    stopped/continued state and any persistence failure return no witness.
    https://man7.org/linux/man-pages/man2/waitid.2.html
    """
    def __init__(self,receiver,binding,*,clock=time.monotonic):
        self.receiver,self.binding=copy.deepcopy(receiver),copy.deepcopy(binding)
        self.clock=clock;self.observer=i.process_identity(os.getpid());self.boot=boot_id()
        self.fd=None;self.used=False
        c.require(i.process_identity(receiver['pid'])==receiver and binding['receiver']==receiver,
            'original live receiver PID/start')
        try:
            self.fd=os.pidfd_open(receiver['pid'],0)
            c.require(i.process_identity(receiver['pid'])==receiver,'receiver changed while opening pidfd')
        except BaseException:
            self.close();raise

    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None

    def observe(self,persist,*,deadline):
        c.require(not self.used and self.fd is not None and self.clock()<deadline and
            deadline<=self.binding['record_binding']['deadlines']['end'] and
            self.boot==boot_id() and self.observer==i.process_identity(os.getpid()),'original parenting observer')
        info=os.waitid(os.P_PIDFD,self.fd,os.WEXITED|os.WNOHANG|os.WNOWAIT)
        c.require(info is not None and info.si_pid==self.receiver['pid'],'exact child terminal event required')
        exit_status(info.si_code,info.si_status)
        self.used=True
        witness=dict(schema='meownero-receiver-exit/1',method='parent_pidfd',scope=self.binding,
            observer=self.observer,boot_id=self.boot,observed_at=self.clock(),code=info.si_code,
            status=info.si_status,detail=dict(reaped=False))
        # Persist before losing the waitable kernel record. No return before
        # exact reaping and its second durable receipt. A failed ack retains custody.
        persist(copy.deepcopy(witness))
        reaped=os.waitid(os.P_PIDFD,self.fd,os.WEXITED|os.WNOHANG)
        c.require(reaped==info and self.clock()<deadline,'same terminal event reaped before deadline')
        witness['detail']['reaped']=True
        persist(copy.deepcopy(witness))
        self.close()
        return witness


class ManagerTransport:
    """Source adapter for the selected bus, never a literal system/user choice.

    The connection authenticates its bus, unique manager identity, epoch, boot,
    PID/start and uid independently of call data. This boundary is UNQUALIFIED.
    StartTransientUnit's typed payload comes only from the frozen renderer.
    https://www.freedesktop.org/software/systemd/man/255/org.freedesktop.systemd1.html
    """
    def __init__(self,plan,manager,boundary,*,clock=time.monotonic):
        self.plan=copy.deepcopy(p.validate_plan(plan));self.manager=copy.deepcopy(manager)
        self.boundary,self.clock=boundary,clock;self.used=set();self.receivers={}
        c.require(plan['attempt_id'] is not None and all(plan['source'].values()),'bound launch source and attempt')
        c.require(set(manager)=={'bus','unique_name','client_unique_name','epoch','boot_id','process','uid'} and
            manager['bus'] in ('system','user') and manager['boot_id']==boot_id() and
            type(manager['uid']) is int and manager['unique_name'].startswith(':') and
            manager['client_unique_name'].startswith(':') and manager['client_unique_name']!=manager['unique_name'] and
            type(manager['epoch']) is str and manager['epoch'],'bound authenticated manager connection')
        self.check()
        authority=copy.deepcopy(boundary.authenticate_launch(self.plan,self.manager))
        c.require(type(authority) is dict and set(authority)=={'bindings','record_binding'} and
            type(authority['bindings']) is dict,'independently authenticated launch substitutions/deadlines')
        self.bindings=authority['bindings'];self.record_binding=authority['record_binding']
        c.require(set(self.record_binding)=={'contract_sha256','inputs_sha256','origin','deadlines','preparation'} and
            self.record_binding['inputs_sha256']==self.plan['source']['inputs_sha256'] and
            type(self.record_binding['origin']) in (int,float) and math.isfinite(self.record_binding['origin']) and
            set(self.record_binding['deadlines'])=={'build','work','end'},'original source/index/clock binding')
        origin=self.record_binding['origin'];limits=c.LIMITS;ends=self.record_binding['deadlines']
        c.require(ends==dict(build=origin+limits['build_seconds'],
            work=origin+limits['build_seconds']+limits['runtime_seconds'],end=origin+limits['wall_seconds']),
            'unchanged original 3600+600+300 deadlines')
        p.operation_deadline(self.plan,0,self.record_binding)

    def check(self):
        c.require(self.manager['boot_id']==boot_id() and
            self.boundary.authenticate_manager()==self.manager,'manager connection/boot/epoch discontinuity')

    def deadline(self,value):
        c.require(type(value) in (int,float) and math.isfinite(value) and
            self.clock()<value<=self.record_binding['deadlines']['end'],'original bound launch deadline')

    def start(self,unit,*,deadline):
        self.check();self.deadline(deadline)
        calls={row['args'][0]:row for row in p.units(self.plan)}
        c.require(unit in calls and unit not in self.used and self.clock()<deadline,'one frozen transient start')
        self.used.add(unit)  # Lost delivery/response cannot retry or restart it.
        call=copy.deepcopy(calls[unit])
        from profile_executor import substitute
        call['args']=substitute(call['args'],self.bindings)
        result=self.boundary.start_transient_unit(self.manager,call,deadline)
        self.check()
        c.require(self.clock()<deadline,'late transient start retains uncertain ownership')
        return result

    def start_receiver(self,record,endpoint_fd,*,deadline):
        """Exactly one fixed no-argument root entry per original record.

        The inherited FD must already be bound to this receiver delivery by the
        protected launch boundary. AddRef/retention accompanies creation; it is
        held through durable settlement confirmation, including a lost reply.
        """
        self.check();self.deadline(deadline)
        cutoff=p.operation_deadline(self.plan,record,self.record_binding)
        c.require(deadline<=cutoff,'receiver launch RPC cannot extend original operation cutoff')
        call=p.receiver_unit(self.plan,record,endpoint_fd,operation_cutoff=cutoff,now=self.clock())
        unit=call['args'][0]
        c.require(unit not in self.used and self.clock()<deadline,'one original root receiver start')
        self.used.add(unit)
        c.require(self.boundary.authenticate_receiver_delivery(self.plan,record,endpoint_fd) is True,
            'original one-use authenticated receiver delivery')
        result=self.boundary.start_transient_unit(self.manager,call,deadline)
        self.check();c.require(self.clock()<deadline,'late receiver launch retains custody')
        return unit,result

    def capture_receiver(self,unit,receiver,binding,*,deadline):
        self.check()
        c.require(unit in self.used and unit.endswith('-root'+str(binding['record'])+'.service') and
            unit not in self.receivers and self.clock()<deadline and
            binding['receiver']==receiver and binding['task']=='TJS-2504' and
            binding['source']==self.plan['source'] and binding['attempt_id']==self.plan['attempt_id'] and
            binding['record_binding']==self.record_binding and
            binding['operation_deadline']==p.operation_deadline(self.plan,binding['record'],self.record_binding) and
            deadline<=binding['record_binding']['deadlines']['end'],
            'receiver belongs to this original start')
        observed=self.boundary.receiver_properties(self.manager,unit,deadline)
        self.check()
        c.require(observed==self.boundary.receiver_properties(self.manager,unit,deadline),
            'coherent original receiver properties around live capture')
        self.check()
        c.require(observed['unit']==unit and observed['MainPID']==observed['ExecMainPID']==receiver['pid'] and
            observed['receiver']==i.process_identity(receiver['pid'])==receiver and
            type(observed['InvocationID']) is str and re.fullmatch('[0-9a-f]{32}',observed['InvocationID']) and
            observed['NRestarts']==0 and observed['Type']=='exec' and observed['Restart']=='no' and
            observed['RemainAfterExit'] is True and self.manager['client_unique_name'] in observed['Refs'] and
            observed['command']==['/usr/bin/python3','-I','-B',
                '/opt/meownero/TJS-2504/helper/profile-root-helper.py'] and
            type(observed['ExecMainStartTimestampMonotonic']) is int and
            observed['ExecMainStartTimestampMonotonic']>0 and self.clock()<deadline and
            observed['ExecMainExitTimestampMonotonic']==0 and observed['ExecMainCode']==0 and
            observed['ExecMainStatus']==0 and observed['object'].startswith('/org/freedesktop/systemd1/unit/'),
            'live exact main process and original invocation before exit')
        self.receivers[unit]=dict(original=copy.deepcopy(observed),scope=copy.deepcopy(binding),witness=None,attempted=False)

    def observe_exit(self,unit,*,persist,deadline):
        self.check();saved=self.receivers[unit];original=saved['original']
        c.require(not saved['attempted'] and self.clock()<deadline<=saved['scope']['record_binding']['deadlines']['end'],
            'one original manager exit observation')
        saved['attempted']=True
        observed=self.boundary.receiver_properties(self.manager,unit,deadline)
        self.check()
        for key in ('unit','object','receiver','InvocationID','ExecMainPID','ExecMainStartTimestampMonotonic',
                'NRestarts','Type','Restart','RemainAfterExit','Refs','command'):
            c.require(observed[key]==original[key],'receiver invocation/process substitution: '+key)
        c.require(observed==self.boundary.receiver_properties(self.manager,unit,deadline),
            'coherent retained receiver terminal properties')
        self.check()
        c.require(observed['MainPID']==0 and
            type(observed['ExecMainExitTimestampMonotonic']) is int and
            original['ExecMainStartTimestampMonotonic']<observed['ExecMainExitTimestampMonotonic']<=self.clock()*1e6,
            'genuine terminal main-process event, not PID absence or unit result')
        c.require(observed['ExecMainCode'] in (os.CLD_EXITED,os.CLD_KILLED,os.CLD_DUMPED),'terminal manager code')
        exit_status(observed['ExecMainCode'],observed['ExecMainStatus'])
        value=dict(schema='meownero-receiver-exit/1',method='manager_reaper',scope=copy.deepcopy(saved['scope']),
            observer=copy.deepcopy(self.manager),boot_id=self.manager['boot_id'],observed_at=self.clock(),
            code=observed['ExecMainCode'],status=observed['ExecMainStatus'],detail=copy.deepcopy(observed))
        persist(copy.deepcopy(value));self.check()
        c.require(self.clock()<deadline,'exit persistence exceeded original deadline')
        saved['witness']=copy.deepcopy(value)
        return value

    def verify_exit(self,witness,expected):
        # Re-read under the same retained manager/unit invocation. A serialized
        # packet by itself does not authenticate a manager's reaper observation.
        unit=witness['detail']['unit'];saved=self.receivers[unit]
        self.check()
        c.require(saved['witness']==witness and saved['scope']==expected and
            self.boundary.receiver_properties(self.manager,unit,expected['record_binding']['deadlines']['end'])==
            witness['detail'],'retained original unit and exact durable exit observation')
        self.check()
        return validate_witness(witness,expected,self.manager,'manager_reaper',self.clock())

    def acknowledge(self,unit,settlement):
        self.check();saved=self.receivers[unit]
        c.require(saved['witness'] is not None and settlement==dict(confirmed=True,
            scope=saved['scope'],exit_witness_sha256=c.digest(c.canonical(saved['witness']))) and
            self.boundary.authenticate_settlement(settlement) is True,
            'durable settlement receipt required before releasing unit reference')
        self.verify_exit(saved['witness'],saved['scope'])
        self.boundary.acknowledge_receiver(self.manager,unit,settlement)
