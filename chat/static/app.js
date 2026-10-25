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
function message(role, text, file=null, actions=true) {
  $('welcome')?.remove();
  const box=document.createElement('article'); box.className=`bubble ${role}`;
  if(file){const name=document.createElement('span');name.className='file-name';name.textContent=`Attachment: ${file.name}`;box.append(name);}
  const content=document.createElement('div');content.className='message-text';content.textContent=text;box.append(content);
  if(actions){
    const buttons=document.createElement('div');buttons.className='actions';
    const copy=document.createElement('button');copy.textContent='Copy';copy.onclick=()=>navigator.clipboard.writeText(content.textContent).catch(()=>error('Copy failed. Please select and copy the text.'));buttons.append(copy);
    const action=document.createElement('button');action.textContent=role==='user'?'Edit & resend':'Download PDF';
    action.onclick=async()=>{if(busy)return;error('');
      if(role==='user'){$('message').value=content.textContent;attachment=file;showAttachment();$('message').focus();error('Edit and send as a new message. The original stays in this chat.');return;}
      action.disabled=true;
      try{const response=await request('/api/media',{action:'create_pdf',title:'coex response',text:content.textContent});download((await response.json()).data);}catch(e){error(e.message);}finally{action.disabled=false;}
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
      for(const line of lines){if(!line)continue;const part=JSON.parse(line);if(part.conversationId){conversationId=part.conversationId;accepted=true;}if(part.delta){reply+=part.delta;answer.content.textContent=reply;$('messages').scrollTop=$('messages').scrollHeight;}if(part.error)throw Error(part.error);if(part.done)finished=true;}
      if(chunk.done)break;
    }
    if(!finished)throw Error('Response interrupted. You can resend your question.');
    answer.box.remove();message('assistant',reply);
  }catch(e){error(e.name==='AbortError'?'Response stopped or timed out. You can resend your question.':e.message);if(answer?.content.textContent==='Thinking…')answer.content.textContent='No response received.';if(!$('message').value)$('message').value=text;}
  finally{clearTimeout(timer);controller=null;setBusy(false);if(accepted)refreshHistory().catch(e=>error(e.message));}
};
refreshHistory().catch(e=>error(e.message));
