/* Torsionfield Reboot Chronicle v7 — rolling state, ghost/detach, reattach. */
'use strict';

const VERSION='0.7.0';
const q=new URLSearchParams(location.search);
const CLIENT=q.get('client')||`chronicle-${chrome.runtime.id}`;
const CHRONICLE=q.get('chronicle')||'http://127.0.0.1:17376';
const RPC=q.get('rpc')||'http://127.0.0.1:17375';
const STATUS=document.getElementById('status');
const STORE_KEY='tf.reboot.chronicle.v7';
const BACKLOG_KEY='tf.reboot.chronicle.v7.backlog';
const GHOST_KEY='tf.reboot.chronicle.v7.ghosts';
const CHAT_RE=/^https:\/\/(?:chatgpt\.com|chat\.openai\.com)\//i;

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function deadline(p,ms,label){return Promise.race([p,new Promise((_,reject)=>setTimeout(()=>reject(new Error(`timeout:${label}`)),ms))])}
async function post(base,path,value){
  const response=await fetch(base+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(value)});
  if(!response.ok)throw new Error(`${path}:${response.status}`);
  return response.json();
}
function ids(url){
  const path=new URL(url).pathname;
  const c=path.match(/\/c\/([^/?#]+)/)?.[1]||'';
  const p=path.match(/\/g\/g-p-([^/?#]+)/)?.[1]||'';
  return{conversationId:c,projectId:p};
}
function keyFor(tab,state={}){return state.conversationId||tab.url||`${CLIENT}:${tab.id}`}

function pageDelta(){
  const composer=document.querySelector('#prompt-textarea,textarea,[contenteditable="true"][data-lexical-editor="true"],[contenteditable="true"][role="textbox"]');
  const draft=composer?('value'in composer?composer.value:(composer.innerText||composer.textContent||'')):'';
  const stop=!!document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]');
  const rows=[...document.querySelectorAll('[data-message-author-role]')];
  const user=rows.filter(n=>n.getAttribute('data-message-author-role')==='user');
  const assistant=rows.filter(n=>n.getAttribute('data-message-author-role')==='assistant');
  const take=n=>String(n?.innerText||n?.textContent||'').slice(-6000);
  const path=location.pathname;
  return{
    url:location.href,title:document.title,readyState:document.readyState,scrollY:window.scrollY,
    draft,streaming:stop,userCount:user.length,assistantCount:assistant.length,
    latestUserText:take(user.at(-1)),latestAssistantText:take(assistant.at(-1)),
    conversationId:path.match(/\/c\/([^/?#]+)/)?.[1]||'',
    projectId:path.match(/\/g\/g-p-([^/?#]+)/)?.[1]||'',
    branchSignature:`${path}${location.search}`,
    capturedAt:Date.now()
  };
}

async function localState(){return (await chrome.storage.local.get(STORE_KEY))[STORE_KEY]||{latest:{},events:[]}}
async function saveLocal(state){await chrome.storage.local.set({[STORE_KEY]:state})}
async function enqueue(path,value){
  const data=(await chrome.storage.local.get(BACKLOG_KEY))[BACKLOG_KEY]||[];
  data.push({path,value});
  if(data.length>100)data.splice(0,data.length-100);
  await chrome.storage.local.set({[BACKLOG_KEY]:data});
}
async function safePost(path,value){try{return await post(CHRONICLE,path,value)}catch(error){await enqueue(path,value);return{ok:false,error:String(error)}}}
async function flushBacklog(){
  const data=(await chrome.storage.local.get(BACKLOG_KEY))[BACKLOG_KEY]||[];
  if(!data.length)return;
  const remain=[];
  for(const item of data){try{await post(CHRONICLE,item.path,item.value)}catch{remain.push(item)}}
  await chrome.storage.local.set({[BACKLOG_KEY]:remain.slice(-100)});
}
async function event(type,tab,data={}){
  const value={client:CLIENT,type,tabId:tab?.id??null,windowId:tab?.windowId??null,url:tab?.url||'',title:tab?.title||'',ts:Date.now(),...data};
  const state=await localState();state.events.push(value);if(state.events.length>200)state.events.splice(0,state.events.length-200);await saveLocal(state);
  await safePost('/event',value);
}
async function capture(tab,reason='periodic'){
  if(!tab||!CHAT_RE.test(tab.url||''))return null;
  let runtimeState=null,pageState=null,runtimeError='',pageError='';
  try{runtimeState=await deadline(chrome.tabs.sendMessage(tab.id,{type:'tf.getSnapshot'}),1600,`message:${tab.id}`)}catch(error){runtimeError=String(error?.message||error)}
  try{
    const result=await deadline(chrome.scripting.executeScript({target:{tabId:tab.id},func:pageDelta}),3500,`script:${tab.id}`);
    pageState=result?.[0]?.result||null;
  }catch(error){pageError=String(error?.message||error)}
  const inferred=ids(tab.url||'https://chatgpt.com/');
  const state={...runtimeState,...pageState,conversationId:pageState?.conversationId||runtimeState?.conversationId||inferred.conversationId,projectId:pageState?.projectId||runtimeState?.projectId||inferred.projectId};
  const value={client:CLIENT,tabId:tab.id,windowId:tab.windowId,index:tab.index,active:tab.active,pinned:tab.pinned,discarded:tab.discarded,frozen:tab.frozen,autoDiscardable:tab.autoDiscardable,url:tab.url,title:tab.title,key:keyFor(tab,state),reason,state,runtimeError,pageError,ts:Date.now()};
  const local=await localState();local.latest[value.key]=value;await saveLocal(local);
  await safePost('/checkpoint',value);
  return value;
}

async function captureActive(reason='active-sweep'){
  const tabs=await chrome.tabs.query({active:true});
  const result=[];
  for(const tab of tabs)if(CHAT_RE.test(tab.url||''))result.push(await capture(tab,reason));
  return result.filter(Boolean);
}
async function metadataSweep(reason='metadata-sweep'){
  const tabs=await chrome.tabs.query({});
  await safePost('/event',{client:CLIENT,type:'tabs.metadata',reason,ts:Date.now(),tabs:tabs.map(t=>({id:t.id,windowId:t.windowId,index:t.index,active:t.active,pinned:t.pinned,discarded:t.discarded,frozen:t.frozen,autoDiscardable:t.autoDiscardable,url:t.url,title:t.title}))});
  return tabs;
}
async function restoreDraft(tabId,text){
  if(!text)return true;
  const fn=value=>{const c=document.querySelector('#prompt-textarea,textarea,[contenteditable="true"][data-lexical-editor="true"],[contenteditable="true"][role="textbox"]');if(!c)return false;c.focus();if('value'in c){const setter=Object.getOwnPropertyDescriptor(Object.getPrototypeOf(c),'value')?.set;setter?setter.call(c,value):c.value=value;c.dispatchEvent(new Event('input',{bubbles:true}))}else{c.textContent=value;c.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:value}))}return true};
  return Boolean((await chrome.scripting.executeScript({target:{tabId},func:fn,args:[text]}))?.[0]?.result);
}
async function ghost(tabId,mode='discard'){
  const tab=await chrome.tabs.get(tabId);const checkpoint=await capture(tab,'ghost');
  if(checkpoint?.state?.streaming)return{ok:false,state:'STREAMING',checkpoint};
  const ghosts=(await chrome.storage.local.get(GHOST_KEY))[GHOST_KEY]||{};
  const ghostId=`${checkpoint?.key||tab.url}:${Date.now()}`;
  ghosts[ghostId]={ghostId,mode,url:tab.url,title:tab.title,windowId:tab.windowId,index:tab.index,pinned:tab.pinned,checkpoint,createdAt:Date.now()};
  await chrome.storage.local.set({[GHOST_KEY]:ghosts});await safePost('/ghost',{client:CLIENT,...ghosts[ghostId]});
  if(mode==='close')await chrome.tabs.remove(tabId);else if(!tab.active)await chrome.tabs.discard(tabId);else return{ok:true,state:'CHECKPOINTED_ACTIVE_NOT_DISCARDED',ghostId};
  return{ok:true,state:mode==='close'?'DETACHED':'DISCARDED',ghostId};
}
async function reattach(ghostId){
  const ghosts=(await chrome.storage.local.get(GHOST_KEY))[GHOST_KEY]||{};const ghost=ghosts[ghostId];if(!ghost)return{ok:false,error:'ghost-not-found'};
  const tab=await chrome.tabs.create({url:ghost.url,active:false,pinned:Boolean(ghost.pinned)});
  const end=Date.now()+20000;while(Date.now()<end){const t=await chrome.tabs.get(tab.id);if(t.status==='complete')break;await sleep(250)}
  const draft=ghost.checkpoint?.state?.draft||ghost.checkpoint?.state?.composerText||'';let draftRestored=false;try{draftRestored=await restoreDraft(tab.id,draft)}catch{}
  delete ghosts[ghostId];await chrome.storage.local.set({[GHOST_KEY]:ghosts});await capture(await chrome.tabs.get(tab.id),'reattach');
  return{ok:true,tabId:tab.id,draftRestored};
}

const HANDLERS={
  health:async()=>({ok:true,version:VERSION,client:CLIENT}),
  flush_active:async()=>({ok:true,checkpoints:await captureActive('rpc-flush')}),
  metadata:async()=>({ok:true,tabs:await metadataSweep('rpc')}),
  chronicle_state:async()=>({ok:true,state:await localState(),ghosts:(await chrome.storage.local.get(GHOST_KEY))[GHOST_KEY]||{}}),
  ghost:async payload=>ghost(Number(payload.tabId),payload.mode||'discard'),
  reattach:async payload=>reattach(String(payload.ghostId||''))
};
async function poll(){
  while(true){
    try{
      const response=await fetch(`${RPC}/api/next?client=${encodeURIComponent(CLIENT)}&wait=20`);const body=await response.json();const command=body.command;
      if(command){let result;try{const fn=HANDLERS[command.message?.op];if(!fn)throw new Error(`unsupported:${command.message?.op}`);result={ok:true,value:await fn(command.message?.payload||{})}}catch(error){result={ok:false,error:String(error?.message||error)}}await post(RPC,'/api/result',{id:command.id,client:CLIENT,result})}
    }catch{await sleep(1000)}
  }
}

chrome.tabs.onActivated.addListener(async info=>{try{const tab=await chrome.tabs.get(info.tabId);await event('tab.activated',tab);await sleep(500);await capture(tab,'activated')}catch{}});
chrome.tabs.onUpdated.addListener(async(_id,change,tab)=>{try{await event('tab.updated',tab,{change});if(change.status==='complete'&&CHAT_RE.test(tab.url||''))await capture(tab,'updated-complete')}catch{}});
chrome.tabs.onCreated.addListener(tab=>event('tab.created',tab).catch(()=>{}));
chrome.tabs.onRemoved.addListener((tabId,removeInfo)=>safePost('/event',{client:CLIENT,type:'tab.removed',tabId,removeInfo,ts:Date.now()}).catch(()=>{}));
chrome.tabs.onMoved.addListener((tabId,moveInfo)=>safePost('/event',{client:CLIENT,type:'tab.moved',tabId,moveInfo,ts:Date.now()}).catch(()=>{}));
chrome.windows.onCreated.addListener(win=>safePost('/event',{client:CLIENT,type:'window.created',windowId:win.id,ts:Date.now()}).catch(()=>{}));
chrome.windows.onRemoved.addListener(windowId=>safePost('/event',{client:CLIENT,type:'window.removed',windowId,ts:Date.now()}).catch(()=>{}));
chrome.runtime.onMessage.addListener((message,sender)=>{if(sender.tab&&CHAT_RE.test(sender.tab.url||'')){const type=String(message?.type||'runtime.message');safePost('/event',{client:CLIENT,type:'runtime.message',messageType:type,tabId:sender.tab.id,windowId:sender.tab.windowId,ts:Date.now()}).catch(()=>{});if(/observe|response|stream|assistant|continue|stall|error/i.test(type))capture(sender.tab,`runtime:${type}`).catch(()=>{})}});

(async()=>{
  STATUS.textContent=`Chronicle ${VERSION}\n${CLIENT}`;
  await post(RPC,'/api/hello',{client:CLIENT,href:location.href,extensionPage:true,runtimeId:chrome.runtime.id,bridgeVersion:VERSION,lastSeen:Date.now()}).catch(()=>{});
  await flushBacklog();await metadataSweep('startup');await captureActive('startup');
  setInterval(()=>{flushBacklog().catch(()=>{});metadataSweep('periodic').catch(()=>{});captureActive('periodic').catch(()=>{})},30000);
  poll();
})();
