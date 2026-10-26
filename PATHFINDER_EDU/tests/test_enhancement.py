from datetime import date,timedelta
from enhancement_core import validate_calendar,longitudinal,reference_schools
from report_pdf import build_pdf
from engine import assess
from pypdf import PdfReader
from io import BytesIO

def test_calendar_add_done_and_overload():
 dt=date.today().isoformat()
 entries=[{'id':'x','title':'오답 풀이','date':dt,'minutes':45,'done':True}, {'id':'y','title':'단어 암기','date':dt,'minutes':80,'done':False}]
 r=validate_calendar(entries,weekly_hours:=2)
 assert r['totalMinutes']==125 and r['completedMinutes']==45 and r['completionRate']==36
 assert not r['ok'] and r['issues']

def test_calendar_graceful_missing():
 r=validate_calendar([],0)
 assert r['completionRate'] is None and r['ok']

def test_longitudinal_no_fabricated_probability():
 p={'mode':'중학생 장기 대입','targetSchool':'서울대학교','middleGrades':{'수학':[90,95]}}
 a=assess(p,{},[])
 l=longitudinal(p,a,{'calendar':[]})
 assert l['probability'] is None and l['dimensions']['계획 실행']['pct'] is None
 assert '개인 합격확률' in l['probabilityReason']

def test_school_2027_specific():
 r=reference_schools('광주','수완')
 assert len(r)==1 and '공립' in r[0]['school_type'] and r[0]['reference_year']==2027
 assert reference_schools('서울')==[]

def test_pdf_korean_chart_long_report():
 r=assess({'mode':'고입','region':'광주','middleGrades':{'수학':[71,73,75,80,85,92]}},{},[])
 r['longitudinal']=longitudinal({'mode':'고입','targetSchool':'수완고등학교'},r,{'calendar':[]})
 r['planSnapshot']={'calendar':[{'id':'a','title':'복습','date':'2026-10-26','minutes':60,'done':True}]}
 pack={'case':{'id':100,'status':'published'},'student':{'display_name':'임시 학생'},'auto':r,'admin':{'summary':'광주 고교 모집요강 확인. '*150}}
 payload=build_pdf(pack)
 assert payload.startswith(b'%PDF-') and len(payload)>15000
 reader=PdfReader(BytesIO(payload)); assert len(reader.pages)>=2
 text=' '.join((pg.extract_text() or '') for pg in reader.pages)
 assert 'PATHFINDER' in text and '진학' in text
