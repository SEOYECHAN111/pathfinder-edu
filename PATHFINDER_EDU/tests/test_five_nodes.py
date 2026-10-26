"""Smoke tests: separate node login, quotas, shared SQLite stand-in for a shared Postgres DB.
Does not claim successful deployment to Render or Supabase.
"""
import tempfile, subprocess,sys,os,time, socket,json,urllib.request,urllib.error,unittest
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def call(base,path,payload=None,cookie=None,csrf=None):
 hdr={'Accept':'application/json'}
 if payload is not None:hdr['Content-Type']='application/json'
 if cookie:hdr['Cookie']=cookie
 if csrf:hdr['X-CSRF']=csrf
 req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=hdr)
 try:
  with urllib.request.urlopen(req,timeout=25) as r:return r.status,json.loads(r.read()),r.headers
 except urllib.error.HTTPError as r:return r.code,json.loads(r.read()),r.headers
class FiveNodes(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.t=tempfile.TemporaryDirectory(prefix='pf_fivenode_');cls.nodes=[]
  for i in (1,2):
   p=port();base='http://127.0.0.1:'+str(p)
   env={**os.environ,'PF_PUBLIC_MODE':'0','PF_REQUIRE_SIGNUP_CODE':'1','PF_NODE_ID':str(i),
   'PF_NODE_COUNT':'5','PF_NODE_CAPACITY':'2','PF_MAX_STUDENTS':'10','PF_SIGNUP_CODE':f'GroupInviteCode_{i}__2026',
   'PF_ADMIN_PASSWORD':'DemoAdminPass1234!','PF_DATA_DIR':cls.t.name,'PORT':str(p)}
   env.pop('DATABASE_URL',None)
   proc=subprocess.Popen([sys.executable,'-u','server.py'],cwd=SITE,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   cls.nodes.append((proc,base))
   for _ in range(300):
    if proc.poll() is not None:raise RuntimeError(proc.stderr.read().decode())
    try:
     if call(base,'/healthz')[0]==200:break
    except Exception:time.sleep(.06)
   else:raise RuntimeError(f'node {i} start timed out')
 @classmethod
 def tearDownClass(cls):
  for proc,_ in cls.nodes:
   proc.terminate();proc.wait(timeout=5)
  cls.t.cleanup()
 def test_group_assignments_limits_and_admin(self):
  one=self.nodes[0][1];two=self.nodes[1][1]
  self.assertEqual(call(one,'/api/public')[1]['nodeId'],1)
  self.assertEqual(call(two,'/api/public')[1]['nodeCount'],5)
  def signup(base,number,key):
   return call(base,'/api/signup',{'username':number,'password':'SecurePass_123456!','name':'시험학생','birthYear':2011,'consent':True,'signupCode':key})
  for i in range(2):
   self.assertEqual(signup(one,'n1_user'+str(i),'GroupInviteCode_1__2026')[0],201)
   self.assertEqual(signup(two,'n2_user'+str(i),'GroupInviteCode_2__2026')[0],201)
  self.assertEqual(signup(one,'n1_third','GroupInviteCode_1__2026')[0],403)
  self.assertEqual(signup(two,'n2_third','GroupInviteCode_2__2026')[0],403)
  self.assertEqual(signup(one,'n1_wrong','GroupInviteCode_2__2026')[0],403)
  self.assertEqual(call(one,'/api/login',{'username':'n2_user0','password':'SecurePass_123456!','role':'student'})[0],403)
  self.assertEqual(call(two,'/api/login',{'username':'n1_user0','password':'SecurePass_123456!','role':'student'})[0],403)
  self.assertEqual(call(one,'/api/login',{'username':'n1_user0','password':'SecurePass_123456!','role':'student'})[0],200)
  self.assertEqual(call(two,'/api/login',{'username':'n2_user0','password':'SecurePass_123456!','role':'student'})[0],200)
  self.assertEqual(call(two,'/api/login',{'username':'brans911','password':'DemoAdminPass1234!','role':'admin'})[0],403)
  st,resp,hdr=call(one,'/api/login',{'username':'brans911','password':'DemoAdminPass1234!','role':'admin'})
  self.assertEqual(st,200)
  cookie=hdr.get('Set-Cookie').split(';')[0]
  students=call(one,'/api/admin/students',cookie=cookie)[1]['students']
  self.assertEqual(sorted(x['group_node'] for x in students),[1,1,2,2])
  csrf=call(one,'/api/session',cookie=cookie)[1]['csrf']
  self.assertEqual(call(one,'/api/admin/assign-node',{'userId':students[0]['id'],'nodeId':3},cookie=cookie,csrf=csrf)[0],200)
  self.assertEqual(call(one,'/api/login',{'username':students[0]['username'],'password':'SecurePass_123456!','role':'student'})[0],403)
if __name__=='__main__':unittest.main()
