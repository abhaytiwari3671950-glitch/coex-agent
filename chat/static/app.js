'use strict';
const $ = id => document.getElementById(id);
let conversationId = null, attachment = null, busy = false, controller = null, chats = [];
const csrf = () => document.querySelector('#composer [name=csrfmiddlewaretoken]').value;
const error = message => { $('error').textContent = message; };
async function request(path, body, signal) {
  const response = await fetch(path, {method:body ? 'POST':'GET', credentials:'same-origin', signal:signal || AbortSignal.timeout(65000), headers:body ? {'Content-Type':'application/json','X-CSRFToken':csrf()}:{}, body:body ? JSON.stringify(body):undefined});
  if (response.status === 401) { location.assign('/login/'); throw Error('Please sign in again.'); }
  if (!response.ok) {
    const result = await response.json().catch(()=>({}));
    throw Error(result.error || 'Unable to complete this request. Please try again.');
  }
  return response;
}
function setBusy(value) {
  busy = value;
  for (const id of ['send','upload','new-chat','new-top','search','chat-mode']) $(id).disabled = value;
  $('stop').hidden = !value;
  document.querySelectorAll('.actions button, #history button').forEach(button=>button.disabled=value);
}
function download(data) {
  const bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0));
  const url=URL.createObjectURL(new Blob([bytes],{type:'application/pdf'}));
  const link=document.createElement('a'); link.href=url; link.download='coex-response.pdf'; link.click();
  setTimeout(()=>URL.revokeObjectURL(url),10000);
}


function appendFormatted(target, input) {
  const pattern = /(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|\*[^*\n]+\*|_[^_\n]+_)/g;
  let offset = 0;
  for (const match of input.matchAll(pattern)) {
    if (match.index > offset) target.append(document.createTextNode(input.slice(offset, match.index)));
    const value = match[0], strong = value.startsWith('**') || value.startsWith('__');
    const el = document.createElement(strong ? 'strong' : value.startsWith('`') ? 'code' : 'em');
    if (strong) appendFormatted(el, value.slice(2, -2));
    else el.textContent = value.slice(1, -1);
    target.append(el);
    offset = match.index + value.length;
  }
  if (offset < input.length) target.append(document.createTextNode(input.slice(offset)));
}

function renderAssistant(content, raw) {
  content.replaceChildren();
  const lines = raw.replace(/&#x20;|&#32;|&nbsp;/gi, ' ').split('\n');
  let paragraph = [];
  const flush = () => {
    if (!paragraph.length) return;
    const p = document.createElement('p');
    paragraph.forEach((line, i) => { if (i) p.append(document.createElement('br')); appendFormatted(p, line); });
    content.append(p);
    paragraph = [];
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const fence = /^\s*```([a-zA-Z0-9_+.#-]*)\s*$/.exec(line);
    if (fence) {
      let end = i + 1;
      while (end < lines.length && !/^\s*```\s*$/.test(lines[end])) end++;
      if (end < lines.length) {
        flush();
        const wrap = document.createElement('div');
        wrap.className = 'code-block';
        const bar = document.createElement('div');
        bar.className = 'code-bar';
        const language = document.createElement('span');
        language.textContent = fence[1] || 'Code';
        const copy = document.createElement('button');
        copy.type = 'button';
        copy.textContent = 'Copy code';
        const codeText = lines.slice(i + 1, end).join('\n');
        copy.onclick = () => navigator.clipboard.writeText(codeText).catch(() => error('Copy failed.'));
        bar.append(language, copy);
        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.textContent = codeText;
        pre.append(code);
        wrap.append(bar, pre);
        content.append(wrap);
        i = end;
        continue;
      }
    }
    if (/^\s*(---+|\*\*\*+|___+)\s*$/.test(line)) {
      flush();
      content.append(document.createElement('hr'));
      continue;
    }
    const bullet = /^\s*([-*+]|\d+[.)])\s+(.+)$/.exec(line);
    if (bullet) {
      flush();
      const tag = /^\d/.test(bullet[1]) ? 'ol' : 'ul';
      let list = content.lastElementChild;
      if (!list || list.tagName.toLowerCase() !== tag) {
        list = document.createElement(tag);
        content.append(list);
      }
      const item = document.createElement('li');
      appendFormatted(item, bullet[2]);
      list.append(item);
      continue;
    }
    const heading = /^\s*(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      flush();
      const h = document.createElement('h' + heading[1].length);
      appendFormatted(h, heading[2]);
      content.append(h);
    } else if (!line.trim()) {
      flush();
    } else {
      paragraph.push(line);
    }
  }
  flush();
}

function message(role, text, file=null, actions=true, metadata={}, messageId=null) {
  $('welcome')?.remove();
  const box=document.createElement('article'); box.className=`bubble ${role}`;
  if(file){const name=document.createElement('span');name.className='file-name';name.textContent=`Attachment: ${file.name}`;box.append(name);}
  const content=document.createElement('div');content.className='message-text';content.dataset.raw=text;if(role==='assistant' && actions)renderAssistant(content,text);else content.textContent=text;box.append(content);
  if(actions){
    const buttons=document.createElement('div');buttons.className='actions';
    const copy=document.createElement('button');copy.textContent='Copy';copy.onclick=()=>navigator.clipboard.writeText(content.dataset.raw).catch(()=>error('Copy failed. Please select and copy the text.'));buttons.append(copy);
    const action=document.createElement('button');action.textContent=role==='user'?'Edit & resend':'Download PDF';
    action.onclick=async()=>{if(busy)return;error('');
      if(role==='user'){$('message').value=content.textContent;attachment=file;showAttachment();$('message').focus();error('Edit and send as a new message. The original stays in this chat.');return;}
      action.disabled=true;
      try{const response=await request('/api/media',{action:'create_pdf',title:'coex response',text:content.dataset.raw});download((await response.json()).data);}catch(e){error(e.message);}finally{action.disabled=false;}
    };buttons.append(action);box.append(buttons);
  }
  if(role==='assistant' && actions)decorateMessage(box,metadata,messageId);
  $('messages').append(box);$('messages').scrollTop=$('messages').scrollHeight;
  return {box,content};
}
function showAttachment(){
  const box=$('attachment');box.replaceChildren();box.hidden=!attachment;if(!attachment)return;
  if(attachment.mediaType.startsWith('image/')){const img=document.createElement('img');img.src=`data:${attachment.mediaType};base64,${attachment.data}`;img.alt='Selected image';box.append(img);}
  box.append(document.createTextNode(attachment.name+' '));const remove=document.createElement('button');remove.textContent='Remove';remove.onclick=()=>{if(!busy){attachment=null;showAttachment();}};box.append(remove);
}
async function refreshHistory(){chats=(await (await request('/api/conversations')).json()).conversations;renderHistory();}
function renderHistory(){
  $('history').replaceChildren();
  for(const chat of chats.filter(c=>c.title.toLowerCase().includes($('search').value.toLowerCase()))){const button=document.createElement('button');button.textContent=chat.title;button.disabled=busy;button.onclick=async()=>{if(busy)return;try{const data=await(await request(`/api/conversations/${chat.id}`)).json();conversationId=data.id;lastStudyId=null;quiz=null;$('messages').replaceChildren();for(const m of data.messages){message(m.role,m.text,m.attachment,true,m.metadata,m.id);if(m.status!=='complete')error('A previous response was interrupted. You can resend your question.');}attachment=null;showAttachment();$('sidebar').classList.remove('open');}catch(e){error(e.message);}};$('history').append(button);}
}
$('search').oninput=renderHistory;
$('new-chat').onclick=$('new-top').onclick=()=>{if(!busy)location.assign('/');};
$('menu').onclick=()=>{$('sidebar').classList.toggle('open');$('menu').setAttribute('aria-expanded',String($('sidebar').classList.contains('open')));};
document.addEventListener('keydown',event=>{if(event.key==='Escape'){$('sidebar').classList.remove('open');$('menu').setAttribute('aria-expanded','false');}});
document.querySelectorAll('[data-prompt]').forEach(button=>button.onclick=()=>{$('message').value=button.dataset.prompt;$('message').focus();});
$('upload').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;error('');attachment=null;studyFile=null;showAttachment();
  if(file.name.toLowerCase().endsWith('.pdf')){const limit=Number($('composer').dataset.maxUpload);if(file.size>limit){error('Study PDF exceeds '+Math.floor(limit/1024/1024)+' MB.');return;}studyFile=file;$('chat-mode').value='study';$('attachment').hidden=false;$('attachment').textContent='Study PDF: '+file.name;event.target.value='';return;}
  if(!file.size || file.size>2*1024*1024){error('Choose a nonempty file up to 2 MB.');event.target.value='';return;}
  setBusy(true);$('stop').hidden=true;
  try{const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('Cannot read this file.'));reader.readAsDataURL(file);});
    const result=await(await request('/api/media',{action:'inspect',data:encoded,mediaType:file.type || (file.name.toLowerCase().endsWith('.pdf')?'application/pdf':'')})).json();
    attachment={name:file.name,data:encoded,mediaType:result.mediaType};showAttachment();
  }catch(e){error(e.name==='TimeoutError'?'Upload timed out. Please try again.':e.message);}finally{setBusy(false);event.target.value='';}
};
$('stop').onclick=()=>controller?.abort();
$('message').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('composer').requestSubmit();}};
const submitChat=async event=>{
  event.preventDefault();if(busy)return;
  const text=$('message').value.trim();if(!text)return;error('');
  const file=attachment;setBusy(true);controller=new AbortController();let timer=setTimeout(()=>controller.abort(),90000);let answer=null,finished=false,accepted=false;
  try{
    const response=await request('/api/chat',{text,conversationId,attachment:file,mode:$('chat-mode').value},controller.signal);
    message('user',text,file);answer=message('assistant','Generating formatted response…',null,false);$('message').value='';attachment=null;showAttachment();
    const reader=response.body.getReader();const decoder=new TextDecoder();let pending='',reply='',metadata={},savedId=null;
    while(true){const chunk=await reader.read();pending+=decoder.decode(chunk.value||new Uint8Array(),{stream:!chunk.done});
      const lines=pending.split('\n');pending=lines.pop();
      for(const line of lines){if(!line)continue;const part=JSON.parse(line);if(part.conversationId){conversationId=part.conversationId;accepted=true;}if(part.delta){reply+=part.delta;answer.content.dataset.raw=reply;}if(part.activity)answer.content.textContent=part.activity;if(part.error)throw Error(part.error);if(part.done){finished=true;metadata=part.metadata||{};savedId=part.messageId;}}
      if(chunk.done)break;
    }
    if(!finished)throw Error('Response interrupted. You can resend your question.');
    answer.box.remove();message('assistant',reply,null,true,metadata,savedId);
  }catch(e){error(e.name==='AbortError'?'Response stopped or timed out. You can resend your question.':e.message);if(answer)answer.content.textContent='Response interrupted. No formatted answer was displayed.';if(!$('message').value)$('message').value=text;}
  finally{clearTimeout(timer);controller=null;setBusy(false);if(accepted)refreshHistory().catch(e=>error(e.message));}
};
refreshHistory().catch(e=>error(e.message));

let studyFile=null,stopStudy=false,quiz=null,lastStudyId=null;
function decorateMessage(box,meta,id){
 if(meta.kind==='image'&&id){const img=document.createElement('img');img.className='generated-image';img.src='/api/generated-image/'+id;img.alt='AI-generated image';box.append(img);const link=document.createElement('a');link.href=img.src;link.download='coex-generated.jpg';link.textContent='Download image';box.append(link);}
 if(meta.kind==='web'){
  const list=document.createElement('ol');list.className='source-links';for(const source of meta.sources||[]){try{const url=new URL(source.url);if(url.protocol!=='https:')continue;const li=document.createElement('li');const a=document.createElement('a');a.href=url.href;a.textContent=source.title||url.hostname;a.target='_blank';a.rel='noopener noreferrer';li.append(a);list.append(li);}catch{}}box.append(list);
  if(id){const iframe=document.createElement('iframe');iframe.title='Google Search suggestions';iframe.src='/api/search-widget/'+id;iframe.setAttribute('sandbox','allow-popups allow-popups-to-escape-sandbox');iframe.className='search-widget';box.append(iframe);}
 }
 if(meta.kind==='study'&&meta.runId){lastStudyId=meta.runId;const b=document.createElement('button');b.textContent='Open study task / quiz';b.onclick=()=>openStudy(meta.runId);box.append(b);}
 if(id){for(const [label,rating] of [['👍',1],['👎',-1]]){const b=document.createElement('button');b.textContent=label;b.title='Optional feedback';b.onclick=async()=>{try{await request('/api/feedback/'+id,{rating});b.textContent=label+' Saved';}catch(e){error(e.message);}};box.append(b);}}
}
function studyCard(run,card){
 lastStudyId=run.id;
 card.replaceChildren();const h=document.createElement('h3');h.textContent='Study Agent · '+run.status;card.append(h);
 for(const step of run.plan||[]){const p=document.createElement('p');p.textContent='• '+step;card.append(p);}
 for(const item of run.trace){const d=document.createElement('details');const summary=document.createElement('summary');summary.textContent=item.action+': '+item.summary;d.append(summary);if(item.result){const pre=document.createElement('pre');pre.textContent=JSON.stringify(item.result,null,2);d.append(pre);}card.append(d);}
 if(run.status==='running'){const b=document.createElement('button');b.textContent='Continue task';b.disabled=busy;b.onclick=()=>driveStudy(run,card);card.append(b);}
 if(run.output){const output=document.createElement('div');renderAssistant(output,run.output);card.append(output);if(run.artifact){const b=document.createElement('button');b.textContent='Download study PDF';b.onclick=()=>download(run.artifact.data);card.append(b);}const txt=document.createElement('button');txt.textContent='Download text';txt.onclick=()=>{const u=URL.createObjectURL(new Blob([run.output],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download='Coex-study.txt';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};card.append(txt);const q=document.createElement('button');q.textContent='Quiz me / practise weak topics';q.onclick=async()=>{if(busy)return;try{quiz=await(await request('/api/quiz/start/'+run.id,{})).json();message('assistant','Question 1 of '+quiz.total+': '+quiz.question);$('message').placeholder='Type your quiz answer here…';}catch(e){error(e.message);}};card.append(q);}
}
async function openStudy(id){if(busy)return;try{const run=await(await request('/api/study/'+id)).json();const card=message('assistant','',null,false).content;studyCard(run,card);}catch(e){error(e.message);}}
async function driveStudy(run,card){stopStudy=false;setBusy(true);try{while(run.status==='running'&&!stopStudy){run=await(await request('/api/study/'+run.id+'/step',{})).json();studyCard(run,card);}if(stopStudy)error('Task paused after its current step. Continue from this card.');}catch(e){error(e.message);}finally{setBusy(false);studyCard(run,card);refreshHistory().catch(e=>error(e.message));}}
const originalStop=$('stop').onclick;$('stop').onclick=()=>{stopStudy=true;originalStop();};
async function startStudy(){const text=$('message').value.trim();if(!text)return;if(!studyFile&&!lastStudyId){error('Attach a PDF to start a study task.');return;}if(text.length>2000){error('Keep the study goal under 2,000 characters.');return;}setBusy(true);$('stop').hidden=true;const card=message('assistant','Uploading and indexing your PDF…',null,false).content;
 try{if(!studyFile&&lastStudyId){const run=await(await request('/api/study/'+lastStudyId+'/reuse',{goal:text})).json();$('message').value='';$('chat-mode').value='auto';await driveStudy(run,card);return;}const form=new FormData();form.append('goal',text);form.append('file',studyFile);if(conversationId)form.append('conversationId',conversationId);
 const run=await sendStudyUpload(form,card);conversationId=run.conversationId;message('user',text);$('message').value='';studyFile=null;attachment=null;showAttachment();$('chat-mode').value='auto';await driveStudy(run,card);
 }catch(e){card.textContent='Study upload failed.';error(e.message);}finally{setBusy(false);}}
$('composer').onsubmit=async event=>{event.preventDefault();if(busy)return;error('');if(quiz&&!quiz.complete){const answer=$('message').value.trim();if(!answer)return;setBusy(true);try{const result=await(await request('/api/quiz/answer/'+quiz.id,{answer,position:quiz.position})).json();message('user',answer);$('message').value='';const grade=result.answers.at(-1);message('assistant','Score '+grade.score+'/2: '+grade.feedback);quiz=result;if(result.complete){message('assistant','Quiz complete: '+result.score+'/'+result.maximum+'\n\nRevision plan:\n'+result.revision_plan.join('\n'));$('message').placeholder='Ask coex anything…';}else message('assistant','Question '+(result.position+1)+' of '+result.total+': '+result.question);}catch(e){error(e.message);}finally{setBusy(false);}return;}
 if(lastStudyId && /^(quiz me|test me|mera test lo|take my quiz|next quiz|practice weak topics)[.!? ]*$/i.test($('message').value.trim())){try{quiz=await(await request('/api/quiz/start/'+lastStudyId,{})).json();$('message').value='';message('assistant','Question 1 of '+quiz.total+': '+quiz.question);$('message').placeholder='Type your quiz answer here…';}catch(e){error(e.message);}return;}
 if($('chat-mode').value==='study'||studyFile || (lastStudyId && /revision plan|study plan|study pack/i.test($('message').value))){await startStudy();return;}await submitChat(event);};
$('chat-mode').onchange=()=>{if(quiz&&!quiz.complete){quiz=null;$('message').placeholder='Ask coex anything…';error('Quiz paused. You can start another quiz from the study task.');}if($('chat-mode').value!=='study'&&studyFile){studyFile=null;showAttachment();}};
async function showMemory(){const data=await(await request('/api/memory')).json();$('memory-enabled').checked=data.enabled;$('memory-list').replaceChildren();for(const row of data.memories){const wrap=document.createElement('div');wrap.className='memory-row';const label=document.createElement('label');label.textContent=row.key;const input=document.createElement('input');input.value=row.value;input.maxLength=500;label.append(input);wrap.append(label);for(const action of ['Save','Delete']){const b=document.createElement('button');b.textContent=action;b.onclick=async()=>{try{await request('/api/memory/update',{id:row.id,action:action.toLowerCase(),value:input.value});await showMemory();}catch(e){error(e.message);}};wrap.append(b);}$('memory-list').append(wrap);}}
$('memory-settings').onclick=async()=>{try{await showMemory();$('memory-dialog').showModal();}catch(e){error(e.message);}};
$('memory-close').onclick=()=>$('memory-dialog').close();
$('memory-enabled').onchange=async()=>{try{await request('/api/memory/update',{enabled:$('memory-enabled').checked});}catch(e){error(e.message);}};
$('memory-clear').onclick=async()=>{try{await request('/api/memory/update',{action:'clear'});await showMemory();}catch(e){error(e.message);}};

function sendStudyUpload(form,card){return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST','/api/study');xhr.setRequestHeader('X-CSRFToken',csrf());xhr.timeout=300000;xhr.upload.onprogress=e=>{if(e.lengthComputable){const n=Math.round(e.loaded/e.total*100);card.textContent=n===100?'Indexing PDF text…':'Uploading PDF · '+n+'%';}};xhr.onload=()=>{try{const value=JSON.parse(xhr.responseText);if(xhr.status>=200&&xhr.status<300)resolve(value);else reject(Error(value.error||'PDF upload failed'));}catch{reject(Error('Server rejected the upload. Check its file-size limit.'));}};xhr.onerror=()=>reject(Error('Upload interrupted. Retry.'));xhr.ontimeout=()=>reject(Error('Upload or indexing timed out. Try a smaller section.'));xhr.send(form);});}
