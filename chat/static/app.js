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
  for (const id of ['send','upload','new-chat','new-top','search']) $(id).disabled = value;
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

function streamingDisplay(raw) {
  // Display only complete lines while tokens are arriving. An unfinished line
  // can contain half of **bold**, a heading, or a code delimiter; rendering it
  // prematurely causes visible Markdown symbols and layout changes.
  const lastNewline = raw.lastIndexOf('\n');
  return lastNewline < 0 ? '' : raw.slice(0, lastNewline + 1);
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

function message(role, text, file=null, actions=true) {
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
  for(const chat of chats.filter(c=>c.title.toLowerCase().includes($('search').value.toLowerCase()))){const button=document.createElement('button');button.textContent=chat.title;button.disabled=busy;button.onclick=async()=>{if(busy)return;try{const data=await(await request(`/api/conversations/${chat.id}`)).json();conversationId=data.id;$('messages').replaceChildren();for(const m of data.messages){message(m.role,m.text,m.attachment);if(m.status!=='complete')error('A previous response was interrupted. You can resend your question.');}attachment=null;showAttachment();$('sidebar').classList.remove('open');}catch(e){error(e.message);}};$('history').append(button);}
}
$('search').oninput=renderHistory;
$('new-chat').onclick=$('new-top').onclick=()=>{if(!busy)location.assign('/');};
$('menu').onclick=()=>{$('sidebar').classList.toggle('open');$('menu').setAttribute('aria-expanded',String($('sidebar').classList.contains('open')));};
document.addEventListener('keydown',event=>{if(event.key==='Escape'){$('sidebar').classList.remove('open');$('menu').setAttribute('aria-expanded','false');}});
document.querySelectorAll('[data-prompt]').forEach(button=>button.onclick=()=>{$('message').value=button.dataset.prompt;$('message').focus();});
$('upload').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;error('');attachment=null;showAttachment();
  if(!file.size || file.size>2*1024*1024){error('Choose a nonempty file up to 2 MB.');event.target.value='';return;}
  setBusy(true);$('stop').hidden=true;
  try{const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('Cannot read this file.'));reader.readAsDataURL(file);});
    const result=await(await request('/api/media',{action:'inspect',data:encoded,mediaType:file.type || (file.name.toLowerCase().endsWith('.pdf')?'application/pdf':'')})).json();
    attachment={name:file.name,data:encoded,mediaType:result.mediaType};showAttachment();
  }catch(e){error(e.name==='TimeoutError'?'Upload timed out. Please try again.':e.message);}finally{setBusy(false);event.target.value='';}
};
$('stop').onclick=()=>controller?.abort();
$('message').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('composer').requestSubmit();}};
$('composer').onsubmit=async event=>{
  event.preventDefault();if(busy)return;
  const text=$('message').value.trim();if(!text)return;error('');
  const file=attachment;setBusy(true);controller=new AbortController();let timer=setTimeout(()=>controller.abort(),90000);let answer=null,finished=false,accepted=false;
  try{
    const response=await request('/api/chat',{text,conversationId,attachment:file},controller.signal);
    message('user',text,file);answer=message('assistant','Thinking…',null,false);$('message').value='';attachment=null;showAttachment();
    const reader=response.body.getReader();const decoder=new TextDecoder();let pending='',reply='';
    while(true){const chunk=await reader.read();pending+=decoder.decode(chunk.value||new Uint8Array(),{stream:!chunk.done});
      const lines=pending.split('\n');pending=lines.pop();
      for(const line of lines){if(!line)continue;const part=JSON.parse(line);if(part.conversationId){conversationId=part.conversationId;accepted=true;}if(part.delta){reply+=part.delta;answer.content.dataset.raw=reply;renderAssistant(answer.content,streamingDisplay(reply));$('messages').scrollTop=$('messages').scrollHeight;}if(part.error)throw Error(part.error);if(part.done)finished=true;}
      if(chunk.done)break;
    }
    if(!finished)throw Error('Response interrupted. You can resend your question.');
    answer.box.remove();message('assistant',reply);
  }catch(e){error(e.name==='AbortError'?'Response stopped or timed out. You can resend your question.':e.message);if(answer?.content.textContent==='Thinking…')answer.content.textContent='No response received.';if(!$('message').value)$('message').value=text;}
  finally{clearTimeout(timer);controller=null;setBusy(false);if(accepted)refreshHistory().catch(e=>error(e.message));}
};
refreshHistory().catch(e=>error(e.message));
