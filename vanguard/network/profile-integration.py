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


def _cli_skeleton(root, transcript, password):
    """Private diagnostic only; never exported. Dictionary binds pinned english.h."""
    # Copyright (c) 2014-2024, The Monero Project
    #
    # All rights reserved.
    #
    # Redistribution and use in source and binary forms, with or without modification, are
    # permitted provided that the following conditions are met:
    #
    # 1. Redistributions of source code must retain the above copyright notice, this list of
    # conditions and the following disclaimer.
    #
    # 2. Redistributions in binary form must reproduce the above copyright notice, this list
    # of conditions and the following disclaimer in the documentation and/or other
    # materials provided with the distribution.
    #
    # 3. Neither the name of the copyright holder nor the names of its contributors may be
    # used to endorse or promote products derived from this software without specific
    # prior written permission.
    #
    # THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
    # EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
    # MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
    # THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
    # SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
    # PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    # INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
    # STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
    # THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
    words = frozenset("""
        abbey abducts ability ablaze abnormal abort abrasive absorb abyss academy aces aching acidic acoustic acquire across
        actress acumen adapt addicted adept adhesive adjust adopt adrenalin adult adventure aerial afar affair afield afloat
        afoot afraid after against agenda aggravate agile aglow agnostic agony agreed ahead aided ailments aimless airport
        aisle ajar akin alarms album alchemy alerts algebra alkaline alley almost aloof alpine already also altitude
        alumni always amaze ambush amended amidst ammo amnesty among amply amused anchor android anecdote angled ankle
        annoyed answers antics anvil anxiety anybody apart apex aphid aplomb apology apply apricot aptitude aquarium arbitrary
        archer ardent arena argue arises army around arrow arsenic artistic ascend ashtray aside asked asleep aspire
        assorted asylum athlete atlas atom atrium attire auburn auctions audio august aunt austere autumn avatar avidly
        avoid awakened awesome awful awkward awning awoken axes axis axle aztec azure baby bacon badge baffles
        bagpipe bailed bakery balding bamboo banjo baptism basin batch bawled bays because beer befit begun behind
        being below bemused benches berries bested betting bevel beware beyond bias bicycle bids bifocals biggest bikini
        bimonthly binocular biology biplane birth biscuit bite biweekly blender blip bluntly boat bobsled bodies bogeys boil
        boldly bomb border boss both bounced bovine bowling boxes boyfriend broken brunt bubble buckets budget buffet
        bugs building bulb bumper bunch business butter buying buzzer bygones byline bypass cabin cactus cadets cafe
        cage cajun cake calamity camp candy casket catch cause cavernous cease cedar ceiling cell cement cent
        certain chlorine chrome cider cigar cinema circle cistern citadel civilian claim click clue coal cobra cocoa
        code coexist coffee cogs cohesive coils colony comb cool copy corrode costume cottage cousin cowl criminal
        cube cucumber cuddled cuffs cuisine cunning cupcake custom cycling cylinder cynical dabbing dads daft dagger daily
        damp dangerous dapper darted dash dating dauntless dawn daytime dazed debut decay dedicated deepest deftly degrees
        dehydrate deity dejected delayed demonstrate dented deodorant depth desk devoid dewdrop dexterity dialect dice diet different
        digit dilute dime dinner diode diplomat directed distance ditch divers dizzy doctor dodge does dogs doing
        dolphin domestic donuts doorway dormant dosage dotted double dove down dozen dreams drinks drowning drunk drying
        dual dubbed duckling dude duets duke dullness dummy dunes duplex duration dusted duties dwarf dwelt dwindling
        dying dynamite dyslexic each eagle earth easy eating eavesdrop eccentric echo eclipse economics ecstatic eden edgy
        edited educated eels efficient eggs egotistic eight either eject elapse elbow eldest eleven elite elope else
        eluded emails ember emerge emit emotion empty emulate energy enforce enhanced enigma enjoy enlist enmity enough
        enraged ensign entrance envy epoxy equip erase erected erosion error eskimos espionage essential estate etched eternal
        ethics etiquette evaluate evenings evicted evolved examine excess exhale exit exotic exquisite extra exult fabrics factual
        fading fainted faked fall family fancy farming fatal faulty fawns faxed fazed feast february federal feel
        feline females fences ferry festival fetches fever fewest fiat fibula fictional fidget fierce fifteen fight films
        firm fishing fitting five fixate fizzle fleet flippant flying foamy focus foes foggy foiled folding fonts
        foolish fossil fountain fowls foxes foyer framed friendly frown fruit frying fudge fuel fugitive fully fuming
        fungal furnished fuselage future fuzzy gables gadget gags gained galaxy gambit gang gasp gather gauze gave
        gawk gaze gearbox gecko geek gels gemstone general geometry germs gesture getting geyser ghetto ghost giant
        giddy gifts gigantic gills gimmick ginger girth giving glass gleeful glide gnaw gnome goat goblet godfather
        goes goggles going goldfish gone goodbye gopher gorilla gossip gotten gourmet governing gown greater grunt guarded
        guest guide gulp gumball guru gusts gutter guys gymnast gypsy gyrate habitat hacksaw haggled hairy hamburger
        happens hashing hatchet haunted having hawk haystack hazard hectare hedgehog heels hefty height hemlock hence heron
        hesitate hexagon hickory hiding highway hijack hiker hills himself hinder hippo hire history hitched hive hoax
        hobby hockey hoisting hold honked hookup hope hornet hospital hotel hounded hover howls hubcaps huddle huge
        hull humid hunter hurried husband huts hybrid hydrogen hyper iceberg icing icon identity idiom idled idols
        igloo ignore iguana illness imagine imbalance imitate impel inactive inbound incur industrial inexact inflamed ingested initiate
        injury inkling inline inmate innocent inorganic input inquest inroads insult intended inundate invoke inwardly ionic irate
        iris irony irritate island isolated issued italics itches items itinerary itself ivory jabbed jackets jaded jagged
        jailed jamming january jargon jaunt javelin jaws jazz jeans jeers jellyfish jeopardy jerseys jester jetting jewels
        jigsaw jingle jittery jive jobs jockey jogger joining joking jolted jostle journal joyous jubilee judge juggled
        juicy jukebox july jump junk jury justice juvenile kangaroo karate keep kennel kept kernels kettle keyboard
        kickoff kidneys king kiosk kisses kitchens kiwi knapsack knee knife knowledge knuckle koala laboratory ladder lagoon
        lair lakes lamb language laptop large last later launching lava lawsuit layout lazy lectures ledge leech
        left legion leisure lemon lending leopard lesson lettuce lexicon liar library licks lids lied lifestyle light
        likewise lilac limits linen lion lipstick liquid listen lively loaded lobster locker lodge lofty logic loincloth
        long looking lopped lordship losing lottery loudly love lower loyal lucky luggage lukewarm lullaby lumber lunar
        lurk lush luxury lymph lynx lyrics macro madness magically mailed major makeup malady mammal maps masterful
        match maul maverick maximum mayor maze meant mechanic medicate meeting megabyte melting memoir menu merger mesh
        metro mews mice midst mighty mime mirror misery mittens mixture moat mobile mocked mohawk moisture molten
        moment money moon mops morsel mostly motherly mouth movement mowing much muddy muffin mugged mullet mumble
        mundane muppet mural musical muzzle myriad mystery myth nabbing nagged nail names nanny napkin narrate nasty
        natural nautical navy nearby necklace needed negative neither neon nephew nerves nestle network neutral never newt
        nexus nibs niche niece nifty nightly nimbly nineteen nirvana nitrogen nobody nocturnal nodes noises nomad noodles
        northern nostril noted nouns novelty nowhere nozzle nuance nucleus nudged nugget nuisance null number nuns nurse
        nutshell nylon oaks oars oasis oatmeal obedient object obliged obnoxious observant obtains obvious occur ocean october
        odds odometer offend often oilfield ointment okay older olive olympics omega omission omnibus onboard oncoming oneself
        ongoing onion online onslaught onto onward oozed opacity opened opposite optical opus orange orbit orchid orders
        organs origin ornament orphans oscar ostrich otherwise otter ouch ought ounce ourselves oust outbreak oval oven
        owed owls owner oxidant oxygen oyster ozone pact paddles pager pairing palace pamphlet pancakes paper paradise
        pastry patio pause pavements pawnshop payment peaches pebbles peculiar pedantic peeled pegs pelican pencil people pepper
        perfect pests petals phase pheasants phone phrases physics piano picked pierce pigment piloted pimple pinched pioneer
        pipeline pirate pistons pitched pivot pixels pizza playful pledge pliers plotting plus plywood poaching pockets podcast
        poetry point poker polar ponies pool popular portents possible potato pouch poverty powder pram present pride
        problems pruned prying psychic public puck puddle puffin pulp pumpkins punch puppy purged push putty puzzled
        pylons pyramid python queen quick quote rabbits racetrack radar rafts rage railway raking rally ramped randomly
        rapid rarest rash rated ravine rays razor react rebel recipe reduce reef refer regular reheat reinvest
        rejoices rekindle relic remedy renting reorder repent request reruns rest return reunion revamp rewind rhino rhythm
        ribbon richly ridges rift rigid rims ringing riots ripped rising ritual river roared robot rockets rodent
        rogue roles romance roomy roped roster rotate rounded rover rowboat royal ruby rudely ruffled rugged ruined
        ruling rumble runway rural rustled ruthless sabotage sack sadness safety saga sailor sake salads sample sanity
        sapling sarcasm sash satin saucepan saved sawmill saxophone sayings scamper scenic school science scoop scrub scuba
        seasons second sedan seeded segments seismic selfish semifinal sensible september sequence serving session setup seventh sewage
        shackles shelter shipped shocking shrugged shuffled shyness siblings sickness sidekick sieve sifting sighting silk simplest sincerely
        sipped siren situated sixteen sizes skater skew skirting skulls skydive slackens sleepless slid slower slug smash
        smelting smidgen smog smuggled snake sneeze sniff snout snug soapy sober soccer soda software soggy soil
        solved somewhere sonic soothe soprano sorry southern sovereign sowed soya space speedy sphere spiders splendid spout
        sprig spud spying square stacking stellar stick stockpile strained stunning stylishly subtly succeed suddenly suede suffice
        sugar suitcase sulking summon sunken superior surfer sushi suture swagger swept swiftly sword swung syllabus symptoms
        syndrome syringe system taboo tacit tadpoles tagged tail taken talent tamper tanks tapestry tarnished tasked tattoo
        taunts tavern tawny taxi teardrop technical tedious teeming tell template tender tepid tequila terminal testing tether
        textbook thaw theatrics thirsty thorn threaten thumbs thwart ticket tidy tiers tiger tilt timber tinted tipsy
        tirade tissue titans toaster tobacco today toenail toffee together toilet token tolerant tomorrow tonic toolbox topic
        torch tossed total touchy towel toxic toyed trash trendy tribal trolling truth trying tsunami tubes tucks
        tudor tuesday tufts tugs tuition tulips tumbling tunnel turnip tusks tutor tuxedo twang tweezers twice twofold
        tycoon typist tyrant ugly ulcers ultimate umbrella umpire unafraid unbending uncle under uneven unfit ungainly unhappy
        union unjustly unknown unlikely unmask unnoticed unopened unplugs unquoted unrest unsafe until unusual unveil unwind unzip
        upbeat upcoming update upgrade uphill upkeep upload upon upper upright upstairs uptight upwards urban urchins urgent
        usage useful usher using usual utensils utility utmost utopia uttered vacation vague vain value vampire vane
        vapidly vary vastness vats vaults vector veered vegan vehicle vein velvet venomous verification vessel veteran vexed
        vials vibrate victim video viewpoint vigilant viking village vinegar violin vipers virtual visited vitals vivid vixen
        vocal vogue voice volcano vortex voted voucher vowels voyage vulture wade waffle wagtail waist waking wallets
        wanted warped washing water waveform waxing wayside weavers website wedge weekday weird welders went wept were
        western wetsuit whale when whipped whole wickets width wield wife wiggle wildly winter wipeout wiring wise
        withdrawn wives wizard wobbly woes woken wolf womanly wonders woozy worry wounded woven wrap wrist wrong
        yacht yahoo yanks yard yawning yearbook yellow yesterday yeti yields yodel yoga younger yoyo zapped zeal
        zebra zero zesty zigzags zinger zippers zodiac zombie zones zoom
    """.split())
    prefixes = {word[:3] for word in words}
    # Discard an incomplete first line rather than expose a truncated secret.
    tail = transcript[-8192:]
    if len(transcript)>8192 and transcript[-8193:-8192]!=b'\n':
        tail = tail.partition(b'\n')[2]
    visible = lambda raw: ''.join(chr(b) if 32<=b<127 else f'<0x{b:02X}>' for b in raw)
    result = []
    for line in tail.split(b'\n'):
        # A lexical view ignores terminal formatting, retaining original offsets.
        # Redacted spans still render every original control/escape byte visibly.
        # Include original words separated or overwritten by terminal controls.
        views = [(line,list(range(len(line))))]
        for displayed in (False,True):
            positions = []; index = 0
            while index<len(line):
                escape = re.match(rb'(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]',line[index:])
                if not escape and displayed:
                    escape = re.match(rb'(?:\x1b\]|\x9d)[\s\S]*?(?:\x07|\x1b\\|\x9c)',line[index:])
                if escape:
                    index += escape.end(); continue
                byte = line[index]
                if displayed and byte==8 and positions:
                    positions.pop()
                elif 32<=byte<127:
                    positions.append(index)
                index += 1
            views.append((bytes(line[i] for i in positions),positions))
        if (any(re.search(rb'seed|mnemonic|key|password',value,re.I) or
                password and password.encode() in value for value in [line]+[v[0] for v in views])):
            continue
        matches = []
        for lexical,positions in views:
            found = [(m.start(),m.end(),'<hex>') for m in re.finditer(rb'[0-9A-Fa-f]{16,}',lexical)]
            found += [(m.start(),m.end(),'<b58>') for m in re.finditer(rb'[1-9A-HJ-NP-Za-km-z]{12,}',lexical)]
            found += [(m.start(),m.end(),'<w>') for m in re.finditer(rb'[A-Za-z]{3,}',lexical)
                      if m.group()[:3].decode().lower() in prefixes]
            matches += [(positions[first],positions[last-1]+1,token) for first,last,token in found]
        spans = []
        for first,last,token in sorted(matches,key=lambda item:(item[0],-(item[1]-item[0]),
                {'<w>':0,'<hex>':1,'<b58>':2}[item[2]])):
            if spans and first<spans[-1][1]:
                start,end,label = spans[-1];spans[-1]=(start,max(end,last),label)
            else:spans.append((first,last,token))
        cursor = 0; parts = []
        for first,last,token in spans:
            parts += [visible(line[cursor:first]),token,
                visible(bytes(b for b in line[first:last] if not 32<=b<127))]
            cursor = last
        parts.append(visible(line[cursor:]));result.append(''.join(parts))
    payload = '<0x0A>\n'.join(result).encode('ascii')
    temporary = root/('.cli-skeleton-'+secrets.token_hex(8)+'.private')
    fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(payload)
        os.replace(temporary,root/'cli-skeleton.private')
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def cli(root,port,create=False):
    transcript=b'';password=''
    try:
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
        prompt=re.compile(rb'\[wallet [1-9A-HJ-NP-Za-km-z]{6}(?: \(no daemon\)| \(out of sync\))?\]: $')
        background_prompt=(b'The daemon is not set up to background mine.\n'
            b'With background mining enabled, the daemon will mine when idle and not on battery.\n'
            b'Enabling this supports the network you are using, and makes you eligible for receiving new monero\n'
            b'Do you want to do it now? [y/N]: ')
        background_refused=False
        def normalize(data):
            data=re.sub(rb'\x1b\][\s\S]*?(?:\x07|\x1b\\)',b'',data)
            data=re.sub(rb'\x1b\[[0-?]*[ -/]*[@-~]',b'',data)
            data=data.replace(b'\x01',b'').replace(b'\x02',b'').replace(b'\r\n',b'\n')
            lines=[];current=bytearray()
            for byte in data:
                if byte==13:current.clear()
                elif byte==10:lines.append(bytes(current));current.clear()
                elif byte==8:
                    if current:current.pop()
                else:current.append(byte)
            return b'\n'.join(lines+[bytes(current)])
        def expect(label):
            nonlocal transcript,background_refused
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
                    clean=normalize(data)
                    if prompt.search(clean):return clean
                    if clean.endswith(b'Wallet password: '):
                        c.require(not password_sent,'repeated password prompt')
                        os.write(master,password.encode()+b'\n');password_sent=True;data=b''
                    elif label=='STARTUP_WALLET_PROMPT' and not background_refused and clean.endswith(background_prompt):
                        # Pinned check_background_mining(): decline once, never enable mining.
                        os.write(master,b'n\n');background_refused=True;data=b''
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
    except BaseException:
        _cli_skeleton(root,transcript,password)
        raise


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
