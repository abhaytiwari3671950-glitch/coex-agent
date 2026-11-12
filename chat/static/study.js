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
function uploadPDF(file,goal){return new Promise((resolve,reject)=>{
 const xhr=new XMLHttpRequest();const form=new FormData();form.append('goal',goal);form.append('file',file);
 xhr.open('POST','/api/study');xhr.setRequestHeader('X-CSRFToken',document.querySelector('[name=csrfmiddlewaretoken]').value);
 xhr.timeout=300000;
 xhr.upload.onprogress=event=>{if(event.lengthComputable){const percent=Math.round(event.loaded/event.total*100);$('status').textContent=percent===100?'Reading PDF…':'Uploading PDF · '+percent+'%';}};
 xhr.onload=()=>{let value;try{value=JSON.parse(xhr.responseText);}catch{reject(Error('Upload failed. The server may have a smaller upload limit.'));return;}if(xhr.status>=200&&xhr.status<300)resolve(value);else reject(Error(value.error||'Upload failed.'));};
 xhr.onerror=()=>reject(Error('Upload interrupted. Check the connection and retry.'));
 xhr.ontimeout=()=>reject(Error('Upload timed out. Try a smaller PDF or retry.'));
 xhr.send(form);
});}
$('study-form').onsubmit=async event=>{event.preventDefault();if(working)return;
 const file=$('source').files[0];const maximum=Number($('study-form').dataset.maxUpload);
 if(!file||!file.size||file.size>maximum){$('error').textContent='Choose a nonempty PDF up to '+Math.floor(maximum/1024/1024)+' MB.';return;}
 busy(true);$('pause').hidden=true;$('error').textContent='';$('status').textContent='Uploading PDF…';
 try{show(await uploadPDF(file,$('goal').value));$('pause').textContent='Pause after this step';await execute();}
 catch(e){$('error').textContent=e.message;$('status').textContent='Upload failed';busy(false);}
};
function download(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('download').onclick=()=>{if(current?.artifact)download(new Blob([Uint8Array.from(atob(current.artifact.data),c=>c.charCodeAt(0))],{type:'application/pdf'}),'Coex_Study_Pack.pdf');};
$('text-download').onclick=()=>{if(current?.output)download(new Blob([current.output],{type:'text/plain;charset=utf-8'}),'Coex_Study_Pack.txt');};
history().catch(e=>{$('error').textContent=e.message;});
