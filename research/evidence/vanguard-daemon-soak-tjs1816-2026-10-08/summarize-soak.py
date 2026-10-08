import json,sys,statistics,math
from pathlib import Path
out=Path(sys.argv[1])
summaries=[]
def stats(values):
 values=sorted(values)
 return {"count":len(values),"min_s":values[0],"median_s":statistics.median(values),"p95_s":values[math.ceil(.95*len(values))-1],"max_s":values[-1]}
for number in ([int(n) for n in sys.argv[2:]] or [1,2]):
 p=out/f"run{number}/public"
 r=json.loads((p/"result.json").read_text())
 raw=[json.loads(x) for x in (p/"rpc.jsonl").read_text().splitlines()]
 samples=[json.loads(x) for x in (p/"samples.jsonl").read_text().splitlines()]
 measured=[s for s in samples if r["measured_start_s"]<=s["monotonic_s"]<=r["measured_end_s"]]
 times=[s["monotonic_s"]-r["measured_start_s"] for s in measured]
 mem=[s["memory_current_bytes"] for s in measured]
 txs=[t for c in r["cohorts"] for t in c["transactions"]]
 delays=[]
 for t in txs:
  origin=0 if t["sender"]=="senderA" else 1
  admission=raw[t["admission_rpc_id"]]
  seen=next(row for row in raw[t["admission_rpc_id"]+1:] if row["path"]=="get_transaction_pool" and row["port"]==19081+100*(1-origin) and any(x["id_hash"]==t["txid"] for x in row["response"].get("transactions",[])))
  delays.append(seen["ended_s"]-admission["ended_s"])
 mean_t,mean_m=statistics.mean(times),statistics.mean(mem)
 slope=sum((t-mean_t)*(m-mean_m) for t,m in zip(times,mem))/sum((t-mean_t)**2 for t in times)
 summaries.append({"trial":number,"result":r["result"],"measured_seconds":r["measured_seconds"],"payments":r["transactions"],"restored_spends":1,"blocks_generated":sum(g["count"] for g in r["generated"]),"rpc_rows":len(raw),"resource_samples":len(samples),"memory_start_bytes":r["start_sample"]["memory_current_bytes"],"memory_end_bytes":r["end_sample"]["memory_current_bytes"],"memory_final_peak_bytes":int((out/f"run{number}/final.memory").read_text()),"memory_current_min_bytes":min(mem),"memory_current_max_bytes":max(mem),"memory_current_fit_bytes_per_minute":slope*60,"measured_cpu_seconds":(r["end_sample"]["cpu"]["usage_usec"]-r["start_sample"]["cpu"]["usage_usec"])/1e6,"construction_rpc":stats([raw[t["construction_rpc_id"]]["ended_s"]-raw[t["construction_rpc_id"]]["began_s"] for t in txs]),"origin_admission_rpc":stats([raw[t["admission_rpc_id"]]["ended_s"]-raw[t["admission_rpc_id"]]["began_s"] for t in txs]),"first_peer_pool_observation_after_admission":stats(delays),"admission_to_confirmed_observation":stats([t["confirmed_s"]-raw[t["admission_rpc_id"]]["ended_s"] for t in txs]),"construction_to_confirmed_observation":stats([t["confirmed_s"]-raw[t["construction_rpc_id"]]["began_s"] for t in txs]),"cohort_durations_seconds":[c["ended_s"]-c["began_s"] for c in r["cohorts"]],"cohort_rates_tps":[c["confirmed_tps"] for c in r["cohorts"]],"child_exits":[{"name":g["name"],"generation":g["generation"],"exit":g["exit"]} for g in r["generations"]],"oom_events":r["shutdown_sample"]["memory_events"],"final_pools":r["final"]["pools"],"final_tips":r["final"]["tips"],"final_cpu_seconds":int(dict(s.split() for s in (out/f"run{number}/final.cpu").read_text().splitlines())["usage_usec"])/1e6,"warmup_seconds":r["warmup_seconds"],"restored_seed_echo_redacted":raw[r["restore"]["restore_rpc_id"]]["response"]["result"].get("redacted_seed_sha256")==r["wallet_seed_sha256"]["recipientA"]})
print(json.dumps({"trials":summaries,"limits":"Idle wall time is excluded from cohort rates; observation delays are RPC sampling bounds. Current-memory fit includes native state and cache, not a leak or production-capacity finding."},indent=2))
