#!/usr/bin/env python3
"""Direct controller tests. Docker/native execution is replaced; host children are real."""
import ast
import base64
import contextlib
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import profile_contract as c

spec = importlib.util.spec_from_file_location('direct_profile',c.HERE/'run-profile.py')
r = importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
GRANT = '11111111-1111-4111-8111-111111111111'
IMAGE = 'sha256:'+'e'*64


def grant(output):
    return dict(schema='meownero-direct-profile-grant/1',authorized=True,
        candidate_commit='a'*40,inputs_sha256=c.digest(b'{}'),artifact_sha256=c.digest(b'packet'),
        runner_sha256=c.digest((c.HERE/'run-profile.py').read_bytes()),output_root=str(output),
        artifact_attachment_id='22222222-2222-4222-8222-222222222222',attempts=1,retry=False,
        wall_seconds=4500,build_seconds=3600,runtime_seconds=600,cleanup_seconds=300,
        container_flags=r.CONTAINER_FLAGS,workload='three-production-binaries-genesis-only',
        non_genesis_blocks=0,transactions=0,valid_from_unix=0,valid_until_unix=time.time()+10000,
        load_rule=dict(metric='host-load-1-5-15',maximum=[6,6,6]),
        host_overhead_allowance=dict(mode='measured-controller-and-descendants-not-kernel-enforced',
            peak_rss_bytes=2*r.GiB,cpu_seconds=600,peak_pids=32))


def comment(value):
    return dict(id=GRANT,issueId=c.ISSUE,authorAgentId=c.PLATFORM,authorUserId=None,
        body='```meownero-direct-profile-grant\n'+json.dumps(value)+'\n```')


@contextlib.contextmanager
def digest_fixture(**options):
    """Disposable epee-shaped server: nonce and nc belong to each TCP session."""
    import hashlib,threading,urllib.request
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    md=lambda value:hashlib.md5(value.encode('ascii')).hexdigest()
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def setup(self):
            super().setup();self.session=len(self.server.sessions)
            self.server.sessions.append(self);self.nonce='';self.counter=0
        def finish(self):
            try:super().finish()
            finally:self.server.closed.add(self.session)
        def handle(self):
            try:super().handle()
            except ConnectionResetError:
                if self.server.progress_stage is None:raise
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            authorization=self.headers.get('Authorization','');valid=stale=False
            if authorization.startswith('Digest '):
                self.counter+=1
                try:
                    fields=urllib.request.parse_keqv_list(urllib.request.parse_http_list(authorization[7:]))
                    user,password=self.server.login.split(':',1)
                    expected=md(':'.join([md(user+':monero-rpc:'+password),fields['nonce'],fields['nc'],
                        fields['cnonce'],'auth',md('POST:'+self.path)]))
                    credential=(fields['username']==user and fields['realm']=='monero-rpc' and
                        fields['algorithm']=='MD5' and fields['qop']=='auth' and fields['uri']==self.path and
                        bool(fields['cnonce']) and fields['response']==expected)
                    stale=credential and (fields['nonce']!=self.nonce or int(fields['nc'],16)!=self.counter)
                    valid=credential and not stale
                except (KeyError,ValueError):pass
            if valid and self.server.force_stale:
                self.server.force_stale=False;valid=False;stale=True
            method=body.get('method','')
            self.server.events.append(dict(session=self.session,authorized=bool(authorization),
                accepted=valid,stale=stale,method=method,path=self.path,
                connection_close=self.headers.get('Connection','').lower()=='close'))
            if self.server.delay:time.sleep(self.server.delay)
            if valid:
                if method in c.denial_requests('dummy-address','dummy-seed'):
                    value={'error':{'code':-7,'message':'PRIVATE_SECRET'}}
                elif method=='get_balance':value={'result':{'balance':0,'unlocked_balance':0}}
                elif self.path=='/get_transaction_pool_hashes':value={}
                elif self.path=='/get_transaction_pool_stats':value={'pool_stats':{'txs_total':0}}
                else:value={'result':dict(status='OK',height=1,top_block_hash=c.GENESIS,wide_cumulative_difficulty='0x1')}
                payload=b'PRIVATE_SECRET' if self.server.bad_json else json.dumps(value).encode()
                self.send_response(200)
            else:
                self.counter=0;self.nonce=os.urandom(16).hex();payload=b'PRIVATE_SECRET'
                self.send_response(401)
                for algorithm in self.server.algorithms:
                    self.send_header('WWW-Authenticate',f'Digest qop="{self.server.qop}", algorithm={algorithm}, realm="monero-rpc", nonce="{self.nonce}", stale='+('true' if stale else 'false'))
                if self.server.close_challenge:self.send_header('Connection','close');self.close_connection=True
            self.send_header('Content-Type','application/json')
            stage=self.server.progress_stage
            chunked=valid and stage in ('chunk_size','chunk_trailer','chunk_invalid')
            self.send_header('Transfer-Encoding','chunked') if chunked else self.send_header('Content-Length',str(len(payload)))
            try:
                if stage==('response_headers' if valid else 'challenge_headers'):
                    self.flush_headers()
                    for _ in range(self.server.progress_count):
                        self.wfile.write(b'X-Progress: ok\r\n');time.sleep(self.server.progress_delay)
                self.end_headers()
                if stage=='chunk_invalid' and valid:
                    self.wfile.write(b'invalid\r\n');self.close_connection=True
                elif chunked:
                    if stage=='chunk_size':
                        self.wfile.write(f'{len(payload):x};'.encode())
                    else:self.wfile.write(f'{len(payload):x}\r\n'.encode()+payload+b'\r\n0\r\nX-Trailer: ')
                    for _ in range(self.server.progress_count):
                        self.wfile.write(b'x');time.sleep(self.server.progress_delay)
                    self.wfile.write(b'\r\n'+payload+b'\r\n0\r\n\r\n' if stage=='chunk_size' else b'\r\n\r\n')
                else:self.wfile.write(payload)
            except (BrokenPipeError,ConnectionResetError):pass
    class Server(ThreadingHTTPServer):
        daemon_threads=False
        def handle_error(self,*args):self.errors.append(sys.exc_info()[1])
    server=Server(('127.0.0.1',0),Handler)
    server.login='fixture:dummy';server.events=[];server.sessions=[];server.closed=set();server.errors=[]
    for key,default in dict(force_stale=False,delay=0,bad_json=False,close_challenge=False,
                            algorithms=('MD5','MD5-sess'),qop='auth',progress_stage=None,
                            progress_delay=.025,progress_count=12).items():
        setattr(server,key,options.get(key,default))
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});thread.start()
    try:yield server
    finally:
        server.shutdown();thread.join(timeout=2);server.server_close()
        assert not thread.is_alive()
        assert not server.errors, server.errors
        assert server.closed==set(range(len(server.sessions))), 'client left session open'


class Direct(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name);self.output = self.base/'attempt'
        self.lock = self.base/'heavy.lock';self.lock.touch(mode=0o600)
        info = self.lock.stat()
        self.stack = contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(r.g,'LOCK',self.lock))
        self.stack.enter_context(patch.object(r.g,'LOCK_ID',(info.st_dev,info.st_ino)))

    def validate(self,value):
        return r.grant_payload(comment(value),commit='a'*40,inputs_hash=c.digest(b'{}'),
            artifact_hash=c.digest(b'packet'),runner_hash=c.digest((c.HERE/'run-profile.py').read_bytes()),
            output=self.output,now=time.time())

    def test_rpc_session_nonce_known_bad_and_daemon_snapshot(self):
        driver=self.driver_fixture();driver.DEADLINE=time.monotonic()+20
        old=subprocess.check_output(['git','show','ed78cd5:./vanguard/network/profile-integration.py']).decode()
        baseline=type(sys)('baseline_digest');baseline.__file__=str(c.HERE/'profile-integration.py')
        exec(compile(old,baseline.__file__,'exec'),baseline.__dict__);baseline.DEADLINE=driver.DEADLINE
        import http.client
        sockets=[];responses=[];connect=http.client.HTTPConnection.connect;getresponse=http.client.HTTPConnection.getresponse
        def capture(connection):
            connect(connection);sockets.append(connection.sock)
        def capture_response(connection):
            response=getresponse(connection);responses.append(response);return response
        with digest_fixture() as server:
            with patch.object(http.client.HTTPConnection,'connect',capture),patch.object(http.client.HTTPConnection,'getresponse',capture_response):
                with self.assertRaises(RuntimeError) as caught:baseline.RPC(server.server_port,server.login).call('get_info')
            self.assertEqual(caught.exception.readiness['http_status'],401)
            pending=[caught.exception];closed=set()
            while pending:
                error=pending.pop()
                if id(error) in closed:continue
                closed.add(id(error))
                pending.extend(x for x in (error.__cause__,error.__context__) if x is not None)
                if hasattr(error,'close'):error.close()
            for response in responses:response.close()
            for sock in sockets:sock.close()
            self.assertFalse(any(x['accepted'] for x in server.events))
            self.assertTrue(any(x['stale'] for x in server.events))
            self.assertTrue(all(x['connection_close'] for x in server.events))
        with digest_fixture() as server:
            rpc=driver.RPC(server.server_port,server.login)
            self.assertEqual(driver.snapshot(rpc),dict(height=1,top_block_hash=c.GENESIS,work='0x1',pool_hashes=[]))
            rpc.auth_controls()
            self.assertTrue(any(x['accepted'] for x in server.events))
            for session in {x['session'] for x in server.events}:
                pair=[x for x in server.events if x['session']==session]
                self.assertIn(len(pair),(1,2));self.assertFalse(pair[0]['authorized'])
                if len(pair)==2:self.assertTrue(pair[1]['authorized'])
            self.assertFalse(any(x['connection_close'] for x in server.events))

    def test_rpc_session_wallet_denials_and_rotated_login(self):
        driver=self.driver_fixture();driver.DEADLINE=time.monotonic()+20
        with digest_fixture() as server:
            rpc=driver.RPC(server.server_port,server.login);rpc.auth_controls(True)
            self.assertEqual(rpc.healthy(True),dict(balance=0,unlocked_balance=0))
            requests=c.denial_requests('dummy-address','dummy-seed')
            self.assertEqual(len(requests),17)
            for method,params in requests.items():
                rpc.healthy(True);code,value=rpc.call(method,params,raw=True)
                self.assertEqual((code,value['error']['code']),(200,-7));rpc.healthy(True)
            old=rpc.login;server.login=rpc.login='fixture:rotated'
            rpc.auth_controls(True,old)
            refused=[x for x in server.events if x['authorized'] and not x['accepted']]
            self.assertEqual(len(refused),3) # wrong before/after rotation, and old.
            for login in (None,'fixture:wrong',old):
                with self.assertRaises(RuntimeError) as caught:rpc.call('get_balance',login=login)
                self.assertEqual(caught.exception.readiness['http_status'],401)
                self.assertEqual(caught.exception.readiness['exception_class'],'RuntimeError')
                self.assertNotIn('PRIVATE_SECRET',json.dumps(caught.exception.readiness))
            self.assertEqual({x['method'] for x in server.events if x['accepted']} & requests.keys(),requests.keys())
            self.assertTrue(all(sum(x['session']==s for x in server.events)<=2 for s in range(len(server.sessions))))

    def test_rpc_session_stale_is_one_response_then_fresh_call(self):
        driver=self.driver_fixture();driver.DEADLINE=time.monotonic()+20
        with digest_fixture(force_stale=True) as server:
            rpc=driver.RPC(server.server_port,server.login)
            self.assertEqual(rpc.call('get_info',raw=True),(401,{}))
            self.assertEqual(len(server.events),2);self.assertTrue(server.events[-1]['stale'])
            self.assertEqual(rpc.healthy()['status'],'OK')
            self.assertEqual([x['session'] for x in server.events],[0,0,1,1])

    def test_rpc_session_closed_or_unsupported_challenge_never_reconnects(self):
        driver=self.driver_fixture();driver.DEADLINE=time.monotonic()+20
        for options in [dict(close_challenge=True),dict(algorithms=('MD5-sess',)),dict(qop='auth-int')]:
            with self.subTest(options=options),digest_fixture(**options) as server:
                self.assertEqual(driver.RPC(server.server_port,server.login).call('get_info',raw=True),(401,{}))
                self.assertEqual(len(server.events),1);self.assertFalse(server.events[0]['authorized'])

    def test_rpc_session_deadline_and_json_errors_close_without_public_text(self):
        driver=self.driver_fixture()
        with digest_fixture(delay=.15) as server:
            driver.DEADLINE=time.monotonic()+.05;start=time.monotonic()
            with self.assertRaises((OSError,ValueError)) as caught:driver.RPC(server.server_port,server.login).healthy()
            self.assertLess(time.monotonic()-start,.12)
            self.assertNotIn('PRIVATE_SECRET',json.dumps(caught.exception.readiness))
        driver.DEADLINE=time.monotonic()+20
        with digest_fixture(bad_json=True) as server:
            with self.assertRaises(json.JSONDecodeError) as caught:driver.RPC(server.server_port,server.login).healthy()
            self.assertEqual(caught.exception.readiness['http_status'],200)
            self.assertNotIn('PRIVATE_SECRET',json.dumps(caught.exception.readiness))

    def test_rpc_session_transport_closes_and_shares_five_second_budget(self):
        from unittest.mock import MagicMock
        driver=self.driver_fixture();driver.DEADLINE=time.monotonic()+20
        for stage in ('connect','request','getresponse','read1'):
            connection=MagicMock();response=MagicMock();response.__enter__.return_value=response
            response.status=200;response.headers={};response.read1.side_effect=[b'{}',b'']
            connection.getresponse.return_value=response
            target=response if stage=='read1' else connection
            getattr(target,stage).side_effect=ConnectionResetError('PRIVATE_SECRET')
            with self.subTest(stage=stage),patch('http.client.HTTPConnection',return_value=connection):
                with self.assertRaises(ConnectionResetError) as caught:driver.RPC(1,'fixture:dummy').healthy()
                connection.close.assert_called_once()
                self.assertNotIn('PRIVATE_SECRET',json.dumps(caught.exception.readiness))
        driver.DEADLINE=600
        clock=[0.0];connection=MagicMock();response=MagicMock();response.__enter__.return_value=response
        response.status=200;response.headers={};response.read1.side_effect=[b'{}',b'']
        connection.getresponse.return_value=response
        def request(*args):clock[0]+=3
        connection.request.side_effect=request
        with patch('http.client.HTTPConnection',return_value=connection),patch.object(driver.time,'monotonic',side_effect=lambda:clock[0]):
            self.assertEqual(driver.RPC(1,'fixture:dummy').healthy(),{})
        timeouts=[x.args[0] for x in connection.sock.settimeout.call_args_list]
        self.assertEqual(timeouts[0],5);self.assertEqual(timeouts[-1],2)
        connection.close.assert_called_once()

    def test_rpc_progressing_headers_and_chunk_framing_obey_driver_deadline(self):
        import threading
        driver=self.driver_fixture()
        old=subprocess.check_output(['git','show','be242236:./vanguard/network/profile-integration.py']).decode()
        baseline=type(sys)('baseline_progress');baseline.__file__=str(c.HERE/'profile-integration.py')
        exec(compile(old,baseline.__file__,'exec'),baseline.__dict__)
        for stage in ('challenge_headers','response_headers','chunk_size','chunk_trailer'):
            for candidate in (baseline,driver):
                with self.subTest(stage=stage,candidate=candidate.__name__),digest_fixture(progress_stage=stage) as server:
                    candidate.DEADLINE=time.monotonic()+.12;start=time.monotonic()
                    caught=None
                    try:candidate.RPC(server.server_port,server.login).healthy()
                    except (OSError,ValueError) as error:caught=error
                    elapsed=time.monotonic()-start
                    print(json.dumps(dict(rpc_deadline_probe=stage,candidate=candidate.__name__,elapsed_seconds=elapsed,
                                          exception=type(caught).__name__ if caught is not None else 'NONE')))
                    if candidate is baseline:self.assertGreater(elapsed,.25)
                    else:
                        self.assertIsInstance(caught,TimeoutError)
                        self.assertLess(elapsed,.24);self.assertGreater(elapsed,.08)
                        self.assertFalse(any(isinstance(t,threading.Timer) for t in threading.enumerate()))
                        self.assertNotIn('PRIVATE_SECRET',json.dumps(caught.readiness))
                    self.assertEqual(len(server.sessions),1)
                    self.assertLessEqual(len(server.events),2)
        with digest_fixture() as server:
            driver.DEADLINE=time.monotonic()+20
            self.assertEqual(driver.RPC(server.server_port,server.login).healthy()['status'],'OK')
            self.assertEqual([x['session'] for x in server.events],[0,0])
            self.assertFalse(any(isinstance(t,threading.Timer) for t in threading.enumerate()))

    def test_rpc_invalid_chunk_framing_closes_socket_and_timer(self):
        import threading
        from http.client import IncompleteRead
        driver=self.driver_fixture();driver.DEADLINE=time.monotonic()+20
        with digest_fixture(progress_stage='chunk_invalid') as server:
            with self.assertRaises(IncompleteRead) as caught:driver.RPC(server.server_port,server.login).healthy()
            self.assertNotIn('PRIVATE_SECRET',json.dumps(caught.exception.readiness))
            self.assertEqual(len(server.sessions),1);self.assertEqual(len(server.events),2)
            self.assertFalse(any(isinstance(t,threading.Timer) for t in threading.enumerate()))

    def test_rpc_progressing_headers_obey_original_five_second_call_budget(self):
        import threading,http.client
        driver=self.driver_fixture();driver.DEADLINE=time.monotonic()+30
        connected=[];connect=http.client.HTTPConnection.connect
        def capture(connection):
            connect(connection);connected.append(connection.sock.getsockname())
        with digest_fixture(progress_stage='response_headers',progress_delay=.25,progress_count=24) as server:
            start=time.monotonic()
            with patch.object(http.client.HTTPConnection,'connect',capture),self.assertRaises(TimeoutError):
                driver.RPC(server.server_port,server.login).healthy()
            elapsed=time.monotonic()-start
            print(json.dumps(dict(rpc_deadline_probe='five_second_call',elapsed_seconds=elapsed,
                owned_connects=len(connected),accepted_sessions=len(server.sessions),http_events=server.events)))
            self.assertGreater(elapsed,4.8);self.assertLess(elapsed,5.5)
            self.assertEqual(len(connected),1)
            owned={h.session for h in server.sessions if h.client_address in connected}
            self.assertEqual(len(owned),1);self.assertEqual(len(server.events),2)
            self.assertEqual({event['session'] for event in server.events},owned)
            self.assertFalse(any(isinstance(t,threading.Timer) for t in threading.enumerate()))

    def readiness_timeout(self,driver,check):
        clock=[0.0]
        def sleep(seconds):clock[0]+=seconds
        driver.DEADLINE=600
        with patch.object(driver.time,'monotonic',side_effect=lambda:clock[0]),patch.object(driver.time,'sleep',side_effect=sleep):
            with self.assertRaises(TimeoutError) as caught:driver.wait(check,seconds=.25)
        return caught.exception

    def test_readiness_transient_recovery_and_last_failure_codes(self):
        driver=self.driver_fixture();clock=[0.0];driver.DEADLINE=600
        def sleep(seconds):clock[0]+=seconds
        checks=iter([ConnectionRefusedError('PRIVATE_SECRET'),False,{'ready':True}])
        def check():
            value=next(checks)
            if isinstance(value,Exception):raise value
            return value
        with patch.object(driver.time,'monotonic',side_effect=lambda:clock[0]),patch.object(driver.time,'sleep',side_effect=sleep):
            self.assertEqual(driver.wait(check,seconds=1),{'ready':True})
        from integration import runtime_diagnostics as d
        def fail():raise KeyError('PRIVATE_SECRET')
        error=self.readiness_timeout(driver,fail)
        self.assertIsInstance(error.__cause__,KeyError)
        codes=d.exception_codes(error,c.require)
        self.assertEqual(codes['readiness'],dict(operation='OTHER_OPERATION',exception_class='KeyError',
            http_status=0,require_label='NONE',key_field='OTHER_FIELD',attempts=3))
        self.assertNotIn('PRIVATE_SECRET',json.dumps(codes))
        # Exact old wait loses both cause and structured diagnosis on this control.
        old=subprocess.check_output(['git','show','530205f7:./vanguard/network/profile-integration.py']).decode()
        baseline=type(sys)('baseline');baseline.__file__=str(c.HERE/'profile-integration.py');exec(compile(old,baseline.__file__,'exec'),baseline.__dict__)
        bad=self.readiness_timeout(baseline,fail)
        self.assertIsNone(bad.__cause__);self.assertNotIn('readiness',d.exception_codes(bad,c.require))

    def test_readiness_snapshot_fields_guards_and_operations(self):
        driver=self.driver_fixture()
        good=[dict(status='OK',height=1,top_block_hash=c.GENESIS,wide_cumulative_difficulty='0x1'),{},dict(pool_stats=dict(txs_total=0))]
        class RPC:
            def call(self,*args,**kwargs):return next(self.rows)
        rpc=RPC();rpc.rows=iter(copy.deepcopy(good));self.assertEqual(driver.snapshot(rpc)['height'],1)
        cases=[(0,'status','get_info'),(0,'height','get_info'),(0,'top_block_hash','get_info'),
            (0,'wide_cumulative_difficulty','get_info'),(2,'pool_stats','pool_stats'),(2,'txs_total','pool_stats')]
        for row,field,operation in cases:
            values=copy.deepcopy(good)
            del (values[row]['pool_stats'] if field=='txs_total' else values[row])[field]
            # Reset the RPC payload on each actual readiness attempt.
            def check():rpc.rows=iter(copy.deepcopy(values));return driver.snapshot(rpc)
            error=self.readiness_timeout(driver,check)
            self.assertEqual((error.readiness['operation'],error.readiness['key_field']),(operation,field))
        for row,field,value,label,operation in [(0,'height',0,'NON_GENESIS_OR_WRONG_CHAIN','get_info'),
            (0,'top_block_hash','0'*64,'NON_GENESIS_OR_WRONG_CHAIN','get_info'),
            (0,'status','BUSY','NON_GENESIS_OR_WRONG_CHAIN','get_info'),
            (1,'tx_hashes',['PRIVATE_SECRET'],'NONEMPTY_POOL','pool_hashes'),
            (2,'pool_stats',{'txs_total':1},'NONEMPTY_POOL','pool_stats')]:
            values=copy.deepcopy(good);values[row][field]=value
            def check():rpc.rows=iter(copy.deepcopy(values));return driver.snapshot(rpc)
            error=self.readiness_timeout(driver,check)
            self.assertEqual((error.readiness['require_label'],error.readiness['operation']),(label,operation))
            self.assertNotIn('PRIVATE_SECRET',json.dumps(error.readiness))

    def test_readiness_http_transport_payload_and_export_boundary(self):
        import io,urllib.error
        driver=self.driver_fixture();driver.DEADLINE=time.monotonic()+60
        from integration import runtime_diagnostics as d
        for method,path,operation in [('get_info','json_rpc','get_info'),('','get_transaction_pool_hashes','pool_hashes'),('','get_transaction_pool_stats','pool_stats')]:
            for failure in (urllib.error.HTTPError('http://127.0.0.1/',503,'PRIVATE_SECRET',{},None),
                    urllib.error.URLError('PRIVATE_SECRET'),ValueError('PRIVATE_SECRET')):
                with patch('http.client.HTTPConnection') as opener:
                    opener.return_value.connect.side_effect=failure
                    with self.assertRaises((OSError,ValueError,RuntimeError)) as caught:driver.RPC(1,'fixture:dummy').call(method,path=path)
                if isinstance(failure,urllib.error.HTTPError):failure.close()
                codes=caught.exception.readiness
                self.assertEqual(codes['operation'],operation)
                self.assertEqual(codes['http_status'],503 if isinstance(failure,urllib.error.HTTPError) else 0)
                self.assertNotIn('PRIVATE_SECRET',json.dumps(codes))
        for body,label,kind in [(b'{"error":{"message":"PRIVATE_SECRET"}}','NATIVE_RPC_RETURNED_ERROR','ValueError'),
                (b'PRIVATE_SECRET','NONE','JSONDecodeError')]:
            from unittest.mock import MagicMock
            response=MagicMock();response.status=200;response.headers={}
            response.read1.side_effect=[body,b''];response.__enter__.return_value=response
            with patch('http.client.HTTPConnection') as opener:
                opener.return_value.getresponse.return_value=response
                with self.assertRaises(ValueError) as caught:driver.RPC(1,'fixture:dummy').call('get_info')
            codes=caught.exception.readiness
            self.assertEqual((codes['http_status'],codes['require_label'],codes['exception_class']),(200,label,kind))
            self.assertNotIn('PRIVATE_SECRET',json.dumps(codes))
        valid=dict(operation='get_info',exception_class='KeyError',http_status=0,require_label='NONE',key_field='height',attempts=3)
        public=dict(step='READINESS_RPC',exception_class='TimeoutError',require_label='NONE',readiness=valid)
        self.assertTrue(d.checked(public))
        for key,bad in [('operation','PRIVATE_SECRET'),('exception_class','PRIVATE_SECRET'),('http_status',True),
                ('http_status',600),('require_label','PRIVATE_SECRET'),('key_field','PRIVATE_SECRET'),('attempts',True),('attempts',0),('attempts',1000001)]:
            self.assertFalse(d.checked(dict(public,readiness=dict(valid,**{key:bad}))))
        self.assertFalse(d.checked(dict(public,readiness=dict(valid,body='PRIVATE_SECRET'))))
        def mutate(root):(root/'public/runtime-diagnostics.json').write_text(json.dumps(public))
        _,receipt,_=self.exercise(failed_phase='runtime',mutate_public=mutate)
        self.assertEqual(receipt['runtime_diagnostics'],public)

    def test_readiness_actual_main_preserves_private_cause_and_public_codes(self):
        driver=self.driver_fixture()
        def fail(*args):
            class RPC:
                def call(self,*args,**kwargs):return {}
            error=self.readiness_timeout(driver,lambda:driver.snapshot(RPC()))
            raise error
        with patch.object(driver,'node',side_effect=fail):result,value=self.traced_main(driver)
        self.assertEqual(result,1);self.assertEqual(value['exception_class'],'TimeoutError')
        self.assertEqual(value['readiness']['key_field'],'status')
        self.assertIn("KeyError: 'status'",(driver.PRIVATE/'failure-traceback').read_text())
        self.assertEqual((driver.PRIVATE/'failure-traceback').stat().st_mode & 0o777,0o600)

    def test_exact_direct_grant_rejects_legacy_and_each_wrong_binding(self):
        value = grant(self.output);self.validate(value)
        for key,bad in [('schema','meownero-platform-grant/2'),('candidate_commit','b'*40),
            ('inputs_sha256','b'*64),('runner_sha256','b'*64),('artifact_sha256','b'*64),
            ('output_root',str(self.base/'other')),('attempts',2),('retry',True),
            ('wall_seconds',4600),('container_flags',[]),('transactions',1)]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(dict(value,**{key:bad}))
        for key in ('host_overhead_allowance','load_rule'):
            with self.assertRaises(KeyError):self.validate({k:v for k,v in value.items() if k != key})

    def test_lock_nonblocking_preserves_inode_and_releases_on_close(self):
        fd,receipt = r.acquire_lock()
        try:
            with self.assertRaises(BlockingIOError):r.acquire_lock()
            self.assertEqual(self.lock.stat().st_ino,receipt['inode'])
        finally:os.close(fd)
        fd,_ = r.acquire_lock();os.close(fd)

    def test_absent_lock_created_0600_and_wrong_existing_never_replaced(self):
        self.lock.unlink();fd,receipt = r.acquire_lock();os.close(fd)
        self.assertTrue(receipt['created']);self.assertEqual(self.lock.stat().st_mode & 0o777,0o600)
        self.lock.chmod(0o644);before = self.lock.stat()
        with self.assertRaisesRegex(ValueError,'metadata'):r.acquire_lock()
        self.assertEqual(self.lock.stat().st_ino,before.st_ino)

    def test_admission_checks_both_floors_collisions_and_explicit_load_rule(self):
        observation = dict(available_memory_bytes=5*r.GiB,native_processes=[],native_containers=[])
        with patch.object(r.g,'admission',return_value=observation), \
             patch.object(r.shutil,'disk_usage',return_value=type('Disk',(),{'free':20*r.GiB})()), \
             patch.object(r.os,'getloadavg',return_value=(6,6,6)):
            r.admit(IMAGE,self.base,grant(self.output))
            for key,bad in [('available_memory_bytes',5*r.GiB-1),('native_processes',[1]),('native_containers',[1])]:
                with patch.dict(observation,{key:bad}),self.assertRaises(ValueError):
                    r.admit(IMAGE,self.base,grant(self.output))
            with patch.object(r.shutil,'disk_usage',return_value=type('Disk',(),{'free':20*r.GiB-1})()), \
                 self.assertRaises(ValueError):r.admit(IMAGE,self.base,grant(self.output))
            with patch.object(r.os,'getloadavg',return_value=(6.01,0,0)),self.assertRaises(ValueError):
                r.admit(IMAGE,self.base,grant(self.output))

    def test_actual_child_deadline_kills_owned_group_and_preserves_unrelated_child(self):
        self.output.mkdir();controller = r.Controller(self.output,grant(self.output),time.monotonic())
        unrelated = subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
        try:
            with self.assertRaisesRegex(ValueError,'deadline'):
                controller.run([sys.executable,'-c','import time; time.sleep(30)'],time.monotonic()+.2,monitor=False)
            self.assertIsNone(unrelated.poll())
            self.assertTrue(all(p.poll() is not None for p,_,_ in controller.children))
        finally:unrelated.terminate();unrelated.wait(timeout=5)

    def test_resource_sampling_records_owned_directory_and_measured_overhead(self):
        self.output.mkdir();(self.output/'data').write_bytes(b'x'*4096)
        controller = r.Controller(self.output,grant(self.output),time.monotonic())
        controller.sample(force=True)
        self.assertGreaterEqual(controller.peak['disk_bytes'],4096)
        self.assertGreater(controller.peak['peak_rss_bytes'],0)
        self.assertEqual(controller.samples,1)
        with patch.object(r.shutil,'disk_usage',return_value=type('Disk',(),{'free':4*r.GiB-1})()), \
             self.assertRaisesRegex(ValueError,'free disk'):controller.sample(force=True)

    def test_staging_high_water_abort_is_measured_without_claiming_a_quota(self):
        self.output.mkdir();controller = r.Controller(self.output,grant(self.output),time.monotonic())
        with patch.object(controller,'run',return_value=subprocess.CompletedProcess([],0,
                 str(15*r.GiB+1).encode()+b'\t'+os.fsencode(self.output)+b'\n',b'')), \
             self.assertRaisesRegex(ValueError,'15 GiB'):controller.sample(force=True)
        self.assertGreater(controller.peak['disk_bytes'],15*r.GiB)

    def vanished_file_sample(self):
        self.output.mkdir();(self.output/'remaining').write_bytes(b'x'*8192)
        gone=self.output/'compiler-temporary';gone.write_bytes(b'temporary')
        # Enumerate the real tree, then remove an entry before GNU du stats it.
        # The extra listed operand deterministically exposes the same GNU du
        # total+ENOENT result as deletion between its internal readdir/stat.
        self.assertIn(gone,list(self.output.iterdir()));gone.unlink()
        observed={}
        def walk(argv,deadline,**kwargs):
            self.assertEqual(argv[0],'du')
            result=subprocess.run(argv+[str(gone)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env={'PATH':os.environ['PATH'],'LC_ALL':'C'},timeout=10)
            self.assertEqual(result.returncode,1);observed['result']=result
            if kwargs.get('check',True):raise subprocess.CalledProcessError(result.returncode,argv)
            return result
        controller=r.Controller(self.output,grant(self.output),time.monotonic())
        with patch.object(controller,'run',side_effect=walk):controller.sample(force=True)
        expected=sum(p.lstat().st_blocks*512 for p in [self.output,*self.output.iterdir()])
        self.assertEqual(controller.peak['disk_bytes'],expected)
        self.assertEqual(controller.samples,1)
        # A directory can also disappear between enumeration and opendir.
        for action in (b'access',b'read directory'):
            result=subprocess.CompletedProcess([],1,observed['result'].stdout,
                b"du: cannot "+action+b" '"+os.fsencode(gone)+b"': No such file or directory\n")
            with patch.object(controller,'run',return_value=result):controller.sample(force=True)
        return observed

    def test_real_du_vanished_entry_keeps_remaining_allocated_total(self):
        self.vanished_file_sample()

    def test_disk_metrology_rejects_every_non_enoent_error_and_invalid_total(self):
        self.output.mkdir();controller=r.Controller(self.output,grant(self.output),time.monotonic())
        total=b'4096\t'+os.fsencode(self.output)+b'\n'
        missing=lambda path:b"du: cannot access '"+os.fsencode(path)+b"': No such file or directory\n"
        for code,out,err,reason in [(2,total,b'','child_exit'),(1,total,b'','missing_error'),
            (1,total,b"du: cannot read directory 'x': Permission denied\n",'unexpected_error'),
            (1,total,missing(self.base/'outside'),'unexpected_error'),
            (1,total,missing(self.output/'..'/'outside'),'unexpected_error'),
            (1,total,missing(self.output),'unexpected_error'),
            (0,total,b'PRIVATE_STDERR\n','unexpected_error'),(0,b'',b'','invalid_total'),
            (0,b'bad\t'+os.fsencode(self.output)+b'\n',b'','invalid_total'),
            (0,b'9'*5000+b'\t'+os.fsencode(self.output)+b'\n',b'','invalid_total'),
            (0,total+total,b'','invalid_total'),(0,b'4096\telsewhere\n',b'','invalid_total')]:
            with self.subTest(code=code,reason=reason),patch.object(controller,'run',
                    return_value=subprocess.CompletedProcess([],code,out,err)),self.assertRaises(r.MetrologyFailure) as error:
                controller.sample(force=True)
            self.assertEqual(error.exception.diagnostic,dict(code='metrology_disk_walk',reason=reason,exit_code=code))
            self.assertNotIn('PRIVATE_STDERR',str(error.exception))

    def test_real_du_permission_denial_is_metrology_failure(self):
        self.output.mkdir();private=self.output/'denied';private.mkdir();private.chmod(0)
        try:
            controller=r.Controller(self.output,grant(self.output),time.monotonic())
            with self.assertRaises(r.MetrologyFailure) as error:controller.sample(force=True)
            self.assertEqual(error.exception.diagnostic['reason'],'unexpected_error')
            self.assertEqual(error.exception.diagnostic['exit_code'],1)
        finally:private.chmod(0o700)

    def test_disk_metrology_refuses_root_symlink_escape_and_never_follows_nested_links(self):
        outside=self.base/'outside';outside.mkdir();(outside/'data').write_bytes(b'x'*65536)
        self.output.symlink_to(outside,target_is_directory=True)
        controller=r.Controller(self.output,grant(self.output),time.monotonic())
        with self.assertRaises(r.MetrologyFailure) as error:controller.sample(force=True)
        self.assertEqual(error.exception.diagnostic['reason'],'unsafe_root')
        self.output.unlink();self.output.mkdir();(self.output/'link').symlink_to(outside,target_is_directory=True)
        controller.sample(force=True)
        self.assertEqual(controller.peak['disk_bytes'],sum(p.lstat().st_blocks*512 for p in
            [self.output,self.output/'link']))

    def test_real_native_child_exit_survives_sampler_failure_without_child_code_attribution(self):
        self.output.mkdir();controller=r.Controller(self.output,grant(self.output),time.monotonic())
        diagnostic={}
        with patch.object(controller,'sample',side_effect=r.MetrologyFailure('metrology_disk_walk','child_exit',23)), \
             self.assertRaises(r.MetrologyFailure):
            controller.run([sys.executable,'-c','import time;time.sleep(30)'],time.monotonic()+10,
                check=False,native_diagnostic=diagnostic)
        self.assertEqual(diagnostic['cli_exit_code'],controller.children[-1][0].returncode)
        self.assertNotEqual(diagnostic['cli_exit_code'],23)
        diagnostic={}
        result=controller.run([sys.executable,'-c','raise SystemExit(17)'],time.monotonic()+10,
            check=False,monitor=False,native_diagnostic=diagnostic)
        self.assertEqual(result.returncode,17);self.assertEqual(diagnostic,dict(cli_exit_code=17))

    def test_expired_positive_command_budget_never_spawns(self):
        controller = r.Controller(self.base,grant(self.output),time.monotonic())
        with patch.object(r.subprocess,'Popen') as spawn,self.assertRaises(ValueError):
            controller.run(['unused'],time.monotonic()-1)
        spawn.assert_not_called()

    def test_entry_has_no_retired_facility_imports(self):
        tree = ast.parse((c.HERE/'run-profile.py').read_text())
        imports = [node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
        imports += [name.name for node in ast.walk(tree) if isinstance(node,ast.Import) for name in node.names]
        self.assertFalse(any(any(part in name for part in ('manager','outer','bootstrap','constructor','ingress','helper','handoff','dispatch'))
                             for name in imports if name))

    def test_actual_staging_prefix_reaches_frozen_driver_missing_binary_sentinel(self):
        class BeforeSourceRead(Exception): pass
        self.output.mkdir()
        control = type('Control',(),{'root':self.output})()
        with patch.object(c,'json_file',side_effect=BeforeSourceRead),self.assertRaises(BeforeSourceRead):
            r.stage_inputs(control,Path('unused'),{})
        private = self.output/'staging/private'
        self.assertFalse(private.exists())
        spec = importlib.util.spec_from_file_location('frozen_driver',c.HERE/'profile-integration.py')
        driver = importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        driver.PRIVATE = private;driver.BIN = self.base/'missing-binaries'
        old_umask = os.umask(0o077)
        try:
            with patch.object(driver.subprocess,'Popen') as spawn,self.assertRaises(FileNotFoundError) as error:
                driver.main()
            self.assertEqual(Path(error.exception.filename),driver.BIN/'monerod')
            self.assertTrue(private.is_dir());self.assertEqual(private.stat().st_mode & 0o777,0o700)
            spawn.assert_not_called();self.assertFalse(driver.PROCS)
        finally:os.umask(old_umask)

    def exercise(self, *, refuse=None, uncertain_create=False, fail_runtime=False,
                 failed_phase=None, raised_phase=None, mutate_public=None, container_exit_only=False,
                 mutate_build=None, mutate_staging=None, cleanup_failure=False,
                 staging_retained=None, mutate_failure=None, reuse=None, stage_binary_sources=None,
                 metrology_phase=None, cleanup_race=None):
        inputs = self.base/'inputs.json';inputs.write_bytes(b'{}')
        value = grant(self.output);events = [];state = {'container':None,'starts':0}
        manifest=self.build_manifest()
        if reuse:
            cached=r.reuse_build(reuse,manifest)
            value.update(mode='runtime-only',reuse_build_root=str(reuse),retained_build_sha256=cached['manifest_sha256'],
                wall_seconds=900,build_seconds=0)
        case = self
        class FakeController(r.Controller):
            def sample(self,force=False):
                self.samples += 1
                self.peak.update(peak_rss_bytes=123456,cpu_seconds=1.5,peak_pids=2,disk_bytes=4096)
            def run(self,argv,deadline,**kwargs):
                case.assertGreater(deadline,time.monotonic())
                case.assertEqual(argv[:len(r.g.DOCKER)],r.g.DOCKER)
                cmd = argv[len(r.g.DOCKER):];events.append(cmd[0])
                output = b'';code = 0;error = b''
                if cmd[:2] == ['image','inspect']:output = json.dumps([{'Id':IMAGE}]).encode()
                elif cmd[0] == 'create':
                    case.assertEqual(cmd.count('--name'),1)
                    h = dict(NetworkMode='none',NanoCpus=2_000_000_000,Memory=4*r.GiB,
                        MemorySwap=4*r.GiB,PidsLimit=256,CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],
                        Privileged=False,PortBindings={},Ulimits=[dict(Name='core',Soft=0,Hard=0)])
                    state['container'] = dict(Id='c'*64,Name='/meownero-profile-'+GRANT,Image=IMAGE,
                        Config=dict(Labels={'meownero.profile.attempt':'meownero-profile-'+GRANT},User=f'{os.getuid()}:{os.getgid()}'),
                        Mounts=[dict(Source=str(case.output/'staging'),Destination='/out')],
                        HostConfig=h,State=dict(Running=False,ExitCode=0,OOMKilled=False))
                    if uncertain_create:raise TimeoutError('create response lost')
                elif cmd[0] == 'inspect':
                    if state['container']:output = json.dumps([state['container']]).encode()
                    else:code,error = 1,b'error: no such object'
                elif cmd[0] == 'ps':
                    output = b'c'*64+b'\n' if state['container'] else b''
                elif cmd[0] == 'start':
                    state['starts'] += 1
                    if state['starts'] == 2 and fail_runtime:
                        state['container']['State']['Running'] = True
                        raise RuntimeError('runtime failed')
                    phase = 'build' if state['starts'] == 1 and not reuse else 'runtime'
                    if phase == metrology_phase:
                        state['container']['State'].update(Running=True,ExitCode=137)
                        kwargs['native_diagnostic']['cli_exit_code']=-15
                        raise r.MetrologyFailure('metrology_disk_walk','child_exit',23)
                    (case.output/'staging'/('resources-'+phase+'.json')).write_text(json.dumps(dict(oom=0,oom_kill=0)))
                    for filename,keys in c.REQUIRED.items():
                        produced = ('build.json',) if phase == 'build' else set(c.REQUIRED)-{'build.json','cleanup.json','resources.json'}
                        if filename in produced:
                            (case.output/'public'/filename).write_text(json.dumps(case.producer_rows()[filename]))
                    if phase == 'build' and mutate_build:mutate_build(case.output/'public/build.json')
                    if phase == 'build' and mutate_staging:mutate_staging(case.output/'staging')
                    if phase in (failed_phase,raised_phase):
                        secret = 'PRIVATE_WALLET_RPC_LOGIN_FRAME_ENV_STDOUT_STDERR_SENTINEL'
                        for name in ('build.log','configure.log','private/console.log'):
                            text = 'COMPILER_ERROR_FIXTURE' if phase == 'build' and name != 'private/console.log' else secret
                            (case.output/'staging'/name).write_text(text)
                        if mutate_failure:mutate_failure(case.output/'staging')
                        if phase == 'runtime':
                            (case.output/'public/peer.json').write_text(json.dumps(dict(
                                native_handshake=dict(status='PASS',request_sha256='a'*64,command=1001))))
                        state['container']['State']['ExitCode'] = 17
                        if phase == raised_phase:
                            raise subprocess.CalledProcessError(17,argv,output=secret.encode(),stderr=secret.encode())
                        code = 0 if container_exit_only else 17
                        output = error = secret.encode()
                    if phase == 'runtime':
                        (case.output/'public/runtime-diagnostics.json').write_text(json.dumps(
                            dict(step='COMPLETE',exception_class='NONE',require_label='NONE')))
                        if mutate_public:mutate_public(case.output)
                elif cmd[0] == 'stop':
                    if cleanup_race != 'kill':state['container']['State']['Running'] = False
                    code=1 if cleanup_race else 0
                elif cmd[0] == 'kill':
                    state['container']['State']['Running']=False;code=1
                elif cmd[0] == 'rm':
                    if cleanup_failure:raise RuntimeError('fixture cleanup failure')
                    state['container'] = None
                    if cleanup_race:code=1
                else:raise AssertionError(cmd)
                return subprocess.CompletedProcess(argv,code,output,error)
        def admission(image,root,grant):
            events.append('admit')
            count = events.count('admit')
            if count == refuse:raise ValueError('real admission refusal')
            case.assertFalse((case.output/'staging').exists() if count == 1 else False)
            fd = os.open(case.lock,os.O_RDWR)
            try:
                with case.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            finally:os.close(fd)
            return dict(available_memory_bytes=5*r.GiB,free_disk_bytes=20*r.GiB)
        def stage(control,inputs,manifest):
            events.append('stage');(case.output/'staging').mkdir();(case.output/'staging/private').mkdir()
            (case.output/'staging/private/secret').write_text('never export')
            (case.output/'staging').chmod(0o700)
            target=case.output/'staging/build/bin';target.mkdir(parents=True,mode=0o700)
            for name in r.BINARIES:
                path=target/name
                if stage_binary_sources:shutil.copy2(stage_binary_sources/name,path)
                else:path.write_bytes(case.binary_bytes(name))
                path.chmod(0o700)
            if reuse:r.runtime_marker(case.output/'staging')
        def api(path):return json.dumps(comment(value)).encode() if '/comments/' in path else b'packet'
        with patch.object(r,'Controller',FakeController),patch.object(r,'stage_inputs',stage), \
             patch.object(r,'stage_reuse',side_effect=lambda control,inputs,manifest,reuse:stage(control,inputs,manifest)), \
             patch.object(r,'admit',admission),patch.object(r,'api',api), \
             patch.object(r,'check_inputs',return_value=manifest), \
             patch.object(r.subprocess,'check_output',side_effect=['a'*40+'\n','']), \
             patch.object(sys,'argv',['run-profile.py','--inputs',str(inputs),'--grant-comment',GRANT,
                 '--artifact-sha256',c.digest(b'packet'),'--out',str(self.output)]+(['--reuse-build',str(reuse)] if reuse else [])):
            result = r.main()
        if not cleanup_failure:self.assertIsNone(state['container'])
        if staging_retained is None:
            staging_retained=bool(fail_runtime or failed_phase=='runtime' or raised_phase=='runtime')
        self.assertEqual((self.output/'staging').exists(),staging_retained)
        fd,_ = r.acquire_lock();os.close(fd)
        receipt = json.loads((self.output/'evidence/receipt.json').read_text()) if self.output.exists() else None
        if receipt:
            self.assertEqual(receipt['rows']['cleanup.json']['lock_released']['status'],'PASS')
            self.assertNotIn('never export',json.dumps(receipt))
            for path in (self.output/'evidence').iterdir():
                if path.is_file():self.assertNotIn('PRIVATE_WALLET_RPC_LOGIN_FRAME_ENV_STDOUT_STDERR_SENTINEL',path.read_text())
        return result,receipt,events

    def test_main_metrology_abort_records_real_stopped_exit_separately_and_confirms_cleanup_races(self):
        for race in ('stop','kill','rm'):
            with self.subTest(race=race):
                self.output=self.base/('metrology-'+race)
                result,receipt,events=self.exercise(metrology_phase='build',cleanup_race=race)
                self.assertEqual(result,1);self.assertEqual(receipt['failure_class'],'MetrologyFailure')
                diagnostic=receipt['phase_diagnostics']['build']
                self.assertEqual(diagnostic['cli_exit_code'],-15)
                self.assertEqual(diagnostic['container_exit_code'],137)
                self.assertEqual(diagnostic['metrology_failure'],dict(
                    code='metrology_disk_walk',reason='child_exit',exit_code=23))
                self.assertEqual(receipt['rows']['resources.json']['disk']['status'],'FAIL')
                self.assertTrue(all(row['status']=='PASS' for row in receipt['rows']['cleanup.json'].values()))
                self.assertEqual(receipt['rows']['build.json'],c.empty_rows()['build.json'])
                self.assertNotIn('runtime',receipt['phase_diagnostics'])
                self.assertEqual(events.count('start'),1)

    def test_two_admissions_one_container_same_container_restart_and_cleanup(self):
        result,receipt,events = self.exercise()
        self.assertEqual(result,0)
        self.assertEqual(events[:5],['admit','stage','image','admit','create'])
        self.assertEqual(events.count('create'),1);self.assertEqual(events.count('start'),2)
        self.assertTrue(receipt['result'].startswith('PASS_'));self.assertFalse(receipt['launch_ready'])
        self.assertTrue(all(x == 'NOT_RUN' for x in receipt['exclusions'].values()))
        self.assertTrue((self.output/'consumed.json').is_file())
        with patch.object(sys,'argv',['run-profile.py','--grant-comment',GRANT,'--artifact-sha256',
            c.digest(b'packet'),'--out',str(self.output)]),patch.object(r,'api') as api, \
             self.assertRaisesRegex(ValueError,'fresh absolute'):r.main()
        api.assert_not_called()

    def test_first_admission_refuses_before_staging_and_releases_lock(self):
        result,receipt,events = self.exercise(refuse=1)
        self.assertEqual(result,1);self.assertIsNone(receipt);self.assertEqual(events,['admit'])

    def test_writable_parent_refuses_before_staging_and_releases_lock(self):
        self.base.chmod(0o770)
        result,receipt,events = self.exercise()
        self.assertEqual(result,1);self.assertIsNone(receipt);self.assertEqual(events,['admit'])

    def test_second_admission_refuses_and_cleans_staging_without_create(self):
        result,receipt,events = self.exercise(refuse=2)
        self.assertEqual(result,1);self.assertNotIn('create',events)
        self.assertEqual(receipt['rows']['cleanup.json']['owned_staging_removed']['status'],'PASS')

    def test_ambiguous_create_is_recovered_by_exact_name_label_mount_and_removed(self):
        result,receipt,events = self.exercise(uncertain_create=True)
        self.assertEqual(result,1);self.assertIn('rm',events);self.assertNotIn('start',events)
        self.assertEqual(receipt['rows']['cleanup.json']['owned_cid_absent']['status'],'PASS')

    def test_runtime_failure_removes_container_and_retains_private_staging(self):
        result,receipt,events = self.exercise(fail_runtime=True)
        self.assertEqual(result,1);self.assertEqual(events.count('create'),1)
        self.assertLess(events.index('stop'),events.index('rm'))
        self.assertEqual(receipt['rows']['cleanup.json']['owned_cid_absent']['status'],'PASS')

    def test_failed_build_retains_partial_rows_and_sanitized_exit_before_cleanup(self):
        result,receipt,events = self.exercise(failed_phase='build')
        self.assertEqual(result,1);self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['failure_phase'],'build');self.assertEqual(events.count('start'),1)
        self.assertEqual(receipt['phase_diagnostics'],dict(build=dict(started=True,cli_exit_code=17,
            container_exit_code=17,oom_killed=False)))
        self.assertEqual(receipt['rows']['build.json']['three_production_binaries']['status'],'PASS')
        self.assertEqual(receipt['rows']['peer.json']['native_handshake']['status'],'NOT_RUN')

    def test_partial_runtime_failure_retains_observed_witnesses_and_unreached_rows(self):
        result,receipt,events = self.exercise(failed_phase='runtime',container_exit_only=True)
        self.assertEqual(result,1);self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['failure_phase'],'runtime');self.assertEqual(events.count('start'),2)
        self.assertEqual(receipt['phase_diagnostics']['runtime'],dict(started=True,cli_exit_code=0,
            container_exit_code=17,oom_killed=False))
        self.assertEqual(receipt['rows']['build.json']['rpc_translation_unit']['status'],'PASS')
        peer = receipt['rows']['peer.json']
        self.assertEqual(peer['native_handshake'],dict(status='PASS',request_sha256='a'*64,command=1001))
        self.assertEqual(peer['genesis_state']['status'],'NOT_RUN')
        self.assertEqual(json.loads((self.output/'evidence/peer.json').read_text()),peer)

    def test_raised_command_failure_keeps_exit_code_without_exception_transcripts(self):
        result,receipt,_ = self.exercise(raised_phase='runtime')
        self.assertEqual(result,1);self.assertEqual(receipt['failure_class'],'CalledProcessError')
        self.assertNotIn('cli_exit_code',receipt['phase_diagnostics']['runtime'])
        self.assertEqual(receipt['phase_diagnostics']['runtime']['container_exit_code'],17)
        self.assertEqual(receipt['rows']['peer.json']['native_handshake']['status'],'PASS')

    def test_incomplete_build_evidence_prevents_runtime_start(self):
        result,receipt,events = self.exercise(mutate_build=lambda path:path.write_text('{}'))
        self.assertEqual(result,1);self.assertEqual(receipt['failure_phase'],'build')
        self.assertEqual(events.count('start'),1);self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['rows']['build.json'],c.empty_rows()['build.json'])

    def test_failed_runtime_rejects_malformed_oversized_symlink_and_unallowlisted_evidence(self):
        secret = 'PRIVATE_WALLET_RPC_LOGIN_FRAME_ENV_STDOUT_STDERR_SENTINEL'
        outside = self.base/'private-transcript';outside.write_text(secret)
        def mutate(root):
            public = root/'public'
            (public/'build.json').write_text('{')
            (public/'wallet.json').write_text(json.dumps(dict(persisted_height_zero=dict(status='PASS',login=secret))))
            (public/'auth.json').write_text(' '*65537)
            (public/'isolation.json').unlink();(public/'isolation.json').symlink_to(outside)
            (public/'reopen.json').write_text(json.dumps({secret:dict(status='PASS')}))
            (public/(secret+'.log')).write_text(secret)
            (public/'cleanup.json').write_text(json.dumps(dict(lock_released=dict(status='PASS',raw=secret))))
            (public/'resources.json').write_text(secret)
            (root/'staging/resources-runtime.json').write_text(json.dumps(dict(oom=0,oom_kill=0,raw=secret)))
        result,receipt,_ = self.exercise(failed_phase='runtime',mutate_public=mutate)
        self.assertEqual(result,1);self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['rejected_evidence'],['auth.json','build.json','isolation.json','reopen.json',
            'unexpected-public-entry','wallet.json','resources-runtime.json'])
        self.assertEqual(receipt['rows']['peer.json']['native_handshake']['status'],'PASS')
        self.assertEqual(receipt['rows']['build.json']['three_production_binaries']['status'],'PASS')
        self.assertEqual(receipt['rows']['cleanup.json']['lock_released']['status'],'PASS')
        self.assertTrue(receipt['rows']['cleanup.json']['lock_released']['descriptor_closed'])
        self.assertNotIn('runtime',receipt['container_counters'])
        self.assertEqual(outside.read_text(),secret)
        self.assertEqual(set(p.name for p in (self.output/'evidence').iterdir()),set(c.REQUIRED)|{'receipt.json'})

    def test_runtime_marker_symlink_refuses_without_clobber_or_runtime(self):
        victim = self.base/'victim';victim.write_text('unchanged')
        result,receipt,events = self.exercise(mutate_staging=lambda path:
            (path/'BUILD_COMPLETE').symlink_to(victim))
        self.assertEqual(victim.read_text(),'unchanged')
        self.assertEqual(result,1);self.assertEqual(receipt['failure_class'],'FileExistsError')
        self.assertEqual(events.count('start'),1);self.assertEqual(receipt['result'],'FAIL')

    def test_runtime_marker_fifo_refuses_promptly_without_runtime(self):
        start = time.monotonic()
        result,receipt,events = self.exercise(mutate_staging=lambda path:os.mkfifo(path/'BUILD_COMPLETE'))
        self.assertLess(time.monotonic()-start,2)
        self.assertEqual(result,1);self.assertEqual(receipt['failure_class'],'FileExistsError')
        self.assertEqual(events.count('start'),1);self.assertEqual(receipt['result'],'FAIL')

    def planted_public(self, root, *, readonly=None):
        public = root/'public';victims = []
        for filename in [*c.REQUIRED,'receipt.json']:
            victim = self.base/('victim-'+filename);victim.write_text('unchanged');victims.append(victim)
            path = public/filename
            path.unlink(missing_ok=True);path.symlink_to(victim)
        (public/'unvalidated-producer.txt').write_text('UNTRUSTED_PRODUCER_SENTINEL')
        if readonly == 'root':
            public.chmod(0o500);self.addCleanup(public.chmod,0o700)
        if readonly == 'subdirectory':
            directory = public/'readonly';directory.mkdir();(directory/'entry').touch()
            directory.chmod(0o500);self.addCleanup(directory.chmod,0o700)
        return victims

    def assert_controller_evidence(self, victims):
        self.assertTrue(all(path.read_text() == 'unchanged' for path in victims))
        evidence = self.output/'evidence'
        self.assertEqual(evidence.stat().st_mode & 0o777,0o700)
        self.assertEqual(set(path.name for path in evidence.iterdir()),set(c.REQUIRED)|{'receipt.json'})
        for path in evidence.iterdir():
            self.assertFalse(path.is_symlink());self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(path.stat().st_nlink,1)
            self.assertNotIn('UNTRUSTED_PRODUCER_SENTINEL',path.read_text())
        argv = r.container_command(self.output,'unused',IMAGE)
        self.assertNotIn(str(evidence)+':/evidence',argv)
        self.assertFalse(any(str(evidence) in arg for arg in argv))

    def test_readonly_public_root_cannot_redirect_finalization(self):
        victims = []
        def mutate(root):victims.extend(self.planted_public(root,readonly='root'))
        result,receipt,_ = self.exercise(mutate_public=mutate,staging_retained=True)
        self.assertEqual(result,1);self.assertEqual(receipt['cleanup_failure_class'],'PermissionError')
        self.assertEqual(receipt['result'],'FAIL');self.assert_controller_evidence(victims)
        self.assertTrue((self.output/'public/receipt.json').is_symlink())

    def test_readonly_public_subdirectory_cannot_redirect_finalization(self):
        victims = []
        def mutate(root):victims.extend(self.planted_public(root,readonly='subdirectory'))
        result,receipt,_ = self.exercise(mutate_public=mutate,staging_retained=True)
        self.assertEqual(result,1);self.assertEqual(receipt['cleanup_failure_class'],'PermissionError')
        self.assertEqual(receipt['result'],'FAIL');self.assert_controller_evidence(victims)

    def test_container_cleanup_failure_still_publishes_only_controller_evidence(self):
        victims = []
        def mutate(root):victims.extend(self.planted_public(root))
        result,receipt,_ = self.exercise(mutate_public=mutate,cleanup_failure=True,staging_retained=True)
        self.assertEqual(result,1);self.assertEqual(receipt['cleanup_failure_class'],'RuntimeError')
        self.assertEqual(receipt['rows']['cleanup.json']['owned_cid_absent']['status'],'FAIL')
        self.assert_controller_evidence(victims)

    def test_absence_uses_successful_empty_listings_not_inspect_error_text(self):
        controller = r.Controller(self.base,grant(self.output),time.monotonic())
        controller.container_id = 'c'*64
        results = [subprocess.CompletedProcess([],1,b'',b'error: no such object')]
        results += [subprocess.CompletedProcess([],0,b'',b'') for _ in range(3)]
        with patch.object(controller,'run',side_effect=results) as run:
            self.assertIsNone(r.inspect_owned(controller,'task',IMAGE,controller.end))
        filters = [call.args[0] for call in run.call_args_list[1:]]
        self.assertEqual(len(filters),3)
        for argv in filters:
            self.assertEqual(argv[:len(r.g.DOCKER)+3],r.g.DOCKER+['ps','--all','--no-trunc'])
        self.assertEqual({argv[-1] for argv in filters},
            {'label=meownero.profile.attempt=task','name=^/task$','id='+'c'*64})

    def test_absence_refuses_nonzero_ps_and_any_matching_row(self):
        for index in range(3):
            for code,output in [(1,b''),(0,b'c'*64+b'\n')]:
                controller = r.Controller(self.base,grant(self.output),time.monotonic())
                controller.container_id = 'c'*64
                results = [subprocess.CompletedProcess([],1,b'',b'No such object')]
                results += [subprocess.CompletedProcess([],0,b'',b'') for _ in range(index)]
                results.append(subprocess.CompletedProcess([],code,output,b'daemon unavailable'))
                with self.subTest(index=index,code=code),patch.object(controller,'run',side_effect=results),self.assertRaises(ValueError):
                    r.inspect_owned(controller,'task',IMAGE,controller.end)

    def test_cleanup_failure_retains_measured_peaks_in_resources_and_cleanup(self):
        _,receipt,_ = self.exercise(cleanup_failure=True,staging_retained=True)
        resource = json.loads((self.output/'evidence/resources.json').read_text())['parent_enclosure']
        self.assertGreater(resource['measured']['peak_rss_bytes'],0)
        self.assertGreater(resource['samples'],0)
        cleanup = receipt['rows']['cleanup.json']['owned_cid_absent']
        self.assertEqual(cleanup['status'],'FAIL')
        self.assertEqual(cleanup['measured'],resource['measured'])
        self.assertEqual(cleanup['samples'],resource['samples'])

    def test_failed_build_exports_only_bounded_compiler_tails_and_versions(self):
        def logs(staging):
            (staging/'configure.log').write_bytes(b'X'*300000+b'CONFIGURE_END')
            (staging/'build.log').write_bytes(b'Y'*300000+b'BUILD_END')
            for name in ('rustc.txt','cargo.txt','cmake-version.txt'):(staging/name).write_text(name+' version')
        _,receipt,_ = self.exercise(failed_phase='build',mutate_failure=logs)
        path = self.output/'evidence/build-diagnostics.json'
        diagnostic = json.loads(path.read_text())
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(len(list(path.parent.iterdir())),10)
        for name,end in [('configure.log','CONFIGURE_END'),('build.log','BUILD_END')]:
            row = diagnostic['files'][name]
            self.assertTrue(row['present']);self.assertEqual(row['tail_bytes'],256*1024)
            self.assertEqual(len(row['text'].encode()),256*1024);self.assertTrue(row['text'].endswith(end))
        for name in ('rustc.txt','cargo.txt','cmake-version.txt'):
            self.assertEqual(diagnostic['files'][name]['text'],name+' version')
        self.assertEqual(receipt['result'],'FAIL')

    def test_diagnostic_reader_reports_absent_files_without_reading_other_paths(self):
        staging = self.base/'staging';staging.mkdir()
        diagnostic = r.build_diagnostics(staging)
        self.assertEqual(len(diagnostic['files']),5)
        self.assertTrue(all(row == {'present':False} for row in diagnostic['files'].values()))

    def test_failed_build_oversized_log_symlink_and_planted_marker_export_nothing(self):
        for kind in ('oversized','symlink','marker','fifo','hardlink'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                staging = Path(tmp)
                path = staging/'build.log'
                if kind == 'oversized':
                    with path.open('wb') as stream:stream.truncate(r.BUILD_LOG_MAX+1)
                elif kind == 'symlink':path.symlink_to(self.base/'missing')
                elif kind == 'marker':(staging/'BUILD_COMPLETE').touch()
                elif kind == 'fifo':os.mkfifo(path)
                else:
                    path.touch();os.link(path,staging/'alias')
                with self.assertRaises((ValueError,OSError)):r.build_diagnostics(staging)

    def test_actual_failed_build_rejects_each_unsafe_diagnostic_before_export(self):
        for kind in ('oversized','symlink','marker','fifo','hardlink','version'):
            with self.subTest(kind=kind):
                case = Direct();case.setUp()
                try:
                    def mutate(staging):
                        path = staging/'build.log'
                        if kind == 'oversized':
                            with path.open('wb') as stream:stream.truncate(r.BUILD_LOG_MAX+1)
                        elif kind == 'symlink':
                            path.unlink();path.symlink_to(staging/'private/secret')
                        elif kind == 'marker':(staging/'BUILD_COMPLETE').touch()
                        elif kind == 'fifo':path.unlink();os.mkfifo(path)
                        elif kind == 'hardlink':os.link(path,staging/'alias')
                        else:(staging/'cargo.txt').write_bytes(b'x'*4097)
                    _,receipt,_ = case.exercise(failed_phase='build',mutate_failure=mutate)
                    self.assertEqual(receipt['build_diagnostics'],'REFUSED')
                    self.assertFalse((case.output/'evidence/build-diagnostics.json').exists())
                finally:case.doCleanups()

    def test_runtime_failure_never_exports_compiler_diagnostics(self):
        self.exercise(failed_phase='runtime',mutate_public=lambda root:(root/'staging/BUILD_COMPLETE').unlink())
        self.assertFalse((self.output/'evidence/build-diagnostics.json').exists())

    def test_exclusive_writes_refuse_existing_entries_and_evidence_directory(self):
        self.output.mkdir();directory = self.output/'staging';directory.mkdir()
        for kind in ('regular','directory','symlink','fifo'):
            path = directory/'BUILD_COMPLETE'
            if kind == 'regular':path.write_text('unchanged')
            elif kind == 'directory':path.mkdir()
            elif kind == 'symlink':path.symlink_to(self.base/'missing')
            else:os.mkfifo(path)
            with self.subTest(kind=kind),self.assertRaises(FileExistsError):r.runtime_marker(directory)
            if kind == 'directory':path.rmdir()
            else:path.unlink()
        r.runtime_marker(directory)
        self.assertEqual((directory/'BUILD_COMPLETE').read_bytes(),b'runtime\n')
        r.publish_evidence(self.output,c.empty_rows(),{'result':'FAIL'})
        original = (self.output/'evidence/receipt.json').read_bytes()
        with self.assertRaises(FileExistsError):r.publish_evidence(self.output,{}, {'result':'changed'})
        self.assertEqual((self.output/'evidence/receipt.json').read_bytes(),original)

    def test_bounded_reader_rejects_special_hardlinked_and_duplicate_key_files(self):
        path = self.base/'evidence.json'
        os.mkfifo(path)
        with self.assertRaises(ValueError):r.bounded_json(path)
        path.unlink();path.write_text('{}');os.link(path,self.base/'alias')
        with self.assertRaises(ValueError):r.bounded_json(path)
        (self.base/'alias').unlink();path.write_text('{"status":"PASS","status":"FAIL"}')
        with self.assertRaises(ValueError):r.bounded_json(path)

    @staticmethod
    def binary_bytes(name):return b'owned executable source fixture '+name.encode()

    @staticmethod
    def build_manifest():
        return dict(builder_image=IMAGE,builder_rustc='rustc fixture',reference={'upstream_files':{
            'tests/functional_tests/wallet.py':c.digest(b'public pinned wallet fixture')}},
            cargo_inputs={'registry':'fixture'},rust_inputs={'tree_sha256':'fixture'})

    def retained_fixture(self):
        root=self.base/'prior';root.mkdir(mode=0o700)
        binary=root/'staging/build/bin';binary.mkdir(parents=True,mode=0o700)
        (root/'staging').chmod(0o700)
        for name in r.BINARIES:
            path=binary/name;path.write_bytes(self.binary_bytes(name));path.chmod(0o700)
        control=r.Controller(root,grant(root),time.monotonic())
        rows=self.producer_rows()['build.json']
        with patch.object(control,'sample'):r.retain_build(control,self.build_manifest(),rows,'a'*40)
        evidence=root/'evidence';evidence.mkdir(mode=0o700)
        (evidence/'build.json').write_text(json.dumps(rows,indent=2)+'\n')
        return root

    def test_retained_build_is_unmounted_and_reuse_checks_exact_hashes(self):
        root=self.retained_fixture();reuse=r.reuse_build(root,self.build_manifest())
        self.assertEqual(reuse['rows'],self.producer_rows()['build.json'])
        self.assertEqual((root/'retained-build').stat().st_mode & 0o777,0o700)
        cmd=r.container_command(self.output,'fixture',IMAGE)
        self.assertFalse(any('retained-build' in part or str(root) in part for part in cmd))
        for name in r.BINARIES:
            self.assertEqual((root/'retained-build'/name).stat().st_mode & 0o777,0o700)

    def test_reuse_tamper_missing_rename_and_unsafe_files_refuse_before_output(self):
        root=self.retained_fixture();directory=root/'retained-build';path=directory/'monerod'
        original=path.read_bytes()
        for case in ('tamper','missing','rename','symlink','hardlink','fifo','nonexecutable'):
            with self.subTest(case=case):
                if case=='tamper':path.write_bytes(b'changed')
                elif case=='missing':path.unlink()
                elif case=='rename':path.rename(directory/'renamed')
                elif case=='symlink':path.unlink();path.symlink_to(root/'staging/build/bin/monerod')
                elif case=='hardlink':os.link(path,directory/'alias')
                elif case=='fifo':path.unlink();os.mkfifo(path)
                elif case=='nonexecutable':path.chmod(0o600)
                with self.assertRaises((ValueError,OSError)):r.reuse_build(root,self.build_manifest())
                self.assertFalse(self.output.exists())
                for other in ('alias','renamed'):(directory/other).unlink(missing_ok=True)
                path.unlink(missing_ok=True);path.write_bytes(original);path.chmod(0o700)

    def test_changed_inputs_and_prior_nonpass_or_changed_evidence_refuse(self):
        root=self.retained_fixture();manifest=self.build_manifest()
        for key in manifest:
            changed=copy.deepcopy(manifest);changed[key]='changed'
            with self.subTest(key=key),self.assertRaises((ValueError,TypeError)):r.reuse_build(root,changed)
        evidence=root/'evidence/build.json';rows=json.loads(evidence.read_text())
        rows['rpc_translation_unit']['status']='NOT_RUN';evidence.write_text(json.dumps(rows))
        with self.assertRaisesRegex(ValueError,'evidence changed'):r.reuse_build(root,manifest)
        self.assertFalse(self.output.exists())

    def test_reuse_grant_binds_root_digest_and_900_seconds(self):
        root=self.retained_fixture();reuse=r.reuse_build(root,self.build_manifest());value=grant(self.output)
        value.update(mode='runtime-only',reuse_build_root=str(root),retained_build_sha256=reuse['manifest_sha256'],
            wall_seconds=900,build_seconds=0)
        kwargs=dict(commit='a'*40,inputs_hash=c.digest(b'{}'),artifact_hash=c.digest(b'packet'),
            runner_hash=c.digest((c.HERE/'run-profile.py').read_bytes()),output=self.output,now=time.time(),reuse=reuse)
        r.grant_payload(comment(value),**kwargs)
        control=r.Controller(self.output,value,10)
        self.assertEqual((control.build_end,control.work_end,control.end),(610,610,910))
        for key,bad in [('reuse_build_root',str(self.base/'wrong')),('retained_build_sha256','0'*64),
                        ('mode','full'),('wall_seconds',4500),('build_seconds',3600)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                r.grant_payload(comment(dict(value,**{key:bad})),**kwargs)
        with self.assertRaises(ValueError):r.grant_payload(comment(value),**dict(kwargs,reuse=None))

    def test_runtime_only_main_keeps_two_admissions_one_start_and_prior_build_rows(self):
        root=self.retained_fixture();result,receipt,events=self.exercise(reuse=root)
        self.assertEqual(result,0);self.assertEqual(events.count('admit'),2);self.assertEqual(events.count('start'),1)
        self.assertEqual(receipt['rows']['build.json'],self.producer_rows()['build.json'])
        self.assertEqual(receipt['build_reuse']['prior_attempt_root'],str(root))
        self.assertEqual(receipt['rows']['resources.json']['deadlines']['wall_seconds'],900)
        self.assertEqual(receipt['rows']['resources.json']['no_oom']['status'],'PASS')
        self.assertEqual(receipt['runtime_diagnostics'],dict(step='COMPLETE',exception_class='NONE',require_label='NONE'))
        self.assertFalse((self.output/'retained-build').exists())

    def test_reuse_input_mismatch_main_never_acquires_lock_or_creates_output(self):
        root=self.retained_fixture();(root/'retained-build/monerod').write_bytes(b'tampered')
        with patch.object(r,'check_inputs',return_value=self.build_manifest()), \
             patch.object(r.subprocess,'check_output',side_effect=['a'*40+'\n','']), \
             patch.object(r,'acquire_lock') as lock,patch.object(r,'api') as api, \
             patch.object(sys,'argv',['run-profile.py','--grant-comment',GRANT,'--artifact-sha256',c.digest(b'packet'),
                 '--out',str(self.output),'--reuse-build',str(root)]),self.assertRaises(ValueError):r.main()
        lock.assert_not_called();api.assert_not_called();self.assertFalse(self.output.exists())

    def test_actual_reuse_staging_copies_only_runtime_inputs_and_marker(self):
        root=self.retained_fixture();reuse=r.reuse_build(root,self.build_manifest());self.output.mkdir(mode=0o700)
        native=self.base/'source-cache';fixture=native/'monero-fcmp/tests/functional_tests/wallet.py'
        fixture.parent.mkdir(parents=True);fixture.write_bytes(b'public pinned wallet fixture')
        inputs=self.base/'runtime-inputs';inputs.write_bytes(b'{}')
        control=r.Controller(self.output,grant(self.output),time.monotonic())
        with patch.object(r.g,'BASE',native),patch.object(control,'sample'):
            r.stage_reuse(control,inputs,self.build_manifest(),reuse)
        self.assertEqual((self.output/'staging/BUILD_COMPLETE').read_bytes(),b'runtime\n')
        self.assertFalse((self.output/'staging/cargo-home').exists())
        self.assertFalse((self.output/'staging/private').exists())
        for name in r.BINARIES:self.assertEqual((self.output/'staging/build/bin'/name).read_bytes(),self.binary_bytes(name))

    def test_diagnostics_reject_all_free_text_and_never_export_private_files(self):
        from integration import runtime_diagnostics as d
        valid=dict(step='HANDSHAKE',exception_class='TimeoutError',require_label='NONE')
        self.assertTrue(d.checked(valid))
        for key in valid:
            self.assertFalse(d.checked(dict(valid,**{key:'PRIVATE_SECRET'})))
        def mutate(root):
            (root/'public/runtime-diagnostics.json').write_text(json.dumps(dict(valid,login='PRIVATE_SECRET')))
            (root/'staging/private/failure-traceback').write_text('PRIVATE_SECRET')
            (root/'staging/private/native.log').write_text('PRIVATE_SECRET')
        _,receipt,_=self.exercise(failed_phase='runtime',mutate_public=mutate)
        self.assertEqual(receipt['runtime_diagnostics_state'],'REFUSED')
        self.assertNotIn('PRIVATE_SECRET',json.dumps(receipt))
        self.assertEqual(receipt['private_staging'],'RETAINED_FOR_AUTHORIZED_LOCAL_INSPECTION')
        self.assertTrue((self.output/'staging/private/failure-traceback').is_file())
        self.assertEqual(set(path.name for path in (self.output/'evidence').iterdir()),set(c.REQUIRED)|{'receipt.json'})
        self.assertEqual((self.output/'staging').stat().st_mode & 0o777,0o700)
        # Same-run local inspection uses only disposable fixture private bytes.
        self.assertEqual((self.output/'staging/private/native.log').read_text(),'PRIVATE_SECRET')
        exact=self.output/'staging';shutil.rmtree(exact)
        self.assertFalse(exact.exists())

    def test_zero_exit_runtime_evidence_failures_retain_private_staging_full_and_reuse(self):
        sentinel='DISPOSABLE_TRACEBACK_NATIVE_WALLET_SENTINEL'
        for mode in ('full','reuse'):
            reuse=self.retained_fixture() if mode == 'reuse' else None
            for scenario in ('diagnostic','witness','fail-row','missing-row','oom-counter','missing-counter'):
                with self.subTest(mode=mode,scenario=scenario):
                    self.output=self.base/('attempt-'+mode+'-'+scenario)
                    def mutate(root):
                        private=root/'staging/private'
                        for name in ('failure-traceback','native.log','wallet.log'):
                            (private/name).write_text(sentinel)
                        if scenario == 'diagnostic':
                            path=root/'public/runtime-diagnostics.json'
                            value=json.loads(path.read_text());value['unexpected']=sentinel
                            path.write_text(json.dumps(value))
                        elif scenario in ('witness','fail-row','missing-row'):
                            path=root/'public/peer.json';value=json.loads(path.read_text())
                            if scenario == 'witness':del value['native_handshake']['request_sha256']
                            elif scenario == 'fail-row':value['native_handshake']['status']='FAIL'
                            else:del value['native_handshake']
                            path.write_text(json.dumps(value))
                        else:
                            path=root/'staging/resources-runtime.json'
                            if scenario == 'missing-counter':path.unlink()
                            else:path.write_text(json.dumps(dict(oom=1,oom_kill=1)))
                    result,receipt,events=self.exercise(mutate_public=mutate,reuse=reuse,staging_retained=True)
                    self.assertEqual(result,1);self.assertEqual(receipt['result'],'FAIL')
                    self.assertEqual(receipt['phase_diagnostics']['runtime']['container_exit_code'],0)
                    self.assertNotIn('failure_phase',receipt)
                    self.assertEqual(events.count('start'),1 if reuse else 2)
                    self.assertEqual(receipt['rows']['cleanup.json']['owned_cid_absent']['status'],'PASS')
                    self.assertEqual(receipt['rows']['cleanup.json']['owned_staging_removed']['status'],'NOT_RUN')
                    self.assertTrue(receipt['rows']['cleanup.json']['owned_staging_removed']['retained_for_private_inspection'])
                    self.assertEqual(receipt['private_staging'],'RETAINED_FOR_AUTHORIZED_LOCAL_INSPECTION')
                    self.assertEqual((self.output/'staging').stat().st_mode & 0o777,0o700)
                    self.assertEqual((self.output/'staging').stat().st_uid,os.getuid())
                    self.assertEqual(set(p.name for p in (self.output/'evidence').iterdir()),set(c.REQUIRED)|{'receipt.json'})
                    for path in (self.output/'evidence').iterdir():self.assertNotIn(sentinel,path.read_text())
                    # Inspect and remove only disposable private fixture data.
                    self.assertEqual((self.output/'staging/private/native.log').read_text(),sentinel)
                    shutil.rmtree(self.output/'staging')
                    self.assertFalse((self.output/'staging').exists())

    def test_nonzero_runtime_reuse_retains_private_staging(self):
        result,receipt,events=self.exercise(reuse=self.retained_fixture(),failed_phase='runtime')
        self.assertEqual(result,1);self.assertEqual(receipt['failure_phase'],'runtime')
        self.assertEqual(events.count('start'),1)
        self.assertEqual(receipt['private_staging'],'RETAINED_FOR_AUTHORIZED_LOCAL_INSPECTION')
        self.assertEqual(receipt['rows']['cleanup.json']['owned_staging_removed']['status'],'NOT_RUN')

    def driver_fixture(self):
        spec=importlib.util.spec_from_file_location('diagnostic_driver',c.HERE/'profile-integration.py')
        driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        driver.PRIVATE=self.base/'private';driver.PUBLIC=self.base/'public';driver.PUBLIC.mkdir()
        driver.BIN=self.base/'bin';driver.BIN.mkdir()
        for name in r.BINARIES:(driver.BIN/name).write_bytes(self.binary_bytes(name))
        class Wire:
            closed=False;error=None;frames=[('request',1001,b'fixture'),('response',1001,b'fixture')]
            def start(self):pass
            def close(self):self.closed=True
        driver.Wire=Wire
        return driver

    def traced_main(self,driver):
        from integration import runtime_diagnostics as d
        previous=sys.gettrace()
        try:
            d.install(c.HERE/'profile-integration.py',c.require)
            result=driver.main()
        finally:sys.settrace(previous)
        value=json.loads((driver.PUBLIC/'runtime-diagnostics.json').read_text())
        self.assertTrue(d.checked(value));self.assertNotIn('PRIVATE_SECRET',json.dumps(value))
        return result,value

    def test_frozen_driver_exception_traceback_is_private_and_codes_are_fixed(self):
        driver=self.driver_fixture()
        def fail(*args):c.require(False,'genesis peer disagreement')
        with patch.object(driver,'node',side_effect=fail):result,value=self.traced_main(driver)
        self.assertEqual(result,1)
        self.assertEqual(value,dict(step='NODE1_START',exception_class='ValueError',require_label='GENESIS_PEER_DISAGREEMENT'))
        self.assertIn('ValueError: genesis peer disagreement',(driver.PRIVATE/'failure-traceback').read_text())
        self.assertFalse((driver.PUBLIC/'failure-traceback').exists())
        self.assertEqual((driver.PRIVATE/'failure-traceback').stat().st_mode & 0o777,0o600)
        # Prior RPC exceptions plus lead-authorized wallet setup/prompt/read correction.
        baseline=subprocess.check_output(['git','show','530205f7:./vanguard/network/profile-integration.py']).decode()
        current=(c.HERE/'profile-integration.py').read_text()
        def without_skeleton(raw):
            helper=next((item for item in ast.parse(raw).body if isinstance(item,ast.FunctionDef)
                         and item.name=='_cli_skeleton'),None)
            if helper:
                lines=raw.splitlines(keepends=True);del lines[helper.lineno-1:helper.end_lineno+2]
                return ''.join(lines)
            return raw
        def frozen(raw):
            raw=without_skeleton(raw)
            tree=ast.parse(raw);lines=raw.splitlines(keepends=True)
            allowed=[item for item in tree.body if isinstance(item,ast.FunctionDef) and item.name in {'wait','snapshot','cli','wallet_rpc','wallet_controls'}]
            rpc=next(item for item in tree.body if isinstance(item,ast.ClassDef) and item.name=='RPC')
            allowed.append(next(item for item in rpc.body if isinstance(item,ast.FunctionDef) and item.name=='call'))
            for item in sorted(allowed,key=lambda x:x.lineno,reverse=True):lines[item.lineno-1:item.end_lineno]=['<AUTHORIZED FUNCTION>\n']
            return ''.join(lines)
        self.assertEqual(frozen(current),frozen(baseline))
        baseline=subprocess.check_output(['git','show','ed78cd5:./vanguard/network/profile-integration.py']).decode()
        def outside_call_and_wallet(raw):
            raw=without_skeleton(raw)
            tree=ast.parse(raw);lines=raw.splitlines(keepends=True)
            rpc=next(item for item in tree.body if isinstance(item,ast.ClassDef) and item.name=='RPC')
            item=next(item for item in rpc.body if isinstance(item,ast.FunctionDef) and item.name=='call')
            allowed=[item]+[item for item in tree.body if isinstance(item,ast.FunctionDef) and item.name in {'cli','wallet_rpc','wallet_controls'}]
            for item in sorted(allowed,key=lambda x:x.lineno,reverse=True):lines[item.lineno-1:item.end_lineno]=['<AUTHORIZED RPC.call OR WALLET>\n']
            return ''.join(lines)
        self.assertEqual(outside_call_and_wallet(current),outside_call_and_wallet(baseline))
        baseline=subprocess.check_output(['git','show','818a4fc6:./vanguard/network/profile-integration.py']).decode()
        def exact_scope(raw):
            tree=ast.parse(raw)
            tree.body=[item for item in tree.body if not isinstance(item,ast.FunctionDef) or
                       item.name not in ('cli','_cli_skeleton')]
            return ast.dump(tree)
        self.assertEqual(exact_scope(current),exact_scope(baseline))

    def test_actual_node_start_and_readiness_failure_codes(self):
        for target in (0,1,'readiness'):
            with self.subTest(target=target):
                if (self.base/'public').exists():shutil.rmtree(self.base/'public')
                if (self.base/'private').exists():shutil.rmtree(self.base/'private')
                if (self.base/'bin').exists():shutil.rmtree(self.base/'bin')
                driver=self.driver_fixture()
                def launch(name,*args):
                    if name=='node'+str(target):raise OSError('PRIVATE_SECRET login seed frame')
                def wait(*args):
                    if target=='readiness':raise TimeoutError('PRIVATE_SECRET native response')
                    return True
                with patch.object(driver,'creation',return_value={}),patch.object(driver,'launch',side_effect=launch),patch.object(driver,'wait',side_effect=wait):
                    result,value=self.traced_main(driver)
                self.assertEqual(result,1)
                self.assertEqual(value['step'],'READINESS_RPC' if target=='readiness' else 'NODE'+str(target)+'_START')
                self.assertIn('PRIVATE_SECRET',(driver.PRIVATE/'failure-traceback').read_text())
                self.assertNotIn('PRIVATE_SECRET',(driver.PUBLIC/'runtime-diagnostics.json').read_text())

    def test_handshake_and_snapshot_codes_and_complete_driver_path(self):
        for scenario in ('handshake','snapshot','complete'):
            for name in ('public','private','bin'):
                path=self.base/name
                if path.exists():shutil.rmtree(path)
            driver=self.driver_fixture();state=dict(height=1,top_block_hash=c.GENESIS,pool_hashes=[],work='0x1')
            class RPC:
                def auth_controls(self):pass
                def call(self,method,*args):
                    return {'hard_forks':[{'hf_version':18,'height':1}]} if method=='get_version' else {'earliest_height':1}
            def node(index,binaries,root=None,reopen=False):
                driver.PROCS['node'+str(index)]=(type('P',(),{'poll':lambda self:0})(),object())
                return RPC(),root or driver.PRIVATE/('node'+str(index))
            def wait(*args):
                if scenario=='handshake':raise TimeoutError('PRIVATE_SECRET')
                return True
            snapshots=iter([state,dict(state,height=2)])
            with patch.object(driver,'node',side_effect=node),patch.object(driver,'wait',side_effect=wait), \
                 patch.object(driver,'snapshot',side_effect=(lambda rpc:next(snapshots)) if scenario=='snapshot' else lambda rpc:state), \
                 patch.object(driver,'save_node'),patch.object(driver,'isolation'),patch.object(driver,'census'), \
                 patch.object(driver,'copy_stopped'),patch.object(driver,'launcher_adverse'), \
                 patch.object(driver,'wallet_controls'),patch.object(driver.time,'sleep'):
                result,value=self.traced_main(driver)
            expected={'handshake':('HANDSHAKE','TimeoutError'),
                'snapshot':('SNAPSHOT_AGREEMENT','ValueError'),'complete':('COMPLETE','NONE')}[scenario]
            self.assertEqual((value['step'],value['exception_class']),expected)
            self.assertEqual(result,0 if scenario=='complete' else 1)

    def test_unknown_exception_and_require_message_map_to_fixed_tokens(self):
        from integration import runtime_diagnostics as d
        for error in (type('PRIVATE_SECRET',(Exception,),{})('PRIVATE_SECRET'),ValueError('PRIVATE_SECRET')):
            result=d.exception_codes(error,c.require)
            self.assertNotIn('PRIVATE_SECRET',json.dumps(result))
        try:c.require(False,'PRIVATE_SECRET')
        except ValueError as error:
            self.assertEqual(d.exception_codes(error,c.require),dict(exception_class='ValueError',require_label='OTHER_REQUIRE'))
        # Every literal driver guard is in the fixed table; no runtime extraction is used.
        tree=ast.parse((c.HERE/'profile-integration.py').read_text())
        for call in ast.walk(tree):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='require' and \
               len(call.args)>1 and isinstance(call.args[1],ast.Constant):self.assertIn(call.args[1].value,d.REQUIRE_CODES)
        node=next(item for item in tree.body if isinstance(item,ast.FunctionDef) and item.name=='main')
        self.assertEqual(node.lineno,743)
        self.assertIn('PRIVATE.mkdir',(c.HERE/'profile-integration.py').read_text().splitlines()[744])

    def test_actual_contract_import_installs_observer_only_for_driver_entry(self):
        script="import sys;sys.path.insert(0,sys.argv[1]);sys.argv=[sys.argv[2]];import profile_contract;assert sys.gettrace() is not None"
        subprocess.run([sys.executable,'-B','-c',script,str(c.HERE),str(c.HERE/'profile-integration.py')],
            check=True,timeout=10,env={'PATH':os.environ['PATH'],'LC_ALL':'C'})
        self.assertNotEqual(getattr(sys.gettrace(),'__module__',None),'integration.runtime_diagnostics')

    def test_source_input_file_hashes_and_nonpass_build_are_rejected(self):
        accepted=json.loads(subprocess.check_output(['git','show',
            '818a4fc646d74b177f2981045b1c1eb125998a9b:vanguard/network/integration/inputs.json']))
        current=c.json_file(c.HERE/'integration/inputs.json')
        self.assertEqual(r.build_identity(accepted),r.build_identity(current),
                         'Runtime diagnostics must preserve published retained-build compatibility')
        root=self.retained_fixture();manifest=self.build_manifest();original=r.build_identity(manifest)
        for key in ('source_lock_sha256','build_sh_sha256','freezer_sha256'):
            altered=dict(original,**{key:'0'*64})
            with self.subTest(key=key),patch.object(r,'build_identity',return_value=altered),self.assertRaises(ValueError):
                r.reuse_build(root,manifest)
        rows=self.producer_rows()['build.json'];rows['rpc_translation_unit']['status']='FAIL'
        raw=(json.dumps(rows,indent=2)+'\n').encode();(root/'evidence/build.json').write_bytes(raw)
        record_path=root/'retained-build/manifest.json';record=json.loads(record_path.read_text())
        record['build_evidence_sha256']=c.digest(raw);record_path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'prior PASS'):r.reuse_build(root,manifest)
        self.assertFalse(self.output.exists())

    def test_retain_build_refuses_symlinked_build_directory(self):
        root=self.base/'linked';root.mkdir(mode=0o700);(root/'staging').mkdir(mode=0o700)
        source=self.base/'elsewhere';(source/'bin').mkdir(parents=True)
        (root/'staging/build').symlink_to(source,target_is_directory=True)
        control=r.Controller(root,grant(root),time.monotonic())
        with self.assertRaises(OSError):r.retain_build(control,self.build_manifest(),self.producer_rows()['build.json'],'a'*40)
        self.assertEqual(list((root/'retained-build').iterdir()),[])

    def test_runtime_setup_code_and_deletion_record_for_local_fixture_inspection(self):
        driver=self.driver_fixture();shutil.rmtree(driver.BIN)
        from integration import runtime_diagnostics as d
        previous=sys.gettrace()
        try:
            d.install(c.HERE/'profile-integration.py',c.require)
            with self.assertRaises(FileNotFoundError):driver.main()
        finally:sys.settrace(previous)
        value=json.loads((driver.PUBLIC/'runtime-diagnostics.json').read_text())
        self.assertEqual(value,dict(step='SETUP',exception_class='FileNotFoundError',require_label='NONE'))
        # Exception predates the frozen try; no unauthorized extra traceback line.
        self.assertFalse((driver.PRIVATE/'failure-traceback').exists())
        exact=driver.PRIVATE;shutil.rmtree(exact)
        record=self.base/'private-inspection-cleanup.json'
        record.write_text(json.dumps(dict(path=str(exact),deleted=not exact.exists(),scope='disposable-source-fixture')))
        self.assertTrue(json.loads(record.read_text())['deleted'])
        self.assertNotIn(record.name,[path.name for path in driver.PUBLIC.iterdir()])

    def test_rejected_retention_and_missing_evidence_close_all_descriptors(self):
        before=len(list(Path('/proc/self/fd').iterdir()))
        for index in range(5):
            root=self.base/('bad-retain-'+str(index));root.mkdir(mode=0o700)
            (root/'staging').mkdir(mode=0o700)
            control=r.Controller(root,grant(root),time.monotonic())
            with self.assertRaises(OSError):r.retain_build(control,self.build_manifest(),self.producer_rows()['build.json'],'a'*40)
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
        root=self.retained_fixture();shutil.rmtree(root/'evidence')
        for _ in range(5):
            with self.assertRaises(OSError):r.reuse_build(root,self.build_manifest())
        self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)

    def producer_rows(self):
        # Evaluate only the producer's row(...) expressions, with public fixture
        # inputs. No RPC, sockets, wallets, frames or native children are run.
        spec = importlib.util.spec_from_file_location('witness_driver',c.HERE/'profile-integration.py')
        driver = importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        state = dict(height=1,top_block_hash=c.GENESIS,work='0x1',pool_hashes=[])
        scope = dict(row=driver.row,c=c,packet=b'public-fixture',wrong=b'wrong-uuid',fixture='b'*64,
            before=state,state=state,a=None,snapshot=lambda unused:state)
        tree = ast.parse((c.HERE/'profile-integration.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id == 'row':
                keys = c.REQUIRED['wallet.json'] if isinstance(node.args[1],ast.Name) else [None]
                for key in keys:
                    eval(compile(ast.Expression(node),'<frozen public row>','eval'),dict(scope,key=key))
        driver.ROWS['build.json'] = dict(three_production_binaries=dict(status='PASS',binaries={name:dict(sha256=c.digest(self.binary_bytes(name)),
            needed=['libc.so.6','libstdc++.so.6','libwallet-crypto.so']) for name in
            ('monerod','monero-wallet-cli','monero-wallet-rpc')}),
            rpc_translation_unit=dict(status='PASS',object_sha256='b'*64))
        return {filename:values for filename,values in driver.ROWS.items()
            if filename not in ('resources.json','cleanup.json')}

    def test_allowlist_accepts_actual_frozen_driver_row_expressions(self):
        public = self.base/'public';public.mkdir()
        rows = c.empty_rows()
        for filename,values in self.producer_rows().items():
            self.assertTrue(all(row['status'] == 'PASS' for row in values.values()))
            (public/filename).write_text(json.dumps(values))
        self.assertEqual(r.collect_public(self.base,rows),[])
        for filename,values in self.producer_rows().items():self.assertEqual(rows[filename],values)

    def test_pass_rows_require_every_producer_field_recursively(self):
        def paths(value,prefix=()):
            for key,item in value.items():
                if key == 'status':continue
                yield prefix+(key,)
                if isinstance(item,dict):yield from paths(item,prefix+(key,))
        for filename,values in self.producer_rows().items():
            path = self.base/filename
            for key,row in values.items():
                path.write_text(json.dumps({key:dict(status='PASS')}))
                with self.subTest(filename=filename,row=key,missing='all'),self.assertRaises(ValueError):
                    r.read_public_rows(path,r.public_shapes())
                for field in paths(row):
                    with self.subTest(filename=filename,row=key,missing=field):
                        incomplete = copy.deepcopy(row);parent = incomplete
                        for part in field[:-1]:parent = parent[part]
                        del parent[field[-1]]
                        path.write_text(json.dumps({key:incomplete}))
                        with self.assertRaises(ValueError):r.read_public_rows(path,r.public_shapes())

    def test_partial_failure_and_unreached_rows_allow_only_valid_known_fields(self):
        path = self.base/'build.json'
        for status in ('FAIL','NOT_RUN'):
            for witness in ({},dict(binaries={'monerod':dict(sha256='a'*64)})):
                value = dict(three_production_binaries=dict(status=status,**witness))
                path.write_text(json.dumps(value))
                self.assertEqual(r.read_public_rows(path,r.public_shapes()),value)
            for witness in (dict(binaries={'monerod':dict(unknown=True)}),
                            dict(binaries={'monerod':dict(sha256='invalid')})):
                path.write_text(json.dumps(dict(three_production_binaries=dict(status=status,**witness))))
                with self.assertRaises(ValueError):r.read_public_rows(path,r.public_shapes())

    def test_missing_wallet_rpc_binary_hash_prevents_runtime_start(self):
        def mutate(path):
            value = json.loads(path.read_text())
            del value['three_production_binaries']['binaries']['monero-wallet-rpc']['sha256']
            path.write_text(json.dumps(value))
        result,receipt,events = self.exercise(mutate_build=mutate)
        self.assertEqual(result,1);self.assertEqual(events.count('start'),1)
        self.assertEqual(receipt['failure_phase'],'build');self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['rejected_evidence'],['build.json'])

    def test_missing_native_witness_cannot_produce_slice_pass(self):
        def mutate(root):
            path = root/'public/peer.json';value = json.loads(path.read_text())
            del value['native_handshake']['request_sha256']
            path.write_text(json.dumps(value))
        result,receipt,events = self.exercise(mutate_public=mutate,staging_retained=True)
        self.assertEqual(result,1);self.assertEqual(events.count('start'),2)
        self.assertEqual(receipt['result'],'FAIL');self.assertEqual(receipt['rejected_evidence'],['peer.json'])
        self.assertEqual(receipt['rows']['peer.json'],c.empty_rows()['peer.json'])
        self.assertEqual(receipt['rows']['wallet.json']['address_roundtrip']['status'],'PASS')
        self.assertEqual(receipt['rows']['cleanup.json']['owned_staging_removed']['status'],'NOT_RUN')

    def test_historical_real_elf_freezer_reader_and_actual_main_build_gate(self):
        # Historical selected-policy ELFs, never executed; not current-lineage acceptance.
        evidence = c.HERE/'integration/evidence/elf-witness-correction'
        inventory = json.loads((evidence/'historical-inputs.json').read_text())
        layout = self.base/'historical';out = layout/'out';public = layout/'public'
        build = out/'build';(build/'bin').mkdir(parents=True);public.mkdir()
        for name,expected in inventory['binaries'].items():
            source = Path(inventory['source_directory'])/name
            self.assertEqual(c.digest(source.read_bytes()),expected)
            shutil.copy2(source,build/'bin'/name)
        log = (evidence/'retained-build.log').read_bytes()
        self.assertEqual(c.digest(log),inventory['compile_log_sha256'])
        (out/'build.log').write_bytes(log)
        obj = build/'src/rpc/CMakeFiles/obj_rpc.dir/core_rpc_server.cpp.o'
        obj.parent.mkdir(parents=True);obj.write_bytes(b'explicit real-layout object stand-in')
        inputs = json.loads((c.HERE/'integration/inputs.json').read_text())
        (out/'inputs.json').write_text(json.dumps(inputs))
        (out/'rustc.txt').write_text(inputs['builder_rustc']+'\n')
        spec = importlib.util.spec_from_file_location('unchanged_freezer',c.HERE/'freeze-profile.py')
        freezer = importlib.util.module_from_spec(spec);spec.loader.exec_module(freezer)
        def mapped(name):
            path = Path(name)
            return layout/str(path).lstrip('/') if path.is_absolute() else path
        readelf = subprocess.check_output
        commands = []
        def inspect(argv,**kwargs):
            self.assertEqual(argv[:2],['readelf','-d']);commands.append(argv)
            return readelf(argv,**kwargs)
        with patch.object(freezer,'Path',side_effect=mapped), \
             patch.object(freezer.c,'json_file',side_effect=lambda name:json.loads(mapped(name).read_text())), \
             patch.object(freezer.subprocess,'check_output',side_effect=inspect):
            freezer.built(build)
        self.assertEqual(len(commands),3)
        emitted = (public/'build.json').read_bytes()
        value = r.read_public_rows(public/'build.json',r.public_shapes())
        for name,expected in inventory['binaries'].items():
            row = value['three_production_binaries']['binaries'][name]
            self.assertEqual(row['sha256'],expected)
            self.assertIn('ld-linux-x86-64.so.2',row['needed'])
        result,receipt,events = self.exercise(mutate_build=lambda path:path.write_bytes(emitted),stage_binary_sources=build/'bin')
        self.assertEqual(result,0);self.assertEqual(events.count('start'),2)
        self.assertEqual(receipt['rows']['build.json'],value)
        self.assertNotIn('build_rejection_key_path',receipt)

    def test_needed_exact_loader_and_existing_grammar_and_32_entry_bound(self):
        path = self.base/'build.json'
        for dependencies in (['ld-linux-x86-64.so.2'],['libc.so.6']*31+['ld-linux-x86-64.so.2']):
            value = self.producer_rows()['build.json']
            value['three_production_binaries']['binaries']['monerod']['needed'] = dependencies
            path.write_text(json.dumps(value));self.assertEqual(r.read_public_rows(path,r.public_shapes()),value)
        for bad in ('ld-linux.so.2','ld-linux-x86-64.so.3','ld-linux-x86-64.so.2.extra',
                    '/lib64/ld-linux-x86-64.so.2','../ld-linux-x86-64.so.2',
                    'ld-linux-x86-64.so.2\n','ld-linux-x86-64.so.2\x00',
                    'libc.so.6\n','libc.so.6/extra','libc.so.bad',32,None,True):
            value = self.producer_rows()['build.json']
            value['three_production_binaries']['binaries']['monerod']['needed'] = [bad]
            path.write_text(json.dumps(value))
            with self.subTest(bad=repr(bad)),self.assertRaises(r.PublicWitnessError) as error:
                r.read_public_rows(path,r.public_shapes())
            self.assertEqual(error.exception.key_path,'build.json.three_production_binaries.binaries.monerod.needed')
        for bad in (['libc.so.6']*32+['ld-linux-x86-64.so.2'],'ld-linux-x86-64.so.2',None,{}):
            value['three_production_binaries']['binaries']['monerod']['needed'] = bad
            path.write_text(json.dumps(value))
            with self.assertRaises(r.PublicWitnessError):r.read_public_rows(path,r.public_shapes())

    def assert_rejected_build_retained(self, **options):
        raw = b'{"three_production_binaries":{"status":"PASS","binaries":{}}}'
        acquire = r.acquire_lock
        def disposable_lock():
            self.assertEqual(r.g.LOCK,self.lock)
            info = self.lock.stat()
            self.assertEqual(r.g.LOCK_ID,(info.st_dev,info.st_ino))
            return acquire()
        with patch.object(r,'acquire_lock',disposable_lock):
            result,receipt,events = self.exercise(mutate_build=lambda path:path.write_bytes(raw),**options)
        self.assertEqual(result,1);self.assertEqual(events.count('start'),1)
        self.assertEqual(receipt['result'],'FAIL');self.assertEqual(receipt['failure_phase'],'build')
        self.assertNotIn('runtime',receipt['phase_diagnostics'])
        self.assertTrue(all(row['status'] == 'PASS' for row in receipt['rows']['cleanup.json'].values()))
        self.assertFalse((self.output/'public/build.json').exists())
        rejected = json.loads((self.output/'evidence/build-diagnostics.json').read_text())['rejected_build']
        self.assertEqual(rejected['payload'],'RETAINED')
        self.assertEqual(rejected['key_path'],'build.json.three_production_binaries.binaries.monerod')
        self.assertEqual(rejected['size_bytes'],len(raw));self.assertEqual(rejected['sha256'],c.digest(raw))
        self.assertEqual(base64.b64decode(rejected['bytes_base64'],validate=True),raw)
        self.assertEqual(receipt['build_rejection_key_path'],rejected['key_path'])
        self.assertEqual(receipt['rejected_key_paths']['build.json'],rejected['key_path'])

    def test_rejected_build_retains_exact_bounded_bytes_and_trusted_key_path(self):
        self.assert_rejected_build_retained()

    def test_nonzero_build_cli_and_container_retain_rejected_build(self):
        self.assert_rejected_build_retained(failed_phase='build')

    def test_zero_build_cli_nonzero_container_retains_rejected_build(self):
        self.assert_rejected_build_retained(failed_phase='build',container_exit_only=True)

    def test_raised_build_command_retains_rejected_build(self):
        self.assert_rejected_build_retained(raised_phase='build')

    def test_rejected_build_retention_refuses_aliases_special_files_and_oversize(self):
        for kind in ('symlink','hardlink','fifo','oversize','directory-alias'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp);staging = root/'staging';staging.mkdir()
                public = root/'public';public.mkdir();path = public/'build.json'
                if kind == 'symlink':path.symlink_to(staging/'secret')
                elif kind == 'fifo':os.mkfifo(path)
                else:
                    path.write_bytes(b'x'*(65537 if kind == 'oversize' else 1))
                    if kind == 'hardlink':os.link(path,root/'alias')
                    if kind == 'directory-alias':
                        public.rename(root/'real-public');public.symlink_to(root/'real-public',target_is_directory=True)
                value = r.build_diagnostics(staging,public=public,rejected_key_path='build.json')
                self.assertEqual(value['rejected_build'],dict(key_path='build.json',payload='REFUSED'))

    def test_malformed_build_64k_retention_and_runtime_rejection_exports_no_values(self):
        staging = self.base/'staging';staging.mkdir();public = self.base/'public';public.mkdir()
        raw = b'\xff' + b'x'*65535;(public/'build.json').write_bytes(raw)
        value = r.build_diagnostics(staging,public=public,rejected_key_path='build.json')
        self.assertEqual(base64.b64decode(value['rejected_build']['bytes_base64']),raw)
        sentinel = 'PRIVATE_RUNTIME_VALUE_AND_KEY'
        def mutate(root):
            path = root/'public/peer.json';value = json.loads(path.read_text())
            value['genesis_state']['work'] = sentinel
            value['native_handshake'][sentinel] = sentinel
            path.write_text(json.dumps(value))
        _,receipt,_ = self.exercise(mutate_public=mutate,staging_retained=True)
        self.assertEqual(receipt['rejected_key_paths']['peer.json'],'peer.json.native_handshake.<unknown>')
        for path in (self.output/'evidence').iterdir():self.assertNotIn(sentinel,path.read_text())
        self.assertFalse((self.output/'evidence/build-diagnostics.json').exists())


UP = Path('<repo>/build/vanguard-src/monero-fcmp')
FIXTURE = c.HERE/'integration/wallet-cli-fixture.py'


def driver(revision=None):
    text = subprocess.check_output(['git', 'show', revision+':./vanguard/network/profile-integration.py']).decode() if revision else (c.HERE/'profile-integration.py').read_text()
    value = types.ModuleType('wallet_fixture_driver'); value.__file__ = str(c.HERE/'profile-integration.py')
    exec(compile(text, value.__file__, 'exec'), value.__dict__)
    value.DEADLINE = time.monotonic()+20
    return value


class WalletCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='TJS-2504-wallet-source-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.root.chmod(0o700)
        self.d = driver(); self.d.PRIVATE = self.root; self.d.BIN = self.root/'bin'; self.d.BIN.mkdir()
        executable = self.d.BIN/'monero-wallet-cli'
        executable.write_text('#!'+sys.executable+'\n'+FIXTURE.read_text()); executable.chmod(0o700)
        for name in ('monerod', 'monero-wallet-rpc'): (self.d.BIN/name).write_text('source fixture only')
        self.patches = [patch.object(self.d, 'released'), patch.object(self.d, 'seal'), patch.object(c, 'root_manifest')]
        for item in self.patches: item.start(); self.addCleanup(item.stop)
        self.d.SAVED = {str(self.root/'wallet0'): {}}

    def config(self, revision=None):
        value = driver(revision); value.PRIVATE = self.root
        class Captured(Exception): pass
        with patch.object(value, 'cli', side_effect=Captured):
            with self.assertRaises(Captured):
                value.wallet_controls(0, types.SimpleNamespace(login='fixture:synthetic', port=48081), {})
        return self.root/'wallet0'

    def invoke(self, root, create=True, mode='normal'):
        with patch.dict(self.d.ENV, WALLET_CLI_FIXTURE_MODE=mode):
            return self.d.cli(root, 48081, create)

    def test_baseline_unknown_config_refuses_before_log_setup(self):
        root = self.config('b17746e67e2512f1348ea05fb90f6955950d08b6')
        with self.assertRaises(OSError) as caught: self.invoke(root)
        self.assertFalse((root/'cli.log').exists())
        self.assertIn('exit_status=1; expected_prompt=STARTUP_WALLET_PROMPT', '\n'.join(caught.exception.__notes__))
        self.assertEqual(self.d.PROCS['cli'][0].returncode, 1)

    def test_actual_create_and_reopen_prompt_sequences(self):
        root = self.config(); self.invoke(root); self.invoke(root, False)
        self.assertEqual(self.d.PROCS['cli'][0].returncode, 0)
        self.assertEqual((root/'cli.log').read_text(), 'FIXTURE_OPTIONS_ACCEPTED\n')

    def test_out_of_sync_prompt_is_accepted(self):
        self.invoke(self.config(), mode='out-of-sync')

    def test_background_mining_startup_is_declined_and_wallet_reopens(self):
        root=self.config();self.invoke(root,mode='background-mining');self.invoke(root,False)
        self.assertEqual((root/'background-refused.fixture').read_text(),'n\n')
        self.assertEqual(self.d.PROCS['cli'][0].returncode,0)

    def test_readline_two_phase_csi_osc_markers_and_backspace_create_reopen(self):
        root=self.config()
        self.invoke(root,mode='readline-normal');self.invoke(root,False,mode='readline-normal')
        self.assertEqual(self.d.PROCS['cli'][0].returncode,0)
        self.assertFalse((root/'cli-skeleton.private').exists())

    def test_readline_background_question_is_declined_once(self):
        root=self.config();self.invoke(root,mode='readline-background-mining')
        self.invoke(root,False,mode='readline-normal')
        self.assertEqual((root/'background-refused.fixture').read_text(),'n\n')

    def test_exact_818a4fc_readline_controls_fail_before_commands(self):
        root=self.config();before=driver('818a4fc646d74b177f2981045b1c1eb125998a9b')
        before.PRIVATE=self.d.PRIVATE;before.BIN=self.d.BIN
        with patch.object(before,'released'),patch.object(before,'seal'),patch.object(before,'budget',return_value=.5):
            for mode in ('readline-normal','readline-background-mining'):
                with self.subTest(mode=mode),patch.dict(before.ENV,WALLET_CLI_FIXTURE_MODE=mode):
                    with self.assertRaises((TimeoutError,ValueError)):before.cli(root,48081,True)
                    self.assertIsNotNone(before.PROCS['cli'][0].returncode)
                    self.assertFalse((root/'background-refused.fixture').exists())

    def test_readline_adverse_prompts_still_refuse_and_reap(self):
        root=self.config()
        with patch.object(self.d,'budget',return_value=.5):
            for mode in ('background-altered','background-during-command','confirmation',
                         'unknown-password','repeated-password','altered-wallet','background-repeated'):
                with self.subTest(mode=mode),self.assertRaises((ValueError,TimeoutError)):
                    self.invoke(root,mode='readline-'+mode)
                self.assertIsNotNone(self.d.PROCS['cli'][0].returncode)
                skeleton=root/'cli-skeleton.private'
                self.assertEqual(skeleton.stat().st_mode & 0o777,0o600)
                answered=root/'background-refused.fixture'
                self.assertEqual(answered.read_text() if answered.exists() else '',
                                 'n\n' if mode=='background-repeated' else '')

    def test_skeleton_connected_failure_redacts_fixture_password_and_secrets(self):
        root=self.config()
        with self.assertRaisesRegex(ValueError,'unknown CLI prompt; input refused'):
            self.invoke(root,mode='readline-skeleton-failure')
        skeleton=(root/'cli-skeleton.private').read_bytes()
        for secret in [b'abbey',b'abducts',b'ability',b'Q'*95,b'0123456789abcdef'*4,
                       b'aces',b'acidic',b'abbex',(root/'password').read_bytes().strip()]:
            self.assertNotIn(secret,skeleton)
        self.assertIn(b'<0x1B>[?2004',skeleton)
        for structure in (b'[<w> 123ABZ<0x08>C]:',b'<0x0D>',b'<0x08>',b'<0x00>'):
            self.assertIn(structure,skeleton)
        self.assertIn(b'<w>',skeleton);self.assertIn(b'<b58>',skeleton);self.assertIn(b'<hex>',skeleton)

    def test_skeleton_original_control_boundary_f1_known_bad(self):
        root=self.config();before=driver('19c0401ae2ff79c36f26b4917173ffc12156deb0')
        for raw,leak in ((b'abbey\rready',b'abbey'),(b'abbey\bx',b'abbey'),
                         (b'aces\x00acidic',b'aces')):
            with self.subTest(raw=raw):
                self.assertIn(leak,before._cli_skeleton(root,raw,''))
                value=self.d._cli_skeleton(root,raw,'')
                self.assertNotIn(leak,value);self.assertIn(b'<w>',value)

    def test_skeleton_mnemonic_prefixes_overwrites_and_split_controls(self):
        root=self.config()
        for raw in (b'abb',b'ABBridged',b'abbey\bx',b'abb\x7fey',
                    b'ab\x1b[31mbey',b'ab\x1b]0;title\x07bey',
                    b'ab\x80bey',b'ab\x9b31mbey',b'ab\x9d0;title\x9cbey'):
            with self.subTest(raw=raw):
                value=self.d._cli_skeleton(root,raw,'')
                self.assertIn(b'<w>',value)
                self.assertNotIn(b'abb',value.lower())
        for control in list(range(32))+list(range(127,160)):
            with self.subTest(control=control):
                value=self.d._cli_skeleton(root,b'abbey'+bytes([control])+b'xyz','')
                self.assertNotIn(b'abb',value)
                self.assertIn(f'<0x{control:02X}>'.encode(),value)

    def test_skeleton_interleaved_full_seed_has_no_mnemonic_prefix(self):
        import re
        root=self.config()
        header=(UP/'src/mnemonics/english.h').read_bytes()
        self.assertIn(b'Base("English", "English", {}, 3)',header)
        words=re.findall(rb'^\s*"([a-z]+)",?\s*$',header,re.M)
        prefixes={word[:3] for word in words};self.assertEqual(len(prefixes),1626)
        source=(UP/'tests/functional_tests/wallet.py').read_text()
        seed=re.search(r"seed = '([^']+)'",source)[1].encode().split()
        self.assertEqual(len(seed),25)
        controls=[bytes([b]) for b in list(range(32))+list(range(127,160))]
        controls += [b'\x1b[31m',b'\x1b]0;title\x07',b'\x1b]0;title\x1b\\',
                     b'\x9b31m',b'\x9d0;title\x9c']
        for control in controls:
            with self.subTest(control=control):
                raw=b' '.join(control.join(bytes([b]) for b in word) for word in seed)
                value=self.d._cli_skeleton(root,raw,'')
                self.assertFalse({m.group()[:3].lower() for m in re.finditer(rb'[A-Za-z]{3,}',value)} & prefixes)
        for first in range(0,len(words),200):
            value=self.d._cli_skeleton(root,b' '.join(word[:3].upper() for word in words[first:first+200]),'')
            self.assertFalse(re.search(rb'[A-Za-z]{3,}',value))

    def test_skeleton_correction_preserves_every_other_driver_byte(self):
        before=subprocess.check_output(['git','show','19c0401a:./vanguard/network/profile-integration.py']).decode()
        after=(c.HERE/'profile-integration.py').read_text()
        def frozen(raw):
            node=next(v for v in ast.parse(raw).body if isinstance(v,ast.FunctionDef) and v.name=='_cli_skeleton')
            lines=raw.splitlines(keepends=True);lines[node.lineno-1:node.end_lineno]=['<AUTHORIZED REDACTOR>\n']
            return ''.join(lines)
        self.assertEqual(frozen(before),frozen(after))

    def test_skeleton_redacts_pinned_seed_address_types_and_keys(self):
        import re
        pinned='e151643c5269c83bf24a83b2548e2493876026b2'
        sources={}
        for name in ('wallet.py','integrated_address.py'):
            path='tests/functional_tests/'+name
            raw=subprocess.check_output(['git','-C',str(UP),'show',pinned+':'+path])
            self.assertEqual(raw,(UP/path).read_bytes());sources[name]=raw.decode()
        seed=re.search(r"seed = '([^']+)'",sources['wallet.py'])[1]
        self.assertEqual(len(seed.split()),25)
        standard=re.search(r"assert res.address == '([^']+)'",sources['wallet.py'])[1]
        sub=re.search(r"assert res.address == '(8[^']+)'",sources['wallet.py'])[1]
        integrated=re.search(r"assert res.integrated_address == '([^']+)'",sources['integrated_address.py'])[1]
        keys=re.findall(r"assert res.key == '([0-9a-f]{64})'",sources['wallet.py'])
        self.assertEqual((len(standard),len(sub),len(integrated),len(keys)),(95,95,106,2))
        root=self.config();password=(root/'password').read_text().strip()
        secrets=[seed,standard,sub,integrated,*keys,password]
        raw=('\n'.join(secrets)+'\nSEED: secret-sentinel\nMnemonic: secret-sentinel\n'
             'view KEY: secret-sentinel\nPASSWORD: secret-sentinel\n').encode()
        result=self.d._cli_skeleton(root,raw,password)
        for secret in secrets+seed.split()+['secret-sentinel']:
            self.assertNotIn(secret.encode(),result)
        self.assertEqual(result.count(b'<b58>'),3)
        self.assertEqual(result.count(b'<hex>'),2)
        self.assertEqual(result.count(b'<w>'),25)
        self.assertEqual((root/'cli-skeleton.private').stat().st_mode & 0o777,0o600)

    def test_skeleton_dictionary_all_1626_words_binds_pinned_header(self):
        import re
        raw=subprocess.check_output(['git','-C',str(UP),'show',
            'e151643c5269c83bf24a83b2548e2493876026b2:src/mnemonics/english.h'])
        self.assertEqual(raw,(UP/'src/mnemonics/english.h').read_bytes())
        words=re.findall(rb'^\s*"([a-z]+)",?\s*$',raw,re.M);self.assertEqual(len(words),1626)
        source=ast.parse((c.HERE/'profile-integration.py').read_text())
        helper=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='_cli_skeleton')
        embedded=next(node.value for node in ast.walk(helper) if isinstance(node,ast.Constant)
                      and isinstance(node.value,str) and 'abbey abducts ability' in node.value)
        self.assertEqual(embedded.split(),[word.decode() for word in words])
        root=self.config();result=b''.join(self.d._cli_skeleton(root,b'\n'.join(words[first:first+200])+b'\n', '')
                                          for first in range(0,len(words),200))
        expected=sum(not re.search(rb'seed|mnemonic|key|password',word,re.I) for word in words)
        self.assertEqual(result.count(b'<w>'),expected)
        self.assertEqual(self.d._cli_skeleton(root,b'ABBEY abducts ability', ''),b'<w> <w> <w>')

    def test_skeleton_controls_formatting_tail_and_atomic_private_replacement(self):
        root=self.config();outside=self.root/'outside';outside.write_bytes(b'untouched')
        (root/'cli-skeleton.private').symlink_to(outside)
        controls=bytes(range(32))+bytes(range(127,160))
        result=self.d._cli_skeleton(root,controls,'')
        for byte in controls:
            self.assertIn(f'<0x{byte:02X}>'.encode(),result)
        self.assertEqual(outside.read_bytes(),b'untouched')
        self.assertFalse((root/'cli-skeleton.private').is_symlink())
        self.assertEqual((root/'cli-skeleton.private').stat().st_mode & 0o777,0o600)
        formatted=b'ab\x1b[31mbey\x1b[0m '+b'Q'*10+b'\x1b[31m'+b'Q'*20
        result=self.d._cli_skeleton(root,formatted,'')
        self.assertIn(b'<w><0x1B>',result);self.assertIn(b'<b58><0x1B>',result)
        self.assertNotIn(b'abbey',result);self.assertNotIn(b'Q'*10,result)
        self.assertEqual(self.d._cli_skeleton(root,b'ab\x1b]0;title\x07bey',''),b'<w><0x1B><0x07>')
        self.assertEqual(self.d._cli_skeleton(root,b'abbey\b',''),b'<w><0x08>')
        self.assertEqual(self.d._cli_skeleton(root,b'\x1b]0;abbey\x07',''),b'<0x1B>]0;<w><0x07>')
        self.assertEqual(self.d._cli_skeleton(root,b'pa\x1b]0;title\x07ssword: SENSITIVE',''),b'')
        self.assertEqual(self.d._cli_skeleton(root,b'x'*9000+b'\n[wallet 123ABC]: ',''),b'[<w> 123ABC]: ')
        self.assertEqual(self.d._cli_skeleton(root,b'x'*9000,''),b'')
        self.assertFalse(list(root.glob('.cli-skeleton-*.private')))

    def test_accepted_baseline_refuses_pinned_background_startup(self):
        root=self.config();before=driver('4ba03433')
        before.PRIVATE=self.d.PRIVATE;before.BIN=self.d.BIN
        with patch.object(before,'released'),patch.object(before,'seal'):
            with self.assertRaisesRegex(ValueError,'unknown CLI prompt; input refused'):
                with patch.dict(before.ENV,WALLET_CLI_FIXTURE_MODE='background-mining'):
                    before.cli(root,48081,True)
        self.assertFalse((root/'background-refused.fixture').exists())

    def test_repeated_background_prompt_refuses_after_one_negative_answer(self):
        root=self.config()
        with self.assertRaisesRegex(ValueError,'unknown CLI prompt; input refused'):
            self.invoke(root,mode='background-repeated')
        self.assertEqual((root/'background-refused.fixture').read_text(),'n\n')

    def test_altered_or_command_background_prompt_refuses_without_answer(self):
        root=self.config()
        for mode in ('background-altered','background-during-command'):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError,'unknown CLI prompt; input refused'):
                    self.invoke(root,mode=mode)
                self.assertFalse((root/'background-refused.fixture').exists())

    def test_actual_wallet_rpc_argv_keeps_server_ssl_and_restriction(self):
        root = self.config()
        with patch.object(self.d, 'launch') as launch, patch.object(self.d, 'wait', side_effect=['fixture:synthetic', True]):
            rpc = self.d.wallet_rpc(root, 48081, 48083, self.root/'rpc')
        self.assertEqual(rpc.port, 48083)
        self.assertEqual(launch.call_args.args[1], [str(self.d.BIN/'monero-wallet-rpc'), '--testnet',
            '--config-file', str(root/'cli.conf'), '--wallet-file', str(root/'wallet'),
            '--password-file', str(root/'password'), '--daemon-address', '127.0.0.1:48081',
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '48083', '--rpc-ssl', 'disabled',
            '--restricted-rpc', '--log-file', str(self.root/'rpc/native.log')])

    def test_early_eio_reaps_and_retains_status_and_label(self):
        root = self.config()
        with self.assertRaises(OSError) as caught: self.invoke(root, mode='early-exit')
        self.assertIn('exit_status=23; expected_prompt=STARTUP_WALLET_PROMPT', '\n'.join(caught.exception.__notes__))
        self.assertFalse(Path('/proc/'+str(self.d.PROCS['cli'][0].pid)).exists())

    def test_command_eio_retains_expected_command(self):
        with self.assertRaises(OSError) as caught: self.invoke(self.config(), mode='command-exit')
        self.assertIn('exit_status=25; expected_prompt=set refresh-from-block-height 0', '\n'.join(caught.exception.__notes__))

    def test_actual_main_keeps_exit_note_private_with_closed_export(self):
        from integration import runtime_diagnostics as diagnostics
        root = self.config(); self.d.PRIVATE = self.root/'main-private'
        self.d.PUBLIC = self.root/'public'; self.d.PUBLIC.mkdir()
        class Wire:
            closed = False
            def start(self): pass
            def close(self): self.closed = True
        previous = sys.gettrace()
        try:
            diagnostics.install(self.d.__file__, c.require)
            with patch.object(self.d, 'Wire', Wire), patch.object(self.d, 'node', side_effect=lambda *args: self.invoke(root, mode='early-exit')):
                self.assertEqual(self.d.main(), 1)
        finally:
            sys.settrace(previous)
        private = self.d.PRIVATE/'failure-traceback'
        self.assertIn('CLI exit_status=23; expected_prompt=STARTUP_WALLET_PROMPT', private.read_text())
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        public = c.json_file(self.d.PUBLIC/'runtime-diagnostics.json')
        self.assertEqual(public, dict(step='NODE1_START', exception_class='OSError', require_label='NONE'))
        self.assertFalse((self.d.PUBLIC/'failure-traceback').exists())
        for path in self.d.PUBLIC.iterdir():
            self.assertNotIn('exit_status', path.read_text()); self.assertNotIn('expected_prompt', path.read_text())

    def test_eof_reaps_and_retains_status(self):
        root = self.config(); actual = self.d.os.read
        def read(fd, size):
            try: return actual(fd, size)
            except OSError as error:
                if error.errno == 5: return b''
                raise
        with patch.object(self.d.os, 'read', side_effect=read):
            with self.assertRaises(OSError) as caught: self.invoke(root, mode='early-exit')
        self.assertIn('exit_status=23', '\n'.join(caught.exception.__notes__))

    def test_unknown_and_repeated_password_prompts_refuse(self):
        root = self.config()
        for mode in ('unknown-password', 'repeated-password'):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError): self.invoke(root, mode=mode)
                self.assertIsNotNone(self.d.PROCS['cli'][0].returncode)

    def test_pinned_confirmation_prompt_refuses_without_answer(self):
        with self.assertRaisesRegex(ValueError, 'unknown CLI prompt; input refused'):
            self.invoke(self.config(), mode='confirmation')

    def test_pinned_options_and_prompts_match_git_objects(self):
        reference = c.json_file(c.HERE/'integration/reference-inputs.json')
        paths = ['src/wallet/wallet2.cpp', 'src/simplewallet/simplewallet.cpp', 'src/wallet/wallet_rpc_server.cpp',
                 'src/rpc/rpc_args.cpp', 'src/wallet/wallet_args.cpp', 'src/common/password.cpp',
                 'contrib/epee/include/console_handler.h']
        source = {}
        for path in paths:
            raw = (UP/path).read_bytes()
            self.assertEqual(raw, subprocess.check_output(['git', '-C', str(UP), 'show', reference['upstream']+':'+path]))
            source[path] = raw.decode()
        cli = source[paths[1]]; wallet = source[paths[0]]; args = source[paths[4]]
        self.assertIn('po::parse_config_file<char>(config_path.string<std::string>().c_str(), desc_params)', args)
        for option in ('daemon_address', 'password_file', 'daemon_login', 'daemon_ssl', 'testnet'):
            self.assertIn('command_line::add_arg(desc_params, opts.'+option+');', wallet)
        for option in ('arg_wallet_file', 'arg_generate_new_wallet', 'arg_mnemonic_language'):
            self.assertIn('command_line::add_arg(desc_params, '+option+');', cli)
        self.assertNotIn('rpc_args::init_options', cli)
        for option in ('arg_rpc_bind_port', 'arg_restricted', 'arg_wallet_file'):
            self.assertIn('command_line::add_arg(desc_params, '+option+');', source[paths[2]])
        self.assertIn('cryptonote::rpc_args::init_options(desc_params);', source[paths[2]])
        for anchor in ['tr("Wallet password")', 'set_refresh_from_block_height(height)',
                       '"refresh-from-block-height = "', 'local_args[0] == "new"',
                       'start_height = boost::lexical_cast<uint64_t>( args[0] )',
                       'tr("Wallet data saved")', '.substr(0, 6)', 'prompt += "]: "']:
            self.assertIn(anchor, cli)
        self.assertIn('std::cout << message <<": "', source[paths[5]])
        self.assertIn('command.compare("exit")', source[paths[6]])
        fixture=FIXTURE.read_text()
        for anchor in ['The daemon is not set up to background mine.',
                       'With background mining enabled, the daemon will mine when idle and not on battery.',
                       'Enabling this supports the network you are using, and makes you eligible for receiving new monero',
                       'Do you want to do it now?']:
            self.assertIn(anchor,cli);self.assertIn(anchor,fixture)
        self.assertIn('m_setup_background_mining(BackgroundMiningMaybe)',wallet)
        self.assertIn('check_background_mining(password);',cli)

    def test_wallet_assertions_commands_credentials_and_rows_unchanged(self):
        before = subprocess.check_output(['git', 'show', 'b17746e6:./vanguard/network/profile-integration.py']).decode()
        after = (c.HERE/'profile-integration.py').read_text()
        def contract(text):
            tree = ast.parse(text)
            return [ast.dump(node) for node in ast.walk(tree) if
                    isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'require']
        # Wrapping cli in the authorized failure boundary changes AST walk order.
        self.assertEqual(sorted(contract(before)), sorted(contract(after)))
        def outside_cli(text):
            tree=ast.parse(text.replace('rpc-ssl=disabled\\n', 'daemon-ssl=disabled\\n'))
            tree.body=[item for item in tree.body if not isinstance(item,ast.FunctionDef) or
                       item.name not in ('cli','_cli_skeleton')]
            return ast.dump(tree)
        self.assertEqual(outside_cli(before), outside_cli(after))
        for anchor in ["commands=['set refresh-from-block-height 0','set','address new','refresh 0','save'] if create else ['set']",
                       "os.write(master,password.encode()+b'\\n')", "os.write(master,b'exit\\n')"]:
            self.assertIn(anchor, before); self.assertIn(anchor, after)



if __name__ == '__main__':unittest.main()
