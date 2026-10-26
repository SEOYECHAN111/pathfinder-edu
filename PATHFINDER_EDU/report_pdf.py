"""Korean PDF output: native reportlab layout, font fallback, multi-page, simple charts."""
import io,os
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab import platypus as P
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm


def korean_font():
 for f in [Path('C:/Windows/Fonts/malgun.ttf'),Path('/usr/share/fonts/truetype/nanum/NanumGothic.ttf'),Path('/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf')]:
  if f.exists():
   try:
    if 'PFHangul' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('PFHangul',str(f)))
    return 'PFHangul'
   except Exception:pass
 try:
  if 'HYGothic-Medium' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(UnicodeCIDFont('HYGothic-Medium'))
  return 'HYGothic-Medium'
 except Exception:return 'Helvetica'

class Bar(P.Flowable):
 def __init__(self,name,value,note,font):P.Flowable.__init__(self);self.width=490;self.height=48;self.name=name;self.value=value;self.note=note;self.font=font
 def draw(self):
  c=self.canv;c.setFont(self.font,10);c.setFillColor(colors.HexColor('#1B3550'));c.drawString(0,30,self.name)
  pct=None if self.value is None else max(0,min(100,float(self.value)))
  c.setFont(self.font,9);c.drawRightString(480,30, '자료 없음' if pct is None else str(round(pct))+'%')
  c.setFillColor(colors.HexColor('#E6EDF2'));c.roundRect(0,17,480,8,4,fill=1,stroke=0)
  if pct is not None:c.setFillColor(colors.HexColor('#087B9B'));c.roundRect(0,17,480*pct/100,8,4,fill=1,stroke=0)
  c.setFillColor(colors.HexColor('#637587'));c.setFont(self.font,7.5);c.drawString(0,2,str(self.note)[:110])


def build_pdf(pack):
 font=korean_font();raw=io.BytesIO();doc=P.SimpleDocTemplate(raw,pagesize=(210*mm,297*mm),rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm,title='PATHFINDER EDU 상담결과지',author='PATHFINDER EDU')
 styles={
  'title':ParagraphStyle('PFTitle',fontName=font,fontSize=19,leading=30,textColor=colors.HexColor('#142F4B'),spaceAfter=16,wordWrap='CJK'),
  'heading':ParagraphStyle('PFH',fontName=font,fontSize=12,leading=20,textColor=colors.HexColor('#125470'),spaceBefore=18,spaceAfter=7,wordWrap='CJK'),
  'body':ParagraphStyle('PFB',fontName=font,fontSize=9.5,leading=16,spaceAfter=7,wordWrap='CJK'),
  'small':ParagraphStyle('PFS',fontName=font,fontSize=8,leading=12,textColor=colors.HexColor('#5C6C7B'),spaceAfter=6,wordWrap='CJK')}
 def para(x,style='body'):return P.Paragraph(escape(str(x)).replace('\n','<br/>'),styles[style])
 def block(title,items):
  story.append(para(title,'heading'))
  for x in items:story.append(para('• '+str(x)))
 auto=pack.get('auto') or {};ad=pack.get('admin') or {};case=pack.get('case') or {};user=pack.get('student') or {};lon=auto.get('longitudinal',{});plan=auto.get('planSnapshot',{})
 story=[para('PATHFINDER EDU | 개인별 진학 컨설팅 결과지','title'),para('보고서 번호: '+str(case.get('id',''))+'  |  상담 상태: '+str(case.get('status','')),'small'),para('학생: '+str(user.get('display_name',''))+'  |  분석 목적: '+str(auto.get('mode',''))),para('이 보고서는 입학 확정 판단이나 합격확률 증명이 아닙니다.','small')]
 story.append(para('학업·진로·계획 그래프','heading'))
 for key,obj in (lon.get('dimensions') or {}).items():story.append(Bar(key,obj.get('pct'),obj.get('basedOn',''),font))
 story.append(para('그래프는 자료 충실도·실제 일정 수행률을 보여주며, 합격확률을 뜻하지 않습니다.','small'))
 story.append(para('현재 추천 경로','heading'))
 for r in auto.get('recommendations',[])[:12]:story.append(para(f"• {r.get('name','')}: {r.get('reason','')}"))
 block('관심 분야·학과 후보',auto.get('fieldOptions',[]))
 record=auto.get('recordSummary') or {}
 evals=list((record.get('middleAssessments') or {}).items())
 if evals or record.get('highGrades'):
  story.append(para('입력된 성취도·등급 기록(원점수 환산 없음)','heading'))
  for name,v in evals[:50]:story.append(para(f"• {name} · {v.get('kind','')} · {v.get('value','')}"))
  for row in (record.get('highGrades') or [])[:50]:story.append(para(f"• {row.get('semester','')} {row.get('subject','')} · 등급 {row.get('grade','미기재')} · 성취도 {row.get('achievement','미기재')}"))
 gr=auto.get('grades',{}) or {};sub=gr.get('subjects',[])
 if sub:
  story.append(para('입력한 성적 요약','heading'))
  for x in sub:story.append(para(f"• {x.get('subject')} · 최근 {x.get('latest')}점 · 입력 {x.get('count')}회 · 변화 {x.get('change') if x.get('change') is not None else '자료 없음'}"))
 if plan:
  story.append(para('학생이 작성한 목표·주간 일정','heading'))
  for key,title in [('yearly','연간'),('monthly','월간'),('weekly','주간'),('daily','일일')]:
   values=plan.get(key) or []
   if values:story.append(para(title+': '+ ' / '.join(str(v) for v in values[:8])))
  events=plan.get('calendar',[])
  if events:
   story.append(para('최근 등록 일정(최대 20건)','heading'))
   for v in sorted(events,key=lambda x:x.get('date',''))[:20]:story.append(para(f"• {v.get('date','')}  {v.get('title','')}  {v.get('minutes','')}분 {'[완료]' if v.get('done') else ''}"))
 block('공식 전형조건 확인 사항',lon.get('scenarioConditions') or auto.get('warnings',[]))
 story.append(para('개인 합격확률 제공 상태','heading'))
 story.append(para(lon.get('probabilityReason','검증된 입결과 예측모델이 없어 개인 합격확률을 제공하지 않습니다.')))
 story.append(para('관리자 최종 상담','heading'))
 if ad:
  for k,label in [('summary','종합 평가'),('evidence','공식 근거 자료·적용 학년도'),('strengths','학생의 강점'),('risks','보완 위험'),('school','학교·전형·자격'),('goals','진로·학과'),('record','세특·활동 검토'),('study','과목별 학습 처방'),('calendar','12주 실행·일간 계획'),('interview','면접·발표 준비'),('parents','보호자 참고사항'),('nextSteps','즉시 실행해야 할 일'),('followup','재평가와 보완 기준')]:
   if ad.get(k):story.append(para(label,'heading'));story.append(para(ad[k]))
 else:story.append(para('관리자 최종 상담 발행 전입니다.','small'))
 story.append(para('공식 자료 확인 경로','heading'))
 for source in auto.get('sources',[])[:8]:story.append(para(str(source.get('title',''))+' — '+str(source.get('url','')),'small'))
 def header_footer(c,d):
  c.saveState();w,h=d.pagesize;c.setStrokeColor(colors.HexColor('#DFE6ED'));c.line(18*mm,16*mm,w-18*mm,16*mm);c.setFont(font,8);c.setFillColor(colors.HexColor('#637587'));c.drawString(18*mm,12*mm,'PATHFINDER EDU · 비공식 참고용 상담 문서');c.drawRightString(w-18*mm,12*mm,str(d.page));c.restoreState()
 doc.build(story,onFirstPage=header_footer,onLaterPages=header_footer)
 return raw.getvalue()
