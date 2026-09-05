#!/usr/bin/env python3
"""Difficulty-adjustment simulator for the Meownero (Candidate M) launch window.

Ports Monero v0.18.5.1 `next_difficulty` exactly (src/cryptonote_basic/difficulty.cpp:203):
window 720, lag 15 (the newest 15 of the last 735 blocks are ignored), cut 60 on each side of the
sorted timestamps, target 120 s, result = ceil(total_work * target / time_span). Timestamp rule
ported from blockchain.cpp: a block's timestamp must exceed the median of the previous 60 and be at
most FTL (7200 s upstream) in the future of the validator's clock.

Scenarios (feasibility only, never security):
  A  launch: hashrate H from t=0 onto a chain with difficulty 1 and no floor -> blocks insta-mined
  B  launch with a difficulty floor F
  C  whiplash: hashrate x10 for 2 h then back
  D  timestamp attack: attacker with share s of hashrate pushes timestamps to the FTL bound
Blocks are drawn with exponential inter-arrival times (time = difficulty / hashrate * Exp(1)).
"""
import random, statistics, sys

WINDOW, LAG, CUT, TARGET = 720, 15, 60, 120
BLOCKS_COUNT = WINDOW + LAG
MTP_WINDOW = 60


def next_difficulty(timestamps, cum_diffs, target=TARGET):
    ts = list(timestamps); cd = list(cum_diffs)
    if len(ts) > WINDOW:
        ts = ts[:WINDOW]; cd = cd[:WINDOW]
    n = len(ts)
    if n <= 1:
        return 1
    ts.sort()
    if n <= WINDOW - 2 * CUT:
        cb, ce = 0, n
    else:
        cb = (n - (WINDOW - 2 * CUT) + 1) // 2
        ce = cb + (WINDOW - 2 * CUT)
    span = max(1, ts[ce - 1] - ts[cb])
    work = cd[ce - 1] - cd[cb]
    return (work * target + span - 1) // span


class Chain:
    def __init__(self, floor=1, ftl=7200, seed=1):
        self.ts, self.cd, self.floor, self.ftl = [0], [1], floor, ftl
        self.rng = random.Random(seed)

    def difficulty(self):
        h = len(self.ts)
        off = max(0, h - BLOCKS_COUNT)
        d = next_difficulty(self.ts[off:], self.cd[off:])
        return max(d, self.floor)

    def min_timestamp(self):
        last = self.ts[-MTP_WINDOW:]
        return int(statistics.median(last)) + 1 if len(last) >= MTP_WINDOW else 0

    def mine(self, hashrate, now, ts_override=None):
        d = self.difficulty()
        dt = d / hashrate * self.rng.expovariate(1.0)
        t = now + dt
        stamp = int(t) if ts_override is None else ts_override(int(t), self)
        stamp = max(stamp, self.min_timestamp())
        stamp = min(stamp, int(t) + self.ftl)
        self.ts.append(stamp); self.cd.append(self.cd[-1] + d)
        return t, d


def run_launch(hashrate, floor, hours=24, seed=1):
    c = Chain(floor=floor, seed=seed); now = 0.0; per_hour = []
    while now < hours * 3600:
        now, d = c.mine(hashrate, now)
        h = int(now // 3600)
        while len(per_hour) <= h: per_hour.append(0)
        per_hour[h] += 1
    return per_hour, c


def run_ramp(h0, h1, switch_hour, floor, hours=12, seed=1):
    """Launch ramp: hashrate h0 until `switch_hour`, then h1 (e.g. a pool joins)."""
    c = Chain(floor=floor, seed=seed); now = 0.0; per_hour = []
    while now < hours * 3600:
        hr = h0 if now < switch_hour * 3600 else h1
        now, d = c.mine(hr, now)
        h = int(now // 3600)
        while len(per_hour) <= h: per_hour.append(0)
        per_hour[h] += 1
    return per_hour


def run_whiplash(hashrate, floor, seed=1):
    c = Chain(floor=floor, seed=seed); now = 0.0
    # 6 h warm-up, 2 h at 10x, 6 h back at 1x
    phases = [(6, 1.0), (2, 10.0), (6, 1.0)]
    out = []
    for hours, mult in phases:
        end = now + hours * 3600; n = 0
        while now < end:
            now, d = c.mine(hashrate * mult, now); n += 1
        out.append((mult, hours, n, round(n / hours, 1), c.difficulty()))
    return out


def run_timestamp_attack(hashrate, share, ftl, floor, seed=1):
    """Attacker mines `share` of blocks and stamps them at now+ftl (max allowed), honest miners
    stamp real time. Measures difficulty drop relative to the honest baseline."""
    c = Chain(floor=floor, ftl=ftl, seed=seed); now = 0.0
    for _ in range(1500):
        now, _ = c.mine(hashrate, now)
    base = c.difficulty()
    rng = random.Random(seed + 7)
    def override(t, chain):
        return t + ftl if rng.random() < share else t
    for _ in range(800):
        now, _ = c.mine(hashrate, now, ts_override=override)
    return base, c.difficulty()


if __name__ == "__main__":
    H = float(sys.argv[1]) if len(sys.argv) > 1 else 5e6  # hashes/s at launch (assumption; 5 MH/s ~ a few hundred CPUs)
    print(f"# Monero DAA (720/15/60, 120 s) on a fresh chain; launch hashrate assumption H = {H:.3g} H/s\n")
    print("## A/B: blocks per hour in the first day (target 30/h)")
    for floor in (1, int(H * TARGET / 4), int(H * TARGET)):
        ph, c = run_launch(H, floor, hours=24)
        print(f"floor={floor:>12,d} ({'none' if floor == 1 else f'{floor / (H * TARGET):.2f} x steady-state'}): "
              f"h0={ph[0]:>6,d}  h1={ph[1]:>5,d}  h2={ph[2]:>4,d}  h3={ph[3]:>3,d}  h6={ph[6]:>3,d}  h12={ph[12]:>3,d}  h23={ph[23]:>3,d}  "
              f"total 24h={sum(ph):>7,d} (target 720)")
    print("\n## E: launch ramp — 10 kH/s (a handful of CPUs) for 1 h, then H arrives (x500); blocks per hour, target 30")
    for floor in (1, int(H * TARGET / 4), int(H * TARGET)):
        ph = run_ramp(1e4, H, 1, floor, hours=12)
        print(f"floor={floor:>12,d}: " + " ".join(f"h{i}={n:>4d}" for i, n in enumerate(ph[:12])) + f"  total={sum(ph)} (target 360)")
    print("\n## C: whiplash x10 for 2 h (blocks per hour; target 30)")
    for floor in (1, int(H * TARGET / 4)):
        rows = run_whiplash(H, floor)
        print(f"floor={floor:>12,d}: " + "  ".join(f"[x{m:g} {h}h: {n} blk = {r}/h]" for m, h, n, r, _ in rows))
    print("\n## D: timestamp attack (attacker share s stamps at now+FTL); difficulty after vs before")
    for ftl in (7200, 1200):
        for share in (0.2, 0.34, 0.5):
            b, a = run_timestamp_attack(H, share, ftl, 1)
            print(f"FTL={ftl:>5d}s share={share:.2f}: difficulty {b:,d} -> {a:,d} ({a / b:.2f}x)")
