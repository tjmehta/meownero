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
    def __init__(self,boundary,*,operator_fd=0,clock=time.monotonic,run=None):
        self.boundary,self.operator_fd,self.clock,self.run=boundary,operator_fd,clock,run
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
            ingress=i.InstalledIngress(self.boundary,anchor,directory_fd,endpoint_fd=ingress_fd,clock=self.clock)
            kwargs={} if self.run is None else dict(run=self.run)
            return e.RootEntry(ingress,clock=self.clock,**kwargs).run_authenticated_inherited_entry()
        finally:
            for fd in fds:os.close(fd)
