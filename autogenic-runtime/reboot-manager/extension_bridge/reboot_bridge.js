/* Torsionfield reboot browser bridge — extension page, no service-worker dependency. */
'use strict';

const VERSION='0.1.0';
const params=new URLSearchParams(location.search);
const CLIENT=params.get('client')||`chrome-${crypto.randomUUID()}`;
const SERVER=params.get('server')||'http://127.0.0.1:17375';
const CHAT_RE=/^https:\/\/(?:chatgpt\.com|chat\.openai\.com)\//i;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

function fnv(text){let h=2166136261;for(const ch of String(text||'')){h^=ch.charCodeAt(0);h=Math.imul(h,16777619)}return(h>>>0).toString(16).padStart(8,'0')}
async function post(path,obj){const r=await fetch(SERVER+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(obj)});const j=await r.json();if(!r.ok)throw new Error(j.error||`HTTP ${r.status}`);return j}
async function get(path){const r=await fetch(SERVER+path);const j=await r.json();if(!r.ok)throw new Error(j.error||`HTTP ${r.status}`);return j}

function pageState(){
  const norm=v=>String(v==null?'':v).replace(/\r\n?/g,'\n').trim();
  const hash=v=>{let x=2166136261;for(const c of String(v||'')){x^=c.charCodeAt(0);x=Math.imul(x,16777619)}return(x>>>0).toString(16).padStart(8,'0')};
  const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
  let marker=sessionStorage.getItem('tf.reboot.tab');if(!marker){marker=(crypto.randomUUID?.()||`tf-${Date.now()}-${Math.random()}`);sessionStorage.setItem('tf.reboot.tab',marker)}
  let composer=null;for(const s of ['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']){const a=[...document.querySelectorAll(s)].filter(visible);if(a.length){composer=a.at(-1);break}}
  const composerText=composer?(typeof composer.value==='string'?composer.value:(composer.innerText||composer.textContent||'')):'';
  const nodes=[...document.querySelectorAll('[data-message-author-role]')];
  const recent=nodes.slice(-16).map((e,index)=>{const role=e.getAttribute('data-message-author-role')||'';const c=role==='user'?(e.querySelector('[data-testid="collapsible-user-message-content"]')||e):e;const text=norm(c.innerText||c.textContent||'').slice(0,10000);return{index,role,text,hash:hash(text)}});
  const users=recent.filter(x=>x.role==='user'), assistants=recent.filter(x=>x.role==='assistant');
  const latestUser=users.at(-1)||null, latestAssistant=assistants.at(-1)||null;
  const streaming=!!document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]');
  const path=location.pathname,conversationId=(path.match(/\/c\/([^/?#]+)/)||[])[1]||'',projectId=(path.match(/\/g\/(g-p-[^/]+)/)||[])[1]||'';
  const branchButtons=[...document.querySelectorAll('button,[role="button"]')].map(e=>({label:e.getAttribute('aria-label')||'',text:norm(e.innerText||e.textContent||'').slice(0,120),disabled:!!e.disabled})).filter(x=>/branch|previous|next|response/i.test(`${x.label} ${x.text}`)).slice(0,40);
  const branchIndicators=[...document.querySelectorAll('body *')].map(e=>norm(e.textContent||'')).filter(t=>/^\d+\s*\/\s*\d+$/.test(t)).slice(0,12);
  const root=document.documentElement;
  const autogenic={state:root?.dataset?.tfAutogenic||'',version:root?.dataset?.tfAutogenicVersion||'',bridge:root?.dataset?.tfExtensionBridge||'',residentElevated:root?.dataset?.tfResidentElevated||'',lastOp:root?.dataset?.tfAutogenicLastOp||'',lastOpStatus:root?.dataset?.tfAutogenicLastOpStatus||'',loopError:root?.dataset?.tfAutogenicLoopError||''};
  const executedActions=document.querySelectorAll('[data-tf-autogenic-executed="1"]').length;
  const pendingAction=!!(latestAssistant&&/\[\[TF_ACTION\/1/.test(latestAssistant.text)&&!executedActions);
  const stateStatus=streaming?'streaming':norm(composerText)?'draft':autogenic.loopError?'automation-error':pendingAction?'pending-action':'idle';
  return{marker,href:location.href,title:document.title,readyState:document.readyState,visibilityState:document.visibilityState,hidden:document.hidden,scrollY:window.scrollY,scrollHeight:document.documentElement.scrollHeight,conversationId,projectId,composerText:composerText.slice(0,65536),streaming,status:stateStatus,turnCount:nodes.length,recent,latestUser,latestAssistant,branchButtons,branchIndicators,branchSignature:[conversationId,latestUser?.hash||'',latestAssistant?.hash||'',branchIndicators.join('|'),branchButtons.map(x=>x.label||x.text).join('|')].join(':'),autogenic,executedActions,pendingAction,capturedAt:Date.now()};
}

async function captureTab(tab){
  const base={id:tab.id,windowId:tab.windowId,index:tab.index,active:tab.active,pinned:tab.pinned,discarded:tab.discarded,audible:tab.audible,mutedInfo:tab.mutedInfo||null,openerTabId:tab.openerTabId??null,groupId:tab.groupId??-1,status:tab.status||'',url:tab.url||'',title:tab.title||'',favIconUrl:tab.favIconUrl||''};
  if(!CHAT_RE.test(base.url))return{...base,chatgpt:false};
  try{
    const result=await chrome.scripting.executeScript({target:{tabId:tab.id},func:pageState});
    return{...base,chatgpt:true,state:result?.[0]?.result||null};
  }catch(error){return{...base,chatgpt:true,error:String(error?.message||error)};}
}

async function inventory(){
  const windows=await chrome.windows.getAll({populate:true,windowTypes:['normal','popup']});
  const groups=chrome.tabGroups?.query?await chrome.tabGroups.query({}).catch(()=>[]):[];
  const tabs=[];
  for(const win of windows){for(const tab of win.tabs||[])tabs.push(await captureTab(tab));}
  return{schema:'TF_BROWSER_INVENTORY/1',version:VERSION,client:CLIENT,runtimeId:chrome.runtime.id,manifest:chrome.runtime.getManifest(),capturedAt:Date.now(),windows:windows.map(w=>({id:w.id,focused:w.focused,top:w.top,left:w.left,width:w.width,height:w.height,state:w.state,type:w.type,incognito:w.incognito,alwaysOnTop:w.alwaysOnTop})),groups,tabs};
}

async function attach(tabId){try{await chrome.debugger.attach({tabId},'1.3');return true}catch(error){if(/already attached/i.test(String(error)))return false;throw error}}
async function detach(tabId){try{await chrome.debugger.detach({tabId})}catch(_) {}}
async function freeze(tabId,state){const owned=await attach(tabId);try{await chrome.debugger.sendCommand({tabId},'Page.setWebLifecycleState',{state});return{tabId,state}}finally{if(owned)await detach(tabId)}}
async function stopGeneration(tabId){
  const r=await chrome.scripting.executeScript({target:{tabId},func:async()=>{const sel='button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]';const before=!!document.querySelector(sel);document.querySelector(sel)?.click();const end=Date.now()+20000;while(document.querySelector(sel)&&Date.now()<end)await new Promise(r=>setTimeout(r,200));return{wasStreaming:before,settled:!document.querySelector(sel)}}});return r?.[0]?.result||{};
}

function setComposerText(text){
  const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
  let node=null;for(const s of ['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']){const a=[...document.querySelectorAll(s)].filter(visible);if(a.length){node=a.at(-1);break}}
  if(!node)throw new Error('composer-missing');node.focus();
  if(typeof node.value==='string'){const p=Object.getPrototypeOf(node),d=p&&Object.getOwnPropertyDescriptor(p,'value');if(d?.set)d.set.call(node,String(text));else node.value=String(text);node.dispatchEvent(new Event('input',{bubbles:true}));}
  else{let ok=false;try{document.execCommand('selectAll',false,null);ok=Boolean(document.execCommand('insertText',false,String(text)))}catch(_){}if(!ok){node.textContent=String(text);node.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:String(text)}));}}
  const observed=typeof node.value==='string'?node.value:(node.innerText||node.textContent||'');return{ok:String(observed).trim()===String(text).trim(),observed:String(observed)};
}

async function restoreDraft(tabId,text,scrollY){
  const r=await chrome.scripting.executeScript({target:{tabId},func:(t,y)=>{const result=(${setComposerText.toString()})(t);if(Number.isFinite(Number(y)))window.scrollTo(0,Number(y));return result;},args:[String(text||''),Number(scrollY||0)]});return r?.[0]?.result||{};
}

async function submitText(tabId,text,timeoutMs=120000){
  const baseline=await captureTab(await chrome.tabs.get(tabId));if(baseline.state?.streaming)throw new Error('target-streaming');if((baseline.state?.composerText||'').trim())throw new Error('composer-not-empty');
  await chrome.scripting.executeScript({target:{tabId},func:t=>{const set=(${setComposerText.toString()});const ins=set(t);if(!ins.ok)throw new Error('insert-not-observed');const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};let b=null;for(const s of ['button[data-testid="send-button"]','button[aria-label="Send prompt"]','button[aria-label="Send message"]','button[aria-label^="Send"]']){const a=[...document.querySelectorAll(s)].filter(visible);if(a.length){b=a.at(-1);break}}if(!b||b.disabled)throw new Error('send-button-not-ready');b.click();return true;},args:[String(text)]});
  const end=Date.now()+Math.max(5000,Number(timeoutMs||120000));let lastHash='',stableAt=0,latest=null;
  while(Date.now()<end){await sleep(500);latest=await captureTab(await chrome.tabs.get(tabId));const st=latest.state||{};const h=st.latestAssistant?.hash||'';const changed=h&&h!==baseline.state?.latestAssistant?.hash;if(changed&&!st.streaming){if(h===lastHash){if(!stableAt)stableAt=Date.now();if(Date.now()-stableAt>1500)return{ok:true,tab:latest,response:st.latestAssistant?.text||''};}else{lastHash=h;stableAt=Date.now();}}else stableAt=0;}
  throw new Error('submit-timeout');
}

async function handoff(tabId,prompt){
  const before=await captureTab(await chrome.tabs.get(tabId));const draft=before.state?.composerText||'';if(before.state?.streaming)await stopGeneration(tabId);
  if(draft)await chrome.scripting.executeScript({target:{tabId},func:()=>{(${setComposerText.toString()})('')}});
  try{return await submitText(tabId,prompt,120000)}finally{if(draft){const live=await captureTab(await chrome.tabs.get(tabId));if(!(live.state?.composerText||'').trim())await restoreDraft(tabId,draft,before.state?.scrollY||0);}}
}

async function restoreBranch(tabId,saved){
  const expected=saved?.state?.latestAssistant?.hash||'';if(!expected)return{matched:true,reason:'no-expected-hash'};
  for(let attempt=0;attempt<20;attempt++){
    const current=await captureTab(await chrome.tabs.get(tabId));if(current.state?.latestAssistant?.hash===expected)return{matched:true,attempt};
    const click=await chrome.scripting.executeScript({target:{tabId},func:()=>{const candidates=[...document.querySelectorAll('button,[role="button"]')].filter(e=>!/disabled/i.test(e.getAttribute('aria-disabled')||'')&&!e.disabled);const next=candidates.find(e=>/next response|next branch|next/i.test(`${e.getAttribute('aria-label')||''} ${e.innerText||''}`));if(next){next.click();return'next'}const prev=candidates.find(e=>/previous response|previous branch|previous/i.test(`${e.getAttribute('aria-label')||''} ${e.innerText||''}`));if(prev){prev.click();return'previous'}return'';}});if(!click?.[0]?.result)break;await sleep(500);
  }
  const final=await captureTab(await chrome.tabs.get(tabId));return{matched:final.state?.latestAssistant?.hash===expected,observed:final.state?.latestAssistant?.hash||'',expected};
}

async function restoreManifest(snapshot){
  const saved=(snapshot?.tabs||[]).filter(t=>t.chatgpt);const current=await chrome.tabs.query({});const used=new Set();const results=[];
  for(const s of saved.sort((a,b)=>(a.windowId-b.windowId)||(a.index-b.index))){let tab=current.find(t=>!used.has(t.id)&&t.url===s.url);if(!tab){tab=await chrome.tabs.create({url:s.url,active:false,pinned:!!s.pinned});await waitTab(tab.id,30000)}used.add(tab.id);try{await chrome.tabs.update(tab.id,{pinned:!!s.pinned});await chrome.tabs.move(tab.id,{index:Math.max(0,Number(s.index||0))});const branch=await restoreBranch(tab.id,s);if((s.state?.composerText||'').trim())await restoreDraft(tab.id,s.state.composerText,s.state.scrollY||0);if(s.active)await chrome.tabs.update(tab.id,{active:true});results.push({savedId:s.id,tabId:tab.id,ok:true,branch});}catch(error){results.push({savedId:s.id,tabId:tab.id,ok:false,error:String(error?.message||error)})}}
  return{ok:results.every(x=>x.ok),results,inventory:await inventory()};
}
async function waitTab(tabId,timeoutMs){const end=Date.now()+timeoutMs;while(Date.now()<end){const t=await chrome.tabs.get(tabId).catch(()=>null);if(t?.status==='complete')return t;await sleep(250)}throw new Error(`tab-ready-timeout:${tabId}`)}

const HANDLERS={
  health:async()=>({ok:true,version:VERSION,client:CLIENT,runtimeId:chrome.runtime.id,manifest:chrome.runtime.getManifest()}),
  inventory:async()=>inventory(),
  freeze:async p=>freeze(Number(p.tabId),'frozen'),
  unfreeze:async p=>freeze(Number(p.tabId),'active'),
  stop:async p=>stopGeneration(Number(p.tabId)),
  close:async p=>(await chrome.tabs.remove(Number(p.tabId)),{closed:true,tabId:Number(p.tabId)}),
  activate:async p=>(await chrome.tabs.update(Number(p.tabId),{active:true}),{activated:true,tabId:Number(p.tabId)}),
  open:async p=>chrome.tabs.create({url:String(p.url),active:p.active!==false,pinned:!!p.pinned}),
  restore_draft:async p=>restoreDraft(Number(p.tabId),p.text||'',p.scrollY||0),
  handoff:async p=>handoff(Number(p.tabId),String(p.prompt||'')),
  submit:async p=>submitText(Number(p.tabId),String(p.text||''),Number(p.timeoutMs||120000)),
  restore_manifest:async p=>restoreManifest(p.snapshot||{}),
};

async function hello(){
  const info={client:CLIENT,href:location.href,userAgent:navigator.userAgent,extensionPage:true,runtimeId:chrome.runtime.id,manifest:chrome.runtime.getManifest(),lastSeen:Date.now()};
  await post('/api/hello',info);document.querySelector('#status').innerHTML=`<span class=ok>browser-native bridge live</span> · ${CLIENT}`;document.querySelector('#detail').textContent=JSON.stringify({runtimeId:info.runtimeId,version:info.manifest.version,name:info.manifest.name},null,2);
}
async function loop(){
  for(;;){try{await hello();const j=await get(`/api/next?client=${encodeURIComponent(CLIENT)}&wait=20`);if(j.command){let result;try{const msg=j.command.message||{};const op=String(msg.op||msg.type||'');const fn=HANDLERS[op];if(!fn)throw new Error(`unsupported-bridge-op:${op}`);result={ok:true,value:await fn(msg.payload||msg)}}catch(error){result={ok:false,error:String(error?.stack||error)}}await post('/api/result',{client:CLIENT,id:j.command.id,result});}}catch(error){document.querySelector('#status').innerHTML=`<span class=bad>${String(error)}</span>`;await sleep(1000)} }
}
loop();
