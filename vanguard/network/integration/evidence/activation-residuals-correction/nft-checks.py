import hashlib,json,math,pathlib,shutil,subprocess,tempfile,time,sys
ROOT=pathlib.Path.cwd()
OUT=ROOT/'vanguard/network/integration/evidence/activation-residuals-correction'
sys.path.insert(0,str(ROOT/'vanguard/network'))
from integration import operator_contract as o
OUT.mkdir(exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(command):
    p=subprocess.run(command,capture_output=True,text=True,timeout=120)
    return dict(command=command,exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
checks=[]; image='meownero-tjs4398-correction-73ec5ffb:local'
with tempfile.TemporaryDirectory(prefix='TJS-4398-correction-nft-') as temp:
    context=pathlib.Path(temp)
    (context/'Dockerfile').write_text('FROM scratch\nCOPY marker /marker\n')
    (context/'marker').write_text('TJS-4398 correction, isolated nft check\n')
    build=run(['docker','build','--network','none','-t',image,str(context)])
    (OUT/'nft-image-build.json').write_text(json.dumps(build,indent=2)+'\n')
    assert build['exit']==0,build
    image_id=subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',image],text=True).strip()
    base=['docker','run','--rm','--network','none','--cap-drop','ALL','--cap-add','NET_ADMIN',
          '--cpus','0.5','--memory','128m','--pids-limit','64']
    for src in ('/usr','/lib','/lib64'):
        base+=['--mount',f'type=bind,src={src},dst={src},readonly']
    base+=['--mount',f'type=bind,src={OUT},dst=/work,readonly',image]
    try:
        for variant in ('private','operator-tls'):
            for maximum in (False,True):
                name=variant+('-max' if maximum else '')+'.nft'
                text=o.port_rule(variant).replace('<interface>','eth0').replace('<bind-ip>','192.0.2.10').replace('<rate>','120' if maximum else '30').replace('<burst>','60' if maximum else '10')+'\n'
                path=OUT/name;path.write_text(text)
                row=run(base+['/usr/sbin/nft','-c','-f','/work/'+name]);row.update(rule=name,sha256=sha(path))
                checks.append(row);assert row['exit']==0,row
        path=OUT/'negative-control.nft';path.write_text((OUT/'private.nft').read_text().replace('size 65535','size banana'))
        neg=run(base+['/usr/sbin/nft','-c','-f','/work/negative-control.nft']);neg['rule']='negative-control.nft';checks.append(neg);assert neg['exit']!=0,neg
        version=run(base+['/usr/sbin/nft','--version'])
        (OUT/'nft-checks.json').write_text(json.dumps(dict(image=image_id,checks=checks,version=version,kernel=subprocess.check_output(['uname','-r'],text=True).strip(),mounts='host tools and libraries read-only; rules and probes read-only; no host network or rules'),indent=2)+'\n')
        func=OUT/'func';func.mkdir(exist_ok=True)
        for name,maximum,size,backstop in [('default',False,65535,True),('maximum',True,65535,True),('full-set',False,4,True),('unbounded-control',False,4,False),('unconditional-control',False,65535,True)]:
            text=o.port_rule().replace('<interface>','lo').replace('<bind-ip>','127.0.0.1').replace('<rate>','120' if maximum else '30').replace('<burst>','60' if maximum else '10').replace('        iifname "lo" accept;\n','').replace('size 65535',f'size {size}')
            if not backstop:text='\n'.join(line for line in text.splitlines() if 'ip saddr !=' not in line)+'\n'
            if name=='unconditional-control':text=text.replace('ip saddr != @seed_sources ','')
            (func/(name+'.nft')).write_text(text)
        row=run(base+['/usr/bin/python3','-B','/work/functional-check.py'])
        (OUT/'functional-check-output.json').write_text(json.dumps(row,indent=2)+'\n')
        assert row['exit']==0,row
        print(json.dumps({'nft_checks':len(checks),'functional':json.loads(row['stdout'])}))
    finally:
        cleanup=run(['docker','image','rm',image]);(OUT/'nft-cleanup.json').write_text(json.dumps(cleanup,indent=2)+'\n');assert cleanup['exit']==0,cleanup
