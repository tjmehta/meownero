from pathlib import Path
import sys,json
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'candidate/vanguard/network'))
import profile_packet as p, profile_executor as e
from test_receiver import bound_plan
from test_executor import InjectedBoundary
plan=bound_plan(); now=[100.0]; backend=InjectedBoundary()
def modeled_wait(operation,args,deadline):
    assert operation=='start_and_wait'
    now[0]=131.0
backend.docker=modeled_wait
result=e.RecordExecutor(plan,backend,clock=lambda:now[0]).execute(
    dict(operation='start_and_wait',record=43,deadline=4300))
properties={name:value for name,kind,value in p.receiver_unit(plan,43,17)['args'][2]}
assert result['result']=='RECORD_RETURNED'
assert properties['RuntimeMaxUSec']==30_000_000
print(json.dumps(dict(result=result,modeled_elapsed_seconds=31,
    generated_runtime_limit_seconds=properties['RuntimeMaxUSec']/1e6,
    actual_systemd_execution='NOT_RUN'),indent=2))
