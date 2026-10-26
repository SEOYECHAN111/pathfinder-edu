"""Input validation: rejects malformed student records before persistence."""
import re

ALLOWED_TERMS={'1-1','1-2','2-1','2-2','3-1','3-2'}
ALLOWED_KINDS={'score','achievement','grade'}
ACHIEVEMENTS={'A','B','C','D','E','P'}
CATEGORIES={'세특','창의적 체험활동','동아리','진로활동','자율활동','독서','수상·탐구','기타'}

def validate_profile(p):
 if not isinstance(p,dict):raise ValueError('학생정보는 객체 형식이어야 합니다.')
 if len(str(p))>180000:raise ValueError('학생 기록 총량이 너무 큽니다.')
 records=p.get('middleAssessments') or {}
 if not isinstance(records,dict) or len(records)>120:raise ValueError('중학교 성적 기록 형식을 확인하세요.')
 for name,rec in records.items():
  if not isinstance(name,str) or not any(name.startswith(t+'|') for t in ALLOWED_TERMS) or len(name)>70:raise ValueError('중학교 학기·과목명을 확인하세요.')
  if not isinstance(rec,dict) or rec.get('kind') not in ALLOWED_KINDS:raise ValueError('성적 구분은 원점수·성취도·등급 중 선택하세요.')
  value=str(rec.get('value','')).strip()
  if not value:continue
  kind=rec['kind']
  if kind=='score':
   try:n=float(value)
   except ValueError:raise ValueError('원점수는 0~100 숫자로 입력하세요.')
   if not 0<=n<=100:raise ValueError('원점수는 0~100 범위입니다.')
  elif kind=='achievement':
   if value not in ACHIEVEMENTS:raise ValueError('성취도는 A~E 또는 P로 입력하세요.')
  elif not re.fullmatch(r'[1-9]',value):raise ValueError('등급은 1~9 중 하나여야 합니다.')
 high=p.get('highGrades') or []
 if not isinstance(high,list) or len(high)>100:raise ValueError('고교 과목 기록이 100개를 넘었습니다.')
 for row in high:
  if not isinstance(row,dict):raise ValueError('고교 성적표 형식이 아닙니다.')
  grade=str(row.get('grade','')).strip();ach=str(row.get('achievement','')).strip()
  if grade and not re.fullmatch(r'[1-9]',grade):raise ValueError('고교 석차등급은 1~9 중 하나입니다.')
  if ach and ach not in ACHIEVEMENTS:raise ValueError('성취도는 A~E 또는 P로 입력하세요.')
  credits=str(row.get('credits','')).strip()
  if credits:
   try:n=float(credits)
   except ValueError:raise ValueError('과목 학점·단위는 숫자로 입력하세요.')
   if not 0<n<=30:raise ValueError('과목 학점·단위는 0초과 30이하여야 합니다.')
  if any(len(str(row.get(key,'')))>100 for key in ('subject','semester')):raise ValueError('과목·학기 이름이 너무 깁니다.')
 se=p.get('studentRecords') or []
 if not isinstance(se,list) or len(se)>35:raise ValueError('세특·활동 기록은 최대 35개입니다.')
 for record in se:
  if not isinstance(record,dict) or record.get('category') not in CATEGORIES:raise ValueError('생기부 기록 종류를 확인하세요.')
  for key,max_len in [('subject',80),('semester',30),('content',2500),('evidence',800)]:
   if not isinstance(record.get(key,''),str) or len(record.get(key,''))>max_len:raise ValueError(f'생기부 {key} 분량을 줄이세요.')
  if any(ord(x)<32 and x not in '\n\t\r' for x in record.get('content','')):raise ValueError('생기부 기록에 허용되지 않는 문자가 있습니다.')
 return p
