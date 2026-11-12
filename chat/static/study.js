'use strict';
const $=id=>document.getElementById(id);
let active=null,working=false,paused=false,current=null;
async function request(url,body){
 const response=await fetch(url,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value},body:body===undefined?undefined:JSON.stringify(body)});
 const value=await response.json();if(!response.ok)throw Error(value.error||'Request failed. Please sign in again.');return value;
}
function busy(value){working=value;$('start').disabled=value;$('pause').hidden=!value;$('resume').hidden=value||!current||current.status!=='running';for(const b of $('runs').querySelectorAll('button'))b.disabled=value;}
function show(run){current=run;active=run.id;$('status').textContent=({running:paused?'Paused':'Agent working',complete:'Study pack ready',needs_input:'More information needed',failed:'Run stopped',limit:'Run limit reached'})[run.status]||run.status;
 $('plan').replaceChildren(...run.plan.map(s=>{const li=document.createElement('li');li.textContent=s;return li;}));
 $('trace').replaceChildren(...run.trace.map(t=>{const box=document.createElement('article');box.className='event';const title=document.createElement('strong');title.textContent=t.action;const p=document.createElement('p');p.textContent=t.summary;box.append(title,p);if(t.result){const d=document.createElement('details');const s=document.createElement('summary');s.textContent='Tool result';const pre=document.createElement('pre');pre.textContent=JSON.stringify(t.result,null,2);d.append(s,pre);box.append(d);if(t.result.question){const q=document.createElement('p');q.textContent=t.result.question+' Update your goal or source and start a new run.';box.append(q);}}return box;}));
 $('pack').hidden=!run.output;$('output').textContent=run.output;$('download').hidden=!run.artifact;$('resume').hidden=working||run.status!=='running';
}
async function history(){const value=await request('/api/study/history');$('runs').replaceChildren(...value.runs.map(run=>{const b=document.createElement('button');b.textContent=run.goal.slice(0,60)+' · '+run.status;b.disabled=working;b.onclick=async()=>{try{show(await request('/api/study/'+run.id));}catch(e){$('error').textContent=e.message;}};return b;}));}
async function execute(){paused=false;busy(true);$('error').textContent='';try{while(!paused&&current.status==='running'){show(await request('/api/study/'+active+'/step',{}));}if(paused&&current.status==='running')$('status').textContent='Paused — you can continue this run';}catch(e){$('error').textContent=e.message;}finally{busy(false);history().catch(e=>{$('error').textContent=e.message;});}}
$('pause').onclick=()=>{paused=true;$('pause').textContent='Pausing after current step…';};
$('resume').onclick=()=>{$('pause').textContent='Pause after this step';execute();};
$('study-form').onsubmit=async event=>{event.preventDefault();if(working)return;const file=$('source').files[0];if(!file||file.size>2*1024*1024){$('error').textContent='Choose a PDF up to 2 MB.';return;}busy(true);$('error').textContent='';try{const encoded=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=()=>reject(Error('File could not be read.'));r.readAsDataURL(file);});show(await request('/api/study',{goal:$('goal').value,attachment:{name:file.name,mediaType:'application/pdf',data:encoded}}));$('pause').textContent='Pause after this step';await execute();}catch(e){$('error').textContent=e.message;busy(false);}};
function download(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('download').onclick=()=>{if(current?.artifact)download(new Blob([Uint8Array.from(atob(current.artifact.data),c=>c.charCodeAt(0))],{type:'application/pdf'}),'Coex_Study_Pack.pdf');};
$('text-download').onclick=()=>{if(current?.output)download(new Blob([current.output],{type:'text/plain;charset=utf-8'}),'Coex_Study_Pack.txt');};
history().catch(e=>{$('error').textContent=e.message;});
