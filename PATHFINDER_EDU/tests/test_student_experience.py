"""Security-oriented regression tests for the student-first pilot."""
import os,unittest,sys
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from student_validation import validate_profile
from db_backend import normalize_sql
from ai_suite import payload_for_ai

class StudentExperience(unittest.TestCase):
 def test_achievement_and_scores_are_distinct(self):
  p={'mode':'고입','middleAssessments':{
      '3-1|과학':{'kind':'achievement','value':'A'},
      '3-2|수학':{'kind':'grade','value':'2'},
      '1-1|국어':{'kind':'score','value':'95'}},
     'studentRecords':[{'category':'세특','subject':'과학','semester':'중3-1',
       'content':'별도의 비공개 탐구 세특 원문','evidence':'과학 실험기록'}]}
  self.assertIs(validate_profile(p),p)
  snap=payload_for_ai(p,{},'과학 상담','comprehensive')
  self.assertIn('성취도및등급요약',snap)
  self.assertNotIn('별도의 비공개 탐구 세특 원문',str(snap))
  self.assertNotIn('studentRecords',str(snap))
 def test_rejects_wrong_grades(self):
  for k,v in [('achievement','99'),('grade','10'),('score','101')]:
   with self.subTest(k=k),self.assertRaises(ValueError):
    validate_profile({'middleAssessments':{'1-1|수학':{'kind':k,'value':v}}})
 def test_rejects_overlong_seoteuk(self):
  with self.assertRaises(ValueError):
   validate_profile({'studentRecords':[{'category':'세특','subject':'수학','semester':'중3-2','content':'X'*2501}]})
 def test_postgres_sql_migration(self):
  self.assertEqual(normalize_sql('CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, role TEXT)'), 'CREATE TABLE IF NOT EXISTS users(id BIGSERIAL PRIMARY KEY, role TEXT)')
  query=normalize_sql('INSERT OR IGNORE INTO school_directory VALUES(?,?)')
  self.assertEqual(query,'INSERT INTO school_directory VALUES(%s,%s) ON CONFLICT DO NOTHING')
 def test_student_shell_has_no_api_manager_link(self):
  s=open(os.path.join(os.path.dirname(os.path.dirname(__file__)),'app.js'),encoding='utf-8').read()
  nav=s[s.index('const navStudent='):s.index('const navAdmin=')]
  self.assertNotIn('apiManager',nav)
  self.assertNotIn('apiSetup',nav)
  self.assertIn('studentRecord',nav)

if __name__=='__main__': unittest.main()
