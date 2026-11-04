#!/usr/bin/env python3
"""Private genesis-only controller, proposed for the later exact grant.

All native transcripts, configs, wallets, frames and credentials stay in /out/private.
Only explicitly constructed row witnesses are exported to /public.
"""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import secrets
import shutil
import signal
import socket
import subprocess
import termios
import threading
import time
import urllib.error
import urllib.request

import profile_contract as c

PRIVATE=Path('/out/private')
PUBLIC=Path('/public')
BIN=Path('/out/build/bin')
ROWS=c.empty_rows()
PROCS={}
SAVED={}
DEADLINE=0
HARD_END=0
FOREIGN='4AzKEX4gXdJdNeM6dfiBFL7kqund3HYGvMBF3ttsNd9SfzgYB6L7ep1Yg1osYJzLdaKAYSLVh6e6jKnAuzj3bw1oGy9kXCb'
ENV={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
     'LC_ALL':'C','TERM':'dumb','HOME':str(PRIVATE),'TMPDIR':'/tmp'}


def budget(seconds=10):
    left=min(seconds,DEADLINE-time.monotonic())
    c.require(left>0,'runtime deadline exhausted')
    return left


def row(file,key,**witness):
    c.require(key in c.REQUIRED[file], 'unknown public row')
    ROWS[file][key]=dict(status='PASS',**witness)


def identity(pid):
    return [pid,Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]]


def launch(name,argv,cwd,env=None,stdin=subprocess.DEVNULL,stdout=None):
    c.require(name not in PROCS or PROCS[name][0].poll() is not None,'overlapping owned process')
    c.require('RPC_LOGIN' not in (env or ENV) or name.startswith('node'),'wallet inherited RPC_LOGIN')
    with (cwd/'console.log').open('ab') as log:
        child_env=dict(env or ENV,HOME=str(cwd))
        p=subprocess.Popen(argv,cwd=cwd,env=child_env,stdin=stdin,stdout=log if stdout is None else stdout,
                           stderr=subprocess.STDOUT,close_fds=True)
    PROCS[name]=(p,identity(p.pid))
    return p


def stop(name,graceful=True):
    p,owned=PROCS[name]
    c.require(p.poll() is None,'unexpected native exit')
    c.stop_identity(owned,identity(p.pid));p.send_signal(signal.SIGTERM)
    forced=False
    try: p.wait(timeout=budget(20))
    except subprocess.TimeoutExpired:
        c.stop_identity(owned,identity(p.pid));p.kill();forced=True;p.wait(timeout=budget(5))
    c.require(not graceful or not forced and p.returncode==0,'graceful save/exit failed')
    c.require(not Path(f'/proc/{p.pid}').exists(),'owned PID not absent')
    return owned


def absent(port):
    with socket.socket() as s:
        s.settimeout(budget(1))
        c.require(s.connect_ex(('127.0.0.1',port)) != 0,'listener remains')


def released(root):
    # Check open owners by actual inode as well as native reopen's own lock acquisition.
    ids={(p.stat().st_dev,p.stat().st_ino) for p in root.rglob('*') if p.is_file()}
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit(): continue
        try:
            for fd in (proc/'fd').iterdir():
                try:
                    st=fd.stat()
                    c.require((st.st_dev,st.st_ino) not in ids,'wallet/data file still open')
                except FileNotFoundError: pass
        except (FileNotFoundError,ProcessLookupError): pass
        # Permission errors fail closed inside this isolated one-user container.


class RPC:
    def __init__(self,port,login): self.port,self.login=port,login
    def call(self,method,params=None,path='json_rpc',login='current',raw=False):
        from http.client import HTTPConnection
        from integration.runtime_diagnostics import readiness_failure
        operation = {'get_info':'get_info'}.get(method, {'get_transaction_pool_hashes':'pool_hashes',
            'get_transaction_pool_stats':'pool_stats'}.get(path, 'OTHER_OPERATION'))
        try:
            auth=self.login if login=='current' else login
            url=f'http://127.0.0.1:{self.port}/{path}'
            body={'jsonrpc':'2.0','id':'0','method':method,'params':params or {}} if path=='json_rpc' else params or {}
            request=urllib.request.Request(url,json.dumps(body).encode(),{'Content-Type':'application/json'})
            end=time.monotonic()+budget(5)
            with contextlib.closing(HTTPConnection('127.0.0.1',self.port,timeout=budget(5))) as connection:
                def remaining():
                    left=min(budget(5),end-time.monotonic())
                    if left<=0:raise TimeoutError('RPC call deadline')
                    connection.timeout=left
                    if connection.sock is not None:connection.sock.settimeout(left)
                def exchange(authorization=None):
                    headers={'Content-Type':'application/json'}
                    if authorization is not None:headers['Authorization']='Digest '+authorization
                    remaining();connection.request('POST',request.selector,request.data,headers)
                    remaining()
                    with connection.getresponse() as response:
                        chunks=[]
                        while True:
                            remaining();chunk=response.read1(65536)
                            if not chunk:break
                            chunks.append(chunk)
                        return response.status,response.headers,b''.join(chunks)
                remaining();connection.connect();session=connection.sock
                expired=threading.Event()
                def expire():
                    # Socket timeouts alone allow indefinitely progressing HTTP headers/framing.
                    expired.set()
                    with contextlib.suppress(OSError):session.shutdown(socket.SHUT_RDWR)
                timer=threading.Timer(max(0,end-time.monotonic()),expire)
                timer.start()
                try:
                    code,headers,payload=exchange()
                    # epee's nonce/nc belong to this socket. Never reconnect using its challenge.
                    if code==401 and auth and connection.sock is session:
                        challenge=None
                        for field in headers.get_all('WWW-Authenticate',[]):
                            scheme,_,value=field.partition(' ')
                            if scheme.lower()!='digest':continue
                            parsed=urllib.request.parse_keqv_list(urllib.request.parse_http_list(value))
                            if parsed.get('algorithm','MD5')=='MD5' and parsed.get('qop')=='auth':
                                challenge=parsed;break
                        if challenge is not None:
                            manager=urllib.request.HTTPPasswordMgrWithDefaultRealm()
                            manager.add_password(None,url,*auth.split(':',1))
                            authorization=urllib.request.HTTPDigestAuthHandler(manager).get_authorization(request,challenge)
                            if authorization is not None:
                                code,headers,payload=exchange(authorization)
                    if expired.is_set() or time.monotonic()>=end:raise TimeoutError('RPC call deadline')
                    # A stale/rejected response ends this call. A readiness retry starts fresh.
                    if not 200<=code<300:
                        if raw:return code,{}
                        error=urllib.error.HTTPError(url,code,'HTTP authentication/transport failure',headers,None)
                        error.close();raise RuntimeError('HTTP authentication/transport failure') from error
                    value=json.loads(payload)
                except Exception as error:
                    if expired.is_set():raise TimeoutError('RPC call deadline') from error
                    raise
                finally:
                    timer.cancel();timer.join();session.close()
            if raw:return code,value
            c.require('error' not in value,'native RPC returned error')
            return value.get('result',value)
        except Exception as error:
            readiness_failure(error, operation, c.require, http_status=locals().get('code', 0))
            raise
    def healthy(self,wallet=False):
        return self.call('get_balance' if wallet else 'get_info')
    def auth_controls(self,wallet=False,old=None):
        self.healthy(wallet)
        for login in ([None,'wrong:wrong']+([old] if old else [])):
            code,_=self.call('get_balance' if wallet else 'get_info',login=login,raw=True)
            c.require(code==401,'missing/wrong/old credential accepted')
            self.healthy(wallet)


def wait(check, seconds=30):
    from integration.runtime_diagnostics import readiness_failure
    end = time.monotonic() + budget(seconds)
    attempts, last_error = 0, None
    while time.monotonic() < end:
        attempts += 1
        try:
            result = check()
            if result: return result
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            last_error = error
        time.sleep(min(.1, budget(.1)))
    error = TimeoutError('native readiness deadline')
    if last_error is not None:
        error.readiness = dict(readiness_failure(last_error, 'OTHER_OPERATION', c.require), attempts=attempts)
    raise error from last_error


def census():
    tables=[(ipv6,Path('/proc/net/'+kind+('6' if ipv6 else '')).read_text())
            for kind in ['tcp','udp'] for ipv6 in [False,True]]
    c.loopback_census(tables)
    # No non-loopback route is allowed in the network-none container.
    routes=Path('/proc/net/route').read_text().splitlines()[1:]
    c.require(all(line.split()[0]=='lo' for line in routes),'non-loopback route')
    return len(tables)


def snapshot(rpc):
    from integration.runtime_diagnostics import readiness_failure
    operation = 'get_info'
    try:
        info = rpc.call('get_info')
        operation = 'pool_hashes'
        hashes = rpc.call('', path='get_transaction_pool_hashes')
        operation = 'pool_stats'
        stats = rpc.call('', path='get_transaction_pool_stats')
        operation = 'get_info'
        c.require(info['status']=='OK' and info['height']==1 and info['top_block_hash']==c.GENESIS,
                  'non-genesis or wrong chain')
        operation = 'pool_hashes' if hashes.get('tx_hashes', []) != [] else 'pool_stats'
        c.require(hashes.get('tx_hashes',[])==[] and stats['pool_stats']['txs_total']==0,'nonempty pool')
        operation = 'get_info'
        return dict(height=info['height'],top_block_hash=info['top_block_hash'],
                    work=info['wide_cumulative_difficulty'],pool_hashes=[])
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        readiness_failure(error, operation, c.require)
        raise


def creation(kind,binaries):
    return dict(kind=kind,profile=c.json_file('/out/inputs.json')['reference']['profile_canonical_sha256'],
                overlay=c.json_file('/out/inputs.json')['reference']['overlay_sha256'],
                binaries=binaries,stopped_saved=True)


def seal(root,kind,binaries):
    manifest=creation(kind,binaries)
    manifest['saved_files']={str(p.relative_to(root)):c.digest(p.read_bytes())
        for p in root.rglob('*') if p.is_file() and p != root/'creation.json'}
    (root/'creation.json').write_bytes(c.canonical(manifest));os.chmod(root/'creation.json',0o600)
    SAVED[str(root)]=manifest
    return manifest


def copy_stopped(root,destination):
    c.root_manifest(root,SAVED[str(root)]);released(root)
    shutil.copytree(root,destination)
    SAVED[str(destination)]=SAVED[str(root)]
    c.root_manifest(destination,SAVED[str(destination)])


def launcher_adverse(root):
    expected=SAVED[str(root)]
    c.root_manifest(root,expected)
    before={str(p.relative_to(root)):c.digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    for case in ['missing','unknown','profile','overlay','binaries','mode','file-drift','symlink']:
        fixture=PRIVATE/('launcher-'+case);shutil.copytree(root,fixture)
        manifest=fixture/'creation.json'
        if case=='missing':manifest.unlink()
        elif case=='unknown':manifest.write_text('{}')
        elif case in ['profile','overlay','binaries']:
            v=c.json_file(manifest);v[case]='wrong';manifest.write_bytes(c.canonical(v))
        elif case=='mode':os.chmod(fixture,0o755)
        elif case=='file-drift':(fixture/'unexpected').write_text('owned adverse fixture')
        elif case=='symlink':(fixture/'alias').symlink_to(root)
        try:c.root_manifest(fixture,expected)
        except (OSError,ValueError):pass
        else:raise ValueError('launcher adverse fixture accepted')
        shutil.rmtree(fixture)
    after={str(p.relative_to(root)):c.digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    c.require(before==after,'original stopped bundle changed')
    row('isolation.json','launcher_refusals',controls=8,kind='launcher-manifest-only',original_unchanged=True)


def node(index,binaries,root=None,reopen=False):
    port=48080+100*index
    root=root or PRIVATE/f'node{index}'
    manifest=creation('daemon',binaries)
    if reopen:c.root_manifest(root,SAVED[str(root)])
    else:
        root.mkdir(mode=0o700);(root/'creation.json').write_bytes(c.canonical(manifest))
        os.chmod(root/'creation.json',0o600)
    login='node:'+secrets.token_hex(24)
    env=dict(ENV,RPC_LOGIN=login)
    argv=[str(BIN/'monerod'),'--testnet','--data-dir',str(root),'--non-interactive','--no-igd',
          '--allow-local-ip','--disable-dns-checkpoints','--check-updates','disabled','--hide-my-port',
          '--max-concurrency','1','--no-zmq','--rpc-ssl','disabled','--restricted-rpc',
          '--p2p-bind-ip','127.0.0.1','--p2p-bind-ipv6-address','::1','--p2p-bind-port',str(port),'--rpc-bind-ip','127.0.0.1',
          '--rpc-bind-port',str(port+1),'--add-exclusive-node',f'127.0.0.1:{49080+index}',
          '--log-level','1','--log-file',str(root/'native.log')]
    (root/'creation.json').write_bytes(c.canonical(dict(manifest,stopped_saved=False)))
    launch(f'node{index}',argv,root,env)
    rpc=RPC(port+1,login);wait(lambda:snapshot(rpc))
    return rpc,root


def save_node(index,root,binaries):
    ident=stop(f'node{index}');absent(48080+index*100);absent(48081+index*100)
    released(root)
    seal(root,'daemon',binaries)
    return ident


class Wire:
    """Same Levin framing as daemon-p2p.py, with all raw frames private."""
    def __init__(self):self.frames=[];self.error=None;self.closed=False;self.sockets=[]
    def start(self):
        self.server=socket.socket();self.server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.server.bind(('127.0.0.1',49080));self.server.listen(4);self.server.settimeout(.2)
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        try:
            while not self.closed:
                try:a,_=self.server.accept()
                except socket.timeout:continue
                b=socket.create_connection(('127.0.0.1',48180),timeout=budget(5))
                self.sockets=[a,b];buffers={a:b'',b:b''}
                while not self.closed:
                    ready,_,_=select.select([a,b],[],[],.2)
                    ended=False
                    for source in ready:
                        raw=source.recv(65536)
                        if not raw:ended=True;break
                        buffers[source]+=raw
                        while len(buffers[source])>=c.HEADER.size:
                            head=buffers[source][:c.HEADER.size]
                            sig,size,ret,cmd,code,flags,version=c.HEADER.unpack(head)
                            c.require(sig==c.SIGNATURE and size<=16*1024**2 and version==1,'Levin framing')
                            if len(buffers[source])<c.HEADER.size+size:break
                            packet=buffers[source][:c.HEADER.size+size];buffers[source]=buffers[source][len(packet):]
                            self.frames.append(('request' if source is a else 'response',cmd,packet))
                            (PRIVATE/f'frame-{len(self.frames):04d}.bin').write_bytes(packet)
                            (b if source is a else a).sendall(packet)
                    if ended:break
                a.close();b.close()
        except Exception as error:
            if not self.closed:self.error=type(error).__name__
    def close(self):
        self.closed=True
        for s in self.sockets:
            with contextlib.suppress(OSError):s.shutdown(socket.SHUT_RDWR)
        self.server.close();self.thread.join(timeout=budget(2))


def read_frame(s):
    def exact(size):
        value=b''
        while len(value)<size:
            part=s.recv(size-len(value));c.require(bool(part),'native frame ended');value+=part
        return value
    head=exact(c.HEADER.size);sig,size,ret,cmd,code,flags,ver=c.HEADER.unpack(head)
    c.require(sig==c.SIGNATURE and size<=16*1024**2 and ver==1,'native Levin frame')
    return cmd,flags,code,head+exact(size)


def handshake(s,packet):
    s.sendall(packet)
    for _ in range(16):
        cmd,flags,code,reply=read_frame(s)
        if cmd==1001 and flags==2:
            c.require(code>0 and c.UUID in reply,'healthy native handshake response')
            return reply
    raise RuntimeError('missing handshake response')


def chain_control(packet,hash_value):
    with socket.create_connection(('127.0.0.1',48180),timeout=budget(5)) as s:
        handshake(s,packet);frame=c.chain_request(hash_value);s.sendall(frame)
        if hash_value==c.GENESIS:
            for _ in range(16):
                cmd,_,_,response=read_frame(s)
                if cmd==2007:return c.digest(frame),c.digest(response)
            raise RuntimeError('missing native chain response')
        return c.digest(frame),None


def isolation(packet,rpc,log):
    before=snapshot(rpc)
    chain_control(packet,c.GENESIS)
    offset=log.stat().st_size
    wrong=c.mutate_uuid(packet)
    with socket.create_connection(('127.0.0.1',48180),timeout=budget(5)) as s:
        s.sendall(wrong)
        with contextlib.suppress(OSError,ValueError):read_frame(s)
    wait(lambda:'WRONG NETWORK AGENT CONNECTED!' in log.read_bytes()[offset:].decode(errors='replace'),5)
    chain_control(packet,c.GENESIS)
    c.require(snapshot(rpc)==before,'UUID negative changed state')
    row('isolation.json','uuid_guard',guard='net_node.inl:handle_handshake/network_id',
        fixture_sha256=c.digest(wrong),healthy_before_after=True,unchanged_state=before)
    chain_control(packet,c.GENESIS);offset=log.stat().st_size
    fixture,_=chain_control(packet,'00'*32)
    def witness():
        text=log.read_bytes()[offset:].decode(errors='replace')
        return 'genesis block mismatch:' in text and 'Failed to handle NOTIFY_REQUEST_CHAIN.' in text
    wait(witness,5);chain_control(packet,c.GENESIS)
    c.require(snapshot(rpc)==before,'chain negative changed state')
    row('isolation.json','chain_genesis_guard',guard='Blockchain::find_blockchain_supplement/genesis',
        fixture_sha256=fixture,healthy_before_after=True,unchanged_state=before,response_command=2007)


def cli(root,port,create=False):
    if not create:c.root_manifest(root,SAVED[str(root)])
    released(root)
    password=c.check_file(root/'password').decode().strip()
    argv=[str(BIN/'monero-wallet-cli'),'--testnet','--config-file',str(root/'cli.conf'),
          '--password-file',str(root/'password'),'--daemon-address',f'127.0.0.1:{port}',
          '--log-file',str(root/'cli.log')]
    argv+=['--generate-new-wallet',str(root/'wallet'),'--mnemonic-language','English'] if create else ['--wallet-file',str(root/'wallet')]
    master,slave=pty.openpty()
    attrs=termios.tcgetattr(slave);attrs[3]&=~termios.ECHO;termios.tcsetattr(slave,termios.TCSANOW,attrs)
    p=launch('cli',argv,root,stdin=slave,stdout=slave);os.close(slave)
    transcript=b''
    prompt=re.compile(rb'\[wallet [1-9A-HJ-NP-Za-km-z]{6}(?: \(no daemon\)| \(out of sync\))?\]: $')
    def expect(label):
        nonlocal transcript
        data=b'';end=time.monotonic()+budget(25);password_sent=False
        while time.monotonic()<end:
            if select.select([master],[],[],min(.1,budget(.1)))[0]:
                try:raw=os.read(master,65536)
                except OSError as error:
                    if error.errno!=5:raise  # Linux PTY EIO when the slave closes.
                    status=p.wait(timeout=budget(5))
                    error.add_note(f'CLI exit_status={status}; expected_prompt={label}')
                    raise
                if not raw:
                    error=OSError(5,'CLI PTY EOF')
                    status=p.wait(timeout=budget(5))
                    error.add_note(f'CLI exit_status={status}; expected_prompt={label}')
                    raise error
                data+=raw;transcript+=raw
                clean=re.sub(rb'\x1b\[[0-9;]*[A-Za-z]',b'',data).replace(b'\r',b'')
                if prompt.search(clean):return clean
                if clean.endswith(b'Wallet password: '):
                    c.require(not password_sent,'repeated password prompt')
                    os.write(master,password.encode()+b'\n');password_sent=True;data=b''
                elif re.search(rb'(?:\[Y/n\]: |\[y/N\]: |Confirm password: |Enter password[^\n]*: )$',clean):
                    raise ValueError('unknown CLI prompt; input refused')
            c.require(p.poll() is None,'CLI exited before expected prompt')
        raise TimeoutError('exact CLI prompt not observed')
    try:
        expect('STARTUP_WALLET_PROMPT')
        commands=['set refresh-from-block-height 0','set','address new','refresh 0','save'] if create else ['set']
        height=False
        for command in commands:
            os.write(master,command.encode()+b'\n');answer=expect(command)
            if command=='set':height=bool(re.search(rb'refresh-from-block-height = 0(?:\n|$)',answer))
        c.require(height,'persisted CLI refresh height differs')
        os.write(master,b'exit\n');p.wait(timeout=budget(20))
        c.require(p.returncode==0,'CLI normal save/exit')
        c.require(not Path(f'/proc/{p.pid}').exists(),'CLI remains')
    finally:
        (root/'cli-transcript.private').write_bytes(transcript);os.close(master)
        if p.poll() is None:stop('cli',graceful=False)
    released(root)
    seal(root,'wallet',{name:c.digest((BIN/name).read_bytes()) for name in ['monerod','monero-wallet-cli','monero-wallet-rpc']})


def wallet_rpc(root,daemon_port,port,cwd):
    c.root_manifest(root,SAVED[str(root)]);released(root)
    cwd.mkdir(mode=0o700)
    argv=[str(BIN/'monero-wallet-rpc'),'--testnet','--config-file',str(root/'cli.conf'),
          '--wallet-file',str(root/'wallet'),'--password-file',str(root/'password'),
          '--daemon-address',f'127.0.0.1:{daemon_port}','--rpc-bind-ip','127.0.0.1',
          '--rpc-bind-port',str(port),'--rpc-ssl','disabled','--restricted-rpc',
          '--log-file',str(cwd/'native.log')]
    launch('wallet',argv,cwd)
    login=wait(lambda: c.check_file(cwd/f'monero-wallet-rpc.{port}.login',modes=(0o400,0o600)).decode(),15)
    rpc=RPC(port,login);wait(lambda:rpc.healthy(True))
    return rpc


def wallet_identity(rpc):
    addresses=rpc.call('get_address',dict(account_index=0,address_index=[]))
    c.require(len(addresses['addresses'])>=2,'subaddress was not provisioned')
    return [a['address'] for a in addresses['addresses']]


def wallet_controls(index,daemon_rpc,binaries):
    root=PRIVATE/f'wallet{index}';root.mkdir(mode=0o700)
    (root/'password').write_text(secrets.token_hex(32)+'\n');os.chmod(root/'password',0o600)
    (root/'cli.conf').write_text('daemon-login='+daemon_rpc.login+'\ndaemon-ssl=disabled\n');os.chmod(root/'cli.conf',0o600)
    cli(root,daemon_rpc.port,True);cli(root,daemon_rpc.port)
    port=48083+index*100
    rpc=wallet_rpc(root,daemon_rpc.port,port,PRIVATE/f'wallet{index}-rpc1')
    addresses=wallet_identity(rpc);standard=addresses[0];rpc.auth_controls(True)
    integrated=rpc.call('make_integrated_address',dict(standard_address=standard,payment_id='0123456789abcdef'))['integrated_address']
    split=rpc.call('split_integrated_address',dict(integrated_address=integrated))
    c.require(split['standard_address']==standard and split['payment_id']=='0123456789abcdef','integrated roundtrip')
    for address in addresses+[integrated]:
        value=rpc.call('validate_address',dict(address=address,any_net_type=False,allow_openalias=False))
        c.require(value['valid'] and value['nettype']=='testnet','same-profile address validation')
    c.require(rpc.call('validate_address',dict(address=FOREIGN,any_net_type=True,allow_openalias=False))['valid'],
              'foreign fixture itself invalid')
    c.require(not rpc.call('validate_address',dict(address=FOREIGN,any_net_type=False,allow_openalias=False))['valid'],
              'foreign prefix accepted')
    # Public upstream test mnemonic is used solely as a well-formed denied request.
    # Its contents and every request body stay controller-private.
    tests=Path('/out/source/tests/functional_tests/wallet.py').read_text()
    seed=re.search(r"seed = '([^']+)'",tests).group(1)
    requests=c.denial_requests(standard,seed)
    expected=set(c.json_file(c.HERE/'integration/reviewed-contract.json')['restricted_wallet']['denial_methods'])
    c.require(set(requests)==expected,'denial matrix drift')
    for method,params in requests.items():
        rpc.healthy(True);code,value=rpc.call(method,params,raw=True)
        c.require(code==200 and value.get('error',{}).get('code')==-7,'restriction handler did not deny')
        rpc.healthy(True)
    old=rpc.login;stop('wallet');absent(port);released(root);seal(root,'wallet',binaries)
    # Reopening the exact stopped bundle proves native lock acquisition and saved identity.
    cli(root,daemon_rpc.port)
    rpc=wallet_rpc(root,daemon_rpc.port,port,PRIVATE/f'wallet{index}-rpc2')
    c.require(old!=rpc.login and wallet_identity(rpc)==addresses,'wallet reopen identity/rotation')
    rpc.auth_controls(True,old);stop('wallet');absent(port);released(root);seal(root,'wallet',binaries)
    restore=PRIVATE/f'wallet{index}-restored';copy_stopped(root,restore)
    cli(restore,daemon_rpc.port)
    rpc=wallet_rpc(restore,daemon_rpc.port,port,PRIVATE/f'wallet{index}-rpc3')
    c.require(wallet_identity(rpc)==addresses,'cold restore changed identity')
    stop('wallet');absent(port);released(restore)
    return dict(denials=len(requests),saved_height=0,restore_identity_matches=True)


def main():
    global DEADLINE,HARD_END
    os.umask(0o077);PRIVATE.mkdir(mode=0o700);DEADLINE=time.monotonic()+570;HARD_END=DEADLINE+30
    binaries={name:c.digest((BIN/name).read_bytes()) for name in ['monerod','monero-wallet-cli','monero-wallet-rpc']}
    wire=Wire();wire.start()
    try:
        b,br=node(1,binaries);a,ar=node(0,binaries)
        wait(lambda: any(d=='request' and cmd==1001 for d,cmd,p in wire.frames) and
                     any(d=='response' and cmd==1001 for d,cmd,p in wire.frames))
        c.require(wire.error is None,'native peer bridge failed')
        packet=next(p for d,cmd,p in wire.frames if d=='request' and cmd==1001)
        c.require(snapshot(a)==snapshot(b),'genesis peer disagreement')
        row('peer.json','native_handshake',request_sha256=c.digest(packet),command=1001)
        row('peer.json','genesis_state',**snapshot(a))
        for rpc in (a,b):
            rpc.auth_controls()
            versions=rpc.call('get_version')['hard_forks']
            hf=rpc.call('hard_fork_info',dict(version=18))
            c.require(any(x['hf_version']==18 and x['height']==1 for x in versions) and
                      hf['earliest_height']==1,'daemon fork schedule')
        row('peer.json','daemon_fork_table',v18_height=1,offline_wallet='NOT_RUN')
        census()
        row('auth.json','http_auth',daemons=2,loopback_socket_census=True)
        save_node(0,ar,binaries);wire.close()
        isolation(packet,b,br/'native.log')
        state=snapshot(b)
        for _ in range(20):
            census();time.sleep(budget(.1))
        c.require(snapshot(b)==state,'no-counterpart state changed')
        row('isolation.json','no_fallback',bounded_seconds=2,loopback_socket_samples=20,
            exclusive_endpoint_absent=True,unchanged_state=state,scope='bounded-no-external-connection')
        save_node(1,br,binaries)
        # Counterpart remains stopped during each retained/cold-restored daemon reopen.
        for index,root in [(0,ar),(1,br)]:
            previous=PROCS[f'node{index}'][1]
            rpc,_=node(index,binaries,root,True)
            c.require(PROCS[f'node{index}'][1]!=previous and snapshot(rpc)==state,'restart identity/state')
            save_node(index,root,binaries)
            restored=PRIVATE/f'node{index}-restored';copy_stopped(root,restored)
            rpc,_=node(index,binaries,restored,True);c.require(snapshot(rpc)==state,'cold restore state')
            save_node(index,restored,binaries)
        row('reopen.json','daemon_reopen_restore',genesis_only=True,counterpart_stopped=True)
        launcher_adverse(ar)
        a,_=node(0,binaries,ar,True);b,_=node(1,binaries,br,True)
        results=[wallet_controls(0,a,binaries),wallet_controls(1,b,binaries)]
        for key in c.REQUIRED['wallet.json']:row('wallet.json',key,wallets=2)
        row('auth.json','seventeen_denials',wallets=2,per_wallet=17,code=-7)
        row('auth.json','rotated_login',wallets=2,old_credentials_rejected=True)
        row('reopen.json','wallet_save_exit_release',wallets=2,forced_kill=False)
        row('reopen.json','wallet_cold_restore',wallets=2,height=0)
        save_node(0,ar,binaries);save_node(1,br,binaries)
    except Exception as error:
        # Keep exception details private. Rows not reached retain NOT_RUN.
        (PRIVATE/'failure-class').write_text(type(error).__name__+'\n')
        (PRIVATE/'failure-traceback').write_text(__import__('traceback').format_exc())
        return 1
    finally:
        DEADLINE=HARD_END
        if not wire.closed:
            with contextlib.suppress(Exception):wire.close()
        for name,(p,_) in PROCS.items():
            if p.poll() is None:
                with contextlib.suppress(Exception):stop(name,graceful=False)
        for name in c.REQUIRED:
            if name not in ('build.json','resources.json','cleanup.json'):
                (PUBLIC/name).write_text(json.dumps(ROWS[name],indent=2)+'\n')
    return 0


if __name__=='__main__': raise SystemExit(main())
