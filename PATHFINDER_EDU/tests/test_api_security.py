"""Security regression tests for admin-only API credential vault and tracking.

Runs an isolated local server using a temporary directory; no internet needed.
"""
import http.cookiejar
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class HttpClient:
    def __init__(self, origin):
        self.origin = origin
        self.csrf = ''
        self.open = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self, path, data=None):
        headers = {'Accept': 'application/json'}
        if data is not None:
            headers.update({'Content-Type': 'application/json', 'X-CSRF': self.csrf})
        req=urllib.request.Request(self.origin+path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            with self.open.open(req, timeout=9) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
    def get(self, path):
        code, body = self.call(path)
        return code, json.loads(body)
    def post(self, path, data):
        code, body = self.call(path, data)
        return code, json.loads(body)
    def session(self):
        self.csrf = self.get('/api/session')[1].get('csrf', '')

class TestSecretsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='pathfinder_api_security_')
        cls.site = Path(cls.temp.name) / 'site'
        shutil.copytree(ROOT, cls.site, ignore=shutil.ignore_patterns('*.sqlite3', '*.sqlite3-wal', '*.sqlite3-shm', '__pycache__', '.api_credentials.dpapi', '*.tmp'))
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); cls.port=s.getsockname()[1]
        cls.base=f'http://127.0.0.1:{cls.port}'
        env={**os.environ,'PF_PORT':str(cls.port)}
        for k in ('OPENAI_API_KEY','NEIS_API_KEY','DATA_GO_KR_API_KEY'):
            env.pop(k,None)
        cls.p=subprocess.Popen([sys.executable,'server.py'],cwd=cls.site,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(150):
            if cls.p.poll() is not None:raise RuntimeError('test server exited unexpectedly')
            try:
                with urllib.request.urlopen(cls.base+'/api/public',timeout=1) as r:
                    if r.status==200:break
            except Exception:time.sleep(0.06)
        else:raise RuntimeError('test server timeout')
    @classmethod
    def tearDownClass(cls):
        cls.p.terminate()
        try:cls.p.wait(timeout=3)
        except subprocess.TimeoutExpired:cls.p.kill()
        cls.temp.cleanup()

    def test_config_guard_tracking_and_secret_mask(self):
        anon=HttpClient(self.base)
        self.assertEqual(anon.get('/api/admin/api-config')[0],403)
        self.assertEqual(anon.get('/api/admin/api-usage')[0],403)
        # Local test admin requires password change before storing secrets.
        adm=HttpClient(self.base)
        self.assertEqual(adm.post('/api/login',{'username':'brans911','password':'brans911!','role':'admin'})[0],200)
        adm.session()
        code, r=adm.post('/api/admin/api-config',{'currentPassword':'brans911!','keys':{'openai':'sk-proj-NOT_A_REAL_KEY'}})
        self.assertEqual(code,403)
        self.assertIn('비밀번호',r['error'])
        code, r=adm.post('/api/change-password',{'old':'brans911!','new':'LocalSecure_951!_changed'})
        self.assertEqual(code,200)
        # Incorrect admin password cannot register secrets.
        self.assertEqual(adm.post('/api/admin/api-config',{'currentPassword':'badpass','keys':{'openai':'sk-proj-NOT_A_REAL_KEY'}})[0],403)
        code, r=adm.post('/api/admin/api-config',{'currentPassword':'LocalSecure_951!_changed',
                  'keys':{'openai':'sk-proj-NOT_A_REAL_KEY','neis':'fake_neis_0123456789'},'model':'gpt-4.1-mini'})
        self.assertEqual(code,200,r)
        self.assertTrue(r['status']['openai']['configured'])
        self.assertNotIn('sk-proj-NOT_A_REAL_KEY',json.dumps(r))
        self.assertNotIn('fake_neis_0123456789',json.dumps(r))
        code,conf=adm.get('/api/admin/api-config')
        self.assertEqual(code,200)
        self.assertTrue(conf['keys']['neis']['configured'])
        self.assertNotIn('NOT_A_REAL',json.dumps(conf))
        code,public=adm.get('/api/v2/status')
        self.assertEqual(code,200)
        self.assertTrue(public['aiAvailable'])
        self.assertNotIn('openaiConfigured',public)
        self.assertNotIn('model',public)
        self.assertNotIn('NOT_A_REAL',json.dumps(public))
        code, usage=adm.get('/api/admin/api-usage')
        self.assertEqual(code,200)
        self.assertEqual(usage['daily'],[])
        self.assertEqual(anon.get('/api/admin/api-usage')[0],403)
        # No outside API call; local stored key deleted by admin.
        code, deleted=adm.post('/api/admin/api-config',{'currentPassword':'LocalSecure_951!_changed','delete':['openai','neis']})
        self.assertEqual(code,200,deleted)
        self.assertFalse(deleted['status']['openai']['configured'])
        self.assertFalse(deleted['status']['neis']['configured'])
        # Private encrypted credential file is never served by HTTP.
        self.assertEqual(anon.get('/data/.api_credentials.dpapi')[0],404)

if __name__=='__main__':unittest.main()
