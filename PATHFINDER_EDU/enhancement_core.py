"""Calendar and evidence-aware guidance. Not an admission-probability model."""
from datetime import date,datetime,timedelta
from collections import Counter,defaultdict
import re

OFFICIAL_SCHOOL_EXAMPLES = [
 ('광주고등학교','자율형 공립고','후기고'),('광주제일고등학교','자율형 공립고','후기고'),
 ('상일여자고등학교','자율형 공립고','후기고'),('수완고등학교','자율형 공립고','후기고'),('전남고등학교','자율형 공립고','후기고'),
 ('보문고등학교','과학중점 운영 일반고','후기고'),('상무고등학교','과학중점 운영 일반고','후기고'),('조선대학교여자고등학교','과학중점 운영 일반고','후기고'),('풍암고등학교','과학중점 운영 일반고','후기고'),
 ('광주과학고등학교','영재학교','별도 선발'),('광주소프트웨어마이스터고등학교','마이스터고','전기고'),('광주자동화설비마이스터고등학교','마이스터고','전기고'),
 ('광주예술고등학교','예술고','전기고'),('광주체육고등학교','체육고','전기고'),('광주공업고등학교','직업교육 특성화·광주형 마이스터','전기고'),
 ('호남삼육고등학교','비평준화 일반고','후기고'),('광일고등학교','비평준화 일반고','후기고')]
OFFICIAL_2027='https://www.gen.go.kr/xboard/board.php?keyset=&mode=downpost&number=454012&page=1&sCat=0&searchword=&tbnum=20'
OFFICIAL_NATIONAL='https://www.data.go.kr/data/15021148/standard.do'
OFFICIAL_2028='https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=294&boardSeq=106040&lev=0&m=020402&opType=N&page=1&s=moe&statusYN=W'

def reference_schools(region='광주',query=''):
 if region and '광주' not in region:return []
 return [{'name':n,'region':'광주','level':'고등학교','school_type':t,'admission_group':g,
          'reference_year':2027,'source':OFFICIAL_2027,
          'verification':'2027학년도 시도 기본계획 유형 참고. 개별 모집요강·지원자격·운영 변동은 별도 대조.'}
         for n,t,g in OFFICIAL_SCHOOL_EXAMPLES if not query or query.replace(' ','') in n.replace(' ','')]

def validate_calendar(entries,week_hours=0):
 issues=[];by_day=defaultdict(list);seen=set();total=0;done=0
 if not isinstance(entries,list):return {'ok':False,'issues':['캘린더 데이터 형식 오류'],'totalMinutes':0,'completedMinutes':0,'days':{}}
 for i,item in enumerate(entries[:600]):
  if not isinstance(item,dict):issues.append(f'{i+1}번째 항목의 형식 오류');continue
  try: day=date.fromisoformat(str(item.get('date','')));minute=int(item.get('minutes',0))
  except (ValueError,TypeError):issues.append(f'{i+1}번째 항목 날짜·시간 오류');continue
  if not 5<=minute<=480:issues.append(f'{day} 계획 시간은 5~480분 범위여야 합니다.');continue
  name=str(item.get('title','')).strip()
  if not name:issues.append(f'{day} 제목 없는 학습 과제');continue
  id_=item.get('id',f'item-{i}')
  if id_ in seen:issues.append('중복된 일정 ID가 있습니다.');continue
  seen.add(id_);total+=minute;done+=minute if item.get('done') else 0;by_day[day.isoformat()].append(item)
 day_totals={d:sum(int(x['minutes']) for x in v) for d,v in by_day.items()}
 for d,m in day_totals.items():
  if m>300:issues.append(f'{d}: 자율학습 {m}분. 수면·학교·휴식과 함께 검토하세요.')
 try:available=float(week_hours)*60
 except (TypeError,ValueError):available=0
 # Important: check only the next actionable week, not total multi-week history.
 now=date.today();monday=now-timedelta(days=now.weekday());sunday=monday+timedelta(days=6)
 this_week=sum(v for d,v in day_totals.items() if monday<=date.fromisoformat(d)<=sunday)
 if available>0 and this_week>available:issues.append(f'이번 주 일정 {this_week}분이 가용시간 {available:.0f}분을 초과합니다.')
 return {'ok':len(issues)==0,'issues':issues,'totalMinutes':total,'completedMinutes':done,'completionRate':round(100*done/total) if total else None,'days':day_totals,'thisWeekMinutes':this_week}

def longitudinal(profile,report,plan,admissions=None):
 """A transparent readiness snapshot; never claim an uncalibrated admission probability."""
 mode=str(profile.get('mode',''))
 grade=report.get('grades',{}) or {}
 survey=report.get('survey',{}) or {}
 cal=validate_calendar(plan.get('calendar',[]),plan.get('weeklyHours',0))
 levels={}
 grades_count=grade.get('records',0)
 levels['학업 기록']={'pct':min(100,round(grades_count/30*100)),'basedOn':f'입력된 중학교 원점수 {grades_count}건 / 시각화 기준 30건','type':'자료 충실도'}
 levels['진로 탐색']={'pct':round(100*survey.get('answered',0)/168),'basedOn':'응답한 자체 설문 / 168문항','type':'자료 충실도'}
 total=cal.get('totalMinutes',0)
 levels['계획 실행']={'pct':cal['completionRate'] if cal['completionRate'] is not None else None,'basedOn':f'완료 {cal.get("completedMinutes",0)}분 / 기록 {total}분','type':'실제 수행률'}
 reqs=[('목표학교',profile.get('targetSchool')),('목표 전공',plan.get('major') or profile.get('targetMajor')),('연간목표',plan.get('yearly')),('월간목표',plan.get('monthly')),('주간 계획',plan.get('weekly') or plan.get('calendar')),('평가 지표',plan.get('measurement'))]
 matched=sum(bool(value) for _,value in reqs)
 levels['목표 구체성']={'pct':round(100*matched/len(reqs)),'basedOn':f'구체화된 목표/계획 항목 {matched}/{len(reqs)}','type':'설계 충실도'}
 major=plan.get('major') or profile.get('targetMajor') or ''
 target=profile.get('targetSchool','')
 checks=[f'목표학교 {target or "미지정"}의 해당 학년도 최종 모집요강과 지원자격 확인',
         '학생부/내신/수능의 평가 방식별 공식 반영점수 확인',
         '학교별 입결의 전형·단위·발표연도 확인',
         '관리자 상담 후 구체적인 목표성적과 측정 주기 확정']
 if mode=='중학생 장기 대입':checks.insert(1,'중학 성적만으로 2030학년도 대학별 합격확률을 계산할 수 없음')
 return {'dimensions':levels,'calendar':cal,'target':target,'major':major,'mode':mode,
         'probability':None,'probabilityReason':'대학·전형별 실제 합격자 원자료와 입학년도에 맞는 점수산식, 독립 검증 데이터가 없어 개인 합격확률을 계산하지 않습니다.',
         'projection':'현재 성적의 단순 연장으로 특정 대학 진학을 보증하거나 대학 명단을 자동 확정할 수 없습니다.',
         'scenarioConditions':checks,'dataGrade':'준비 진단(모형 미검증)',
         'next':'상담자가 목표 대학·학과를 확정한 후 공식 전형 요건을 확인하고, 4~8주 단위 실제 학습 성과에 따라 계획을 갱신합니다.'}
