"""Receive independent operator authority before constructing the existing ingress.

The separate operator channel is not the custodian ingress being authenticated.
Its expectations must come from an independently qualified protected launch
boundary. No installed implementation of that boundary is supplied here. Local
fixtures use real credentialed packets with explicitly injected TEST authority.
"""
import copy
import os
import time

import profile_bootstrap as b
import profile_contract as c
import profile_executor as e
import profile_ingress as i
import profile_manager as m


def boot_identity():
    with open('/proc/sys/kernel/random/boot_id',encoding='ascii') as stream:
        return stream.read().strip()


class OperatorConstructor:
    """One fresh invocation, independently delivered receipt and original FDs.

    The OS boundary authenticates operator/receiver manager invocation and pins
    the receipt digest *before* this channel is read. Neither the received
    receipt, local index, root UID nor unit membership can create that pin.
    Received descriptor ownership belongs to this invocation and always closes.
    """
    def __init__(self,boundary,*,operator_fd=0,clock=time.monotonic,run=None,record_authority=None):
        self.boundary,self.operator_fd,self.clock,self.run=boundary,operator_fd,clock,run
        self.record_authority=record_authority
        self.used=False

    def _check_invocation(self,expected):
        c.require(expected['receiver']==i.process_identity(os.getpid()) and
            expected['receiver_credentials']==[os.getpid(),os.getuid(),os.getgid()] and
            expected['operator']==i.process_identity(expected['operator_credentials'][0]) and
            expected['boot_id']==boot_identity(),'original boot/operator/receiver PID and start')
        # Independent manager observation is still an unimplemented OS boundary.
        c.require(self.boundary.operator_invocation_observation()==expected['invocation'],
            'independent authorized operator and receiver unit invocation')
        invocation=expected['invocation']
        c.require(set(invocation)=={'operator_unit','operator_invocation','receiver_unit','receiver_invocation'} and
            all(type(x) is str and x for x in invocation.values()),'complete manager invocation identities')

    def run_authenticated_inherited_entry(self):
        c.require(not self.used,'one-use operator constructor')
        self.used=True
        fds=()
        try:
            expected=copy.deepcopy(self.boundary.operator_entry_expectation())
            c.require(set(expected)=={'schema','operator','operator_credentials','receiver','receiver_credentials',
                'boot_id','invocation','receipt_sha256','endpoint_identity','descriptor_identities','deadline'} and
                expected['schema']=='meownero-operator-expectation/1','independent protected operator expectation')
            self._check_invocation(expected)
            c.require(i.identity(self.operator_fd)==expected['endpoint_identity'] and
                self.clock()<expected['deadline']<=self.clock()+5,'original bounded independent operator channel')
            with b.socket_from_fd(self.operator_fd) as endpoint:
                b.seqpacket(endpoint)
                receipt,fds=m.receive_packet(endpoint,expected['operator_credentials'],expected['deadline'],
                    fd_count=3,clock=self.clock)
            self._check_invocation(expected)
            c.require(c.digest(c.canonical(receipt))==expected['receipt_sha256'] and
                set(receipt)=={'schema','boot_id','invocation','anchor'} and
                receipt['schema']=='meownero-operator-entry/1' and
                receipt['boot_id']==expected['boot_id'] and receipt['invocation']==expected['invocation'],
                'exact independently authorized startup receipt')
            c.require([i.identity(fd) for fd in fds]==expected['descriptor_identities'] and
                len({tuple(i.identity(fd)) for fd in fds})==3,'original ingress/directory/index descriptors')
            ingress_fd,directory_fd,index_fd=fds
            c.require(i.identity(ingress_fd)!=i.identity(self.operator_fd),
                'operator trust channel distinct from authenticated ingress')
            anchor=copy.deepcopy(receipt['anchor'])
            c.require('inputs_raw' not in anchor and 'inputs_sha256' in anchor,
                'immutable separately transferred index, not JSON index authority')
            raw=i.sealed_bytes(index_fd,1024*1024)
            c.require(c.digest(raw)==anchor.pop('inputs_sha256') and
                anchor['receiver']==expected['receiver'] and
                anchor['receiver_credentials']==expected['receiver_credentials'] and
                anchor['endpoint_identity']==i.identity(ingress_fd) and
                anchor['directory_identity']==i.identity(directory_fd),
                'operator-to-constructor original source/index/state/receiver binding')
            anchor['inputs_raw']=raw
            ingress=i.InstalledIngress(self.boundary,anchor,directory_fd,endpoint_fd=ingress_fd,clock=self.clock,
                record_authority=self.record_authority)
            kwargs={} if self.run is None else dict(run=self.run)
            return e.RootEntry(ingress,clock=self.clock,**kwargs).run_authenticated_inherited_entry()
        finally:
            for fd in fds:os.close(fd)


class SurvivingAuthority:
    """Original source-process owner, outside the local order/role rollback set.

    The independent launcher supplies this original launch once, before any
    receiver exists. It also owns the protected command endpoint. No request
    supplies source/index/state bindings or reconstructs this object. Installed
    launch protection, manager observations and power-loss survival are NOT
    supplied by this source process. A lost owner cannot be restarted from its
    journal: construction requires the original RESERVED state and live owner.
    """
    def __init__(self,launch,directory_fd,index_fd,state_fd,*,clock=time.monotonic):
        import fcntl
        import json
        import stat
        self.launch=copy.deepcopy(launch)
        self.directory_fd,self.index_fd,self.state_fd=directory_fd,index_fd,state_fd
        self.clock=clock;self.failed=False;self.clients={};self.awaiting_exit=None
        self.boot=boot_identity()
        info=os.fstat(state_fd)
        c.require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and
            info.st_uid==info.st_gid==launch['owner_uid'] and stat.S_IMODE(info.st_mode)==0o600 and
            i.identity(state_fd)==launch['supervisor_identity'] and
            i.identity(directory_fd)==launch['directory_identity'] and
            i.identity(index_fd)==launch['index_identity'] and
            i.sealed_bytes(index_fd,1024*1024)==launch['inputs_raw'], 'original supervisor custody')
        fcntl.flock(state_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.binding=dict(record_binding=launch['record_binding'],boot_id=self.boot,
            task='TJS-2504',attempt_id=launch['plan']['attempt_id'],source=launch['plan']['source'],
            supervisor_identity=launch['supervisor_identity'],namespace_identity=launch['namespace_identity'],
            directory_identity=launch['directory_identity'],order_identity=launch['order_identity'],
            capability_identities=launch['capability_identities'],index_identity=launch['index_identity'])
        expected=dict(schema='meownero-surviving-authority/2',binding=self.binding,
            mode='LIVE',position=0,pending=None,stage='RESERVED',receiver=None,dispositions={})
        raw=os.pread(state_fd,65537,0)
        c.require(json.loads(raw)==expected and raw==c.canonical(expected),'original unused supervisor reservation')
        self.state=expected

    def _uncertain(self,record):
        # These flags only move to True. Completion followed by an abnormal
        # receiver exit retains both facts; neither can make a record unused.
        self.state['dispositions'][str(record)]['uncertain']=True
        self.state.update(mode='RECOVERY_ONLY',stage='UNCERTAIN')

    def _settle(self,message):
        c.require(set(message)=={'operation','receiver','status'} and
            self.awaiting_exit is not None and message['receiver']==self.awaiting_exit and
            (message['status'] is None or type(message['status']) is int) and
            self.state['receiver']==self.awaiting_exit and not self.clients and
            self.state['stage'] in ('AWAITING_EXIT','UNCERTAIN','SETTLEMENT_SENT'),
            'exact awaiting receiver and witnessed exit status')
        try:i.process_identity(message['receiver']['pid'])
        except FileNotFoundError:pass
        else:raise ValueError('receiver still present; no independent exit')
        record=self.state['pending'];disposition=self.state['dispositions'][str(record)]
        if message['status']!=0 or not disposition['completed'] or disposition['uncertain']:
            self._uncertain(record)
        # Retain custody until the launcher confirms receipt of this reply.
        # A lost reply cannot advance activation or silently release custody.
        self.state['stage']='SETTLEMENT_SENT';self._persist()

    def _confirm_settlement(self,message):
        c.require(set(message)=={'operation','receiver'} and self.awaiting_exit is not None and
            message['receiver']==self.awaiting_exit==self.state['receiver'] and
            self.state['stage']=='SETTLEMENT_SENT' and not self.clients,
            'original launcher received exact settlement acknowledgement')
        try:i.process_identity(message['receiver']['pid'])
        except FileNotFoundError:pass
        else:raise ValueError('receiver still present; no independent exit')
        disposition=self.state['dispositions'][str(self.state['pending'])]
        if disposition['completed'] and not disposition['uncertain']:
            self.state.update(position=self.state['position']+1,stage='COMPLETED')
        else:self.state['stage']='UNCERTAIN'
        self.state.update(pending=None,receiver=None)
        self._persist()  # No custody release or acknowledgement before durability.
        self.awaiting_exit=None

    def _persist(self):
        # Poison memory BEFORE IO. A failed fsync/readback cannot be cured by
        # restoring either this file or the separate local order/role files.
        import profile_outer as outer
        self.failed=True
        raw=c.canonical(self.state)
        c.require(len(raw)<=65536,'bounded charged supervisor state')
        os.lseek(self.state_fd,0,os.SEEK_SET);outer.write_all(self.state_fd,raw)
        os.ftruncate(self.state_fd,len(raw));os.fsync(self.state_fd)
        c.require(os.pread(self.state_fd,len(raw)+1,0)==raw,'supervisor state readback')
        self.failed=False

    def _live(self):
        c.require(not self.failed and self.boot==boot_identity() and
            self.clock()<self.launch['record_binding']['deadlines']['end'],
            'original surviving boot, custody and absolute deadline')
        c.require(i.identity(self.directory_fd)==self.launch['directory_identity'] and
            i.identity(self.index_fd)==self.launch['index_identity'] and
            i.identity(self.state_fd)==self.launch['supervisor_identity'] and
            os.pread(self.state_fd,65537,0)==c.canonical(self.state), 'unchanged original supervisor descriptors/state')

    def _issue(self,receiver,record,recovered):
        import fcntl
        self._live()
        c.require(self.awaiting_exit is None and not self.clients,'previous entry exit must be settled independently')
        c.require(i.process_identity(receiver['pid'])==receiver,'original launched receiver PID/start')
        route=self.launch['recovery'] if recovered else self.launch['itinerary']
        c.require(type(record) is int and record in route and record!=54,'frozen route; no automatic disposition')
        c.require(str(record) not in self.state['dispositions'],'consumed record never receives authority again')
        if recovered:
            if self.state['mode']=='LIVE':
                self.state.update(mode='RECOVERY_ONLY');self._persist()
            # Disposition, rather than a reset cursor, determines eligibility.
            unused=[n for n in route if str(n) not in self.state['dispositions']]
            c.require(unused and unused[0]==record,'next unconsumed frozen cleanup record')
            position=route.index(record)
        else:position=self.state['position']
        c.require(recovered or self.state['mode']=='LIVE','surviving classification cannot reactivate')
        c.require(self.state['pending'] is None and self.state['stage'] in ('RESERVED','COMPLETED','UNCERTAIN') and
            position<len(route) and route[position]==record,'issued, pending, replay or skipped record')
        # Burn delivery before returning any descriptor or authority packet.
        self.state['dispositions'][str(record)]=dict(consumed=True,completed=False,uncertain=False)
        self.state.update(position=position,pending=record,receiver=receiver,stage='ISSUED');self._persist()
        sockets=[];fds=[]
        try:
            op_tx,op_rx=b.delivery_pair();sockets.extend([op_tx,op_rx])
            in_tx,in_rx=b.delivery_pair();sockets.extend([in_tx,in_rx])
            au_tx,au_rx=b.delivery_pair();sockets.extend([au_tx,au_rx])
            control,client=m.private_pair();sockets.extend([control,client])
            creds=[os.getpid(),os.getuid(),os.getgid()];current=i.process_identity(os.getpid())
            deadline=min(self.clock()+4,self.launch['record_binding']['deadlines']['end'])
            role='observer' if recovered else 'keeper'
            delivery=dict(schema='meownero-helper-bootstrap/1',task='TJS-2504',
                attempt_id=self.launch['plan']['attempt_id'],role=role,mode='observe' if recovered else 'serve',
                invocation_id=os.urandom(16).hex(),source=self.launch['plan']['source'],
                spec_sha256=c.digest(c.canonical(self.launch['plan'])),
                contract_sha256=self.launch['record_binding']['contract_sha256'],
                origin=self.launch['record_binding']['origin'],deadlines=self.launch['record_binding']['deadlines'],
                sender_credentials=creds,sender_start=current['start'],delivery_deadline=deadline,
                namespace_identity=self.launch['namespace_identity'])
            context=os.memfd_create('TJS2504-produced-context',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING);fds.append(context)
            os.write(context,c.canonical(dict(schema='meownero-helper-bootstrap-context/1',
                delivery=delivery,contract=self.launch['contract'])))
            fcntl.fcntl(context,fcntl.F_ADD_SEALS,b.SEALS)
            request=dict(operation=p_record(self.launch['plan'],record)['operation'],record=record,
                deadline=min(self.clock()+30,self.launch['record_binding']['deadlines']['end']))
            envelope=dict(schema='meownero-root-ingress/1',delivery=delivery,request=request,
                activation=self.launch['secret'].hex(),recovery_only=recovered)
            anchor={key:copy.deepcopy(self.launch[key]) for key in ('plan','directory_identity','order_identity',
                'capability_identities','capability_expected','record_binding','itinerary','recovery','owner_uid')}
            anchor.update(schema='meownero-root-trust/1',inputs_sha256=c.digest(self.launch['inputs_raw']),
                envelope=envelope,receiver=receiver,receiver_credentials=[receiver['pid'],os.getuid(),os.getgid()],
                custodian=current,descriptor_identities=[i.identity(au_rx.fileno()),i.identity(context),i.identity(self.index_fd)],
                endpoint_identity=i.identity(in_rx.fileno()))
            invocation=copy.deepcopy(self.launch['invocation'])
            # Manager unit identity comes from the original launch contract;
            # receiver PID/start comes from the independently registered child.
            receipt=dict(schema='meownero-operator-entry/1',boot_id=self.boot,invocation=invocation,anchor=anchor)
            expected=dict(schema='meownero-operator-expectation/1',operator=current,operator_credentials=creds,
                receiver=receiver,receiver_credentials=anchor['receiver_credentials'],boot_id=self.boot,
                invocation=invocation,receipt_sha256=c.digest(c.canonical(receipt)),endpoint_identity=i.identity(op_rx.fileno()),
                descriptor_identities=[i.identity(in_rx.fileno()),i.identity(self.directory_fd),i.identity(self.index_fd)],deadline=deadline)
            m.send_packet(in_tx,envelope,[au_rx.fileno(),context,self.index_fd])
            m.send_packet(op_tx,receipt,[in_rx.fileno(),self.directory_fd,self.index_fd])
            held=[control,au_tx]
            self.clients[control.fileno()]=dict(endpoint=control,held=held,receiver=receiver,
                record=record,expected=expected,request=request,stage='ISSUED',recovered=recovered)
            sockets.remove(control);sockets.remove(au_tx)
            return client,op_rx,sockets,fds
        except BaseException:
            try:
                self.awaiting_exit=receiver
                self._uncertain(record)
                if not self.failed:self._persist()
            finally:
                for endpoint in sockets:endpoint.close()
                for fd in fds:os.close(fd)
            raise

    def _entry(self,client,message):
        self._live()
        c.require(self.clock()<client['request']['deadline'],'original per-record effect/completion deadline')
        c.require(i.process_identity(client['receiver']['pid'])==client['receiver'],'live registered receiver')
        c.require(set(message)=={'operation','record'} and message['record']==client['record'],'exact surviving record scope')
        operation=message['operation']
        if operation=='expectation':return client['expected']
        if operation=='recovery_position':
            c.require(client['recovered'] and client['stage']=='ISSUED' and
                self.state['pending']==client['record'] and self.state['stage']=='ISSUED',
                'original surviving recovery issuance before local admission')
            return self.launch['recovery'].index(client['record'])
        if operation=='admit':
            c.require(self.state['pending']==client['record'] and self.state['stage']=='ISSUED' and
                client['stage']=='ISSUED','one surviving effect admission')
            self.state['stage']='PENDING';client['stage']='PENDING';self._persist()
        elif operation=='complete':
            c.require(self.state['pending']==client['record'] and self.state['stage']=='PENDING' and
                client['stage']=='PENDING','exact surviving pending completion')
            self.state['stage']='COMPLETION_SENT'
            self.state['dispositions'][str(client['record'])]['completed']=True
            client['stage']='COMPLETION_SENT';self._persist()
        elif operation=='uncertain':
            self._uncertain(client['record']);self._persist()
        elif operation=='close':
            c.require(client['stage']=='COMPLETION_SENT','unacknowledged entry cannot close successfully')
            self.awaiting_exit=client['receiver']
            self.state['stage']='AWAITING_EXIT';self._persist()
        else:raise ValueError('closed surviving authority protocol')
        return dict(ack=operation,record=client['record'])

    def serve(self,endpoint,owner_credentials,owner_identity,*,deadline):
        """Original protected launcher only; no pathname listener or reconnect."""
        import select
        try:
            while self.clock()<deadline:
                c.require(i.process_identity(owner_credentials[0])==owner_identity,'original launcher still survives')
                ready=select.select([endpoint,*[x['endpoint'] for x in self.clients.values()]],[],[],
                    min(1,max(0,deadline-self.clock())))[0]
                for channel in ready:
                    if channel is endpoint:
                        message,_=m.receive_packet(channel,owner_credentials,deadline,clock=self.clock)
                        if message==dict(operation='stop'):return
                        try:
                            self._live()
                            if message==dict(operation='snapshot'):
                                m.send_packet(channel,dict(completed=[int(n) for n,value in
                                    self.state['dispositions'].items() if value['completed'] and not value['uncertain']],
                                    awaiting_exit=self.awaiting_exit,
                                    entries_closed=not self.clients and self.awaiting_exit is None,
                                    state=copy.deepcopy(self.state)));continue
                            if message.get('operation')=='settle':
                                record=self.state['pending']
                                self._settle(message)
                                try:m.send_packet(channel,dict(settled=True))
                                except Exception:
                                    # The exact receiver has exited, but a lost
                                    # settle acknowledgement cannot renew LIVE.
                                    self._uncertain(record);self._persist()
                                    raise
                                continue
                            if message.get('operation')=='confirm_settlement':
                                self._confirm_settlement(message)
                                m.send_packet(channel,dict(confirmed=True));continue
                            c.require(set(message)=={'operation','receiver','record','recovered'} and
                                message['operation']=='issue' and type(message['recovered']) is bool,'closed launcher request')
                            client,operator,sockets,fds=self._issue(message['receiver'],message['record'],message['recovered'])
                            try:m.send_packet(channel,dict(issued=True),[client.fileno(),operator.fileno()])
                            finally:
                                for sock in sockets:sock.close()
                                for fd in fds:os.close(fd)
                        except Exception:m.send_packet(channel,dict(issued=False))
                    else:
                        key=channel.fileno();client=self.clients[key]
                        try:
                            message,_=m.receive_packet(channel,[client['receiver']['pid'],os.getuid(),os.getgid()],
                                deadline,clock=self.clock)
                            result=self._entry(client,message)
                            m.send_packet(channel,dict(ok=True,result=result))
                            if message['operation']=='close':
                                for sock in client['held']:sock.close()
                                del self.clients[key]
                        except Exception:
                            # Any lost packet/ack/child is retained independently.
                            self.awaiting_exit=client['receiver']
                            self._uncertain(client['record'])
                            if not self.failed:
                                try:self._persist()
                                except Exception:pass
                            try:m.send_packet(channel,dict(ok=False))
                            except Exception:pass
                            for sock in client['held']:sock.close()
                            del self.clients[key]
        finally:
            for client in self.clients.values():
                for sock in client['held']:sock.close()
            self.clients.clear()


def p_record(plan,number):
    import profile_packet
    return profile_packet.render(plan)['records'][number]


class AuthorityClient:
    """Protected inherited link to the original surviving source process."""
    def __init__(self,fd,credentials,identity,record,deadline,*,clock=time.monotonic):
        self.fd,self.credentials,self.identity=fd,credentials,identity
        self.record,self.deadline,self.clock=record,deadline,clock

    def call(self,operation):
        c.require(i.process_identity(self.credentials[0])==self.identity,'original supervisor PID/start; no reconnect')
        with b.socket_from_fd(self.fd) as endpoint:
            m.send_packet(endpoint,dict(operation=operation,record=self.record),deadline=self.deadline,clock=self.clock)
            reply,_=m.receive_packet(endpoint,self.credentials,self.deadline,clock=self.clock)
        c.require(reply.get('ok') is True,'surviving authority refused')
        return reply['result']

    def admit(self,record):
        c.require(record['sequence']==self.record,'exact supervised record')
        self.call('admit')

    def complete(self,record):
        c.require(record['sequence']==self.record,'exact supervised completion')
        self.call('complete')

    def uncertain(self,record):self.call('uncertain')

    def recovery_position(self,record):
        c.require(record['sequence']==self.record,'exact supervised recovery record')
        return self.call('recovery_position')

    def close(self):self.call('close')
