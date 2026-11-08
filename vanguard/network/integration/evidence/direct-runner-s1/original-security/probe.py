"""Disposable Security probe for TJS-2504 35240d74 run-profile.py controller writes.
Models a container-planted symlink in the two container-writable bind mounts
(staging -> /out, public -> /public). No Docker, lock, network or native work."""
import importlib.util, json, os, sys, tempfile, stat
from pathlib import Path
NET = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(NET))
import network as n, profile_contract as c
spec = importlib.util.spec_from_file_location('rp', NET/'run-profile.py')
rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
src = (NET/'run-profile.py').read_text().splitlines()
assert src[465].strip() == "(args.out/'staging/BUILD_COMPLETE').write_text('runtime\\n')", src[465]
assert src[555].strip() == "for filename,data in rows.items(): n.write_json(args.out/'public'/filename,data)", src[555]
out = {}
scratch = Path(tempfile.mkdtemp(prefix='sec-probe-', dir='/tmp/sec-61768eac'))
root = scratch/'attempt'; (root/'staging').mkdir(parents=True); (root/'public').mkdir()
outside = scratch/'outside'; outside.mkdir()
# (a) build phase plants staging/BUILD_COMPLETE -> host file outside the owned root
victim_a = outside/'victim-a'; victim_a.write_text('ORIGINAL\n')
os.symlink(victim_a, root/'staging/BUILD_COMPLETE')
(root/'staging/BUILD_COMPLETE').write_text('runtime\n')            # line 466 expression
out['a_victim_after'] = victim_a.read_text()
# (b) runtime plants an undeletable dir plus symlinks under /public
pub = root/'public'
locked = pub/'aaa'; locked.mkdir(); (locked/'x').write_text('x'); os.chmod(locked, 0o500)
victims = {}
for name in list(c.REQUIRED) + ['receipt.json']:
    v = outside/('victim-'+name); v.write_text('ORIGINAL\n'); victims[name] = v
    os.symlink(v, pub/name)
order = [p.name for p in os.scandir(pub)]
rows = c.empty_rows()
try:
    rp.collect_public(root, rows); out['b_collect'] = 'returned'
except Exception as e:
    out['b_collect'] = 'raised ' + type(e).__name__
out['b_scandir_order'] = order
out['b_left_after_collect'] = sorted((p.name, p.is_symlink()) for p in pub.iterdir())
for filename, data in rows.items(): n.write_json(pub/filename, data)   # line 556
n.write_json(pub/'receipt.json', dict(result='FAIL'))                  # line 557
out['b_victims_clobbered'] = sorted(k for k, v in victims.items() if v.read_text() != 'ORIGINAL\n')
# owned cleanup
os.chmod(locked, 0o700)
import shutil; shutil.rmtree(scratch)
out['scratch_removed'] = not scratch.exists()
out['python'] = sys.version.split()[0]
print(json.dumps(out, indent=1))
