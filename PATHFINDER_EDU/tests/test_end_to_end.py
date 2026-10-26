import http.cookiejar,json,os,sys,unittest,urllib.request,urllib.error,random
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from engine import assess,evaluate_survey,review_plan
from question_bank import QUESTIONS
HOST=os.environ.get('PF_TEST_URL','http://127.0.0.1:8879')
class Client:
 def __init__(self):self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar));self.csrf=''
 def call(self,url,data=None):
  hd={'Accept':'application/json'}
  if data is not None:hd.update({'Content-Type':'application/json','X-CSRF':self.csrf})
  req=urllib.request.Request(HOST+url,data=json.dumps(data).encode() if data is not None else None,headers=hd)
  try:
   with self.opener.open(req,timeout=8) as r:
    ct=r.headers.get('Content-Type','')
    return r.status,json.loads(r.read()) if 'json' in ct else r.read()
  except urllib.error.HTTPError as e:
   return e.code,json.loads(e.read())
 def session(self):
  r=self.call('/api/session')[1];self.csrf=r.get('csrf','');return r
class Logic(unittest.TestCase):
 def test_question_bank_168(self):self.assertEqual(len(QUESTIONS),168)
 def test_no_iq(self):self.assertIn('IQ',evaluate_survey({'r-0':2})['reasoning']['disclaimer'])
 def test_general_without_survey(self):self.assertEqual(assess({'mode':'고입','schoolTrack':'일반고'}, {},[])['recommendations'][0]['name'],'일반고')
 def test_no_invented_school(self):self.assertEqual(assess({'mode':'고입'}, {},[])['schools'],[])
 def test_no_advanced_regular(self):self.assertTrue(all('고급 ' not in c for c in assess({'mode':'고입','schoolTrack':'일반고'}, {},[])['courses']))
 def test_plan_missing(self):self.assertTrue(review_plan({'yearly':[]}, {})['issues'])
class Integration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.st=Client();cls.ad=Client();cls.other=Client();cls.name='test'+str(random.randrange(1000000,9999999))
 def test_flow(self):
  st=self.st;admin=self.ad
  code,a=st.call('/api/signup',{'username':self.name,'password':'SampleStrong_1234','name':'테스트 학생','birthYear':2011,'consent':True});self.assertEqual(code,201,a)
  code,a=st.call('/api/login',{'username':self.name,'password':'SampleStrong_1234','role':'student'});self.assertEqual(code,200,a)
  st.session()
  p={'mode':'고입','grade':'중1','region':'광주','schoolTrack':'일반고','middleGrades':{'수학':['95',None,None,None,None,None]},'targetSchool':'가상 목표학교'}
  code,a=st.call('/api/profile/save',{'profile':p});self.assertEqual(code,200,a)
  code,a=st.call('/api/answers/save',{'answers':{'i-0-0':5,'i-0-1':5,'r-0':2}});self.assertEqual(code,200,a)
  code,a=st.call('/api/assessment',{});self.assertEqual(code,200,a);self.assertTrue(a['assessment']['recommendations']);self.assertTrue(a['assessment']['warnings'])
  plan={'major':'물리학과','daily':['개념 복습'],'weekly':['단원 테스트'],'monthly':['오답 추적'],'yearly':['학습기초'],'weeklyHours':10,'measurement':'오답률'}
  code,a=st.call('/api/plan/save',{'plan':plan});self.assertEqual(code,200,a)
  code,a=st.call('/api/plan/review',{'plan':plan});self.assertEqual(code,200,a)
  code,a=st.call('/api/cases/submit',{'message':'진학 조언'});self.assertEqual(code,201,a);cid=a['id']
  code,a=self.other.call('/api/cases/'+str(cid));self.assertEqual(code,403,a)
  code,a=st.call('/api/download/'+str(cid)+'.pdf');self.assertEqual(code,403,a)
  code,a=admin.call('/api/login',{'username':'brans911','password':'brans911!','role':'admin'});self.assertEqual(code,200,a)
  admin.session()
  code,a=admin.call('/api/admin/cases');self.assertEqual(code,200,a);self.assertTrue(any(x['id']==cid for x in a['cases']))
  code,a=admin.call('/api/admin/cases/'+str(cid)+'/publish',{'report':{'summary':'현행 수학의 기초 개념 복습과 단원별 오답 데이터를 바탕으로 성적 상승의 근거를 월별로 기록합니다. 이 계획은 학생의 실행 가능 시간과 시험 일정에 맞춰 조정해야 하며 모집요강 검증은 별도입니다. 연속 수행 여부도 확인합니다.','goals':'자연과학 탐색','school':'일반고 학교별 최신 전형과 지원자격을 해당 연도 공식 모집요강으로 확인해야 합니다.','study':'매주 오답 학습','nextSteps':'1개월 후 재상담'},'note':'추가 확인'});self.assertEqual(code,200,a)
  code,a=st.call('/api/cases/'+str(cid));self.assertEqual(code,200,a);self.assertEqual(a['case']['status'],'published')
  code,pdf=st.call('/api/download/'+str(cid)+'.pdf');self.assertEqual(code,200);self.assertTrue(pdf.startswith(b'%PDF'))
  code,docx=st.call('/api/download/'+str(cid)+'.docx');self.assertEqual(code,200);self.assertTrue(docx.startswith(b'PK'))
  code,a=st.call('/api/admin/students');self.assertEqual(code,403,a)
  code,a=admin.call('/api/admin/students');self.assertEqual(code,200,a)
  # user cleanup
  code,a=st.call('/api/account/delete',{'password':'SampleStrong_1234'});self.assertEqual(code,200,a)
if __name__=='__main__':unittest.main()
