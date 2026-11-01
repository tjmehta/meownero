"""Probe 2: container chmods the /public mount root itself (no order gaming), and a FIFO at /out/BUILD_COMPLETE."""
import importlib.util, json, os, subprocess, sys, tempfile, shutil
from pathlib import Path
NET = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(NET))
import network as n, profile_contract as c
spec = importlib.util.spec_from_file_location('rp', NET/'run-profile.py')
rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
out = {}
scratch = Path(tempfile.mkdtemp(prefix='sec-probe2-', dir='/tmp/sec-61768eac'))
root = scratch/'attempt'; (root/'staging').mkdir(parents=True); pub = root/'public'; pub.mkdir()
outside = scratch/'outside'; outside.mkdir(); victims = {}
for name in list(c.REQUIRED) + ['receipt.json']:
    v = outside/('victim-'+name); v.write_text('ORIGINAL\n'); victims[name] = v; os.symlink(v, pub/name)
os.chmod(pub, 0o500)                      # container owns the mount root: same uid
rows = c.empty_rows()
try: rp.collect_public(root, rows); out['collect'] = 'returned'
except Exception as e: out['collect'] = 'raised ' + type(e).__name__
out['left_symlinks'] = sorted(p.name for p in pub.iterdir() if p.is_symlink())
for f, d in rows.items(): n.write_json(pub/f, d)
n.write_json(pub/'receipt.json', dict(result='FAIL'))
out['victims_clobbered'] = sorted(k for k, v in victims.items() if v.read_text() != 'ORIGINAL\n')
os.chmod(pub, 0o700)
# FIFO variant at staging/BUILD_COMPLETE: same expression as run-profile.py:466, in a child with a 3 s bound
os.mkfifo(root/'staging/BUILD_COMPLETE')
code = "from pathlib import Path; Path(%r).write_text('runtime\\n')" % str(root/'staging/BUILD_COMPLETE')
try:
    subprocess.run([sys.executable, '-I', '-B', '-c', code], timeout=3); out['fifo'] = 'returned'
except subprocess.TimeoutExpired: out['fifo'] = 'blocked >3s (child killed by timeout)'
shutil.rmtree(scratch); out['scratch_removed'] = not scratch.exists()
print(json.dumps(out, indent=1))
