'use strict';
/* Student-first experience: intentionally has no admin or API secret controls. */
function start(){
 const p=state.profile,hasGrades=Object.keys(p.middleAssessments||{}).length+(p.highGrades||[]).length,notes=(p.studentRecords||[]).length;
 const cards=[['profile','1','내 정보 입력','학년·지역·관심계열·목표 입학연도를 입력합니다.'],['grades','2','성적 정리','원점수 또는 성취도/등급으로 학교 성적을 입력합니다.'],['studentRecord','3','생기부·세특 기록','과목별 세특, 탐구활동, 동아리·독서기록을 구분해 저장합니다.'],['goals','4','목표 학교 설정','희망 고교·대학과 전공, 통학·기숙사 조건을 설정합니다.'],['aiStudio','5','AI 상세 분석','학업 우선순위·학교 비교·면접·12주 공부 방법을 분석합니다.'],['inbox','6','전문상담원에게 의뢰','실제 상담 담당자가 검토하고 최종 결과지를 발행합니다.']];
 $('pageContent').innerHTML=`<div class="hero-panel banner"><img src="assets/orbit-editorial.webp" alt="푸른 행성과 학습의 미래"><div><div class="eyebrow" style="color:#9cd3e6">YOUR STUDY PATH</div><h1>${esc(state.user.display_name)}님의 진학 설계를 시작합니다.</h1><p>성적 입력부터 AI 분석, 상담원 검토, 매주 학습계획까지 순서대로 진행하세요.</p></div></div>
 <div class="milestone-grid"><div class="milestone"><small>현재 학년</small><strong>${esc(p.grade||'미입력')}</strong></div><div class="milestone"><small>성적 기록</small><strong>${hasGrades}개</strong></div><div class="milestone"><small>생기부·세특</small><strong>${notes}개</strong></div><div class="milestone"><small>목표 학교</small><strong>${esc((p.targetSchool||'설정 전').slice(0,18))}</strong></div></div>
 ${pageHeader('STUDENT WORKFLOW','어떤 순서로 해야 하나요?','아래 버튼을 순서대로 누르면 필요한 정보와 작성 예시가 나타납니다.')}
 <div class="student-steps">${cards.map(([id,no,title,desc])=>`<button class="step-tile" data-jump="${id}"><span class="step-no">${no}</span><div><b>${title}</b><p>${desc}</p></div><span class="step-arrow">→</span></button>`).join('')}</div>
 <div class="notice">AI 분석은 학생 본인이 입력한 자료에 근거하며 실제 합격률을 임의 생성하지 않습니다. 상담원 최종 의견은 관리자 검토·발행 후에만 확인됩니다.</div>`;
 document.querySelectorAll('[data-jump]').forEach(el=>el.onclick=()=>{state.page=el.dataset.jump;render()});
}

function grades(){
 const p=state.profile,mid=courseP(),uni=uniP();if(!p.middleAssessments)p.middleAssessments={};
 const selected=state.gradeTerm||'1-1';
 let section='';
 if(mid){
  section=`<div class="notice"><b>학기 선택 → 과목 → 평가방식 → 결과 입력</b><p style="margin:5px 0 0">원점수는 0~100점, 성취도는 A~E 또는 P, 등급은 1~9입니다. 서로 변환하지 않으며 학교생활기록부에 적힌 방식으로 입력합니다.</p></div>
  <div class="term-tabs">${terms.map(t=>`<button class="tab ${selected===t?'active':''}" data-grade-term="${t}">중${t.replace('-','학년 ')}학기</button>`).join('')}</div>
  <div class="table-wrap"><table class="table record-table"><thead><tr><th>과목</th><th>기록 종류</th><th>성적·성취도</th><th>입력 안내</th></tr></thead><tbody>
  ${subjects.map(sub=>{const saved=p.middleAssessments[selected+'|'+sub]||{};const kind=saved.kind||'score';return `<tr data-mrow="${esc(sub)}"><td><b>${esc(sub)}</b></td><td><select data-middle-kind="${esc(sub)}">${options([['score','원점수 (0~100점)'],['achievement','성취도 (A~E/P)'],['grade','석차등급 (1~9)']],kind)}</select></td><td class="record-val" data-middle-value-slot="${esc(sub)}">${middleInput(sub,kind,saved.value||'')}</td><td><small>${kind==='score'?'점수만 숫자로 입력':kind==='achievement'?'학교 표기 그대로 입력':'1등급~9등급'}</small></td></tr>`}).join('')}
  </tbody></table></div><p class="fieldhint">입력하지 않은 과목은 비워두세요. 자유학기·자유학년은 실제 성적 기재 방식에 따릅니다.</p>`;
 }else if(uni){
  section=`<div class="formgrid"><label>현재 전공<input data-field="major" value="${esc(p.major||'')}"></label><label>총 취득학점<input type="number" data-field="credits" value="${esc(p.credits||'')}"></label><label>GPA<input type="number" step=".01" data-field="gpa" value="${esc(p.gpa||'')}"></label><label>GPA 만점<select data-field="gpaMax">${options(['4.5','4.3','4.0'],p.gpaMax)}</select></label></div>`;
 }else{
  const rows=p.highGrades||(p.highGrades=[]);
  section=`<div class="notice">고교 내신은 <b>석차등급, 성취도, 학점·단위</b>를 각각 기록합니다. 적용되는 5등급제/9등급제는 학년도·과목별로 다를 수 있으므로 실제 성적표 기준을 사용하세요.</div>
  <div class="formgrid"><label>현재 적용되는 주된 석차등급 체계<select data-field="gradeSystem">${options([['5','1~5등급'],['9','1~9등급'],['mix','과목별 상이']],p.gradeSystem||'5')}</select></label></div>
  <div class="table-wrap"><table class="table record-table"><thead><tr><th>학기</th><th>과목</th><th>석차등급</th><th>성취도</th><th>학점·단위</th><th></th></tr></thead><tbody>${rows.map((r,i)=>`<tr><td><input class="long" data-high="${i}" data-highfield="semester" value="${esc(r.semester||'')}" placeholder="예: 고1-1"></td><td><input class="long" data-high="${i}" data-highfield="subject" value="${esc(r.subject||'')}" placeholder="예: 공통수학1"></td><td><select data-high="${i}" data-highfield="grade">${options([['','미기재'],...Array.from({length:9},(_,j)=>[String(j+1),(j+1)+'등급'])],String(r.grade||''))}</select></td><td><select data-high="${i}" data-highfield="achievement">${options([['','미기재'],...['A','B','C','D','E','P'].map(v=>[v,v])],r.achievement||'')}</select></td><td><input type="number" min="1" max="30" data-high="${i}" data-highfield="credits" value="${esc(r.credits||'')}"></td><td><button class="btn alt small" data-delhigh="${i}">삭제</button></td></tr>`).join('')}</tbody></table></div>
  <button class="btn alt" id="addHigh" style="margin-top:14px">+ 과목 성적 추가</button><p class="fieldhint">내신 등급과 수능 모의고사 등급은 구분해서 관리합니다. 자료가 없으면 공란으로 두세요.</p>`;
 }
 $('pageContent').innerHTML=`${pageHeader('STEP 02 · GRADE RECORD','학기별 성적·성취도 입력','성적표에 있는 종류대로 기록합니다. 모르는 항목은 비워도 됩니다.')}
 <section class="card airy">${section}<div class="formgrid"><label class="stretch">성적 변화 설명 · 시험 결과에 영향을 준 이유<textarea data-field="gradesNote" maxlength="1500" placeholder="예: 2학년 2학기에 수학 개념학습이 부족해서 오답이 늘었음. 단원별 복습 후 보완 중.">${esc(p.gradesNote||'')}</textarea></label></div>
 <div class="footer-actions"><button class="btn alt" id="gradePrev">이전: 기본정보</button><button class="btn" id="gradeSave">성적 저장 후 생기부 입력 →</button></div><p class="fieldhint">원점수와 성취도, 석차등급은 같은 척도로 바꿔 계산하지 않습니다. 합격확률을 의미하지 않습니다.</p></section>`;
 bindProfile();
 document.querySelectorAll('[data-grade-term]').forEach(x=>x.onclick=()=>{state.gradeTerm=x.dataset.gradeTerm;grades()});
 document.querySelectorAll('[data-middle-kind]').forEach(x=>x.onchange=()=>{
  const sub=x.dataset.middleKind,k=selected+'|'+sub;
  p.middleAssessments[k]={kind:x.value,value:''};
  if(p.middleGrades?.[sub])p.middleGrades[sub][terms.indexOf(selected)]='';
  document.querySelector(`[data-middle-value-slot="${sub}"]`).innerHTML=middleInput(sub,x.value,'');
  bindMiddleInputs();
 });
 bindMiddleInputs();
 document.querySelectorAll('[data-high]').forEach(x=>x.onchange=()=>{const i=+x.dataset.high;p.highGrades[i][x.dataset.highfield]=x.value});
 document.querySelectorAll('[data-delhigh]').forEach(x=>x.onclick=()=>{p.highGrades.splice(+x.dataset.delhigh,1);grades()});
 if($('addHigh'))$('addHigh').onclick=()=>{p.highGrades.push({semester:'고1-1',subject:'',grade:'',achievement:'',credits:''});grades()};
 $('gradePrev').onclick=()=>{state.page='profile';render()};
 $('gradeSave').onclick=async()=>{try{await api('/api/profile/save',{profile:p});state.page='studentRecord';render();alertx('성적을 저장했습니다.')}catch(e){error(e)}};
 function bindMiddleInputs(){document.querySelectorAll('[data-mvalue]').forEach(x=>x.onchange=()=>{const sub=x.dataset.mvalue,k=selected+'|'+sub;const kind=p.middleAssessments[k]?.kind||'score';if(!x.value){delete p.middleAssessments[k]}else{p.middleAssessments[k]={kind,value:x.value}};let arr=p.middleGrades[sub]||Array(6).fill('');arr[terms.indexOf(selected)]=kind==='score'?x.value:'';p.middleGrades[sub]=arr;});}
}
function middleInput(subject,kind,value){
 if(kind==='score')return `<input aria-label="${esc(subject)} 원점수" type="number" min="0" max="100" step=".1" data-mvalue="${esc(subject)}" value="${esc(value)}" placeholder="예: 86">`;
 return `<select data-mvalue="${esc(subject)}" aria-label="${esc(subject)} ${kind==='grade'?'등급':'성취도'}">${options([['','선택'],...(kind==='achievement'?['A','B','C','D','E','P'].map(v=>[v,v]):Array.from({length:9},(_,i)=>[String(i+1),(i+1)+'등급']))],value)}</select>`;
}

function studentRecord(){
 const p=state.profile,records=p.studentRecords||(p.studentRecords=[]);
 const categories=['세특','창의적 체험활동','동아리','진로활동','자율활동','독서','수상·탐구','기타'];
 $('pageContent').innerHTML=`${pageHeader('STEP 03 · SCHOOL LIFE RECORD','생활기록부·세특 정리','과목별 관찰 사실과 탐구 과정, 교내 활동을 나눠 기록하세요.')}
 <div class="notice"><b>왜 작성하나요?</b> AI 학업상담에서 활동의 방향을 정리하고, 전문상담원이 강점·보완점을 검토할 때 참고하기 위해서입니다. 여기에는 실제 학교생활기록부에 존재하는 사실만 적으세요. 교사·친구 등 제3자의 개인정보는 제외하세요.<p style="margin:7px 0 0">세특 원문은 외부 OpenAI 분석 API로 자동 전송하지 않습니다. 상담원에게 전달할 때는 상담 의뢰 화면에서 별도로 동의해야 합니다.</p></div>
 <div class="card airy"><div class="row between"><h3>내가 저장한 생기부·활동 기록 (${records.length}건)</h3><button class="btn alt" id="recordAdd">+ 기록 추가</button></div>
 <div id="recordList">${records.map((r,i)=>`<article class="record-item"><div class="row between"><b>${i+1}. ${esc(r.category)} · ${esc(r.subject||'과목 미설정')}</b><button class="btn alt small" data-record-remove="${i}">삭제</button></div><div class="formgrid"><label>구분<select data-record="${i}" data-recordfield="category">${options(categories,r.category||'세특')}</select></label><label>과목·활동 이름<input data-record="${i}" data-recordfield="subject" value="${esc(r.subject||'')}" placeholder="예: 물리학 / 과학동아리"></label><label>학기<input data-record="${i}" data-recordfield="semester" value="${esc(r.semester||'')}" placeholder="예: 중3-1 / 고1-2"></label><label>증빙·출처(선택)<input data-record="${i}" data-recordfield="evidence" value="${esc(r.evidence||'')}" maxlength="800" placeholder="예: 실험보고서, 학생부 기재"></label><label class="stretch">세특·활동 상세 내용<textarea data-record="${i}" data-recordfield="content" maxlength="2500" rows="5" placeholder="탐구 주제 → 본인 역할 → 자료·방법 → 실제 결과 → 배운 점을 사실대로 적으세요.">${esc(r.content||'')}</textarea></label></div></article>`).join('')||'<div class="empty">아직 기록이 없습니다. + 기록 추가를 눌러 세특·동아리·독서 등을 작성하세요.</div>'}</div>
 <div class="notice">작성 예시: ‘물체의 비행거리에 영향을 미치는 요인을 조사하며, 동일한 질량 조건에서 날개 면적을 바꾼 실험을 5회 진행하고 평균값과 오차 원인을 비교함.’ 실제 수행하지 않은 활동은 작성하지 마세요.</div>
 <div class="footer-actions"><button class="btn alt" id="recordBack">이전: 성적</button><button class="btn" id="recordSave">생기부 저장 후 목표 설정 →</button></div></div>`;
 $('recordAdd').onclick=()=>{if(records.length>=35)return alertx('기록은 최대 35건까지 저장합니다.');records.push({category:'세특',subject:'',semester:'',content:'',evidence:''});studentRecord()};
 document.querySelectorAll('[data-record]').forEach(el=>el.oninput=()=>{records[+el.dataset.record][el.dataset.recordfield]=el.value});
 document.querySelectorAll('[data-record-remove]').forEach(el=>el.onclick=()=>{if(confirm('기록을 삭제하시겠습니까?')){records.splice(+el.dataset.recordRemove,1);studentRecord()}});
 $('recordBack').onclick=()=>{state.page='grades';render()};
 $('recordSave').onclick=async()=>{try{await api('/api/profile/save',{profile:p});state.page='goals';render();alertx('생기부 기록을 저장했습니다.')}catch(e){error(e)}};
}

async function inbox(){
 try{state.cases=(await api('/api/me/cases')).cases}catch(e){error(e)}
 const statuses={pending:['접수 완료','AI·규칙 기초진단 결과가 접수되고 상담원 검토를 기다리고 있습니다.'],reviewing:['전문상담원 검토 중','담당자가 자료를 확인해 학교·진로·학습 처방을 작성하고 있습니다.'],published:['상담 결과 도착','담당자 검토가 완료돼 상세 상담 결과지를 확인할 수 있습니다.']};
 $('pageContent').innerHTML=`${pageHeader('EXPERT REVIEW','전문상담원에게 분석 의뢰','AI 초안과 기록을 바탕으로 담당 상담원이 검토한 뒤 결과지를 발행합니다.')}
 <div class="flow-steps"><div><b>01 · 정보 정리</b><small>성적·목표·세특 확인</small></div><div><b>02 · 기초 분석</b><small>서버에서 자료 요약</small></div><div><b>03 · 상담원 검토</b><small>관리자가 사실관계 확인</small></div><div><b>04 · 최종 발행</b><small>결과지 PDF·DOCX</small></div></div>
 <section class="card airy"><h3>새로운 심층 상담 신청</h3><p class="muted">다음 중 구체적으로 상담받고 싶은 내용을 적어주세요. 정확한 결과를 위해 목표 학교·학기와 현재 고민을 함께 적는 것이 좋습니다.</p>
 <label>상담 주제<select id="consultPriority"><option>종합 진학전략</option><option>고등학교 학교 유형 비교</option><option>대학·학과 장기 목표</option><option>학습시간·오답·주간 계획</option><option>생기부 세특·탐구 방향</option><option>면접 및 자기소개 준비</option><option>지원자격·모집요강 확인</option></select></label>
 <label style="margin-top:12px">상담원에게 전달할 자세한 질문<textarea id="consultMessage" rows="7" maxlength="1500" placeholder="예: 현재 중3이고 목표는 ○○고입니다. 수학 성취도 A, 과학 B이며 탐구활동은 ○○입니다. 지원자격과 부족한 과목, 12주 학습 우선순위, 면접 준비를 구체적으로 검토해주세요."></textarea></label>
 <label class="check"><input type="checkbox" id="consultRecordConsent"><span>선택: 작성한 세특·학교활동 원문을 이 상담 건의 담당 관리자에게 전달하는 데 동의합니다. 동의하지 않으면 상담원은 세특 원문을 받지 않습니다. 외부 AI API로 전송하는 동의가 아닙니다.</span></label>
 <div id="consultProgress" role="status" aria-live="polite"></div><div class="footer-actions"><button class="btn" id="consultSubmit">전문상담원에게 심층 분석 의뢰하기</button></div>
 <p class="fieldhint">상담은 자동 발행되지 않습니다. 실제 관리자가 결과를 검토·발행해야 학생에게 도착합니다.</p></section>
 <section class="card airy" style="margin-top:20px"><div class="row between"><h3>내 상담 신청 및 처리 현황</h3><button class="btn alt small" id="consultRefresh">새로고침</button></div>
 <div>${state.cases.length?state.cases.map(c=>{const st=statuses[c.status]||statuses.pending;return `<div class="case-row"><div><b>상담 #${c.id} · ${st[0]}</b><p class="fieldhint">${st[1]}<span style="display:block">접수: ${esc(c.created)} · 최근 변경: ${esc(c.updated)}</span></p></div><div class="row"><button class="btn alt small" data-consult-detail="${c.id}">상세</button>${c.status==='published'?`<a class="btn small" href="/api/download/${c.id}.pdf">PDF</a><a class="btn alt small" href="/api/download/${c.id}.docx">DOCX</a>`:''}</div></div>`}).join(''):'<div class="empty">아직 제출한 상담이 없습니다. 위에서 첫 상담을 신청하세요.</div>'}</div><div id="consultDetail"></div></section>`;
 $('consultRefresh').onclick=inbox;
 $('consultSubmit').onclick=async()=>{
  const btn=$('consultSubmit'),progress=$('consultProgress');if(btn.disabled)return;
  const msg=$('consultMessage').value.trim();if(msg.length<12)return alertx('상담 목적과 질문을 12자 이상 작성해주세요.');
  btn.disabled=true;progress.innerHTML='<div class="live-progress"><span class="spin-circle"></span><div><b>접수 준비 중 · 입력 기록 확인</b><small>성적·학습계획·상담 질문을 저장하고 있습니다.</small></div></div>';
  try{
   await api('/api/profile/save',{profile:state.profile});
   await api('/api/answers/save',{answers:state.answers});
   await api('/api/plan/save',{plan:state.plan});
   progress.innerHTML='<div class="live-progress"><span class="spin-circle"></span><div><b>기초 분석 중 · 목표와 성적 검토</b><small>자료를 기반으로 상담원 검토용 진단을 생성하고 있습니다.</small></div></div>';
   const r=await api('/api/cases/submit',{message:msg,priority:$('consultPriority').value,includeRecords:$('consultRecordConsent').checked});
   progress.innerHTML=`<div class="done-progress"><b>✓ 기초 분석 완료 · 상담 #${r.id} 접수</b><p>다음 단계는 전문상담원의 실제 검토입니다. 상담원이 발행하면 결과지와 다운로드 버튼이 나타납니다.</p></div>`;
   alertx('상담 의뢰가 정상 접수되었습니다.');
   setTimeout(()=>{inbox()},3000);
  }catch(e){progress.innerHTML='<div class="notice warn">분석을 접수하지 못했습니다. '+esc(e.message)+'</div>';error(e)}finally{btn.disabled=false}
 };
 document.querySelectorAll('[data-consult-detail]').forEach(el=>el.onclick=async()=>{
  try{const r=await api('/api/cases/'+el.dataset.consultDetail),c=r.case,report=JSON.parse(c.admin_report||'{}'),a=JSON.parse(c.auto_report||'{}');
   $('consultDetail').innerHTML=`<div class="soft" style="margin-top:18px"><h3>상담 #${c.id} · 처리 기록</h3><p>분석 목적: ${esc(a.mode)} · 상담 주제: ${esc(a.studentRequest?.priority||'종합')}</p><p>현재 상태: <b>${esc(statuses[c.status]?.[0]||c.status)}</b></p>${c.status==='published'?Object.entries(report).map(([k,v])=>`<article class="source"><b>${esc(({summary:'종합 상담 결과',school:'학교·전형 검토',goals:'진로·학과 목표',study:'학습전략',nextSteps:'실행해야 할 일',evidence:'공식 자료 검증',strengths:'강점·기회',risks:'위험·불확실성',record:'세특·활동 분석',interview:'면접 준비',calendar:'12주 계획',parents:'보호자 안내',followup:'재상담 조건'})[k]||k)}</b><p style="white-space:pre-wrap">${esc(v)}</p></article>`).join(''):'<p class="fieldhint">상담원의 최종 문서는 아직 발행되지 않았습니다. 관리자 검토 없이 완료로 표시하지 않습니다.</p>'}</div>`;
  }catch(e){error(e)}
 });
}

async function editor(){const cid=state.adminCaseId;if(!cid){state.page='queue';return render()}
 try{
  const resp=await api('/api/cases/'+cid),c=resp.case,a=JSON.parse(c.auto_report||'{}'),r=JSON.parse(c.admin_report||'{}'),sr=a.recordSummary||{};
  const fields=[['summary','1. 종합 평가 · 핵심 결론'],['evidence','2. 확인한 원문 자료 및 적용 학년도'],['strengths','3. 학생의 입증된 강점과 경험'],['risks','4. 성적·지원요건·학습상의 위험'],['school','5. 목표 학교·전형·지원자격 검증'],['goals','6. 진로·학과와 대체 경로'],['record','7. 세특·교과/비교과 활동 연결 분석'],['study','8. 과목별 구체 공부법 · 부족 단원'],['calendar','9. 12주 실행표 · 주간·일간 실천'],['interview','10. 면접·자기소개 준비'],['parents','11. 보호자 안내와 지원 방법'],['nextSteps','12. 학생이 바로 시작할 우선 과제'],['followup','13. 재평가 시점·변화 측정 지표']];
  $('pageContent').innerHTML=`${pageHeader('COUNSELOR ONLY','상담 #'+cid+' · 전문상담원 심층 검토','원문 근거, 불확실성, 개인별 실행전략을 구분해서 작성해야 최종 발행할 수 있습니다.')}
  <div class="cols"><section class="card"><h3>학생이 제출한 상담 의뢰</h3><div class="source"><b>상담 주제</b><p>${esc(a.studentRequest?.priority||'미지정')}</p></div><div class="source"><b>학생 질문</b><p style="white-space:pre-wrap">${esc(c.student_message||a.studentRequest?.questions||'')}</p></div><div class="source"><b>목표 학교·전공</b><p>${esc(a.studentRequest?.targetSchool||'미정')} · ${esc(a.studentRequest?.targetMajor||'미정')}</p></div><div class="source"><b>학업 기록</b><p>중학교 척도별 성적 ${Object.keys(sr.middleAssessments||{}).length}건 · 고교 성적 ${(sr.highGrades||[]).length}건</p>${Object.entries(sr.middleAssessments||{}).slice(0,55).map(([name,v])=>`<div class="source"><small>${esc(name)} · ${esc(v.kind)} ${esc(v.value)}</small></div>`).join('')}${(sr.highGrades||[]).slice(0,30).map(v=>`<div class="source"><small>${esc(v.semester)} ${esc(v.subject)} · 등급 ${esc(v.grade||'미기재')} / 성취도 ${esc(v.achievement||'미기재')} / 학점 ${esc(v.credits||'미기재')}</small></div>`).join('')}</div>
  <h3>교과 세특·활동 원문</h3>${sr.recordPermission?((sr.schoolRecords||[]).length?(sr.schoolRecords||[]).map(v=>`<div class="source"><b>${esc(v.category)} · ${esc(v.subject)}</b><small>${esc(v.semester)}</small><p style="white-space:pre-wrap">${esc(v.content)}</p><small>${esc(v.evidence)}</small></div>`).join(''):'<p>학생이 전송을 허용했지만 기록은 없습니다.</p>'):'<div class="notice">학생이 이 상담 건에 세특 원문 전송을 동의하지 않았습니다. 원문은 상담원에게 제공되지 않습니다.</div>'}
  <div class="divider"></div><h3>규칙 기반 분석 초안</h3><p>${esc(a.mode)} · ${esc(a.area)}</p>${(a.warnings||[]).slice(0,18).map(x=>`<p>• ${esc(x)}</p>`).join('')}
  <p class="notice">이 자료는 현재 학생에게만 귀속된 상담 건입니다. 원문을 다른 학생에게 공유하지 마세요.</p></section>
  <section class="card"><h3>전문상담원 최종 결과지 작성</h3><p class="fieldhint">각 항목은 확인한 사실과 해석, 다음 행동, 근거 URL 및 학년도 등을 적어 주세요. 미확인 부분은 확인 필요로 표시하세요.</p>
  <form id="fullReport" class="group">${fields.map(([key,title])=>`<label>${title}<textarea name="${key}" rows="5" maxlength="13000" placeholder="구체적인 근거·학년도·과목·단계·실행시간·검증방법을 적으세요.">${esc(r[key]||'')}</textarea></label>`).join('')}
  <label>학생에게 보이는 상담 진행 메모<input name="note" maxlength="1000" value="${esc(c.admin_note||'')}" placeholder="예: 전형 요강 원문 확인 중"></label><div class="row"><button class="btn alt" id="saveReview" type="button">검토 중 표시</button><button class="btn" type="submit">최종 결과지 발행하기</button></div>
  <p class="fieldhint">최종 발행 후 학생이 본인 결과만 열람·PDF 저장할 수 있습니다. 상담 근거가 부족한 경우 발행하지 마세요.</p></form></section></div>`;
  $('saveReview').onclick=async()=>{try{await api('/api/admin/cases/'+cid+'/note',{status:'reviewing',note:document.querySelector('[name="note"]').value});alertx('상태: 전문상담원 검토 중')}catch(e){error(e)}};
  $('fullReport').onsubmit=async(e)=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));const note=data.note;delete data.note;if((data.summary||'').trim().length<80)return alertx('종합 평가를 적어도 80자 이상 구체적으로 작성해주세요.');if((data.school||'').trim().length<30)return alertx('학교·전형 검토를 적어도 30자 이상 작성해주세요.');if(!confirm('실제 검토를 마치고 이 학생에게 최종 문서를 발행하시겠습니까?'))return;try{await api('/api/admin/cases/'+cid+'/publish',{report:data,note});alertx('상담 결과를 학생에게 발행했습니다.');state.page='queue';render()}catch(ex){error(ex)}};
 }catch(e){error(e)}
}
