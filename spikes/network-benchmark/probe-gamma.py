#!/usr/bin/env python3
"""Literal pinned gamma picker + crypto RNG probe; not full wallet integration."""
import hashlib,json,math,re,subprocess,sys
from pathlib import Path

src,out=map(Path,sys.argv[1:])
lock=Path(__file__).resolve().parents[1]/'selected-issuance/gamma-fixture-source-lock.json'
inputs=json.loads(lock.read_text())['sha256']
for name,h in inputs.items():
 assert hashlib.sha256((src/name).read_bytes()).hexdigest()==h,name
out.mkdir(parents=True,exist_ok=False)
h=(src/'src/wallet/wallet2.h').read_text(); cpp=(src/'src/wallet/wallet2.cpp').read_text(); crypto=(src/'src/crypto/crypto.h').read_text()
cls=h[h.index('  class gamma_picker\n'):h.index('  class wallet_keys_unlocker\n')]
methods=cpp[cpp.index('gamma_picker::gamma_picker('):cpp.index('boost::mutex wallet_keys_unlocker::lockers_lock;')]
random=crypto[crypto.index('  template<typename T>\n  T rand()'):crypto.index('  /* Generate a new key pair')]
macros='\n'.join(re.search(r'^#define '+name+r' .+$',cpp,re.M)[0] for name in ['GAMMA_SHAPE','GAMMA_SCALE','DEFAULT_UNLOCK_TIME','RECENT_SPEND_WINDOW'])
header='''#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <type_traits>
#include <vector>
extern "C" {
#include "random.h"
}
#define CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE 10
#define THROW_WALLET_EXCEPTION_IF(c, ...) do { if(c) throw std::runtime_error("picker invariant"); } while(0)
#define MTRACE(x) do {} while(0)
namespace crypto {
// Probe is serial: preserve production random.c/Keccak and native random templates.
void generate_random_bytes_thread_safe(size_t n, uint8_t *p) { generate_random_bytes_not_thread_safe(n,p); }
'''+random+'}\n'
main=r'''
int main(int argc, char **argv) {
  size_t blocks=std::stoull(argv[1]), samples=std::stoull(argv[2]), repeats=std::stoull(argv[3]);
  double conversion=std::stod(argv[4]);
  std::vector<uint64_t> offsets(blocks);
  for(size_t i=0;i<blocks;++i) offsets[i]=i+1;
  for(size_t trial=0;trial<repeats;++trial) {
    tools::gamma_picker picker(offsets);
    std::vector<double> ages; ages.reserve(samples);
    size_t rejected=0;
    while(ages.size()<samples) {
      uint64_t o=picker.pick();
      if(o>=blocks) { if(++rejected>samples) return 3; continue; }
      double age=(blocks-1-o)*conversion;
      if(age<0 || age>blocks*conversion) return 4;
      ages.push_back(age);
    }
    std::sort(ages.begin(),ages.end());
    std::cout << (ages[(samples-1)/2]+ages[samples/2])/2 << "\n";
  }
}
'''
incs=['-I'+str(src/'contrib/epee/include'),'-I'+str(src/'src/crypto')]
for file in ('random.c','hash.c','keccak.c'):
 subprocess.run(['cc','-O2',*incs,'-c',str(src/'src/crypto'/file),'-o',str(out/(file+'.o'))],check=True)
for target in (90,120):
 file=out/f'gamma-{target}.cpp'
 file.write_text(header+f'\n#define DIFFICULTY_TARGET_V2 {target}\n'+macros+'\nnamespace tools {\n'+cls+methods+'}\n'+main)
 subprocess.run(['g++','-std=c++14','-O2',*incs,str(file),*(str(out/(f+'.o')) for f in ('random.c','hash.c','keccak.c')),'-o',str(out/f'gamma-{target}')],check=True)

def cdf(t):
 x=math.log(t)*1.61; a=19.28; term=1/a; total=term
 for n in range(1,300):
  term*=x/(a+n); total+=term
  if term<total*1e-15: break
 return total*math.exp(a*math.log(x)-x-math.lgamma(a))

rows=[]
for name,target,blocks,samples,repeats,conversion in [
 ('old-conversion-negative',90,300000,100000,4,120),
 ('conversion-only-control',90,300000,100000,16,90),
 ('equal-history-90',90,400000,1000000,16,90),
 ('equal-history-120',120,300000,1000000,16,120)]:
 medians=list(map(float,subprocess.check_output([str(out/f'gamma-{target}'),str(blocks),str(samples),str(repeats),str(conversion)],text=True,timeout=240).splitlines()))
 lo,hi=1000.,1000000.
 for _ in range(70):
  m=(lo+hi)/2
  if cdf(m)<.5*cdf((blocks+1)*target):lo=m
  else:hi=m
 row=dict(name=name,target=target,blocks=blocks,samples=samples,medians_seconds=medians,
          outside_original_bounds=sum(not 1.3*86400<=m<=1.4*86400 for m in medians),conditional_median_seconds=m)
 rows.append(row)
 print(json.dumps(row),flush=True)
 if name.startswith('equal-history'): assert row['outside_original_bounds']==0,row
 if name=='old-conversion-negative': assert row['outside_original_bounds']==repeats,row
(out/'summary.json').write_text(json.dumps({'scope':'literal picker and real crypto RNG; serial adapter; not native wallet suite','source_sha256':inputs,'trials':rows},indent=2)+'\n')
