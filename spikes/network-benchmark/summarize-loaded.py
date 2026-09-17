#!/usr/bin/env python3
"""Summarize loaded matrix cells (chain/test-network-loaded.py results) and apply the
predeclared 90-versus-120 decision criteria.

Reads every <root>/**/result.json (+ resources.json), writes <root>/summary.json and
<root>/summary.md. Wall-clock latencies from accelerated cells are also expressed in
emulated chain seconds (wall x accel); those are model conversions, not target-rate
measurements. Only cells with accel == 1 are target-rate evidence. FCMP integration is
unavailable in the pinned source and block capacity is not normalized, so the best
attainable verdict is "defer (no blocker found)", never "go".
"""
import argparse
import json
import math
import statistics
from pathlib import Path

CRITERIA = dict(
    relay_max_fraction_of_target=0.10,   # block relay max under load <= 10% of target interval, every link/seed
    stale_ratio_vs_120=2.0,              # derived stale probability (max-based) <= 2x the 120 value ...
    stale_absolute=0.01,                 # ... and < 1%
)


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, 0
    return statistics.fmean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0), len(xs)


def load_cell(path):
    r = json.loads(path.read_text())
    res_path = path.with_name('resources.json')
    res = json.loads(res_path.read_text()) if res_path.exists() else {}
    exit_path = path.with_name('exit')
    rel = path.parent.relative_to(path.parents[3]) if len(path.parents) > 3 else path.parent
    parts = path.parent.parts
    group = parts[-3] if len(parts) >= 3 else None
    accel = r.get('accel') or 1
    steady = [b for b in (r.get('blocks') or []) if b.get('relay_s') is not None]
    txs = r.get('transactions') or []
    first_conf = [t.get('first_confirmation_s') for t in txs]
    eq_conf = [t.get('equal_work_confirmation_s') for t in txs]
    mem_events = res.get('memory.events', '')
    oom = any(line.split()[0] in ('oom', 'oom_kill', 'max') and line.split()[1] != '0'
              for line in mem_events.splitlines() if len(line.split()) == 2)
    exits = res.get('exit_codes', {})
    daemon_exit_ok = all(v == 0 for k, v in exits.items() if k != 'wallet')
    target = r.get('target_seconds')
    stale = r.get('derived_stale_probability_poisson') or {}
    return dict(
        cell=str(rel), group=group, profile=r.get('profile'), target_seconds=target, link=r.get('link'),
        seed=r.get('seed'), accel=accel, target_rate=bool(r.get('target_rate')), outputs=r.get('outputs_per_tx'),
        duration_s=r.get('duration_s'), result=r.get('result'), wrapper_exit=exit_path.read_text().strip() if exit_path.exists() else None,
        transactions_submitted=r.get('transactions_submitted'), transactions_lost=len(r.get('transactions_lost') or []),
        wallet_errors=len(r.get('wallet_errors') or []),
        steady_blocks=len(steady), txs_per_block_mean=statistics.fmean([b['num_txes'] for b in steady]) if steady else None,
        admitted_weight=r.get('admitted_weight'), offered_bytes=r.get('offered_bytes'),
        admitted_weight_per_wall_s=(r.get('admitted_weight') or 0) / r['duration_s'] if r.get('duration_s') else None,
        admitted_weight_per_chain_s=((r.get('admitted_weight') or 0) / (len(steady) * target)) if steady and target else None,
        block_relay_median_s=r.get('block_relay_median_s'), block_relay_max_s=r.get('block_relay_max_s'),
        tx_relay_median_s=r.get('tx_relay_median_s'), tx_relay_max_s=r.get('tx_relay_max_s'),
        relay_max_fraction_of_target=(r['block_relay_max_s'] / target) if r.get('block_relay_max_s') and target else None,
        relay_max_fraction_of_slot=(r['block_relay_max_s'] / r['emulated_interval_s']) if r.get('block_relay_max_s') and r.get('emulated_interval_s') else None,
        stale_p_median=stale.get('median'), stale_p_max=stale.get('max'),
        competing_slots=len(r.get('competing_slots') or []),
        competing_diverged=sum(1 for c in (r.get('competing_slots') or []) if c.get('diverged')),
        first_confirmation_median_wall_s=med(first_conf), first_confirmation_median_chain_s=(med(first_conf) * accel) if med(first_conf) is not None else None,
        equal_work_k=(txs[0].get('equal_work_k') if txs else None),
        equal_work_confirmation_median_wall_s=med(eq_conf), equal_work_confirmation_median_chain_s=(med(eq_conf) * accel) if med(eq_conf) is not None else None,
        partition=r.get('partition'), memory_peak_bytes=int(res['memory.peak']) if res.get('memory.peak') else None,
        memory_limit_or_oom_event=oom, daemon_exit_ok=daemon_exit_ok, exit_codes=exits,
        capacity_normalization_enforced=r.get('capacity_normalization_enforced'), fcmp_integration=r.get('fcmp_integration'),
        difficulty=r.get('difficulty'))


def evaluate(cells):
    """Apply the predeclared criteria to the accelerated group per link; report target-rate cells separately."""
    by = {}
    for c in cells:
        by.setdefault((c['group'], c['link'], c['target_seconds']), []).append(c)
    checks = []

    def arm(group, link, t):
        return by.get((group, link, t), [])

    groups = sorted({c['group'] for c in cells if c['group']})
    links = sorted({c['link'] for c in cells})
    for g in groups:
        for link in links:
            a90, a120 = arm(g, link, 90), arm(g, link, 120)
            if not a90 or not a120:
                continue
            row = dict(group=g, link=link, n90=len(a90), n120=len(a120))
            row['relay_ok_90'] = all((c['relay_max_fraction_of_target'] or 9) <= CRITERIA['relay_max_fraction_of_target'] for c in a90)
            row['relay_ok_120'] = all((c['relay_max_fraction_of_target'] or 9) <= CRITERIA['relay_max_fraction_of_target'] for c in a120)
            s90 = max((c['stale_p_max'] or 1) for c in a90)
            s120 = max((c['stale_p_max'] or 1) for c in a120)
            row['stale_p_max_90'], row['stale_p_max_120'] = s90, s120
            row['stale_ok_90'] = s90 < CRITERIA['stale_absolute'] and (s120 == 0 or s90 <= CRITERIA['stale_ratio_vs_120'] * s120)
            row['stale_ok_120'] = s120 < CRITERIA['stale_absolute']
            row['converge_ok_90'] = all(c['result'] == 'PASS' and c['transactions_lost'] == 0 and (c['partition'] or {}).get('rejoin_s') is not None for c in a90)
            row['converge_ok_120'] = all(c['result'] == 'PASS' and c['transactions_lost'] == 0 and (c['partition'] or {}).get('rejoin_s') is not None for c in a120)
            row['resources_ok_90'] = all(c['daemon_exit_ok'] and not c['memory_limit_or_oom_event'] for c in a90)
            row['resources_ok_120'] = all(c['daemon_exit_ok'] and not c['memory_limit_or_oom_event'] for c in a120)
            f90, f120 = med([c['first_confirmation_median_chain_s'] for c in a90]), med([c['first_confirmation_median_chain_s'] for c in a120])
            e90, e120 = med([c['equal_work_confirmation_median_chain_s'] for c in a90]), med([c['equal_work_confirmation_median_chain_s'] for c in a120])
            row.update(first_confirmation_chain_s_90=f90, first_confirmation_chain_s_120=f120,
                       equal_work_confirmation_chain_s_90=e90, equal_work_confirmation_chain_s_120=e120)
            row['confirmation_ok_90'] = (f90 is not None and f120 is not None and f90 < f120
                                         and e90 is not None and e120 is not None and e90 <= e120 * 1.05)
            row['pass_90'] = all(row[k] for k in ('relay_ok_90', 'stale_ok_90', 'converge_ok_90', 'resources_ok_90', 'confirmation_ok_90'))
            row['pass_120'] = all(row[k] for k in ('relay_ok_120', 'stale_ok_120', 'converge_ok_120', 'resources_ok_120'))
            checks.append(row)
    if not checks:
        verdict = 'inconclusive: no paired cells'
    elif any(not r['pass_90'] and r['pass_120'] for r in checks):
        verdict = 'no-go for 90 s on these criteria (120 s passed where 90 s failed)'
    elif any(not r['pass_90'] and not r['pass_120'] for r in checks):
        verdict = 'inconclusive: both arms failed a predeclared criterion in the same cell group; inspect harness/host before attributing to the interval'
    else:
        verdict = 'defer (no blocker found): 90 s met every predeclared criterion against 120 s, but actual FCMP integration is unavailable and block capacity is not normalized, so this does not lock 90 s'
    return dict(criteria=CRITERIA, checks=checks, verdict=verdict)


def fmt(x, nd=3):
    if x is None:
        return '—'
    if isinstance(x, float):
        return f'{x:.{nd}f}'
    return str(x)


def markdown(cells, aggregates, ev):
    out = ['# Loaded matrix summary', '',
           f'Cells: {len(cells)}. Verdict: **{ev["verdict"]}**', '',
           'Latencies are wall seconds from RPC generate/submit to receiver observation; `chain_s` columns multiply by `accel` '
           '(a conversion, not a measurement). Only `accel=1` rows are target-rate evidence. Fixed difficulty 1; no FCMP; capacity not normalized.', '',
           '## Cells', '',
           '| cell | result | txs | lost | wallet err | blocks | tx/blk | adm w/wall s | adm w/chain s | blk relay med/max s | tx relay med/max s | relay max/target | stale p max | 1st conf chain s | equal-work k / chain s | rejoin s | peak MiB | OOM |',
           '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for c in sorted(cells, key=lambda c: (c['group'] or '', c['link'] or '', c['seed'] or 0, c['target_seconds'] or 0)):
        p = c['partition'] or {}
        out.append('| ' + ' | '.join([
            c['cell'], str(c['result']), fmt(c['transactions_submitted']), fmt(c['transactions_lost']), fmt(c['wallet_errors']),
            fmt(c['steady_blocks']), fmt(c['txs_per_block_mean'], 1), fmt(c['admitted_weight_per_wall_s'], 0), fmt(c['admitted_weight_per_chain_s'], 0),
            f"{fmt(c['block_relay_median_s'])}/{fmt(c['block_relay_max_s'])}", f"{fmt(c['tx_relay_median_s'])}/{fmt(c['tx_relay_max_s'])}",
            fmt(c['relay_max_fraction_of_target'], 4), fmt(c['stale_p_max'], 5), fmt(c['first_confirmation_median_chain_s'], 1),
            f"{fmt(c['equal_work_k'])} / {fmt(c['equal_work_confirmation_median_chain_s'], 1)}", fmt(p.get('rejoin_s')),
            fmt(c['memory_peak_bytes'] / 2**20 if c['memory_peak_bytes'] else None, 0), 'yes' if c['memory_limit_or_oom_event'] else 'no']) + ' |')
    out += ['', '## Aggregates across seeds (mean ± sd, n)', '',
            '| group | link | target | metric | mean | sd | n | min | max |', '|---|---|---|---|---|---|---|---|---|']
    for a in aggregates:
        out.append(f"| {a['group']} | {a['link']} | {a['target_seconds']} | {a['metric']} | {fmt(a['mean'],4)} | {fmt(a['sd'],4)} | {a['n']} | {fmt(a['min'],4)} | {fmt(a['max'],4)} |")
    out += ['', '## Predeclared criteria', '', '```json', json.dumps(ev['criteria'], indent=2), '```', '',
            '| group | link | relay 90/120 | stale 90/120 (p max) | converge 90/120 | resources 90/120 | confirmation 90 | pass 90 | pass 120 |', '|---|---|---|---|---|---|---|---|---|']
    for r in ev['checks']:
        out.append(f"| {r['group']} | {r['link']} | {r['relay_ok_90']}/{r['relay_ok_120']} | {r['stale_ok_90']}/{r['stale_ok_120']} ({fmt(r['stale_p_max_90'],5)}/{fmt(r['stale_p_max_120'],5)}) | {r['converge_ok_90']}/{r['converge_ok_120']} | {r['resources_ok_90']}/{r['resources_ok_120']} | {r['confirmation_ok_90']} (1st {fmt(r['first_confirmation_chain_s_90'],1)} vs {fmt(r['first_confirmation_chain_s_120'],1)}; eq-work {fmt(r['equal_work_confirmation_chain_s_90'],1)} vs {fmt(r['equal_work_confirmation_chain_s_120'],1)}) | {r['pass_90']} | {r['pass_120']} |")
    out += ['', f"**Verdict:** {ev['verdict']}", '']
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', required=True)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    cells = [load_cell(p) for p in sorted(root.rglob('result.json')) if '.interrupted-' not in str(p)]
    metrics = ['block_relay_median_s', 'block_relay_max_s', 'tx_relay_median_s', 'tx_relay_max_s', 'txs_per_block_mean',
               'admitted_weight_per_wall_s', 'admitted_weight_per_chain_s', 'stale_p_max', 'first_confirmation_median_chain_s',
               'equal_work_confirmation_median_chain_s']
    aggregates = []
    keys = sorted({(c['group'], c['link'], c['target_seconds']) for c in cells}, key=lambda k: (k[0] or '', k[1] or '', k[2] or 0))
    for g, link, t in keys:
        arm = [c for c in cells if (c['group'], c['link'], c['target_seconds']) == (g, link, t)]
        for m in metrics:
            xs = [c[m] for c in arm if c[m] is not None]
            mu, sd, n = mean_sd(xs)
            aggregates.append(dict(group=g, link=link, target_seconds=t, metric=m, mean=mu, sd=sd, n=n,
                                   min=min(xs) if xs else None, max=max(xs) if xs else None))
        rejoin = [(c['partition'] or {}).get('rejoin_s') for c in arm]
        mu, sd, n = mean_sd(rejoin)
        aggregates.append(dict(group=g, link=link, target_seconds=t, metric='partition_rejoin_s', mean=mu, sd=sd, n=n,
                               min=min([x for x in rejoin if x is not None], default=None), max=max([x for x in rejoin if x is not None], default=None)))
    ev = evaluate(cells)
    summary = dict(root=str(root), cells=cells, aggregates=aggregates, evaluation=ev)
    (root / 'summary.json').write_text(json.dumps(summary, indent=2, default=str) + '\n')
    (root / 'summary.md').write_text(markdown(cells, aggregates, ev))
    print(f'{len(cells)} cells -> {root}/summary.json, summary.md')
    print('verdict:', ev['verdict'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
