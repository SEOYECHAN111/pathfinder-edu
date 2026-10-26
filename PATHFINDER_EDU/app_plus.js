'use strict';
/* PATHFINDER PLUS: separate client module, no API keys in browser. */
let pfPlusModes=[];
let pfPlusPreview=[];
const pfPlusSelected=new Map();
async function aiStudio(){
 $('pageContent').innerHTML=`${pageHeader('AI 심층 상담 · 28가지 분야','AI 전문 컨설팅 센터','목표·성적·학습시간을 분석해 전문가 수준의 실행안을 만들되, 학교별 미확인 사실이나 합격 확률을 만들어내지 않습니다.')}
 <div class="notice">학생이 전송에 동의한 경우에만 AI 분석을 시작합니다. 과목별 학업 요약과 직접 입력한 질문을 사용하고 이름·생년월일·세특 원문은 보내지 않습니다. 질문에도 개인정보를 작성하지 마세요.</div>
 <section class="plus-status" id="aiStatus">AI 연결 상태를 확인하고 있습니다.</section>
 <div class="plus-two"><section class="card airy">
 <h3>분석 분야를 골라주세요</h3><p class="fieldhint">궁금한 내용을 직접 적거나 아래 분야를 선택하세요. 전문상담원의 실제 검토를 원하면 ‘전문상담원 상담’ 메뉴를 이용하세요.</p><input id="plusSearch" placeholder="예: 면접, 수학, 학교 비교, 학생부" aria-label="AI 전문가 검색">
 <div class="plus-mode-grid" id="aiModes"></div></section>
 <section class="card airy"><h3 id="aiModeTitle">AI에게 무엇을 분석시킬까요?</h3><p id="aiModeDesc" class="muted"></p>
 <label>상세 질문 / 상담 지시<textarea id="aiQuestion" maxlength="2500" rows="8" placeholder="예: 현재 성적이 목표 학교에 얼마나 부합하고, 3개월 동안 어떤 공부를 우선해야 하는지 자세히 설명해줘. 기말고사는 11월 마지막 주야."></textarea></label>
 <label class="check"><input id="aiConsent" type="checkbox"><span>축약된 학업정보·목표학교·입력한 질문이 외부 OpenAI API로 전송되는 데 동의합니다. API 비용이 발생할 수 있으며, 학교 지원자격과 합격률은 보장되지 않습니다.</span></label>
 <div class="row" style="margin:16px 0"><button class="btn" id="aiRun">선택한 전문가에게 심층 분석 요청</button><button class="btn alt" id="aiLocal">먼저 무료 로컬 진단</button></div><div id="aiFeedback" role="status" aria-live="polite"></div></section></div>
 <section class="card airy" style="margin-top:20px"><div class="row between"><h3>분석 결과</h3><div class="row"><button class="btn alt small" id="aiCopy">결과 복사</button><button class="btn alt small" id="aiText">TXT 저장</button><button class="btn alt small" id="aiPrint">인쇄 · PDF</button></div></div><div id="aiAnswer" class="plus-answer">전문 모드를 선택하고 분석을 요청하면 결과가 표시됩니다.</div></section>
 <section class="card airy" style="margin-top:20px"><div class="row between"><h3>최근 20건 상담 기록</h3><button class="btn alt small" id="aiReload">기록 새로고침</button></div><div id="aiHistory" class="plus-history"></div></section>`;
 let selected='comprehensive';let answer='';
 const title=$('aiModeTitle'),desc=$('aiModeDesc');
 const draw=()=>{const keyword=$('plusSearch').value.trim();$('aiModes').innerHTML=pfPlusModes.filter(m=>!keyword||(m.title+m.description).includes(keyword)).map(m=>`<button data-mode="${esc(m.id)}" class="plus-mode ${selected===m.id?'selected':''}"><strong>${esc(m.title)}</strong><small>${esc(m.description)}</small></button>`).join('')||'<p class="muted">일치하는 모드가 없습니다.</p>';
 document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>{selected=b.dataset.mode;const m=pfPlusModes.find(m=>m.id===selected);title.textContent=m.title;desc.textContent=m.description;draw()})};
 const show=(text)=>{answer=text;$('aiAnswer').textContent=answer};
 $('plusSearch').oninput=draw;
 const history=async()=>{try{const r=await api('/api/v2/ai-history');$('aiHistory').innerHTML=r.history.length?r.history.map((x,i)=>`<button class="plus-history-item" data-history="${i}"><b>${esc(pfPlusModes.find(m=>m.id===x.mode)?.title||x.mode)}</b><span>${esc(x.created)}</span><small>${esc((x.question||'요청 내용 없음').slice(0,75))}</small></button>`).join(''):'<p class="muted">아직 저장된 분석 기록이 없습니다.</p>';document.querySelectorAll('[data-history]').forEach(b=>b.onclick=()=>{const h=r.history[+b.dataset.history];show(h.answer);$('aiQuestion').value=h.question||'';$('aiAnswer').scrollIntoView({behavior:'smooth'})})}catch(e){$('aiHistory').textContent=e.message}};
 $('aiReload').onclick=history;
 try{const r=await api('/api/v2/status');pfPlusModes=r.modes;$('aiStatus').innerHTML=`<b>${r.aiAvailable?'● AI 심층분석 사용 가능':'○ AI 기능 준비 중: 무료 로컬 진단 이용 가능'}</b><span>전국 학교 ${Number(r.nationalSchoolCount).toLocaleString('ko-KR')}개 기반 · 분석의 근거와 한계 안내</span>`;draw();const m=pfPlusModes[0];title.textContent=m.title;desc.textContent=m.description;await history()}catch(e){$('aiStatus').textContent=e.message}
 $('aiRun').onclick=async()=>{if(!$('aiConsent').checked)return alertx('AI 외부 전송 동의가 필요합니다.');const btn=$('aiRun');btn.disabled=true;btn.textContent='분석 요청 처리 중…';$('aiFeedback').innerHTML='<div class="live-progress"><span class="spin-circle"></span><div><b>AI가 학습 기록을 요약해 분석하고 있습니다</b><small>과목별 강점·보완점, 목표 경로와 실행 계획을 작성합니다. 분석이 끝나면 결과가 표시됩니다.</small></div></div>';try{const r=await api('/api/v2/ai',{mode:selected,question:$('aiQuestion').value,externalConsent:true});show(r.result.answer);$('aiFeedback').innerHTML='<div class="done-progress"><b>✓ AI 심층 분석 완료</b><p>아래에서 개인별 분석 결과를 확인하고, 상담원 검토가 필요하면 전문상담 메뉴에서 의뢰할 수 있습니다.</p></div>';history()}catch(e){$('aiFeedback').textContent='실패: '+e.message;error(e)}finally{btn.disabled=false;btn.textContent='선택한 전문가에게 심층 분석 요청'}};
 $('aiLocal').onclick=async()=>{try{const r=await api('/api/v2/offline-analysis');const a=r.analysis;show(`무료 로컬 진단 (AI API 미사용)\n\n목표 학교: ${a.targetSchool}\n희망 전공: ${a.targetMajor}\n\n성적 요약:\n${a.grades.map(x=>`${x.subject}: 최근 ${x.latest}점, 평균 ${x.average}점, 변화 ${x.change===null?'비교 불가':x.change+'점'}`).join('\n')||'점수 입력 전'}\n\n우선 과목: ${a.subjectPriorities.join(' → ')||'성적을 입력하세요'}\n\n일정 실천율: ${a.calendar.completionRate===null?'측정 전':a.calendar.completionRate+'%'}\n\n확인사항:\n${a.issues.map(x=>'• '+x).join('\n')||'미흡 항목이 추가로 발견되지 않았습니다.'}\n\n개인 합격확률: 산출할 수 없음. ${a.admissionProbabilityReason}\n\n* 이 결과는 입력된 수치에 대한 규칙 기반 진단이며 공인 검사나 유료 AI 컨설팅이 아닙니다.`)}catch(e){error(e)}};
 $('aiCopy').onclick=()=>{if(!answer)return alertx('결과가 없습니다.');navigator.clipboard?.writeText(answer).then(()=>alertx('결과가 복사되었습니다.'),()=>alertx('브라우저의 클립보드 권한을 확인하세요.'))};
 $('aiText').onclick=()=>{if(!answer)return alertx('결과가 없습니다.');const blob=new Blob([answer],{type:'text/plain;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='PATHFINDER_AI_분석.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),3000)};
 $('aiPrint').onclick=()=>{if(!answer)return alertx('결과가 없습니다.');window.print()};
}
async function schoolLab(){
 $('pageContent').innerHTML=`${pageHeader('NATIONAL SCHOOL EXPLORER','전국 학교 검색 · 학생 맞춤 후보 비교','공식 위치 데이터와 나이스 API를 구분합니다. 선호 점수는 자체 탐색 기준이며 합격률이 아닙니다.')}
 <div class="notice">학교별 모집요강·교육과정·전년도 합격선이 포함되지 않은 위치 자료입니다. 입학전형 확인 링크: <a target="_blank" rel="noopener" href="https://www.hischool.go.kr/">고입정보포털</a> · <a target="_blank" rel="noopener" href="https://www.adiga.kr/">대입정보포털</a></div>
 <section class="card airy"><div class="formgrid"><label>학교 이름 또는 주소<input id="sQuery" placeholder="예: 과학고, 공업고, 광주"></label><label>지역<input id="sRegion" placeholder="예: 광주 또는 전남" value="${esc(state.profile.region||'')}"></label><label>학교급<select id="sLevel"><option>고등학교</option><option>중학교</option><option>초등학교</option><option>전체</option></select></label></div>
 <div class="row"><button class="btn" id="sFind">공식 학교 DB 검색</button><button class="btn alt" id="sRecommend">내 목표와 맞는 고교 탐색</button><button class="btn alt" id="sNeis">나이스 학교 정보 조회</button></div><p class="muted" id="sCount"></p></section>
 <section class="plus-two"><div class="card airy"><h3>학교 검색 결과</h3><div id="sRows" class="plus-schools"></div><div class="row"><button class="btn alt small" id="sPrev">이전 50개</button><button class="btn alt small" id="sNext">다음 50개</button></div></div>
 <div class="card airy"><h3>내 비교 목록 (최대 4곳)</h3><div id="sCompare">학교를 추가하면 근거 기반 비교표가 생성됩니다.</div><button class="btn alt small" id="sClear">비교 초기화</button><div class="notice" style="margin-top:15px"><b>학교 지원가능성</b><p>지원 자격은 현재 데이터만으로 판정할 수 없습니다. 고입은 학교유형·학생의 지원 지역·교육청 배정 규정, 대입은 대학별 전형과 과목 조건을 확인해야 합니다.</p></div></div></section>`;
 let page=0,total=0,rows=[];
 const compare=()=>{$('sCompare').innerHTML=pfPlusSelected.size?`<div class="table-wrap"><table class="table"><thead><tr><th>학교</th><th>지역·설립</th><th>탐색 적합도*</th><th></th></tr></thead><tbody>${[...pfPlusSelected.values()].map(x=>`<tr><td>${esc(x.name)}<small class="muted">${esc(x.classification)}</small></td><td>${esc(x.region)} / ${esc(x.school_form)}</td><td>${x.heuristic?.score??'미산출'}${x.heuristic?.score!==undefined?'/100':''}</td><td><button class="mini-link" data-remove-school="${esc(x.school_id)}">삭제</button></td></tr>`).join('')}</tbody></table></div><p class="fieldhint">*탐색 점수는 자격·선발 결과의 예측이 아닙니다. 점수가 높아도 지원 불가능할 수 있습니다.</p>`:'<p class="muted">검색 결과에서 학교를 선택해 비교하세요.</p>';document.querySelectorAll('[data-remove-school]').forEach(b=>b.onclick=()=>{pfPlusSelected.delete(b.dataset.removeSchool);compare()})};
 const draw=(recommend=false)=>{$('sCount').textContent=`${total.toLocaleString('ko-KR')}개 검색 결과 · 현재 ${rows.length}개 표시${recommend?' · 학교 선호 점수는 개인 합격률이 아닙니다.':''}`;$('sRows').innerHTML=rows.length?rows.map((x,i)=>`<article class="plus-school"><div class="row between"><b>${esc(x.name)}</b><small>${esc(x.level)}</small></div><p>${esc(x.address)}<br>${esc(x.region)} · ${esc(x.school_form||'설립형태 미확인')} · 운영 상태 ${esc(x.status||'미확인')}</p><small class="muted">${esc(x.classification||'유형 미확인')} · 기준일: ${esc(x.as_of||'미상')}</small>${x.heuristic?`<p class="plus-score">내 탐색 적합도 <strong>${x.heuristic.score}/100</strong> · 지원 가능성과 무관</p><p class="fieldhint">${x.heuristic.components.map(c=>`${esc(c.name)} ${c.points}점`).join(' · ')}</p>`:''}<div class="row"><button class="btn alt small" data-add-school="${i}">학교 비교에 담기</button></div></article>`).join(''):'<p class="muted">일치하는 학교가 없습니다. 지역을 비우거나 검색어를 줄여주세요.</p>';document.querySelectorAll('[data-add-school]').forEach(b=>b.onclick=()=>{const x=rows[+b.dataset.addSchool];if(pfPlusSelected.size>=4&&!pfPlusSelected.has(x.school_id))return alertx('비교는 최대 4개까지 가능합니다.');pfPlusSelected.set(x.school_id,x);compare()})};
 const load=async(recommend)=>{try{let r;if(recommend){r=await api('/api/v2/recommend-schools?region='+encodeURIComponent($('sRegion').value)+'&q='+encodeURIComponent($('sQuery').value)+'&limit=70');rows=r.schools;total=r.count;page=0}else{r=await api('/api/v2/schools?q='+encodeURIComponent($('sQuery').value)+'&region='+encodeURIComponent($('sRegion').value)+'&level='+encodeURIComponent($('sLevel').value)+'&limit=50&offset='+page*50);rows=r.schools;total=r.total};draw(recommend)}catch(e){error(e)}};
 $('sFind').onclick=()=>{page=0;load(false)};$('sRecommend').onclick=()=>{page=0;load(true)};
 $('sPrev').onclick=()=>{if(page>0){page--;load(false)}};$('sNext').onclick=()=>{if((page+1)*50<total){page++;load(false)}};
 $('sClear').onclick=()=>{pfPlusSelected.clear();compare()};
 $('sNeis').onclick=async()=>{if(($('sQuery').value||'').length<2)return alertx('나이스 조회는 학교명 2자 이상이 필요합니다.');try{const r=await api('/api/v2/neis?q='+encodeURIComponent($('sQuery').value));$('sRows').innerHTML=r.schools.length?r.schools.map(x=>`<div class="plus-school"><b>${esc(x.SCHUL_NM)}</b><p>${esc(x.ORG_RDNMA)} · ${esc(x.SCHUL_KND_SC_NM||'')}</p><small>나이스 코드: ${esc(x.SD_SCHUL_CODE)} · 최신 모집요강과 다름</small></div>`).join(''):'<div class="notice">나이스 결과 없음: '+esc(r.message)+'</div>';$('sCount').textContent=`나이스 기본정보 ${r.schools.length}건 · 검색 결과는 개인 합격 판정이 아닙니다.`}catch(e){error(e)}};
 compare();load(false);
}
async function aiPlanner(){
 $('pageContent').innerHTML=`${pageHeader('AUTO ROADMAP ENGINE','자동 12주 계획표 생성기','주간 공부 가능 시간과 최근 성적을 반영해 12주·72개의 주간 과제 초안을 만들고 검토 후에만 내 캘린더에 저장합니다.')}
 <div class="notice">기존 일정과 학원 시간까지 자동으로 알 수는 없습니다. 생성 후 캘린더에서 충돌·시험일·휴식일을 반드시 조정하세요. 일요일은 기본 휴식일입니다.</div>
 <section class="card airy"><div class="formgrid"><label>주간 학습시간(1~50h)<input id="plusHours" type="number" min="1" max="50" value="${esc(state.plan.weeklyHours||state.profile.weeklyHours||8)}"></label><label>첫 시작 날짜(선택)<input id="plusStart" type="date"></label></div><div class="row"><button id="plusMake" class="btn">12주 맞춤 일정 만들기</button><button id="plusApply" class="btn alt" disabled>미리보기 확인 후 캘린더에 저장</button></div><p id="plusPlanInfo" class="muted"></p><div id="plusPlanRows" class="plus-plan-grid"></div></section>`;
 $('plusMake').onclick=async()=>{try{const data={weeklyHours:Number($('plusHours').value)};if($('plusStart').value)data.start=$('plusStart').value;const r=await api('/api/v2/plan/generate',data);pfPlusPreview=r.preview.calendar;$('plusApply').disabled=false;$('plusPlanInfo').textContent=`${r.preview.weekCount}주 · ${r.preview.sessionCount}개 세션 · 시작 ${r.preview.start} · 주간 ${r.preview.weeklyHours}시간 (자동 생성 초안)`;$('plusPlanRows').innerHTML=Array.from({length:12},(_,w)=>`<div class="plus-week"><b>${w+1}주차</b><p>${pfPlusPreview.slice(w*6,w*6+6).map(x=>`${esc(x.date.slice(5))} ${esc(x.subject)} ${x.minutes}분`).join(' / ')}</p></div>`).join('')}catch(e){error(e)}};
 $('plusApply').onclick=async()=>{if(!pfPlusPreview.length)return;const existing=Array.isArray(state.plan.calendar)?state.plan.calendar:[];if(!confirm(`12주 일정 ${pfPlusPreview.length}개를 내 캘린더에 추가할까요? 같은 날짜·과제 ID는 중복하지 않습니다. 기존 계획은 삭제하지 않습니다.`))return;const ids=new Set(existing.map(x=>x.id));const newEvents=pfPlusPreview.filter(x=>!ids.has(x.id));const newPlan={...state.plan,weeklyHours:Number($('plusHours').value),calendar:[...existing,...newEvents]};try{await api('/api/plan/save',{plan:newPlan});state.plan=newPlan;alertx(`캘린더에 ${newEvents.length}개 과제가 저장되었습니다.`);state.page='plan';render()}catch(e){error(e)}};
}
async function plusAnalytics(){
 $('pageContent').innerHTML=`${pageHeader('EVIDENCE FIRST ANALYTICS','성과·목표 격차 대시보드','실제 학습 데이터, 성적 입력의 한계, 학교선택에 필요한 미확인 자료를 분리하여 보여줍니다.')}<div class="plus-two"><section class="card airy" id="plusProgress">분석 중</section><section class="card airy" id="plusQuality">분석 중</section></div><section class="card airy" id="plusScores" style="margin-top:18px"></section>`;
 try{const r=await api('/api/v2/offline-analysis');const x=r.analysis;const c=x.calendar;$('plusProgress').innerHTML=`<h3>계획 실행 현황</h3><div class="plus-large">${c.completionRate===null?'—':c.completionRate+'%'}</div><div class="dimension-track"><div style="width:${c.completionRate||0}%"></div></div><p>완료 ${c.done}/${c.count}개 · 전체 ${c.minutes}분 / 완료 ${c.completedMinutes}분</p><p class="fieldhint">이 수치는 계획 수행률이지 합격 확률이 아닙니다.</p>`;
 $('plusQuality').innerHTML=`<h3>입력자료 검증</h3><p><b>학교 위치 DB</b> — 공식 CSV 제공, 적용연도 확인 필요</p><p><b>모집요강·지원 자격</b> — 확인 전</p><p><b>합격 확률</b> — 모델 없음 / 미산출</p>${x.issues.map(t=>`<p class="notice">${esc(t)}</p>`).join('')}`;
 $('plusScores').innerHTML=`<h3>과목별 최근 성적과 변화</h3>${x.grades.length?x.grades.map(g=>`<div style="margin:13px 0"><div class="row between"><b>${esc(g.subject)}</b><span>최근 ${g.latest}점 · ${g.count}회 입력 · 변화 ${g.change===null?'비교 전':g.change+'점'}</span></div><div class="dimension-track"><div style="width:${Math.max(0,Math.min(100,g.latest))}%"></div></div></div>`).join(''):'<div class="empty">학기별 성적을 입력하면 이곳에서 분석합니다.</div>'}<div class="notice">학년·시험별 난이도와 석차가 다른 원점수는 합격 예측 근거가 아닙니다.</div>`;
 }catch(e){error(e)}
}
async function apiSetup(){
 $('pageContent').innerHTML=`${pageHeader('OFFICIAL API CONNECTIONS','API 사용 안내','학생은 키를 입력하지 않습니다. 모든 비밀 키는 관리자가 서버에만 등록합니다.')}
 <section class="card airy"><h3>OpenAI의 Tracking과 Secret Key</h3>
 <p><b>Secret Key</b>는 실제 AI 요청에 사용하는 인증키입니다. <b>Tracking</b>은 API 호출량·토큰 사용량을 확인하는 기능으로 OpenAI에서 별도 Secret Key가 필요하지 않습니다. 관리자 화면에는 서버 자체 트래킹 집계가 표시됩니다.</p>
 <p><a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI Secret Key 발급</a> · <a href="https://platform.openai.com/usage" target="_blank" rel="noopener">OpenAI 공식 사용량 보기</a></p>
 <h3>공식 교육 API</h3><p><a href="https://open.neis.go.kr/portal/mainPage.do" target="_blank" rel="noopener">나이스(NEIS)</a>에서는 학교정보 인증키를, <a href="https://www.data.go.kr/" target="_blank" rel="noopener">공공데이터포털</a>에서는 대학정보 조회 서비스키를 발급받습니다.</p>
 <div class="notice">AI 분석은 학생이 외부 전송에 동의할 때만 실행됩니다. 키를 갖고 있다는 사실은 전형별 모집요강, 합격선, 개인 합격확률을 조회할 권한이 있다는 뜻이 아닙니다.</div>
 ${state.user?.role==='admin'?'<button class="btn" id="goApiManager">관리자 API 키 설정으로 이동</button>':'<p class="fieldhint">관리자 계정으로 로그인하면 API 키와 Tracking을 관리할 수 있습니다.</p>'}</section>
 <section class="card airy" style="margin-top:18px" id="plusApiState">상태를 조회하고 있습니다.</section>`;
 if($('goApiManager'))$('goApiManager').onclick=()=>{state.page='apiManager';render()};
 try{let r=await api('/api/v2/status');$('plusApiState').innerHTML=`<h3>연결된 서비스</h3><p>OpenAI: <b>${r.openaiConfigured?'키 등록됨':'키 미등록'}</b> · 모델 ${esc(r.model)}</p><p>나이스: <b>${r.neisConfigured?'키 등록됨':'키 미등록'}</b> · 대학정보: <b>${r.universityApiConfigured?'키 등록됨':'키 미등록'}</b></p><p>전국학교 기본 데이터 ${Number(r.nationalSchoolCount).toLocaleString('ko-KR')}개</p><p class="fieldhint">키 등록 상태일 뿐 실시간 인증 성공 여부는 아닙니다.</p>`}catch(e){$('plusApiState').textContent=e.message}
}
async function apiManager(){
 if(state.user?.role!=='admin')return apiSetup();
 $('pageContent').innerHTML=`${pageHeader('ADMIN · SECRET VAULT & TRACKING','API 비밀 키 · 사용량 관리','비밀 키는 관리자만 등록합니다. 원문 키는 저장 이후 브라우저로 반환되지 않습니다.')}
 <div class="notice">처음 받은 관리자 비밀번호를 사용 중이면 먼저 <b>마이페이지에서 비밀번호 변경</b>을 완료하세요. 이후 실제 비밀 키를 등록할 수 있습니다. Render에서는 API 키가 서버 환경변수로 관리되며 이 화면에서는 연결 테스트 및 사용량 조회만 가능합니다.</div>
 <section class="card airy" style="margin-top:18px"><h3>1 · OpenAI Secret Key</h3><p class="notice">키 저장 완료 ≠ AI 연결 성공. 아래 <b>OpenAI 실제 AI 생성 테스트</b> 버튼으로 테스트해야 합니다. 소량의 API 사용료가 발생할 수 있습니다.</p>
 <div class="plus-two"><div><label>Secret Key (sk-... · 입력한 값만 새 키로 교체)<input type="password" id="keyOpenai" autocomplete="new-password" placeholder="sk-proj-... (화면에 다시 표시되지 않음)"></label><p class="fieldhint"><a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI API 키 발급·관리</a>. 키 생성 시 전체 값은 한 번만 보이므로 안전하게 보관하세요.</p></div>
 <div><label>사용할 OpenAI 모델<input id="keyModel" placeholder="gpt-4.1-mini" maxlength="90"></label><p class="fieldhint">등록한 Secret Key의 프로젝트에서 사용 가능한 모델이어야 합니다. 실제 생성 테스트에서는 모델 권한·크레딧까지 검증합니다.</p></div></div>
 <p><b>OpenAI Tracking</b>은 별도의 입력 키가 없습니다. 서버가 호출 수·성공/실패·입력/출력 토큰을 자동 집계하며, OpenAI 플랫폼에서도 Usage 대시보드로 확인합니다.</p><div id="keyStatusOpenai" class="fieldhint"></div>
 <h3 style="margin-top:24px">2 · 나이스 학교정보 인증키</h3><label>NEIS API 인증키<input type="password" id="keyNeis" autocomplete="new-password" placeholder="NEIS 포털 인증키"></label><p><a href="https://open.neis.go.kr/portal/mainPage.do" target="_blank" rel="noopener">나이스 교육정보 개방포털에서 발급</a></p><div id="keyStatusNeis" class="fieldhint"></div>
 <h3 style="margin-top:24px">3 · 공공데이터포털 대학정보 서비스키</h3><label>DATA.GO.KR 서비스키 (일반 인증키 · 인코딩/디코딩형 입력 가능)<input type="password" id="keyUniversity" autocomplete="new-password" placeholder="서비스키를 여기에 붙여넣기"></label><p><a href="https://www.data.go.kr/data/15107736/standard.do" target="_blank" rel="noopener">대학 기본정보 오픈 API 활용신청</a></p><div id="keyStatusUniversity" class="fieldhint"></div>
 <h3 style="margin-top:24px">4 · 변경 / 삭제 / 연결 테스트</h3><p class="fieldhint">비워둔 Secret Key 입력칸은 기존 키를 유지합니다. 삭제 체크는 해당 키만 삭제합니다. 환경변수로 실행한 키는 이 화면에서 제거할 수 없으며 서버 실행환경에서 삭제해야 합니다.</p>
 <div class="formgrid"><label class="check"><input type="checkbox" id="removeOpenai"> OpenAI 키 삭제</label><label class="check"><input type="checkbox" id="removeNeis"> 나이스 키 삭제</label><label class="check"><input type="checkbox" id="removeUniversity"> 대학정보 키 삭제</label></div>
 <label>현재 관리자 로그인 비밀번호 (저장·테스트할 때 확인)<input type="password" id="keyAdminPassword" autocomplete="current-password" placeholder="현재 관리자 비밀번호"></label>
 <div class="row"><button class="btn" id="keySave">API 설정 안전 저장</button><button class="btn alt" data-key-test="openai">OpenAI 실제 AI 생성 테스트</button><button class="btn alt" data-key-test="neis">나이스 테스트</button><button class="btn alt" data-key-test="university">대학정보 테스트</button></div><p class="notice" id="keyNotice">실제 API 키는 화면에서 읽어 오지만 서버가 브라우저에 다시 반환하지 않습니다. 온라인(Render) 서버에서는 API 키를 Render 대시보드 Environment에서 변경하세요.</p></section>
 <section class="card airy" style="margin-top:20px"><h3>5 · API Tracking 대시보드</h3><p class="muted">이 집계는 누가 어떤 질문을 했는지 저장하지 않고, API 종류·분석 모드·일자별 사용량만 저장합니다.</p><div id="keyTracking">집계 로딩 중…</div><p><a href="https://platform.openai.com/usage" target="_blank" rel="noopener">OpenAI 플랫폼의 공식 비용·사용량 추적</a></p></section>`;
 const keyLabels={openai:'OpenAI',neis:'나이스',university:'대학정보'};
 const keyStatusIds={openai:'keyStatusOpenai',neis:'keyStatusNeis',university:'keyStatusUniversity'};
 const stateKeys={openai:'keyOpenai',neis:'keyNeis',university:'keyUniversity'};
 const removeIds={openai:'removeOpenai',neis:'removeNeis',university:'removeUniversity'};
 async function refresh(){
  try{const r=await api('/api/admin/api-config');$('keyModel').value=r.model||'gpt-4.1-mini';
   if(String(r.storage||'').startsWith('Render:')){
    $('keyNotice').textContent='Render 온라인 서버: API 키는 Render Dashboard → 서비스 → Environment 메뉴에서 변경하고 재배포합니다. 이 페이지에서는 조회와 테스트만 가능합니다.';
    ['keyOpenai','keyNeis','keyUniversity','keyModel','removeOpenai','removeNeis','removeUniversity','keySave'].forEach(id=>{const el=$(id);if(el)el.disabled=true});
   }
   for(const [k,label] of Object.entries(keyLabels)){
    const x=r.keys[k]||{};$(keyStatusIds[k]).textContent=`${label}: ${x.configured?'등록됨':'미등록'} · ${x.source||'미설정'}${x.environmentOverride?' · 주의: 환경변수 키가 우선 적용됨':''} (키 원문 비공개)`;
   }
  }catch(e){$('keyNotice').textContent=e.message}
  try{const r=await api('/api/admin/api-usage');let rows=r.daily||[];let sum=rows.reduce((a,x)=>{a.calls+=Number(x.calls)||0;a.input+=Number(x.input_tokens)||0;a.output+=Number(x.output_tokens)||0;return a},{calls:0,input:0,output:0});
   $('keyTracking').innerHTML=`<div class="plus-two"><div class="soft"><b>전체 요청 건수</b><div class="plus-large">${sum.calls.toLocaleString('ko-KR')}</div></div><div class="soft"><b>입력/출력 토큰 합계</b><div class="plus-large">${sum.input.toLocaleString('ko-KR')} / ${sum.output.toLocaleString('ko-KR')}</div></div></div>`+
    `<div class="table-wrap"><table class="table"><thead><tr><th>날짜</th><th>제공사</th><th>상태</th><th>횟수</th><th>입력</th><th>출력</th></tr></thead><tbody>${rows.map(x=>`<tr><td>${esc(x.day)}</td><td>${esc(x.provider)}</td><td>${esc(x.status)}</td><td>${Number(x.calls)||0}</td><td>${Number(x.input_tokens)||0}</td><td>${Number(x.output_tokens)||0}</td></tr>`).join('')||'<tr><td colspan="6">아직 API 사용 기록이 없습니다.</td></tr>'}</tbody></table></div><p class="fieldhint">비용은 임의 추정하지 않습니다. 모델별 정확한 사용료는 공식 청구 대시보드에서 확인하세요.</p>`;
  }catch(e){$('keyTracking').textContent=e.message}
 }
 $('keySave').onclick=async()=>{const password=$('keyAdminPassword').value;if(!password)return alertx('현재 관리자 비밀번호를 입력하세요.');
  const keys={};const del=[];
  for(const k of Object.keys(keyLabels)){const val=$(stateKeys[k]).value.trim();if(val)keys[k]=val;if($(removeIds[k]).checked)del.push(k)}
  if(del.length&&!confirm(`${del.map(x=>keyLabels[x]).join(', ')}의 API 키를 삭제하시겠습니까?`))return;
  const btn=$('keySave');btn.disabled=true;
  try{const r=await api('/api/admin/api-config',{currentPassword:password,keys,delete:del,model:$('keyModel').value.trim()});
   for(const k of Object.keys(keyLabels)){$(stateKeys[k]).value='';$(removeIds[k]).checked=false;}
   $('keyNotice').textContent=r.notice||'저장되었습니다.';await refresh();alertx('설정 저장 완료');
  }catch(e){$('keyNotice').textContent=e.message;error(e)}finally{btn.disabled=false}
 };
 document.querySelectorAll('[data-key-test]').forEach(btn=>btn.onclick=async()=>{
  if(!$('keyAdminPassword').value)return alertx('현재 관리자 비밀번호를 입력하세요.');
  btn.disabled=true;try{const r=await api('/api/admin/api-test',{currentPassword:$('keyAdminPassword').value,provider:btn.dataset.keyTest});
   $('keyNotice').textContent=`${r.ok?'연결 및 AI 생성 확인':'연결 실패'} · ${r.message}${r.httpStatus?' [HTTP '+r.httpStatus+']':''}${r.errorCode?' ['+r.errorCode+']':''}`;await refresh();
  }catch(e){$('keyNotice').textContent=e.message;error(e)}finally{btn.disabled=false}
 });
 await refresh();
}
async function universityLab(){
 $('pageContent').innerHTML=`${pageHeader('UNIVERSITY DIRECTORY','공식 대학 기본정보 찾아보기','연동이 준비된 경우 대학명·소재지·설립형태를 찾아볼 수 있습니다. 최신 지원 요건과 합격확률을 제공하는 기능은 아닙니다.')}
 <div class="notice">공식 원본: <a href="https://www.data.go.kr/data/15107736/standard.do" target="_blank" rel="noopener">전국대학및전문대학정보표준데이터</a>. API 인증키와 해당 서비스의 이용 승인이 필요합니다. 대학별 학과 정보는 별도 <a href="https://www.data.go.kr/data/15158666/openapi.do" target="_blank" rel="noopener">대학별 학과정보 API</a>로 추가 확보할 수 있으며, 이 화면에서는 아직 연동하지 않았습니다.</div>
 <section class="card airy"><div class="formgrid"><label>대학명 검색<input id="uName" placeholder="예: 전남대학교, 한국항공대학교"></label><label>시도명(선택)<input id="uRegion" placeholder="예: 서울특별시, 광주광역시"></label></div><div class="row"><button class="btn" id="uQuery">공식 대학정보 API 조회</button><button class="btn alt" id="uSet">공식정보 이용안내</button></div><p class="fieldhint">학교 추천을 원하면 목표 학과·지원학년·성적을 먼저 입력한 뒤 AI 전문가 '대학·전공 장기 진학' 모드로 요청하세요. AI 분석에도 검증되지 않은 합격률은 표시하지 않습니다.</p><div id="uResults"></div></section>`;
 $('uSet').onclick=()=>alertx('공식 API 연결은 운영자가 관리합니다. 학생은 API 키를 입력하지 않습니다.');
 $('uQuery').onclick=async()=>{let btn=$('uQuery');btn.disabled=true;try{let r=await api('/api/v2/universities?q='+encodeURIComponent($('uName').value)+'&region='+encodeURIComponent($('uRegion').value));$('uResults').innerHTML=`<h3>조회 결과</h3><p class="muted">${esc(r.totalCount)}건 · 출처: 공공데이터포털</p>`+(r.universities||[]).map(x=>`<article class="plus-school"><b>${esc(x.SCHL_NM)}</b><p>${esc(x.CTPV_NM)} · ${esc(x.LCTN_ROAD_NM_ADDR)}</p><small>${esc(x.UNIV_SE_NM)} · ${esc(x.SCHL_SE_NM)} · ${esc(x.FNDN_FORM_SE_NM)} · 기준연도 ${esc(x.CRTR_YR)}</small></article>`).join('')+`<div class="notice">${esc(r.caution)}</div>`}catch(e){$('uResults').innerHTML=`<div class="notice warn">${esc(e.message)}</div>`}finally{btn.disabled=false}};
}
