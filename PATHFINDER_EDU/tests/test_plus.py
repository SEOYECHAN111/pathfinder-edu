"""Additional PLUS regression tests; no network or API key needed."""
import os,sys,sqlite3,unittest,json
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ai_suite import CATALOG,school_search,score_school,explain_offline,make_12week_plan,redact,payload_for_ai,init_suite,university_lookup,neis_lookup,call_openai

class TestPlus(unittest.TestCase):
 def test_modes_and_unique(self):
  self.assertGreaterEqual(len(CATALOG),28)
  self.assertEqual(len({x[0] for x in CATALOG}),len(CATALOG))
 def test_bundled_public_file(self):
  fp=Path(__file__).resolve().parents[1]/'data'/'national_schools.csv'
  self.assertTrue(fp.is_file());self.assertGreater(fp.stat().st_size,2_000_000)
 def test_import_school_data(self):
  c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
  n=init_suite(c)
  self.assertEqual(n,12004)
  self.assertEqual(school_search(c,'','', '고등학교')['total'],2402)
  self.assertEqual(school_search(c,'광주과학고','광주')['total'],1)
  self.assertEqual(school_search(c,'전남과학고','광주')['total'],0)
  self.assertEqual(school_search(c,'전남과학고','전남')['total'],1)
  self.assertEqual(init_suite(c),0)
  c.close()
 def test_fit_score_not_admit_probability(self):
  s={'name':'전남과학고등학교','level':'고등학교','region':'전남광주통합특별시교육청','address':'전남광주통합특별시 나주시 금천면 오강길 33','classification':'과학고 의심'}
  r=score_school(s,{'region':'광주','schoolTrack':'과학고','middleGrades':{'수학':[95],'과학':[97]}})
  self.assertTrue(0<=r['score']<=100)
  self.assertIn('합격 확률',r['caution'])
 def test_readiness_no_probability(self):
  a=explain_offline({'middleGrades':{'수학':[94,75],'영어':[70]}},{'calendar':[{'date':'2026-10-27','minutes':60,'done':True}]},{})
  self.assertIsNone(a['admissionProbability'])
  self.assertEqual(a['calendar']['completionRate'],100)
  self.assertIn('수학',a['subjectPriorities'])
 def test_12_weeks(self):
  a=make_12week_plan({'middleGrades':{'영어':[70],'수학':[91]}},{'weeklyHours':8},'2026-10-26')
  self.assertEqual(a['sessionCount'],72)
  self.assertEqual(a['weekCount'],12)
  self.assertEqual(len(set(x['id'] for x in a['calendar'])),72)
  self.assertEqual(a['calendar'][0]['date'],'2026-10-26')
  self.assertTrue(all(x['minutes']>=10 for x in a['calendar']))
  self.assertEqual(len(set(x['date'] for x in a['calendar'])),72)
 def test_minimized_external(self):
  p={'targetSchool':'전남과학고등학교','targetMajor':'물리학과','display_name':'홍길동','birth_year':2012,'email':'test@example.com','middleGrades':{'과학':[72,91]}}
  question='전화 010-1234-5678 내 이메일 test@example.com에게 답줘'
  snap=payload_for_ai(p,{},question,'comprehensive');js=json.dumps(snap,ensure_ascii=False)
  for secret in ('홍길동','test@example.com','010-1234-5678','2012'):
   self.assertNotIn(secret,js)
  self.assertIn('[전화번호 삭제]',js)
 def test_offline_api_requires_key(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
   with self.assertRaisesRegex(RuntimeError,'API 키'):call_openai('comprehensive',{})
  with patch.dict(os.environ,{'DATA_GO_KR_API_KEY':''}):
   with self.assertRaisesRegex(RuntimeError,'DATA_GO_KR'):university_lookup('전남대학교')
  with patch.dict(os.environ,{'NEIS_API_KEY':''}):
   with self.assertRaisesRegex(RuntimeError,'NEIS'):neis_lookup('전남과학고')
 def test_ai_parses_response_and_disables_storage(self):
  fake=MagicMock();fake.__enter__.return_value.read.return_value=json.dumps({'output':[{'content':[{'type':'output_text','text':'테스트 분석'}]}],'usage':{'input_tokens':40,'output_tokens':50}}).encode()
  with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-testing-key','OPENAI_MODEL':'gpt-4.1-mini'}):
   with patch('ai_suite.urllib.request.urlopen',return_value=fake) as mock_open:
    r=call_openai('comprehensive',{'광역지역':'광주'})
    self.assertEqual(r['answer'],'테스트 분석')
    body=json.loads(mock_open.call_args.args[0].data)
    self.assertFalse(body['store']);self.assertIn('max_output_tokens',body)
 def test_no_api_key_leaks_from_ui(self):
  folder=Path(__file__).resolve().parents[1]
  for f in ['index.html','app.js','app_plus.js']:
   s=(folder/f).read_text()
   self.assertNotIn('sk-testing-key',s)

if __name__=='__main__':unittest.main()
