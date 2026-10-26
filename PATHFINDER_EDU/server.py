"""PATHFINDER EDU pilot server: local by default; opt-in controlled Render deployment."""
import base64,csv,hashlib,hmac,html,io,json,mimetypes,os,re,secrets,sqlite3,sys,time,urllib.request,threading
from datetime import datetime,timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from engine import assess,evaluate_survey,review_plan,SOURCES
from enhancement_core import reference_schools,validate_calendar,longitudinal
from question_bank import QUESTIONS
from secure_config import secret as provider_secret, model_name, key_status, change as change_keys, CredentialError
from api_diagnostics import check_real_model, diagnose_http, extract_text
from db_backend import connect as db_connect, IS_POSTGRES
from ai_suite import CATALOG, MODE_MAP, init_suite, school_search, score_school, explain_offline, make_12week_plan, payload_for_ai, call_openai, neis_lookup, university_lookup
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('PF_DATA_DIR', str(ROOT/'data'))).expanduser().resolve(); DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/'pathfinder.sqlite3'
ADMIN_USER=os.environ.get('PF_ADMIN_USER','brans911')
ADMIN_PASSWORD=os.environ.get('PF_ADMIN_PASSWORD','brans911!')
PUBLIC_MODE=os.environ.get('PF_PUBLIC_MODE','0')=='1'
HOST='0.0.0.0' if PUBLIC_MODE else '127.0.0.1'
PORT=int(os.environ.get('PORT') or os.environ.get('PF_PORT','8765'))
AI_CAPACITY=threading.BoundedSemaphore(max(1,min(12,int(os.environ.get('PF_AI_CONCURRENCY','4')))))
AI_LOCK=threading.Lock()
MAX_STUDENTS=max(1,min(1000,int(os.environ.get('PF_MAX_STUDENTS','25'))))
# Optional 5-node pilot. One-node mode stays compatible with earlier deployments.
NODE_ID=int(os.environ.get('PF_NODE_ID','1'))
NODE_COUNT=int(os.environ.get('PF_NODE_COUNT','1'))
NODE_CAPACITY=max(1,min(25,int(os.environ.get('PF_NODE_CAPACITY','4'))))
class CapacityError(Exception):pass

def verify_online_launch():
 if not (1<=NODE_COUNT<=5 and 1<=NODE_ID<=NODE_COUNT):
  raise RuntimeError('PF_NODE_ID / PF_NODE_COUNT 설정 범위가 잘못되었습니다.')
 if NODE_COUNT>1 and MAX_STUDENTS>NODE_COUNT*NODE_CAPACITY:
  raise RuntimeError('전체 정원이 조별 허용 인원보다 많습니다. PF_MAX_STUDENTS 값을 확인하세요.')
 if not PUBLIC_MODE:return
 if len(ADMIN_PASSWORD)<16 or ADMIN_PASSWORD=='brans911!' or ADMIN_PASSWORD.lower() in ('password','password1234','admin1234'):
  raise RuntimeError('온라인 실행 전에 Render Environment에서 PF_ADMIN_PASSWORD (16자 이상, 유추 어려운 임시 암호)를 지정해야 합니다.')
 code=os.environ.get('PF_SIGNUP_CODE','')
 if len(code)<12:
  raise RuntimeError('온라인 회원가입 보호를 위해 PF_SIGNUP_CODE (12자 이상)를 설정해야 합니다.')
 if not os.environ.get('DATABASE_URL','').startswith(('postgres://','postgresql://')):
  raise RuntimeError('Render 무료 서비스는 영구 디스크가 없습니다. 외부 PostgreSQL의 DATABASE_URL을 입력해야 합니다.')

MAX_BODY=24*1024*1024
SESSIONS={}; FAILS={}; AI_LAST={}
NOW=lambda:datetime.now(timezone.utc).isoformat(timespec='seconds')

def db():
 return db_connect(DB)

def make_pw(pw):
 salt=secrets.token_bytes(16); key=hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,240000)
 return 'pbkdf2$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(key).decode()
def check_pw(pw,stored):
 try:
  _,s,k=stored.split('$'); salt=base64.b64decode(s); want=base64.b64decode(k)
  return hmac.compare_digest(want,hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,240000))
 except Exception:return False

def init_db():
 with db() as c:
  # Five Render instances may start together against the same PostgreSQL database.
  # Serialize schema and school-directory initialization transactionally.
  if IS_POSTGRES:
   c.execute('SELECT pg_advisory_xact_lock(7222271001)')
  c.executescript('''
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL, display_name TEXT, birth_year INTEGER, created TEXT NOT NULL,force_pw_change INTEGER DEFAULT 0, consent_at TEXT);
  CREATE TABLE IF NOT EXISTS profiles(user_id INTEGER PRIMARY KEY,payload TEXT NOT NULL,updated TEXT);
  CREATE TABLE IF NOT EXISTS answers(user_id INTEGER PRIMARY KEY,payload TEXT NOT NULL,updated TEXT);
  CREATE TABLE IF NOT EXISTS plans(user_id INTEGER PRIMARY KEY,payload TEXT NOT NULL,updated TEXT);
  CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,status TEXT NOT NULL,auto_report TEXT NOT NULL,admin_report TEXT,admin_note TEXT,created TEXT,updated TEXT,student_message TEXT);
  CREATE TABLE IF NOT EXISTS schools(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,region TEXT,address TEXT,level TEXT,school_type TEXT,source TEXT,verified TEXT,UNIQUE(name,address));
  CREATE TABLE IF NOT EXISTS admissions(id INTEGER PRIMARY KEY AUTOINCREMENT,school TEXT,year INTEGER,track TEXT,capacity INTEGER,applicants INTEGER,cutoff TEXT,source TEXT,verification TEXT);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor INTEGER,action TEXT,when_at TEXT);
  CREATE TABLE IF NOT EXISTS api_usage(day TEXT,provider TEXT,mode TEXT,status TEXT,calls INTEGER DEFAULT 0,input_tokens INTEGER DEFAULT 0,output_tokens INTEGER DEFAULT 0,total_ms INTEGER DEFAULT 0,PRIMARY KEY(day,provider,mode,status));
  CREATE TABLE IF NOT EXISTS student_nodes(user_id INTEGER PRIMARY KEY,node_id INTEGER NOT NULL,created TEXT NOT NULL);
  ''')
  if (NODE_COUNT==1 or NODE_ID==1) and not c.execute('SELECT id FROM users WHERE username=?',(ADMIN_USER,)).fetchone():
   c.execute('INSERT INTO users(username,password,role,display_name,birth_year,created,force_pw_change) VALUES(?,?,?,?,?,?,1)',(ADMIN_USER,make_pw(ADMIN_PASSWORD),'admin','관리자',1980,NOW()))
  count=init_suite(c)
  if count:print(f'Public school directory indexed: {count:,} rows (local reference only).')
  # Accounts and case reports are not shipped in the ZIP.

def jloads(raw,default):
 try:return json.loads(raw)
 except:return default

def audit(actor,action):
 with db() as c:c.execute('INSERT INTO audit(actor,action,when_at) VALUES(?,?,?)',(actor,action,NOW()))

def track_api(provider, mode, status, elapsed, usage=None):
 # Aggregate-only tracking: do not record student IDs, questions, credentials or IPs.
 usage=usage if isinstance(usage,dict) else {}
 def safe_int(key):
  try:return max(0,int(usage.get(key,0) or 0))
  except (TypeError,ValueError):return 0
 with db() as c:
  c.execute('''INSERT INTO api_usage(day,provider,mode,status,calls,input_tokens,output_tokens,total_ms)
   VALUES(?,?,?,?,1,?,?,?) ON CONFLICT(day,provider,mode,status) DO UPDATE SET
   calls=calls+1,input_tokens=input_tokens+excluded.input_tokens,
   output_tokens=output_tokens+excluded.output_tokens,total_ms=total_ms+excluded.total_ms''',
   (datetime.now(timezone.utc).date().isoformat(),provider,mode,status,
    safe_int('input_tokens'),safe_int('output_tokens'),max(0,int(elapsed*1000))))

def usage_summary():
 with db() as c:
  daily=[dict(x) for x in c.execute('''SELECT day,provider,status,SUM(calls) AS calls,
   SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens,
   SUM(total_ms) AS total_ms FROM api_usage GROUP BY day,provider,status ORDER BY day DESC LIMIT 75''')]
  modes=[dict(x) for x in c.execute('''SELECT mode,SUM(calls) AS calls,
   SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens
   FROM api_usage GROUP BY mode ORDER BY calls DESC LIMIT 30''')]
 return {'daily':daily,'modes':modes,'tracking':'서버 자체 집계. Tracking 전용 OpenAI API 키는 필요하지 않습니다.',
         'cost':'비용은 모델별 과금 단가, 캐시, 할인에 따라 달라집니다. 원화/달러 비용은 임의 계산하지 않습니다.'}

def verify_provider(provider):
 # Real network attempt only on explicit administrator action.
 if provider not in ('openai','neis','university'):
  raise ValueError('알 수 없는 API 제공자입니다.')
 if not provider_secret(provider):
  return {'ok':False,'provider':provider,'message':'설정된 API 키가 없습니다.'}
 try:
  if provider=='openai':
   result=check_real_model()
   result['provider']='openai'
   return result
  if provider=='neis':
   result=neis_lookup('광주고등학교')
   return {'ok':True,'provider':provider,'message':'나이스 요청 성공 · 기본정보 '+str(len(result.get('schools',[])))+'개 (전형/합격선 아님)'}
  result=university_lookup('전남대학교')
  return {'ok':True,'provider':provider,'message':'대학정보 요청 완료 · '+str(len(result.get('universities',[])))+'개 (서비스별 응답 내용을 확인하세요)'}
 except urllib.error.HTTPError as e:
  return {'ok':False,'provider':provider,'message':f'인증 또는 요청 실패 HTTP {e.code}. 키·권한·서비스 활성화를 확인하세요.'}
 except Exception:
  return {'ok':False,'provider':provider,'message':'연결 실패: 네트워크·키 종류·서비스 승인 여부를 확인하세요. 상세 비밀 정보는 표시하지 않습니다.'}

def get_saved(table,uid):
 with db() as c:r=c.execute(f'SELECT payload FROM {table} WHERE user_id=?',(uid,)).fetchone()
 return jloads(r['payload'],{}) if r else {}

def save(table,uid,payload):
 if not isinstance(payload,dict):raise ValueError('객체 형식만 저장 가능합니다.')
 val=json.dumps(payload,ensure_ascii=False)
 if len(val)>180000:raise ValueError('저장 가능한 데이터 용량을 초과했습니다.')
 with db() as c:c.execute(f'INSERT INTO {table}(user_id,payload,updated) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',(uid,val,NOW()))

def read_schools(region='',name='',limit=100):
 sql='SELECT name,region,address,level,school_type,source,verified FROM schools WHERE 1=1';args=[]
 if region:sql+=' AND (region LIKE ? OR address LIKE ?)';args.extend([f'%{region}%',f'%{region}%'])
 if name:sql+=' AND name LIKE ?';args.append(f'%{name}%')
 sql+=' ORDER BY name LIMIT ?';args.append(min(max(limit,1),500))
 with db() as c:
  rows=[dict(x) for x in c.execute(sql,args)]
  if rows:return rows
  # Fall back to the bundled, provenance-tagged nationwide school directory.
  directory=school_search(c,name,region,'고등학교',limit)
  return [{'name':x['name'],'region':region if region in ('광주','전남') else x['region'],
           'address':x['address'],'level':x['level'],'school_type':x['classification'],
           'source':x['source'],'verified':'공식 위치 기본정보 / 모집요강 미검증'} for x in directory['schools']]

def import_csv(kind,text,source):
 if not isinstance(text,str) or len(text)>18000000:raise ValueError('CSV 크기 초과')
 if not source or not str(source).startswith('https://'):raise ValueError('원문 출처(HTTPS)를 입력하세요.')
 reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
 if not reader.fieldnames:raise ValueError('CSV 열 이름이 없습니다.')
 num=0
 with db() as c:
  for row in reader:
   if num>=24000:break
   if kind=='schools':
    name=(row.get('학교명') or row.get('name') or '').strip();region=(row.get('시도교육청명') or row.get('지역') or row.get('region') or '').strip()
    address=(row.get('소재지도로명주소') or row.get('주소') or row.get('address') or '').strip();level=(row.get('학교급구분') or row.get('학교급') or row.get('level') or '').strip()
    if not name:continue
    c.execute('INSERT OR IGNORE INTO schools(name,region,address,level,school_type,source,verified) VALUES(?,?,?,?,?,?,?)',(name[:90],region[:90],address[:200],level[:50],'미확인',source,'기본 학교정보만 확인'))
   else:
    name=(row.get('학교명') or row.get('school') or '').strip();year=row.get('학년도') or row.get('year');capacity=row.get('모집인원') or row.get('capacity');applicants=row.get('지원자수') or row.get('applicants')
    if not name or not str(year).isdigit():continue
    cap=int(capacity) if str(capacity).isdigit() else None;app=int(applicants) if str(applicants).isdigit() else None
    c.execute('INSERT INTO admissions(school,year,track,capacity,applicants,cutoff,source,verification) VALUES(?,?,?,?,?,?,?,?)',(name[:90],int(year),(row.get('전형') or row.get('track') or '')[:80],cap,app,(row.get('합격선') or row.get('cutoff') or '')[:150],source,'관리자 등록·원문 대조 필요'))
   num+=1
 return num

# No text of a school life record is sent to outside APIs. Optional LLM gets study plan only after opt-in.
def llm_review(plan):
 key=provider_secret('openai')
 if not key:raise ValueError('생성형 AI API 키 미설정: 로컬 규칙 검토는 항상 사용할 수 있습니다.')
 model=model_name()
 sanitized={'major':str(plan.get('major',''))[:100],'yearly':plan.get('yearly',[])[:15],'monthly':plan.get('monthly',[])[:15], 'weekly':plan.get('weekly',[])[:30],'daily':plan.get('daily',[])[:40],'weeklyHours':plan.get('weeklyHours',0),'measurement':str(plan.get('measurement',''))[:200]}
 instructions='한국어 학습계획 검토자. 개인정보나 학생부를 요청하지 마세요. 부족한 시간, 과부하, 목표간 연결, 측정 지표를 구체적으로 검토하고 800자 이내로 수정안을 제시하세요. 합격 가능성 확률을 만들지 마세요.'
 body=json.dumps({'model':model,'instructions':instructions,'input':json.dumps(sanitized,ensure_ascii=False),'max_output_tokens':700,'store':False}).encode()
 req=urllib.request.Request('https://api.openai.com/v1/responses',data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=35) as r:data=json.load(r)
 except urllib.error.HTTPError as ex:raise RuntimeError(diagnose_http(ex)['message']) from None
 output=extract_text(data)
 if not output:raise RuntimeError('학습계획 AI 답변이 비어 있습니다. 모델과 출력 토큰 한도를 확인하세요.')
 return output[:4000]

def report_content(case_id,uid):
 with db() as c:
  case=c.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
  u=c.execute('SELECT username,display_name FROM users WHERE id=?',(uid,)).fetchone()
 if not case or not u:return None
 return {'case':dict(case),'student':dict(u),'auto':jloads(case['auto_report'],{}),'admin':jloads(case['admin_report'],{})}

def pdf_bytes(case_id,uid):
 from report_pdf import build_pdf
 pack=report_content(case_id,uid)
 return build_pdf(pack) if pack else None

def docx_bytes(case_id,uid):
 from docx import Document
 from docx.shared import Pt
 pack=report_content(case_id,uid)
 if not pack:return None
 d=Document();normal=d.styles['Normal'];normal.font.name='맑은 고딕';normal.font.size=Pt(10)
 d.add_heading('PATHFINDER EDU | 진학 컨설팅 결과지',0)
 d.add_paragraph('보고서 번호: '+str(case_id)+' | 학생: '+str(pack['student'].get('display_name','')))
 auto=pack['auto'];d.add_heading('개인 분석',1);d.add_paragraph('준비 목적: '+str(auto.get('mode',''))+' / 관심영역: '+str(auto.get('area','')))
 for h,records,key in [('추천 학교/진학 경로',auto.get('recommendations',[]),'name'),('연결 전공·학과',auto.get('fieldOptions',[]),None),('확인·주의사항',auto.get('warnings',[]),None)]:
  d.add_heading(h,2)
  for r in records:d.add_paragraph((r.get('name','')+' — '+r.get('reason','')) if isinstance(r,dict) else str(r),style='List Bullet')
 d.add_heading('관리자 최종 컨설팅',1)
 for k,v in (pack['admin'] or {}).items():
  if v:d.add_heading({'summary':'종합 의견','evidence':'공식 자료 및 학년도','strengths':'강점','risks':'우려사항','school':'학교·전형 판단','goals':'목표 전공·학과','record':'학생부·세특 검토','study':'학습 전략','calendar':'12주 계획','interview':'면접','parents':'보호자 안내','nextSteps':'실행 과제','followup':'재검토 기준'}.get(k,k),2);d.add_paragraph(str(v))
 d.add_paragraph('이 문서는 확정 합격판정이나 공인 심리검사가 아닙니다. 개인 전형자격은 학교/대학 입학처에서 확인해야 합니다.')
 b=io.BytesIO();d.save(b);return b.getvalue()

class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
 def log_message(self,fmt,*args):pass
 def end_headers(self):
  if PUBLIC_MODE:self.send_header('Strict-Transport-Security','max-age=31536000; includeSubDomains')
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'");super().end_headers()
 def send(self,code,data,extra=None):
  if isinstance(data,(dict,list)):content=json.dumps(data,ensure_ascii=False).encode();mime='application/json; charset=utf-8'
  else:content=data if isinstance(data,bytes) else str(data).encode();mime='text/plain; charset=utf-8'
  extras=extra or {}
  self.send_response(code);self.send_header('Content-Type',extras.get('Content-Type',mime));self.send_header('Content-Length',str(len(content)))
  for k,v in extras.items():
   if k.lower()!='content-type':self.send_header(k,v)
  self.end_headers();self.wfile.write(content)
 def body(self):
  size=int(self.headers.get('Content-Length','0'))
  if size<=0 or size>MAX_BODY:raise ValueError('요청 크기 오류')
  try:return json.loads(self.rfile.read(size))
  except:raise ValueError('잘못된 JSON')
 def user(self):
  cookie=SimpleCookie()
  try:cookie.load(self.headers.get('Cookie',''))
  except:return (None,None)
  token=cookie.get('pf_session')
  if not token:return (None,None)
  x=SESSIONS.get(token.value)
  if not x or x['expires']<time.time():return (None,None)
  with db() as c:
   u=c.execute('SELECT id,username,role,display_name,force_pw_change,birth_year FROM users WHERE id=?',(x['uid'],)).fetchone()
   if not u:return (None,None)
   if NODE_COUNT>1:
    if u['role']=='admin' and NODE_ID!=1:return (None,None)
    if u['role']=='student':
     assignment=c.execute('SELECT node_id FROM student_nodes WHERE user_id=?',(u['id'],)).fetchone()
     if not assignment or assignment['node_id']!=NODE_ID:return (None,None)
  return (dict(u),x)
 def require(self,role=None,csrf=False):
  u,s=self.user()
  if not u:raise PermissionError('로그인이 필요합니다.')
  if role and u['role']!=role:raise PermissionError('권한이 없습니다.')
  if csrf and not hmac.compare_digest(self.headers.get('X-CSRF',''),s['csrf']):raise PermissionError('보안 확인 실패, 페이지를 새로고침하세요.')
  return u
 def do_GET(self):
  route=urlparse(self.path).path
  try:
   if route=='/healthz':
    try:
     with db() as c: c.execute('SELECT 1').fetchone()
     return self.send(200,{'ok':True,'service':'pathfinder-edu','databaseReady':True})
    except Exception:return self.send(503,{'ok':False,'service':'pathfinder-edu','databaseReady':False})
   if route=='/robots.txt':return self.send(200,b'User-agent: *\nDisallow: /\n',{'Content-Type':'text/plain; charset=utf-8'})
   if route=='/api/public':return self.send(200,{'questionCount':len(QUESTIONS),'sources':SOURCES,'schoolTypes':[x[0] for x in __import__('engine').SCHOOL_TYPES],'features':{'offlineEngine':True,'llmEnabled':bool(provider_secret('openai')),'paymentsLive':False},'inviteRequired':PUBLIC_MODE,'nodeId':NODE_ID,'nodeCount':NODE_COUNT,'nodeCapacity':NODE_CAPACITY if NODE_COUNT>1 else MAX_STUDENTS})
   if route=='/api/questions':return self.send(200,{'questions':QUESTIONS,'notice':'자체 탐색 문항이며 공인 IQ/심리검사가 아닙니다.'})
   if route=='/api/session':
    u,s=self.user();return self.send(200,{'user':u,'csrf':s['csrf']} if u else {'user':None})
   if route.startswith('/api/'):
    u=self.require();uid=u['id'];qs=parse_qs(urlparse(self.path).query)
    if route=='/api/admin/api-config':
     self.require('admin')
     return self.send(200,{'keys':key_status(),'model':model_name(),'tracking':'서버 자체 집계, 별도 Tracking Secret 불필요',
                            'storage':'Render: API 키는 Render Environment에서 관리 (웹 설정은 읽기 전용)' if PUBLIC_MODE else 'Windows: 사용자 DPAPI 암호화 저장 / 기타 운영체제: 프로세스 메모리'})
    if route=='/api/admin/api-usage':
     self.require('admin');return self.send(200,usage_summary())
    if route=='/api/v2/status':
     with db() as c:amount=c.execute('SELECT COUNT(*) FROM school_directory').fetchone()[0]
     # Students receive feature availability, NEVER provider configuration, key source or model IDs.
     return self.send(200,{'aiAvailable':bool(provider_secret('openai')),'nationalSchoolCount':amount,
        'modes':[{'id':mid,'title':title,'description':description} for mid,title,description in CATALOG],
        'privacy':'외부 AI에는 별도 동의한 축약 학습통계·질문만 전송. 원본 세특·이름·생년월일은 제외.'})
    if route=='/api/v2/schools':
     with db() as c:result=school_search(c,qs.get('q',[''])[0],qs.get('region',[''])[0],qs.get('level',['고등학교'])[0],qs.get('limit',['60'])[0],qs.get('offset',['0'])[0])
     return self.send(200,result)
    if route=='/api/v2/recommend-schools':
     self.require('student');profile=get_saved('profiles',uid)
     region=qs.get('region',[str(profile.get('region',''))])[0]
     with db() as c:result=school_search(c,qs.get('q',[''])[0],region,'고등학교',min(100,max(1,int(qs.get('limit',['50'])[0]))))
     options=[dict(s,heuristic=score_school(s,profile)) for s in result['schools']]
     options.sort(key=lambda x:-(x['heuristic']['score'] or 0))
     return self.send(200,{'schools':options,'count':result['total'],'source':result['source'],'disclaimer':'표시 점수는 입력 기반 후보 탐색 우선순위로, 공식 순위·합격률·합격 가능성을 뜻하지 않습니다. 입학 요강과 자격은 미검증.'})
    if route=='/api/v2/offline-analysis':
     self.require('student');p=get_saved('profiles',uid);plan=get_saved('plans',uid)
     return self.send(200,{'analysis':explain_offline(p,plan,get_saved('answers',uid))})
    if route=='/api/v2/ai-history':
     self.require('student')
     with db() as c:rows=[dict(x) for x in c.execute('SELECT id,mode,question,answer,model,created FROM ai_history WHERE user_id=? ORDER BY id DESC LIMIT 20',(uid,))]
     return self.send(200,{'history':rows})
    if route=='/api/v2/universities':
     return self.send(200,university_lookup(qs.get('q',[''])[0],qs.get('region',[''])[0]))
    if route=='/api/v2/neis':
     query=qs.get('q',[''])[0].strip()
     return self.send(200,neis_lookup(query))
    if route=='/api/profile':return self.send(200,{'profile':get_saved('profiles',uid),'answers':get_saved('answers',uid),'plan':get_saved('plans',uid)})
    if route=='/api/schools':return self.send(200,{'schools':read_schools(qs.get('region',[''])[0],qs.get('name',[''])[0]) or reference_schools(qs.get('region',[''])[0],qs.get('name',[''])[0]),'note':'제공된 전국학교 공공 CSV에서 학교명·주소를 조회합니다. 입학자격·전형·과목 개설 여부는 별도 확인 필요'})
    if route=='/api/reference-schools':return self.send(200,{'schools':reference_schools(qs.get('region',['광주'])[0],qs.get('name',[''])[0]),'referenceYear':2027,'note':'개별 학교의 확정 입결이나 지원가능성은 아님'})
    if route=='/api/longitudinal':
     self.require('student');p=get_saved('profiles',uid);a=get_saved('answers',uid);plan=get_saved('plans',uid)
     report=assess(p,a,read_schools(str(p.get('region','')),limit=100) or reference_schools(str(p.get('region',''))))
     return self.send(200,{'analysis':longitudinal(p,report,plan)})
    if route=='/api/admissions':
     with db() as c:rows=[dict(x) for x in c.execute('SELECT * FROM admissions WHERE school LIKE ? ORDER BY year DESC LIMIT 60',('%'+qs.get('school',[''])[0]+'%',))]
     return self.send(200,{'admissions':rows,'note':'과거 경쟁률은 개인 합격확률이 아님'})
    if route=='/api/me/cases':
     with db() as c:rows=[dict(x) for x in c.execute('SELECT id,status,created,updated,admin_note FROM cases WHERE user_id=? ORDER BY id DESC',(uid,))]
     return self.send(200,{'cases':rows})
    if route=='/api/admin/cases':
     self.require('admin')
     with db() as c:rows=[dict(x) for x in c.execute('SELECT cases.id,cases.user_id,cases.status,cases.created,cases.updated,users.display_name,users.username FROM cases JOIN users ON cases.user_id=users.id ORDER BY cases.id DESC LIMIT 200')]
     return self.send(200,{'cases':rows})
    if route=='/api/admin/students':
     self.require('admin')
     with db() as c:rows=[dict(x) for x in c.execute("SELECT users.id,users.username,users.display_name,users.birth_year,users.created,student_nodes.node_id AS group_node FROM users LEFT JOIN student_nodes ON student_nodes.user_id=users.id WHERE users.role='student' ORDER BY users.id DESC LIMIT 250")]
     return self.send(200,{'students':rows})
    if route.startswith('/api/cases/'):
     cid=int(route.split('/')[-1]);
     with db() as c:row=c.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone()
     if not row or (u['role']!='admin' and row['user_id']!=uid):raise PermissionError('보고서 조회 권한 없음')
     result={'case':dict(row)}
     if u['role']!='admin' and row['status']!='published':result['case']['admin_report']=None;result['case']['admin_note']=None
     return self.send(200,result)
    if route.startswith('/api/download/'):
     cid=int(route.split('/')[-1].split('.')[0]);format=route.rsplit('.',1)[-1]
     with db() as c:r=c.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone()
     if not r or (u['role']!='admin' and (r['user_id']!=uid or r['status']!='published')):raise PermissionError('다운로드 권한이 없습니다.')
     content=pdf_bytes(cid,r['user_id']) if format=='pdf' else docx_bytes(cid,r['user_id']) if format=='docx' else None
     if content is None:raise ValueError('지원되지 않는 파일입니다.')
     return self.send(200,content,{'Content-Type':'application/pdf' if format=='pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document','Content-Disposition':f'attachment; filename="PATHFINDER_report_{cid}.{format}"'})
   if route in ('/','/admin','/index.html','/app.js','/styles.css','/app_plus.js','/styles_plus.css',
                '/assets/flight-path.webp','/assets/orbit-editorial.webp','/experience.js',
                '/학교목록_업로드_양식.csv','/입결_업로드_양식.csv'):
    if route=='/admin':
     self.path='/index.html'
    return super().do_GET()
   return self.send(404,{'error':'리소스가 없거나 비공개 경로입니다.'})
  except PermissionError as ex:self.send(403,{'error':str(ex)})
  except Exception as ex:
   # Programmer/network/SQL exceptions never reveal internal paths, connection strings or credentials.
   if isinstance(ex,(ValueError,CapacityError)):self.send(400,{'error':str(ex)})
   else:self.send(503 if PUBLIC_MODE else 400,{'error':'요청을 처리할 수 없습니다. 잠시 후 다시 시도하거나 관리자에게 문의하세요.' if PUBLIC_MODE else str(ex)})
 def do_POST(self):
  route=urlparse(self.path).path
  try:
   if PUBLIC_MODE:
    origin=self.headers.get('Origin','')
    if origin and urlparse(origin).netloc!=self.headers.get('Host',''):
     raise PermissionError('허용되지 않은 요청 출처입니다.')
   data=self.body()
   if route=='/api/signup':
    if (PUBLIC_MODE or os.environ.get('PF_REQUIRE_SIGNUP_CODE')=='1') and not hmac.compare_digest(str(data.get('signupCode','')),os.environ.get('PF_SIGNUP_CODE','')):
     raise PermissionError('가입코드가 맞지 않습니다. 운영자에게 초대코드를 확인하세요.')
    username=str(data.get('username','')).strip();pw=str(data.get('password',''));name=str(data.get('name','')).strip();birth=int(data.get('birthYear',0))
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{4,80}',username):raise ValueError('아이디는 영문·숫자 4자 이상으로 입력')
    if not (10<=len(pw)<=120):raise ValueError('비밀번호는 10자 이상')
    if len(name)<1:raise ValueError('이름을 입력하세요.')
    if datetime.now(timezone.utc).year-birth<15:raise ValueError('출생연도만 입력받는 현재 시범판은 만 14세 이상임이 확실한 경우만 가입할 수 있습니다. 14세 미만 법정대리인 인증 기능은 아직 제공하지 않습니다.')
    if not data.get('consent'):raise ValueError('필수 이용 안내 동의 필요')
    try:
     with db() as c:
      # Prevent seat oversubscription between five independently running services.
      if NODE_COUNT>1 and IS_POSTGRES:
       c.execute('SELECT pg_advisory_xact_lock(7222271002)')
      if PUBLIC_MODE and c.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]>=MAX_STUDENTS:
       raise PermissionError('전체 20명 정원에 도달했습니다. 관리자에게 문의하세요.')
      if NODE_COUNT>1:
       assigned=c.execute('SELECT COUNT(*) FROM student_nodes WHERE node_id=?',(NODE_ID,)).fetchone()[0]
       if assigned>=NODE_CAPACITY:raise PermissionError(f'{NODE_ID}조는 {NODE_CAPACITY}명 정원입니다. 배정 담당자에게 문의하세요.')
      created=c.execute('INSERT INTO users(username,password,role,display_name,birth_year,created,consent_at) VALUES(?,?,?,?,?,?,?) RETURNING id',(username,make_pw(pw),'student',name[:45],birth,NOW(),NOW())).fetchone()[0]
      if NODE_COUNT>1:
       c.execute('INSERT INTO student_nodes(user_id,node_id,created) VALUES(?,?,?)',(created,NODE_ID,NOW()))
    except Exception as ex:
     if 'unique' in str(ex).lower() or isinstance(ex,sqlite3.IntegrityError):raise ValueError('이미 사용 중인 아이디입니다.')
     raise
    return self.send(201,{'ok':True,'message':'가입 완료. 로그인하세요.'})
   if route=='/api/login':
    username=str(data.get('username','')).strip();pw=str(data.get('password',''));role=str(data.get('role','student'))
    key=username  # proxy 뒤에서 여러 학생이 동일 IP를 공유하므로 계정별 제한
    records=[t for t in FAILS.get(key,[]) if t>time.time()-300];FAILS[key]=records
    if len(records)>=8:raise PermissionError('로그인 오류가 많습니다. 5분 후 다시 시도하세요.')
    with db() as c:u=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
    if not u or u['role']!=role or not check_pw(pw,u['password']):
     FAILS[key].append(time.time());raise PermissionError('아이디 또는 비밀번호가 일치하지 않습니다.')
    if NODE_COUNT>1:
     if role=='admin' and NODE_ID!=1:
      raise PermissionError('관리자 상담은 1번 서버에서만 로그인할 수 있습니다.')
     if role=='student':
      with db() as c:assignment=c.execute('SELECT node_id FROM student_nodes WHERE user_id=?',(u['id'],)).fetchone()
      if not assignment:
       raise PermissionError('기존 계정의 조 배정이 없습니다. 관리자에게 조 배정을 요청하세요.')
      if assignment['node_id']!=NODE_ID:
       raise PermissionError(f'이 계정은 {assignment["node_id"]}조 전용입니다. 배정받은 {assignment["node_id"]}번 서버로 접속하세요.')
    FAILS.pop(key,None);token=secrets.token_urlsafe(36);csrf=secrets.token_urlsafe(24)
    SESSIONS[token]={'uid':u['id'],'csrf':csrf,'expires':time.time()+8*3600}
    audit(u['id'],'login')
    secure='; Secure' if PUBLIC_MODE else ''
    return self.send(200,{'ok':True,'role':role},{'Set-Cookie':f'pf_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+secure})
   u=self.require(csrf=True);uid=u['id']
   if route=='/api/admin/api-config':
    self.require('admin')
    if PUBLIC_MODE:raise PermissionError('Render 운영 환경에서는 대시보드 Environment에서 API 키를 변경하세요. 웹에서 키를 저장하지 않습니다.')
    current=str(data.get('currentPassword',''))
    with db() as c:row=c.execute('SELECT password,force_pw_change FROM users WHERE id=?',(uid,)).fetchone()
    if not row or not check_pw(current,row['password']):raise PermissionError('관리자 비밀번호가 일치하지 않습니다.')
    if row['force_pw_change']:
     raise PermissionError('초기 관리자 비밀번호를 먼저 변경해야 API 키를 등록할 수 있습니다.')
    result=change_keys(keys=data.get('keys'),delete=data.get('delete'),model=data.get('model'))
    audit(uid,'api-config-updated')
    return self.send(200,result)
   if route=='/api/admin/api-test':
    self.require('admin')
    current=str(data.get('currentPassword',''))
    with db() as c:row=c.execute('SELECT password,force_pw_change FROM users WHERE id=?',(uid,)).fetchone()
    if not row or not check_pw(current,row['password']):raise PermissionError('관리자 비밀번호가 일치하지 않습니다.')
    if row['force_pw_change']:raise PermissionError('초기 관리자 비밀번호를 먼저 변경하세요.')
    provider=str(data.get('provider',''))
    if provider not in ('openai','neis','university'):raise ValueError('잘못된 API 종류입니다.')
    started=time.monotonic();result=verify_provider(provider)
    track_api(provider,'connection-test','success' if result['ok'] else 'error',time.monotonic()-started,result.get('usage'))
    audit(uid,'api-test-'+provider)
    return self.send(200,result)
   if route=='/api/logout':
    token=SimpleCookie();token.load(self.headers.get('Cookie',''));session=token.get('pf_session')
    if session:SESSIONS.pop(session.value,None)
    return self.send(200,{'ok':True},{'Set-Cookie':'pf_session=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/'})
   if route=='/api/change-password':
    old=str(data.get('old',''));new=str(data.get('new',''))
    if len(new)<10:raise ValueError('새 비밀번호는 10자 이상')
    with db() as c:
     row=c.execute('SELECT password FROM users WHERE id=?',(uid,)).fetchone()
     if not check_pw(old,row['password']):raise PermissionError('현재 비밀번호가 틀립니다.')
     c.execute('UPDATE users SET password=?,force_pw_change=0 WHERE id=?',(make_pw(new),uid))
    audit(uid,'change-password');return self.send(200,{'ok':True})
   if route=='/api/profile/save':
    self.require('student')
    from student_validation import validate_profile
    profile=validate_profile(data.get('profile',{}))
    save('profiles',uid,profile);return self.send(200,{'ok':True})
   if route=='/api/answers/save':
    self.require('student');save('answers',uid,data.get('answers',{}));return self.send(200,{'ok':True,'survey':evaluate_survey(data.get('answers',{}))})
   if route=='/api/assessment':
    self.require('student');p=get_saved('profiles',uid);a=get_saved('answers',uid);schools=read_schools(str(p.get('region','')),limit=100)
    result=assess(p,a,schools);return self.send(200,{'assessment':result})
   if route=='/api/v2/plan/generate':
    self.require('student')
    p=get_saved('profiles',uid);plan=get_saved('plans',uid)
    # Accept optional week hours in preview; do not write to DB automatically.
    proposed=dict(plan)
    if 'weeklyHours' in data:
     n=float(data['weeklyHours'])
     if not 1<=n<=50:raise ValueError('주간 학습시간은 1~50시간이어야 합니다.')
     proposed['weeklyHours']=n
    start=data.get('start')
    result=make_12week_plan(p,proposed,start)
    return self.send(200,{'preview':result})
   if route=='/api/v2/ai':
    self.require('student')
    if not data.get('externalConsent'):raise ValueError('외부 AI로 최소화한 학습 정보와 질문을 전송하는 데 동의해야 합니다.')
    mode=str(data.get('mode',''))
    if mode not in MODE_MAP:raise ValueError('정의되지 않은 AI 분석 종류입니다.')
    question=str(data.get('question','')).strip()
    if len(question)>2500:raise ValueError('질문은 2,500자 이하만 가능합니다.')
    if not provider_secret('openai'):raise ValueError('AI Secret Key가 연결되지 않았습니다. 관리자 API 설정에서 키를 등록해 주세요.')
    with AI_LOCK:
     now=time.time()
     if now-AI_LAST.get(uid,0)<8:raise ValueError('AI 요청은 8초 이상 간격으로 실행하세요.')
     with db() as c:daily=c.execute("SELECT COUNT(*) FROM ai_history WHERE user_id=? AND created>=?",(uid,datetime.now(timezone.utc).strftime('%Y-%m-%d')+'T00:00:00')).fetchone()[0]
     if daily>=35:raise ValueError('하루 35회 분석 한도입니다. API 비용 보호를 위한 설정입니다.')
     AI_LAST[uid]=now
    profile=get_saved('profiles',uid);plan=get_saved('plans',uid)
    snapshot=payload_for_ai(profile,plan,question,mode)
    if not AI_CAPACITY.acquire(timeout=15):
     raise CapacityError('AI 분석 요청이 집중되고 있습니다. 잠시 뒤 다시 시도해 주세요 (동시 실행 제한).')
    api_started=time.monotonic()
    try:
     result=call_openai(mode,snapshot)
    except Exception:
     track_api('openai',mode,'error',time.monotonic()-api_started)
     raise
    finally:
     AI_CAPACITY.release()
    track_api('openai',mode,'success',time.monotonic()-api_started,result.get('usage'))
    created=NOW()
    with db() as c:
     c.execute('INSERT INTO ai_history(user_id,mode,question,answer,model,created) VALUES(?,?,?,?,?,?)',(uid,mode,question[:2500],result['answer'],result['model'],created))
    audit(uid,'ai-'+mode)
    return self.send(200,{'result':result, 'created':created,'sentFields':list(snapshot.keys()),
         'disclaimer':'생성형 AI의 답변은 공식 모집요강이나 합격 판정이 아닙니다. 사실과 자격요건은 최종 원문으로 검증해야 합니다.'})
   if route=='/api/plan/save':
    self.require('student');plan=data.get('plan',{});cal=validate_calendar(plan.get('calendar',[]),plan.get('weeklyHours',0));
    if len(cal['issues'])>20:raise ValueError('계획 오류가 많습니다. 시간·날짜를 확인하세요.')
    save('plans',uid,plan);return self.send(200,{'ok':True,'calendarReview':cal})
   if route=='/api/plan/review':
    self.require('student');plan=data.get('plan',get_saved('plans',uid));result=review_plan(plan,get_saved('profiles',uid));result['calendar']=validate_calendar(plan.get('calendar',[]),plan.get('weeklyHours',0))
    if data.get('useLLM'):
     if not data.get('externalConsent'):raise ValueError('외부 AI로 학습계획만 전송하는 데 명시적으로 동의해야 합니다.')
     try:result['aiReview']=llm_review(plan)
     except Exception as e:result['aiError']=str(e)
    return self.send(200,{'review':result})
   if route=='/api/cases/submit':
    self.require('student');p=get_saved('profiles',uid);a=get_saved('answers',uid)
    if not p.get('mode'):raise ValueError('학생정보와 진학목적을 먼저 입력하세요.')
    report=assess(p,a,read_schools(str(p.get('region','')),limit=100) or reference_schools(str(p.get('region',''))));report['longitudinal']=longitudinal(p,report,get_saved('plans',uid));report['planSnapshot']=get_saved('plans',uid)
    # Only the counselor gets these educational notes and only with explicit per-case consent.
    report['recordSummary']={'middleAssessments':p.get('middleAssessments',{}),
       'highGrades':p.get('highGrades',[]),'gradeSystem':p.get('gradeSystem','5'),
       'schoolRecords':p.get('studentRecords',[]) if data.get('includeRecords') is True else [],
       'recordPermission':bool(data.get('includeRecords') is True)}
    report['studentRequest']={'questions':str(data.get('message',''))[:1500],
        'priority':str(data.get('priority','일반'))[:30],
        'targetSchool':str(p.get('targetSchool',''))[:120],
        'targetMajor':str(p.get('targetMajor',''))[:120]}
    with db() as c:
     cur=c.execute('INSERT INTO cases(user_id,status,auto_report,created,updated,student_message) VALUES(?,?,?,?,?,?) RETURNING id',(uid,'pending',json.dumps(report,ensure_ascii=False),NOW(),NOW(),str(data.get('message',''))[:1500]));cid=cur.fetchone()[0]
    audit(uid,'submit-case-'+str(cid));return self.send(201,{'ok':True,'id':cid})
   if route.startswith('/api/admin/cases/') and route.endswith('/publish'):
    self.require('admin');cid=int(route.split('/')[-2]);report=data.get('report',{})
    if not isinstance(report,dict) or len(str(report.get('summary','')).strip())<80 or len(str(report.get('school','')).strip())<30:raise ValueError('상담 품질 확인: 종합 의견 80자 이상, 학교·전형 검토 30자 이상을 작성하세요.')
    with db() as c:
     if not c.execute('SELECT id FROM cases WHERE id=?',(cid,)).fetchone():raise ValueError('상담 접수 건이 없습니다.')
     c.execute("UPDATE cases SET status='published',admin_report=?,admin_note=?,updated=? WHERE id=?",(json.dumps(report,ensure_ascii=False),str(data.get('note',''))[:1000],NOW(),cid))
    audit(uid,'publish-case-'+str(cid));return self.send(200,{'ok':True,'message':'학생 마이페이지로 최종 컨설팅 결과지를 발송했습니다.'})
   if route.startswith('/api/admin/cases/') and route.endswith('/note'):
    self.require('admin');cid=int(route.split('/')[-2]);status=data.get('status','reviewing')
    if status not in ['reviewing','pending']:raise ValueError('잘못된 상태')
    with db() as c:c.execute('UPDATE cases SET status=?,admin_note=?,updated=? WHERE id=?',(status,str(data.get('note',''))[:1500],NOW(),cid))
    return self.send(200,{'ok':True})
   if route=='/api/admin/assign-node':
    self.require('admin')
    if NODE_COUNT==1:raise ValueError('단일 서버에서는 조 배정이 필요하지 않습니다.')
    target=int(data.get('userId',0));dest=int(data.get('nodeId',0))
    if target<=0 or not 1<=dest<=NODE_COUNT:raise ValueError('학생과 배정할 서버 번호를 확인하세요.')
    with db() as c:
     if IS_POSTGRES:c.execute('SELECT pg_advisory_xact_lock(7222271002)')
     candidate=c.execute("SELECT id FROM users WHERE id=? AND role='student'",(target,)).fetchone()
     if not candidate:raise ValueError('학생 계정이 없습니다.')
     current=c.execute('SELECT node_id FROM student_nodes WHERE user_id=?',(target,)).fetchone()
     if not current or current['node_id']!=dest:
      n=c.execute('SELECT COUNT(*) FROM student_nodes WHERE node_id=?',(dest,)).fetchone()[0]
      if n>=NODE_CAPACITY:raise PermissionError('해당 조 정원이 가득 찼습니다.')
     c.execute('INSERT INTO student_nodes(user_id,node_id,created) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET node_id=excluded.node_id,created=excluded.created',(target,dest,NOW()))
    audit(uid,'assign-node-'+str(target))
    return self.send(200,{'ok':True,'userId':target,'nodeId':dest})
   if route=='/api/admin/import':
    self.require('admin');kind=data.get('kind')
    if kind not in ('schools','admissions'):raise ValueError('자료 형식 확인')
    count=import_csv(kind,data.get('csv',''),data.get('source',''))
    audit(uid,'import-'+kind+'-'+str(count));return self.send(200,{'imported':count,'notice':'출처가 등록되었지만 개별 학교 전형의 원문 검증이 완료된 것은 아닙니다.'})
   if route=='/api/account/delete':
    self.require('student');pw=str(data.get('password',''))
    with db() as c:
     row=c.execute('SELECT password FROM users WHERE id=?',(uid,)).fetchone()
     if not check_pw(pw,row['password']):raise PermissionError('비밀번호 확인 실패')
     for table in ('profiles','answers','plans','ai_history'):c.execute(f'DELETE FROM {table} WHERE user_id=?',(uid,))
     c.execute('DELETE FROM cases WHERE user_id=?',(uid,));c.execute('DELETE FROM student_nodes WHERE user_id=?',(uid,));c.execute('DELETE FROM users WHERE id=?',(uid,))
    audit(uid,'delete-account');return self.send(200,{'ok':True},{'Set-Cookie':'pf_session=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/'})
   raise ValueError('지원하지 않는 요청')
  except PermissionError as ex:self.send(403,{'error':str(ex)})
  except CapacityError as ex:self.send(429,{'error':str(ex)})
  except Exception as ex:
   # Programmer/network/SQL exceptions never reveal internal paths, connection strings or credentials.
   if isinstance(ex,(ValueError,CapacityError)):self.send(400,{'error':str(ex)})
   else:self.send(503 if PUBLIC_MODE else 400,{'error':'요청을 처리할 수 없습니다. 잠시 후 다시 시도하거나 관리자에게 문의하세요.' if PUBLIC_MODE else str(ex)})

if __name__=='__main__':
 verify_online_launch();init_db()
 print('PATHFINDER EDU '+('Render pilot' if PUBLIC_MODE else 'local')+f' listening on {HOST}:{PORT}',flush=True)
 server=ThreadingHTTPServer((HOST,PORT),Handler)
 server.daemon_threads=True
 server.serve_forever()
