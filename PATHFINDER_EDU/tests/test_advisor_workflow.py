import json,os,socket,subprocess,sys,tempfile,time,unittest,urllib.request,urllib.error
from pathlib import Path
SITE=Path(__file__).resolve().parents[1]
class Client:
 def __init__(self,url):self.url=url;self.cookie='';self.csrf=''
 def call(self,path,body=None):
  hdr={'Accept':'application/json'}
  if self.cookie:hdr['Cookie']=self.cookie
  if body is not None:hdr.update({'Content-Type':'application/json','X-CSRF':self.csrf})
  req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=hdr)
  try:r=urllib.request.urlopen(req,timeout=20)
  except urllib.error.HTTPError as e:r=e
  with r:
   code=r.status;raw=r.read();obj=json.loads(raw) if raw.startswith(b'{') else raw
   if path=='/api/login' and code==200:self.cookie=r.headers['Set-Cookie'].split(';',1)[0]
   if path=='/api/session' and code==200:self.csrf=obj.get('csrf','')
   return code,obj
class AdvisorFlow(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  with socket.socket() as s:s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1]
  cls.url=f'http://127.0.0.1:{cls.port}'
  env={**os.environ,'PORT':str(cls.port),'PF_DATA_DIR':cls.tmp.name}
  cls.proc=subprocess.Popen([sys.executable,'-u','server.py'],cwd=SITE,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(200):
   if cls.proc.poll() is not None:raise RuntimeError('server failed')
   try:
    if Client(cls.url).call('/healthz')[0]==200:break
   except Exception:time.sleep(.07)
  else:raise RuntimeError('server failed to open')
 @classmethod
 def tearDownClass(cls):cls.proc.terminate();cls.proc.wait(timeout=6);cls.tmp.cleanup()
 def test_advisor_opt_in_permissions(self):
  st=Client(self.url)
  self.assertEqual(st.call('/api/signup',{'username':'grade_demo1','password':'Demo_Strong_2026!','name':'학생1','birthYear':2009,'consent':True})[0],201)
  self.assertEqual(st.call('/api/login',{'username':'grade_demo1','password':'Demo_Strong_2026!','role':'student'})[0],200)
  st.call('/api/session')
  profile={'mode':'고입','middleAssessments':{'3-1|과학':{'kind':'achievement','value':'A'}},
           'studentRecords':[{'category':'세특','semester':'중3-1','subject':'과학','content':'비공개원문XYZ','evidence':'자율탐구'}]}
  self.assertEqual(st.call('/api/profile/save',{'profile':profile})[0],200)
  self.assertEqual(st.call('/api/cases/submit',{'message':'상담 자료 검증','includeRecords':False})[0],201)
  code,result=st.call('/api/cases/submit',{'message':'탐구활동 상담을 원합니다','includeRecords':True});self.assertEqual(code,201,result)
  yes_id=result['id']
  other=Client(self.url)
  self.assertEqual(other.call('/api/signup',{'username':'grade_demo2','password':'Demo_Strong_2026!','name':'학생2','birthYear':2008,'consent':True})[0],201)
  self.assertEqual(other.call('/api/login',{'username':'grade_demo2','password':'Demo_Strong_2026!','role':'student'})[0],200)
  other.call('/api/session')
  self.assertEqual(other.call('/api/cases/'+str(yes_id))[0],403)
  self.assertEqual(other.call('/api/admin/cases')[0],403)
  self.assertEqual(other.call('/api/admin/api-config')[0],403)
  self.assertNotIn('model',other.call('/api/v2/status')[1])
  admin=Client(self.url)
  self.assertEqual(admin.call('/api/login',{'username':'brans911','password':'brans911!','role':'admin'})[0],200)
  admin.call('/api/session')
  records=admin.call('/api/admin/cases')[1]['cases'];self.assertEqual(len(records),2)
  rows=[admin.call('/api/cases/'+str(r['id']))[1]['case'] for r in records]
  shared=[json.loads(r['auto_report'])['recordSummary'] for r in rows]
  self.assertEqual(sorted(len(item['schoolRecords']) for item in shared),[0,1])
  self.assertEqual(admin.call('/api/admin/cases/'+str(yes_id)+'/publish',{'report':{'summary':'짧음','school':'x'}})[0],400)
  complete={'summary':'각 과목별 개념, 학습 시간, 시험 변화, 실험 결과를 분리해 기록하고 해당 학교 원문을 확인한 뒤 일정 단위로 평가합니다. 합격확률은 단정하지 않습니다.',
            'school':'모집요강의 학교별 전형, 거주요건, 지역 권역을 공식 입학처에서 확인할 필요가 있습니다.'}
  self.assertEqual(admin.call('/api/admin/cases/'+str(yes_id)+'/publish',{'report':complete})[0],200)
  self.assertEqual(st.call('/api/cases/'+str(yes_id))[1]['case']['status'],'published')
  self.assertEqual(other.call('/api/download/'+str(yes_id)+'.pdf')[0],403)

if __name__=='__main__': unittest.main()
