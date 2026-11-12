"""Inside a --network none container: load each rule file and count admitted loopback connects per source."""
import json, socket, subprocess, sys, threading, time
NFT = '/usr/sbin/nft'
def nft(*a):
    r = subprocess.run([NFT, *a], capture_output=True, text=True)
    assert r.returncode == 0, (a, r.stderr)
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(('127.0.0.1', 48080)); srv.listen(4096)
def acceptor():
    while True:
        c, _ = srv.accept(); c.close()
threading.Thread(target=acceptor, daemon=True).start()
def attempt(src):
    s = socket.socket(); s.bind((src, 0)); s.settimeout(0.05)
    try:
        s.connect(('127.0.0.1', 48080)); return 1
    except (socket.timeout, OSError):
        return 0
    finally:
        s.close()
def burst(src, n):
    return sum(attempt(src) for _ in range(n))
def scenario(name, steps):
    nft('flush', 'ruleset'); nft('-f', f'/work/func/{name}.nft')
    out = []
    for label, sources, n in steps:
        out.append(dict(step=label, admitted={s: burst(s, n) for s in sources}, attempts_each=n))
    return dict(rules=name, steps=out)

# Probe adapted from Security round 1 (attachment 3120ac7d, tools/func_lib.py).
# Rule variants are generated from the candidate, with loopback exposed only
# inside the disposable --network none container. No host rule operation.
attackers = [f'127.0.0.{i}' for i in range(11, 23)]
results = []
for name in ('default', 'unconditional-control'):
    row = scenario(name, [('12 sources', attackers, 15), ('fresh source', ['127.0.0.3'], 5)])
    results.append(row)
    counts = row['steps'][0]['admitted']
    fresh = row['steps'][1]['admitted']['127.0.0.3']
    if name == 'default':
        assert set(counts.values()) == {10}, row
        assert fresh == 5, row
    else:
        assert fresh < 5, row  # This probe detects the rejected shared-budget design.
row = scenario('maximum', [('one source', ['127.0.0.2'], 70), ('fresh source', ['127.0.0.3'], 5)])
assert row['steps'][0]['admitted']['127.0.0.2'] == 60, row
assert row['steps'][1]['admitted']['127.0.0.3'] == 5, row
results.append(row)
for name in ('full-set', 'unbounded-control'):
    start = time.monotonic()
    row = scenario(name, [('fill set', [f'127.0.0.{i}' for i in range(31,35)], 1),
                          ('fifth source', ['127.0.0.35'], 80)])
    elapsed = time.monotonic()-start
    admitted = row['steps'][1]['admitted']['127.0.0.35']
    assert sum(row['steps'][0]['admitted'].values()) == 4, row
    if name == 'full-set':
        assert admitted < 80 and admitted <= 60+2*elapsed+1, row
    else:
        assert admitted == 80, row  # Confirms full-set insertion failure can bypass the meter.
    row['seconds'] = elapsed
    results.append(row)
nft('flush', 'ruleset')
print(json.dumps(results, indent=2))
