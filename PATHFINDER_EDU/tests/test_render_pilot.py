"""Offline smoke tests for the opt-in Render pilot, including 20 concurrent read requests.
No external API key or Render account required. Run: python -m unittest tests/test_render_pilot.py
"""
import concurrent.futures
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

SITE = Path(__file__).resolve().parents[1]

def api(base, path, payload=None, cookie=None, csrf=None):
    headers={'Accept':'application/json'}
    if payload is not None:headers['Content-Type']='application/json'
    if cookie:headers['Cookie']=cookie
    if csrf:headers['X-CSRF']=csrf
    req=urllib.request.Request(base+path, data=json.dumps(payload).encode('utf8') if payload is not None else None,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=40) as r:return r.status,json.loads(r.read()),r.headers
    except urllib.error.HTTPError as r:return r.code,json.loads(r.read()),r.headers

class RenderPilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='pf_render_pilot_')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.base='http://127.0.0.1:'+str(cls.port)
        cls.env={**os.environ,'PORT':str(cls.port),'PF_PUBLIC_MODE':'0','PF_REQUIRE_SIGNUP_CODE':'1','PF_DATA_DIR':cls.temp.name,
                 'PF_ADMIN_PASSWORD':'StrongAdminDemoPassword!241','PF_SIGNUP_CODE':'SecurePilotInvite_2026!',
                 'PF_MAX_STUDENTS':'25','PF_AI_CONCURRENCY':'4'}
        cls.process=subprocess.Popen([sys.executable,'-u','server.py'],cwd=SITE,env=cls.env, stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(300):
            if cls.process.poll() is not None:raise RuntimeError('Render pilot failed on launch')
            try:
                if api(cls.base,'/healthz')[0]==200:break
            except Exception:time.sleep(.07)
        else:raise RuntimeError('Render pilot healthcheck timeout')
    @classmethod
    def tearDownClass(cls):
        cls.process.terminate();cls.process.wait(timeout=5);cls.temp.cleanup()
    def test_free_render_fails_closed_without_postgres(self):
        env={**os.environ,'PF_PUBLIC_MODE':'1','PF_ADMIN_PASSWORD':'StrongAdminDemoPassword!241',
             'PF_SIGNUP_CODE':'SecurePilotInvite_2026!'}
        env.pop('DATABASE_URL',None)
        proc=subprocess.run([sys.executable,'-c','import server;server.verify_online_launch()'],cwd=SITE,env=env,capture_output=True,text=True)
        self.assertNotEqual(proc.returncode,0)
        self.assertIn('DATABASE_URL',proc.stderr)
    def test_20_concurrent_school_search(self):
        def request(_):
            return api(self.base,'/api/v2/schools?q=%EA%B3%A0&limit=5')[0] # unauthenticated should deny
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            codes=list(pool.map(request,range(20)))
        self.assertEqual(codes,[403]*20)
        status, result, _=api(self.base,'/healthz')
        self.assertEqual(status,200)
        self.assertTrue(result['databaseReady'])
    def test_20_concurrent_authenticated_student_reads(self):
        members=[]
        for i in range(20):
            name='student_'+str(i)
            status, _, _=api(self.base,'/api/signup',{'username':name,'password':'SecurePass_123456!','name':'시험사용자','birthYear':2011,'consent':True,'signupCode':'SecurePilotInvite_2026!'})
            self.assertEqual(status,201)
            status,response,head=api(self.base,'/api/login',{'username':name,'password':'SecurePass_123456!','role':'student'})
            self.assertEqual(status,200,response)
            members.append(head.get('Set-Cookie').split(';',1)[0])
        def read(cookie):
            return api(self.base,'/api/v2/schools?q=%EA%B3%A0&limit=5',cookie=cookie)[:2]
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            results=list(pool.map(read,members))
        self.assertTrue(all(code==200 for code,_ in results),[(code,x.get('error')) for code,x in results if code!=200])
        self.assertTrue(all(x['total']>0 for _,x in results))

    def test_signup_auth_and_isolation(self):
        self.assertEqual(api(self.base,'/api/signup',{'username':'wrongcode','password':'SecurePass_123456!','name':'가상학생','birthYear':2011,'consent':True,'signupCode':'wrong'})[0],403)
        for name in ['pilot_a','pilot_b']:
            self.assertEqual(api(self.base,'/api/signup',{'username':name,'password':'SecurePass_123456!','name':'가상학생','birthYear':2011,'consent':True,'signupCode':'SecurePilotInvite_2026!'})[0],201)
        users=[]
        for name in ['pilot_a','pilot_b']:
            status,resp,hdr=api(self.base,'/api/login',{'username':name,'password':'SecurePass_123456!','role':'student'})
            self.assertEqual(status,200,resp)
            self.assertIn('HttpOnly',hdr.get('Set-Cookie',''))
            cookie=hdr.get('Set-Cookie').split(';',1)[0]
            status,resp,_=api(self.base,'/api/session',cookie=cookie)
            self.assertEqual(status,200)
            users.append((cookie,resp['csrf']))
        c1,t1=users[0];c2,t2=users[1]
        self.assertEqual(api(self.base,'/api/profile/save',{'profile':{'mode':'고입','targetSchool':'비공개A'}},cookie=c1,csrf=t1)[0],200)
        status,resp,_=api(self.base,'/api/profile',cookie=c2)
        self.assertEqual(status,200)
        self.assertNotIn('비공개A',json.dumps(resp,ensure_ascii=False))
        status,resp,_=api(self.base,'/api/v2/schools?q=%EA%B3%A0&limit=5',cookie=c2)
        self.assertEqual(status,200)
        self.assertGreater(resp['total'],0)
        status,resp,_=api(self.base,'/api/v2/ai',{'mode':'comprehensive','externalConsent':True},cookie=c2,csrf=t2)
        self.assertEqual(status,400) # No OPENAI_API_KEY, must not pretend successful
    def test_admin_security(self):
        st,_,_=api(self.base,'/api/login',{'username':'brans911','password':'brans911!','role':'admin'})
        self.assertEqual(st,403)
        st,resp,h=api(self.base,'/api/login',{'username':'brans911','password':'StrongAdminDemoPassword!241','role':'admin'})
        self.assertEqual(st,200,resp)
        cookie=h.get('Set-Cookie').split(';',1)[0]
        csrf=api(self.base,'/api/session',cookie=cookie)[1]['csrf']
        st,resp,_=api(self.base,'/api/admin/api-config',cookie=cookie)
        self.assertEqual(st,200)
        self.assertIn('Windows:',str(resp['storage'])) if os.name=='nt' else self.assertIn('메모리',str(resp['storage']))
        self.assertEqual(api(self.base,'/api/admin/api-config',{'currentPassword':'StrongAdminDemoPassword!241','keys':{'openai':'sk-test00000000'}},cookie=cookie,csrf=csrf)[0],403)
        self.assertEqual(api(self.base,'/data/pathfinder.sqlite3')[0],404)

if __name__=='__main__':unittest.main()
