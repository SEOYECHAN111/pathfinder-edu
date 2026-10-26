"""Explainable advisory heuristics. No individual admission probability."""
import json
from collections import defaultdict
from datetime import date
from question_bank import QUESTIONS, ANSWERS
AREAS={
 '탐구·연구':['자연과학','수학','물리학','화학','생명과학','의학·보건(추가 조건 확인)'],
 '기술·제작':['기계공학','항공우주공학','전기전자공학','컴퓨터공학','소프트웨어'],
 '표현·창작':['시각디자인','영상·콘텐츠','문예창작','음악·미술'],
 '소통·도움':['교육학','사회복지학','간호학','상담·심리'],
 '기획·도전':['경영학','경제학','행정학','국제통상'],
 '정리·관리':['회계·세무','통계학','행정학','데이터관리'],
}
SCHOOL_TYPES=[('일반고','폭넓은 대학·직업 진로 탐색'),('자율형 공립고','지역 연계·학교별 특화 교육과정 확인'),('자율형 사립고','자기주도 학습환경·학비·선발조건 검토'),('과학중점학교 운영 일반고','학교별 과학중점 운영 여부 확인'),('과학고','수학·과학의 지속적 성취 및 탐구근거 필요'),('영재학교','별도 영재학교 입학전형·심층탐구 준비 필요'),('외국어고','언어·문화 관심과 해당 전형조건 확인'),('국제고','언어·국제사회 관심과 전형 확인'),('예술고','실기·포트폴리오 등 별도 검토'),('체육고','종목·실기·선발요건 확인'),('특성화고','직업교육·계열별 취업 및 후진학 경로'),('마이스터고','산업수요맞춤형 교육·졸업 이후 진로 확인'),('대안계열 학교','학력인정 여부와 교육환경 확인'),('방송통신고·기타','학력·학교급·지원자격 확인')]
COURSES={
 '탐구·연구':['공통수학','대수','미적분Ⅰ','공통과학','물리학','화학','생명과학'],
 '기술·제작':['공통수학','대수','미적분Ⅰ','공통과학','물리학','정보'],
 '표현·창작':['국어','영어','미술','음악','매체 의사소통'],
 '소통·도움':['국어','사회','영어','사회와 문화'],
 '기획·도전':['수학','사회','영어','경제'],
 '정리·관리':['수학','정보','경제','확률과 통계']}
ADVANCED=['고급 수학','고급 물리학','고급 화학','고급 생명과학','고급 미적분']
SOURCES=[
 {'title':'전국초중등학교위치표준데이터','url':'https://www.data.go.kr/data/15021148/standard.do','category':'학교 기본정보','year':'상시·갱신형','status':'2026-10-01 기준 사용자가 제공한 전국학교 CSV 기본 탑재. 고입 요강 자료 아님'},
 {'title':'고입정보포털','url':'https://www.hischool.go.kr/','category':'고입 모집요강','year':'2027 포함','status':'시도 기본계획과 학교별 요강 별도 확인'},
 {'title':'대입정보포털 어디가','url':'https://www.adiga.kr/','category':'대입·전년도 결과','year':'대학별 상이','status':'지원학년도와 대학별 최종요강 대조 필수'},
 {'title':'2028학년도 대학 전형 시행계획','url':'https://m.adiga.kr/mob/uct/ces/archiveView.do?menuId=MOUCTCES1001&prtlBbsId=26997','category':'대입 계획','year':'2028','status':'2030학년도 확정 요강 아님'},
 {'title':'커리어넷 진로심리검사 안내','url':'https://www.career.go.kr/cnet/front/openapi/openApiv2TestCenter.do','category':'공식 진로검사','year':'상시','status':'API 발급 필요, 자체 설문과 구분'},
 {'title':'국가법령정보센터 — 학교생활기록 상업적 이용 제한','url':'https://www.law.go.kr/LSW/lsInfoP.do?ancYnChk=0&lsId=000900','category':'법령','year':'2026 확인','status':'유료 학생부 서비스 법률검토 필요'},
 {'title':'나이스 교육정보 개방포털','url':'https://open.neis.go.kr/','category':'학교 코드·시간표·학사일정','year':'상시','status':'API 발급필요, 미래 편제표와 구분'},
 {'title':'2028 모집단위별 반영·권장과목','url':'https://m.adiga.kr/mob/uct/ces/archiveView.do?menuId=MOUCTCES1001&prtlBbsId=26239','category':'학과·과목','year':'2028','status':'목표학년도 확인'}]
def evaluate_survey(answers):
 answers=answers or {}; grouped=defaultdict(list)
 for q in QUESTIONS:
  if q['type']=='likert' and q['id'] in answers:
   try:v=int(answers[q['id']])
   except:continue
   if 1<=v<=5:grouped[q['dimension']].append(v)
 dims={k:{'average':round(sum(v)/len(v),2),'count':len(v)} for k,v in grouped.items()}
 interest={k:dims[k] for k in AREAS if k in dims}
 top=sorted(interest,key=lambda x:-interest[x]['average'])
 reason=[q for q in QUESTIONS if q['type']=='reasoning' and q['id'] in answers]
 correct=sum(str(answers[q['id']])==str(ANSWERS[q['id']]) for q in reason)
 return {'answered':sum(d['count'] for d in dims.values())+len(reason),'total':168,'dimensions':dims,'top':top[:3],'reasoning':{'answered':len(reason),'correct':correct,'percent':round(correct/len(reason)*100) if reason else None,'disclaimer':'연습문항 정답률이며 IQ·지능지수가 아닙니다.'},'disclaimer':'PATHFINDER 자체 탐색 설문. 공인 심리검사·진단이 아닙니다.'}
def grade_analysis(profile):
 grades=(profile or {}).get('middleGrades',{}); out=[]
 for subject,vals in grades.items():
  nums=[]
  for v in vals if isinstance(vals,list) else []:
   try:
    f=float(v)
    if 0<=f<=100:nums.append(f)
   except (ValueError,TypeError):pass
  if nums:out.append({'subject':subject,'count':len(nums),'latest':nums[-1],'average':round(sum(nums)/len(nums),1),'change':round(nums[-1]-nums[0],1) if len(nums)>1 else None})
 return {'subjects':out,'records':sum(x['count'] for x in out),'weak':[x['subject'] for x in out if x['latest']<75 or (x['change'] is not None and x['change']<=-10)]}
def assess(profile,answers,schools=None,admissions=None):
 p=profile or {}; survey=evaluate_survey(answers); g=grade_analysis(p); mode=p.get('mode','고입'); region=p.get('region',''); target=p.get('targetSchool','')
 primary=survey['top'][0] if survey['top'] else '미정'; paths=AREAS.get(primary,['탐색·진로 체험'])
 math=next((x for x in g['subjects'] if x['subject']=='수학'),None); science=next((x for x in g['subjects'] if x['subject']=='과학'),None)
 sustained=p.get('researchMonths',0)
 try:sustained=int(sustained)
 except:sustained=0
 evidence=(math and science and math['count']>=3 and science['count']>=3 and math['latest']>=90 and science['latest']>=90 and sustained>=6 and primary in ('탐구·연구','기술·제작'))
 priorities=[]
 if mode in ('고입','중학생 장기 대입'):
  priorities=[('일반고','진로 변경 가능성을 열어두는 기본 비교대상'),('자율형 공립고','교육과정 및 지역별 선발방식 확인'),('특성화고','실무·취업 관심이 높다면 비교')]
  if primary in ('탐구·연구','기술·제작'):priorities.insert(1,('과학중점학교 운영 일반고','수학·과학 과목 개설을 확인'))
  if evidence:priorities.append(('과학고','기록상 탐색 후보: 학교별 지원자격·면접 추가 확인'))
  else:priorities.append(('과학고·영재학교','성적·지속적 탐구 근거 부족: 최우선 추천 아님'))
  if primary=='표현·창작':priorities.append(('예술고','실기와 포트폴리오 경험 확인'))
  if primary=='소통·도움':priorities.append(('외국어고·국제고','언어·국제사회 관심일 때 비교'))
  if p.get('careerPreference')=='취업·실무':priorities.insert(1,('마이스터고','산업분야 관심·기숙사·선발규정 확인'))
 else:priorities=[('대학·학과·전형','대학별 모집요강과 과목반영 규칙 필수 확인')]
 studentschools=[]
 for s in (schools or []):
  if len(studentschools)>=10:break
  if region and region not in (s.get('region','')+s.get('address','')):continue
  if mode in ('고입','중학생 장기 대입') and ('고등학교' not in s.get('level','') and '고교' not in s.get('level','')):continue
  studentschools.append({**s,'eligibility':'자료 부족: 최종 모집요강을 확인해야 합니다.'})
 steps=[]
 for week,text in [(1,'과목별 취약단원과 최근 오답 10개 분류'),(2,'복습 루틴·학습시간 기록 시작'),(4,'첫 4주 모의점검 및 과목 우선순위 수정'),(8,'고입: 학교별 요강·통학 비교 / 대입: 학과 권장과목 확인'),(12,'학습성과 검토·다음 분기 계획 확정')]:steps.append({'week':week,'task':text})
 return {'mode':mode,'area':primary,'fieldOptions':paths,'survey':survey,'grades':g,'recommendations':[{'name':a,'reason':b} for a,b in priorities], 'courses':[x for x in COURSES.get(primary,COURSES['탐구·연구']) if not (p.get('schoolTrack')=='일반고' and x in ADVANCED)],'schools':studentschools,'goal':target,'roadmap':steps,'warnings':['추천 적합성과 합격확률은 다릅니다. 실제 입결 검증 없이는 개인 합격률을 제공하지 않습니다.','학년도·지역·학교별 전형조건은 근거 자료실에서 원문 확인 후 관리자 최종 검토가 필요합니다.']+(['현재 성적 입력이 적어 설문·진로 선호를 중심으로 분석했습니다.'] if g['records']<4 else []),'sources':SOURCES[:4]}
def review_plan(plan,profile):
 p=plan or {}; out=[]; daily=p.get('daily',[]); weekly=p.get('weekly',[]); monthly=p.get('monthly',[]); yearly=p.get('yearly',[])
 for part,value in [('일간',daily),('주간',weekly),('월간',monthly),('연간',yearly)]:
  if not value:out.append({'level':'주의','message':part+' 목표가 비어 있습니다.'})
 if not p.get('major'):out.append({'level':'보완','message':'계열 안에서 목표 학과를 먼저 정해 보세요. 미정이어도 탐색 목표를 쓸 수 있습니다.'})
 hour=float(p.get('weeklyHours') or 0)
 if hour>35:out.append({'level':'주의','message':'자율학습 주당 35시간 초과: 수면·학교·휴식을 포함해 현실성을 재검토하세요.'})
 if hour<=0:out.append({'level':'보완','message':'실제 가능한 주당 공부시간을 입력하세요.'})
 if daily and not weekly:out.append({'level':'보완','message':'일간 목표를 달성하면 어떤 주간 결과로 연결되는지 명시하세요.'})
 if weekly and not monthly:out.append({'level':'보완','message':'주간 목표의 누적이 월간 목표와 연결되도록 수정하세요.'})
 if monthly and not yearly:out.append({'level':'보완','message':'월간 점검 기준을 연간 목표와 연결해 보세요.'})
 if not p.get('measurement'):out.append({'level':'보완','message':'정답률·복습 횟수·완료율 등 측정 가능한 지표를 한 가지 정하세요.'})
 if p.get('advanceRatio',0)>60 and (profile or {}).get('grade','').startswith('중'):
  out.append({'level':'주의','message':'선행 비중이 높습니다. 현행 학교 단원에 빈틈이 없는지 점검하세요.'})
 return {'score':max(0,100-len(out)*11),'issues':out,'summary':'자동 규칙 검토(생성형 AI 아님). 실천 후 성적·시간 기록으로 재평가하세요.','proposal':['하루 1회 짧은 복습','주 1회 오답·목표 실적 점검','월 1회 우선순위 조정','학기 말 학교·학과 조건 재확인']}
