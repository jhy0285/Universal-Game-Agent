"use strict";
const token = document.querySelector('meta[name="uga-token"]').content;
const $ = id => document.getElementById(id);
let selected = null, cursor = 0, polling = false, imageURL = null;
const labels = {queued:"대기",running:"실행 중",succeeded:"완료",failed:"실패",cancelled:"취소",timed_out:"시간 초과"};
async function api(path, data) {
  const response = await fetch(`/api/v1/${path}`, {headers:{"X-UGA-Token":token,...(data!==undefined?{"Content-Type":"application/json"}:{})},method:data!==undefined?"POST":"GET",body:data!==undefined?JSON.stringify(data):undefined});
  if(!response.ok){const problem=await response.json();throw new Error(typeof problem.detail==="string"?problem.detail:JSON.stringify(problem.detail));}
  return response.json();
}
function notice(text){$("notice").hidden=!text;$("notice").textContent=text;}
function element(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
async function launch(agent,operation,parameters,authorized=false){
  notice("");const row=await api("jobs",{agent,operation,parameters,authorized});selected=row.id;await refresh();
}
document.querySelectorAll("[data-launch]").forEach(button=>button.addEventListener("click",async()=>{
  button.disabled=true;
  try{
    const agent=button.dataset.launch;
    if(agent==="player")await launch(agent,"play",{seed:Number($("seed").value)});
    if(agent==="builder"){
      const engine=$("run-godot").checked, preset=$("export-preset").value;
      if(preset&&!engine)throw new Error("내보내기에는 Godot 실행 허용이 필요합니다.");
      await launch(agent,engine?"build":"generate",{requirements:$("requirements").value,...(preset?{export_preset:preset}:{})},engine);
    }
    if(agent==="reverse"){
      if(!$("authorized").checked)throw new Error("분석 대상에 대한 권한 확인이 필요합니다.");
      await launch(agent,"analyze",{path:$("analysis-path").value||"test_games/godot"},true);
    }
  }catch(e){notice(e.message);}finally{button.disabled=false;}
}));
$("workflow").onclick=async()=>{try{
  const engine=$("run-godot").checked,preset=$("export-preset").value;
  if(preset&&!engine)throw new Error("내보내기에는 Godot 실행 허용이 필요합니다.");
  await launch("workflow","build-play",{requirements:$("requirements").value,backend:engine?"godot":"reference",...(preset?{export_preset:preset}:{})},engine);
}catch(e){notice(e.message);}};
$("stop-all").onclick=async()=>{try{await api("stop",{});await refresh();}catch(e){notice(e.message);}};
$("rollback").onclick=async()=>{try{await api("rollback",{});await refresh();}catch(e){notice(e.message);}};
function renderJobs(rows){
  $("running").textContent=rows.filter(r=>r.status==="running").length;
  $("completed").textContent=rows.filter(r=>r.status==="succeeded").length;
  for(const agent of ["player","reverse","builder"]){const active=rows.some(r=>r.spec.agent===agent&&r.status==="running");$(`${agent}-state`).textContent=active?"실행 중":"대기";}
  if(!rows.length)return;
  const body=$("job-list");body.replaceChildren();
  for(const row of rows){
    const tr=element("tr");tr.append(element("td",`${row.spec.operation} · ${row.id.slice(0,8)}`),element("td",row.spec.agent),element("td",labels[row.status],`status-${row.status}`),element("td",new Date(row.created).toLocaleTimeString("ko-KR")),element("td",row.error|| (row.result?.success===true?"목표 달성":row.result?.generated===true?"프로젝트 생성":row.result?"결과 저장":"—")));
    const controls=element("td");if(["queued","running"].includes(row.status)){const cancel=element("button","중지");cancel.onclick=async(event)=>{event.stopPropagation();try{await api(`jobs/${row.id}/cancel`,{});await refresh();}catch(e){notice(e.message);}};controls.append(cancel);}tr.append(controls);
    tr.onclick=()=>{selected=row.id;$("job-detail").hidden=false;$("job-detail").textContent=JSON.stringify(row.result||row,null,2);updatePreview();};body.append(tr);
  }
  if(!selected){selected=rows.find(r=>r.spec.agent==="player"||r.spec.agent==="workflow")?.id||null;}
}
async function updatePreview(){
  if(!selected)return;
  const response=await fetch(`/api/v1/jobs/${selected}/preview`,{headers:{"X-UGA-Token":token}});
  $("preview-label").textContent=selected.slice(0,8);
  if(!response.ok){$("preview").hidden=true;$("preview-empty").hidden=false;return;}
  const next=URL.createObjectURL(await response.blob());if(imageURL)URL.revokeObjectURL(imageURL);imageURL=next;$("preview").src=next;$("preview").hidden=false;$("preview-empty").hidden=true;
}
function renderEvents(events){
  if(!events.length)return;
  const log=$("event-log");if(cursor===0)log.replaceChildren();
  for(const event of events){const row=element("div",undefined,"event");row.append(element("time",new Date(event.timestamp).toLocaleTimeString("ko-KR")),element("span",`${event.agent} / ${event.event}  ${event.message}`,event.level));log.append(row);cursor=Math.max(cursor,event.sequence);}
  while(log.children.length>100)log.firstChild.remove();log.scrollTop=log.scrollHeight;
}
function renderExperiments(rows){
  if(!rows.length)return;const box=$("experiment-list");box.replaceChildren();
  for(const experiment of rows){
    const row=element("div",undefined,"experiment");const description=element("div");description.append(element("strong",`실험 ${experiment.id.slice(0,8)} · ${experiment.status}`));const comparison=element("div",undefined,"comparison");for(const [name,result] of [["BEFORE",experiment.baseline],["AFTER",experiment.candidate]]){const values=element("div",name);values.append(element("strong",`${(result.metrics.success_rate*100).toFixed(0)}% / ${result.metrics.mean_steps.toFixed(1)} steps`));comparison.append(values);}description.append(comparison,element("small",experiment.comparison.reasons.join(", "),"muted"));row.append(description);
    if(experiment.status==="proposed"){const approve=element("button","후보 적용 승인");approve.disabled=!experiment.comparison.eligible;approve.onclick=async()=>{try{await api(`experiments/${experiment.id}/approve`,{approved:true});await refresh();}catch(e){notice(e.message);}};row.append(approve);}box.append(row);
  }
}
async function refresh(){
  if(polling)return;polling=true;
  try{const [jobs,system,events,experiments]=await Promise.all([api("jobs"),api("system"),api(`events?after=${cursor}`),api("experiments")]);renderJobs(jobs);renderEvents(events);renderExperiments(experiments);$("cpu").textContent=`${system.cpu_percent.toFixed(0)}%`;$("ram").textContent=`RAM ${system.ram_percent.toFixed(0)}%`;$("memory").textContent=`${system.rss_mb.toFixed(0)} MB`;$("connection").textContent=system.orchestrator_healthy?"● 로컬 연결됨":"● 감시 프로세스 오류";await updatePreview();}catch(e){$("connection").textContent="● 연결 오류";notice(e.message);}finally{polling=false;}
}
refresh();setInterval(refresh,1000);
