import importlib.util,sys,time,json,threading,hashlib,urllib.request
from http.server import BaseHTTPRequestHandler,HTTPServer
sys.path.insert(0,'vanguard/network')
s=importlib.util.spec_from_file_location('driver','vanguard/network/profile-integration.py');d=importlib.util.module_from_spec(s);s.loader.exec_module(d);d.DEADLINE=time.monotonic()+60
seen=[]
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  body=self.rfile.read(int(self.headers['Content-Length']));auth=self.headers.get('Authorization')
  if auth:
   p=urllib.request.parse_keqv_list(urllib.request.parse_http_list(auth[7:]));md=lambda x:hashlib.md5(x.encode()).hexdigest()
   expected=md(':'.join([md('fixture:monero-rpc:dummy'),p['nonce'],p['nc'],p['cnonce'],'auth',md('POST:'+self.path)]))
   ok=p['realm']=='monero-rpc' and p['nonce']=='Zml4dHVyZQ==' and p['uri']==self.path and p['username']=='fixture' and p['response']==expected and p['algorithm']=='MD5' and p['qop']=='auth' and p['nc']=='00000001' and bool(p['cnonce'])
   seen.append(ok)
   if ok:self.send_response(200);self.end_headers();self.wfile.write(b'{"result":{"status":"OK"}}');return
  self.send_response(401)
  for algo in ('MD5','MD5-sess'):self.send_header('WWW-Authenticate',f'Digest qop="auth", algorithm={algo}, realm="monero-rpc", nonce="Zml4dHVyZQ==", stale=false')
  self.end_headers()
srv=HTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=srv.serve_forever);t.start()
try:
 rpc=d.RPC(srv.server_port,'fixture:dummy');assert rpc.call('get_info')=={'status':'OK'}
 assert rpc.call('get_info',login=None,raw=True)[0]==401
 assert rpc.call('get_info',login='fixture:wrong',raw=True)[0]==401
 print(json.dumps({'paired_epee_challenges':'PASS','valid_digest_verified':seen[0],'bad_digest_refused':not any(seen[1:]),'python':sys.version.split()[0],'native':'NOT_RUN'}))
finally:srv.shutdown();t.join();srv.server_close()
