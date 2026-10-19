from pathlib import Path
import hashlib,json,tarfile
root=Path('build/tjs1882-abf0b97a-export01');archive=root/'meownero-vanguard-aarch64.tar.gz'
full='b9f06ea78cf7da5c2272b998b48eed5a46dc404b721f32db7f09dc39407de1dc'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==full
parts=root/'parts';parts.mkdir();manifest={'schema':'meownero-numbered-archive-parts/1','archive':archive.name,'bytes':archive.stat().st_size,'sha256':full,'part_size_limit':8388608,'review_state':'PENDING_ORIGINAL_REVIEWER','parts':[]}
with archive.open('rb') as f:
 for n in range(1,10):
  data=f.read(8388608);assert data
  p=parts/(archive.name+'.part'+str(n).zfill(3));p.write_bytes(data)
  manifest['parts'].append({'name':p.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 assert not f.read(1)
h=hashlib.sha256();size=0
for row in manifest['parts']:
 data=(parts/row['name']).read_bytes();assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'];h.update(data);size+=len(data)
assert h.hexdigest()==full and size==manifest['bytes']
manifest['reassembly_verification']='PASS_ACTUAL_ORDERED_PART_BYTES_MATCH_FULL_ARCHIVE'
(root/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(root/'PARTS.SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in manifest['parts']))
with tarfile.open(archive) as t:
 m=t.getmember('meownero-vanguard-aarch64/release.json');data=t.extractfile(m).read()
 assert hashlib.sha256(data).hexdigest()=='d0b3c2d7a405d2ede1d07227ab90feb6d142afd6b3b15468af353d8800449d58'
 (root/'release.json').write_bytes(data)
 (root/'TESTER.md').write_bytes(t.extractfile('meownero-vanguard-aarch64/TESTER.md').read())
(root/'REASSEMBLE.md').write_text('''ARM39 Linux aarch64 candidate; independent artifact acceptance pending.\n\nPut all nine numbered parts and PARTS.SHA256SUMS in one fresh directory. Verify every part, concatenate explicitly in numerical order, then verify the whole archive before extracting.\n\n```sh\nsha256sum -c PARTS.SHA256SUMS\ncat meownero-vanguard-aarch64.tar.gz.part001 meownero-vanguard-aarch64.tar.gz.part002 meownero-vanguard-aarch64.tar.gz.part003 meownero-vanguard-aarch64.tar.gz.part004 meownero-vanguard-aarch64.tar.gz.part005 meownero-vanguard-aarch64.tar.gz.part006 meownero-vanguard-aarch64.tar.gz.part007 meownero-vanguard-aarch64.tar.gz.part008 meownero-vanguard-aarch64.tar.gz.part009 > meownero-vanguard-aarch64.tar.gz\nsha256sum -c SHA256SUMS\nmkdir meownero-arm39\ntar -xzf meownero-vanguard-aarch64.tar.gz -C meownero-arm39\ncd meownero-arm39/meownero-vanguard-aarch64\npython3 -B tester.py preflight\n```\n\nOn macOS use `shasum -a 256 -c` in place of `sha256sum -c`. This ELF package executes on Linux ARM64, requiring glibc 2.35+, Python 3.8+ and ARMv8 crypto instructions (AES/PMULL/SHA1/SHA2). It is unsigned. Use the included TESTER.md for a fresh disposable valueless regtest payment/receive/restore/later-spend journey. No shared public network is supplied.\n\nThe immutable in-archive release.json intentionally records its build-time BUILT_UNTESTED status. The separately bound native receipts record later Ubuntu 22.04 and Debian 12 userland execution of these exact bytes; they do not change independent acceptance.\n\nParent owns group delivery after independent acceptance. Each part is at most 8 MiB, fitting the existing WhatsApp document route (50 MiB cap) and Paperclip attachment limit (10 MB). Authenticated board links are reviewer downloads, not a public group route. Parent can use these local export files or authenticated task downloads, then send the nine documents and checksum/instruction files using the existing approved gateway route. No group send occurred in this run.\n''')
evidence=Path('research/evidence/vanguard-native-arm39-tjs1882-2026-10-19')
for name in ('delivery-manifest.json','PARTS.SHA256SUMS','SHA256SUMS','release.json','REASSEMBLE.md'):(evidence/name).write_bytes((root/name).read_bytes())
print(json.dumps({'parts':len(manifest['parts']),'bytes':size,'sha256':h.hexdigest(),'reassembly':'PASS'}))
