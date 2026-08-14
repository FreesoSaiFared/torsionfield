/* Torsionfield reboot browser bridge — extension page, no service-worker dependency. */
'use strict';

const VERSION='0.2.0';
const params=new URLSearchParams(location.search);
const CLIENT=params.get('client')||`chrome-${crypto.randomUUID()}`;
const SERVER=params.get('server')||'http://127.0.0.1:17375';
const CHAT_RE=/^https:\/\/(?:chatgpt\.com|chat\.openai\.com)\//i;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

async function post(path,obj){
  const response=await fetch(SERVER+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(obj)});
  const value=await response.json();
  if(!response.ok)throw new Error(value.error||`HTTP ${response.status}`);
  return value;
}
async function get(path){
  const response=await fetch(SERVER+path);
  const value=await response.json();
  if(!response.ok)throw new Error(value.error||`HTTP ${response.status}`);
  return value;
}

/* Every function passed to chrome.scripting.executeScript is intentionally
   self-contained. No closure serialization or generated JavaScript is used. */
function pageState(){
  const norm=v=>String(v==null?'':v).replace(/\r\n?/g,'\n').trim();
  const hash=v=>{let x=2166136261;for(const c of String(v||'')){x^=c.charCodeAt(0);x=Math.imul(x,16777619)}return(x>>>0).toString(16).padStart(8,'0')};
  const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
  let marker=sessionStorage.getItem('tf.reboot.tab');
  if(!marker){marker=(crypto.randomUUID?.()||`tf-${Date.now()}-${Math.random()}`);sessionStorage.setItem('tf.reboot.tab',marker)}
  let composer=null;
  for(const selector of ['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']){
    const candidates=[...document.querySelectorAll(selector)].filter(visible);
    if(candidates.length){composer=candidates.at(-1);break}
  }
  const composerText=composer?(typeof composer.value==='string'?composer.value:(composer.innerText||composer.textContent||'')):'';
  const nodes=[...document.querySelectorAll('[data-message-author-role]')];
  const recent=nodes.slice(-16).map((element,index)=>{
    const role=element.getAttribute('data-message-author-role')||'';
    const content=role==='user'?(element.querySelector('[data-testid="collapsible-user-message-content"]')||element):element;
    const text=norm(content.innerText||content.textContent||'').slice(0,10000);
    return{index,role,text,hash:hash(text)};
  });
  const users=recent.filter(x=>x.role==='user');
  const assistants=recent.filter(x=>x.role==='assistant');
  const latestUser=users.at(-1)||null;
  const latestAssistant=assistants.at(-1)||null;
  const latestAssistantNode=nodes.filter(n=>n.getAttribute('data-message-author-role')==='assistant').at(-1)||null;
  const streaming=!!document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]');
  const path=location.pathname;
  const conversationId=(path.match(/\/c\/([^/?#]+)/)||[])[1]||'';
  const projectId=(path.match(/\/g\/(g-p-[^/]+)/)||[])[1]||'';
  const branchButtons=[...document.querySelectorAll('button,[role="button"]')]
    .map(element=>({
      label:element.getAttribute('aria-label')||'',
      text:norm(element.innerText||element.textContent||'').slice(0,120),
      parentText:norm(element.parentElement?.innerText||element.parentElement?.textContent||'').slice(0,180),
      disabled:!!element.disabled||element.getAttribute('aria-disabled')==='true'
    }))
    .filter(x=>/branch|previous|next|response/i.test(`${x.label} ${x.text} ${x.parentText}`))
    .slice(0,40);
  const root=document.documentElement;
  const autogenic={
    state:root?.dataset?.tfAutogenic||'',
    version:root?.dataset?.tfAutogenicVersion||'',
    bridge:root?.dataset?.tfExtensionBridge||'',
    residentElevated:root?.dataset?.tfResidentElevated||'',
    lastOp:root?.dataset?.tfAutogenicLastOp||'',
    lastOpStatus:root?.dataset?.tfAutogenicLastOpStatus||'',
    loopError:root?.dataset?.tfAutogenicLoopError||''
  };
  const latestExecuted=latestAssistantNode?.dataset?.tfAutogenicExecuted==='1'||!!latestAssistantNode?.querySelector?.('[data-tf-autogenic-executed="1"]');
  const pendingAction=!!(latestAssistant&&/\[\[TF_ACTION\/1/.test(latestAssistant.text)&&!latestExecuted);
  const status=streaming?'streaming':norm(composerText)?'draft':autogenic.loopError?'automation-error':pendingAction?'pending-action':'idle';
  return{
    marker,href:location.href,title:document.title,readyState:document.readyState,
    visibilityState:document.visibilityState,hidden:document.hidden,scrollY:window.scrollY,
    scrollHeight:document.documentElement.scrollHeight,conversationId,projectId,
    composerText:composerText.slice(0,65536),streaming,status,turnCount:nodes.length,
    recent,latestUser,latestAssistant,branchButtons,
    branchSignature:[conversationId,latestUser?.hash||'',latestAssistant?.hash||'',branchButtons.map(x=>`${x.label}|${x.parentText}`).join('||')].join(':'),
    autogenic,pendingAction,capturedAt:Date.now()
  };
}

function setComposerText(text){
  const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
  let node=null;
  for(const selector of ['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']){
    const candidates=[...document.querySelectorAll(selector)].filter(visible);
    if(candidates.length){node=candidates.at(-1);break}
  }
  if(!node)throw new Error('composer-missing');
  const intended=String(text??'');
  node.focus();
  if(typeof node.value==='string'){
    const prototype=Object.getPrototypeOf(node);
    const descriptor=prototype&&Object.getOwnPropertyDescriptor(prototype,'value');
    if(descriptor?.set)descriptor.set.call(node,intended);else node.value=intended;
    node.dispatchEvent(new Event('input',{bubbles:true}));
  }else{
    let applied=false;
    try{
      document.execCommand('selectAll',false,null);
      applied=intended?Boolean(document.execCommand('insertText',false,intended)):Boolean(document.execCommand('delete',false,null));
    }catch(_){}
    if(!applied){
      node.textContent=intended;
      try{node.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:intended?'insertText':'deleteContentBackward',data:intended||null}))}
      catch(_){node.dispatchEvent(new Event('input',{bubbles:true}))}
    }
  }
  const observed=typeof node.value==='string'?node.value:(node.innerText||node.textContent||'');
  return{ok:String(observed).trim()===intended.trim(),observed:String(observed)};
}

function clickSend(){
  const visible=e=>{if(!e)return false;const s=getComputedStyle(e),r=e.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0};
  const root=document.querySelector('#prompt-textarea')?.closest('form')||document;
  for(const selector of ['button[data-testid="send-button"]','button[aria-label="Send prompt"]','button[aria-label="Send message"]','button[aria-label^="Send"]']){
    const candidates=[...root.querySelectorAll(selector)].filter(visible);
    if(candidates.length){const button=candidates.at(-1);if(button.disabled)throw new Error('send-button-disabled');button.click();return true}
  }
  throw new Error('send-button-missing');
}

function clickBranchStep(){
  const buttons=[...document.querySelectorAll('button,[role="button"]')].filter(element=>!element.disabled&&element.getAttribute('aria-disabled')!=='true');
  const label=element=>`${element.getAttribute('aria-label')||''} ${element.innerText||element.textContent||''}`;
  const next=buttons.find(element=>/next response|next branch/i.test(label(element)));
  if(next){next.click();return'next'}
  const previous=buttons.find(element=>/previous response|previous branch/i.test(label(element)));
  if(previous){previous.click();return'previous'}
  return'';
}

async function captureTab(tab){
  const base={
    id:tab.id,windowId:tab.windowId,index:tab.index,active:tab.active,pinned:tab.pinned,
    discarded:tab.discarded,audible:tab.audible,mutedInfo:tab.mutedInfo||null,
    openerTabId:tab.openerTabId??null,groupId:tab.groupId??-1,status:tab.status||'',
    url:tab.url||'',title:tab.title||'',favIconUrl:tab.favIconUrl||''
  };
  if(!CHAT_RE.test(base.url))return{...base,chatgpt:false};
  if(tab.discarded)return{...base,chatgpt:true,discardedState:true};
  try{
    const result=await chrome.scripting.executeScript({target:{tabId:tab.id},func:pageState});
    return{...base,chatgpt:true,state:result?.[0]?.result||null};
  }catch(error){return{...base,chatgpt:true,error:String(error?.message||error)};}
}

async function inventory(){
  const windows=await chrome.windows.getAll({populate:true,windowTypes:['normal','popup']});
  let groups=[];
  try{if(chrome.tabGroups?.query)groups=await chrome.tabGroups.query({})}catch(_){}
  const tabs=[];
  for(const win of windows)for(const tab of win.tabs||[])tabs.push(await captureTab(tab));
  return{
    schema:'TF_BROWSER_INVENTORY/1',version:VERSION,client:CLIENT,runtimeId:chrome.runtime.id,
    manifest:{name:chrome.runtime.getManifest().name,version:chrome.runtime.getManifest().version},
    capturedAt:Date.now(),
    windows:windows.map(w=>({id:w.id,focused:w.focused,top:w.top,left:w.left,width:w.width,height:w.height,state:w.state,type:w.type,incognito:w.incognito,alwaysOnTop:w.alwaysOnTop})),
    groups,tabs
  };
}

async function attachDebugger(tabId){
  try{await chrome.debugger.attach({tabId},'1.3');return true}
  catch(error){if(/already attached/i.test(String(error?.message||error)))return false;throw error}
}
async function detachDebugger(tabId){try{await chrome.debugger.detach({tabId})}catch(_) {}}
async function setLifecycle(tabId,state){
  const owned=await attachDebugger(tabId);
  try{await chrome.debugger.sendCommand({tabId},'Page.setWebLifecycleState',{state});return{tabId,state}}
  finally{if(owned)await detachDebugger(tabId)}
}

async function stopGeneration(tabId){
  const result=await chrome.scripting.executeScript({target:{tabId},func:async()=>{
    const selector='button[data-testid="stop-button"],button[aria-label^="Stop"],button[aria-label*="Stop generating"]';
    const before=!!document.querySelector(selector);
    document.querySelector(selector)?.click();
    const deadline=Date.now()+20000;
    while(document.querySelector(selector)&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,200));
    return{wasStreaming:before,settled:!document.querySelector(selector)};
  }});
  return result?.[0]?.result||{};
}

async function restoreDraft(tabId,text,scrollY=0){
  const result=await chrome.scripting.executeScript({target:{tabId},func:setComposerText,args:[String(text??'')]});
  if(Number.isFinite(Number(scrollY)))await chrome.scripting.executeScript({target:{tabId},func:y=>{window.scrollTo(0,Number(y));return window.scrollY},args:[Number(scrollY)]});
  return result?.[0]?.result||{};
}

async function submitText(tabId,text,timeoutMs=120000){
  const baseline=await captureTab(await chrome.tabs.get(tabId));
  if(baseline.state?.streaming)throw new Error('target-streaming');
  if((baseline.state?.composerText||'').trim())throw new Error('composer-not-empty');
  const inserted=await chrome.scripting.executeScript({target:{tabId},func:setComposerText,args:[String(text)]});
  if(!inserted?.[0]?.result?.ok)throw new Error('insert-not-observed');
  await chrome.scripting.executeScript({target:{tabId},func:clickSend});
  const deadline=Date.now()+Math.max(5000,Number(timeoutMs||120000));
  let lastHash='',stableAt=0,latest=null;
  while(Date.now()<deadline){
    await sleep(500);
    latest=await captureTab(await chrome.tabs.get(tabId));
    const state=latest.state||{};
    const hash=state.latestAssistant?.hash||'';
    const changed=hash&&hash!==baseline.state?.latestAssistant?.hash;
    if(changed&&!state.streaming){
      if(hash===lastHash){
        if(!stableAt)stableAt=Date.now();
        if(Date.now()-stableAt>1500)return{ok:true,tab:latest,response:state.latestAssistant?.text||''};
      }else{lastHash=hash;stableAt=Date.now()}
    }else stableAt=0;
  }
  throw new Error('submit-timeout');
}

async function handoff(tabId,prompt){
  const before=await captureTab(await chrome.tabs.get(tabId));
  const draft=before.state?.composerText||'';
  if(before.state?.streaming)await stopGeneration(tabId);
  if(draft)await chrome.scripting.executeScript({target:{tabId},func:setComposerText,args:['']});
  try{return await submitText(tabId,prompt,120000)}
  finally{
    if(draft){
      const live=await captureTab(await chrome.tabs.get(tabId));
      if(!(live.state?.composerText||'').trim())await restoreDraft(tabId,draft,before.state?.scrollY||0);
    }
  }
}

async function restoreBranch(tabId,saved){
  const expected=saved?.state?.latestAssistant?.hash||'';
  if(!expected)return{matched:true,reason:'no-expected-hash'};
  for(let attempt=0;attempt<20;attempt++){
    const current=await captureTab(await chrome.tabs.get(tabId));
    if(current.state?.latestAssistant?.hash===expected)return{matched:true,attempt};
    const step=await chrome.scripting.executeScript({target:{tabId},func:clickBranchStep});
    if(!step?.[0]?.result)break;
    await sleep(500);
  }
  const final=await captureTab(await chrome.tabs.get(tabId));
  return{matched:final.state?.latestAssistant?.hash===expected,observed:final.state?.latestAssistant?.hash||'',expected};
}

async function waitTab(tabId,timeoutMs=30000){
  const deadline=Date.now()+timeoutMs;
  while(Date.now()<deadline){
    const tab=await chrome.tabs.get(tabId).catch(()=>null);
    if(tab?.status==='complete')return tab;
    await sleep(250);
  }
  throw new Error(`tab-ready-timeout:${tabId}`);
}

async function restoreManifest(snapshot){
  const saved=(snapshot?.tabs||[]).filter(tab=>tab.chatgpt);
  let current=await chrome.tabs.query({});
  const used=new Set();
  const results=[];
  for(const record of saved.sort((a,b)=>(a.windowId-b.windowId)||(a.index-b.index))){
    let tab=current.find(candidate=>!used.has(candidate.id)&&candidate.url===record.url);
    if(!tab){
      tab=await chrome.tabs.create({url:record.url,active:false,pinned:!!record.pinned});
      await waitTab(tab.id,30000);
      current=await chrome.tabs.query({});
    }
    used.add(tab.id);
    try{
      await chrome.tabs.update(tab.id,{pinned:!!record.pinned});
      await chrome.tabs.move(tab.id,{index:Math.max(0,Number(record.index||0))});
      const branch=await restoreBranch(tab.id,record);
      if((record.state?.composerText||'').trim())await restoreDraft(tab.id,record.state.composerText,record.state.scrollY||0);
      if(record.active)await chrome.tabs.update(tab.id,{active:true});
      results.push({savedId:record.id,tabId:tab.id,ok:true,branch});
    }catch(error){results.push({savedId:record.id,tabId:tab.id,ok:false,error:String(error?.message||error)})}
  }
  return{ok:results.every(x=>x.ok&&x.branch?.matched!==false),results,inventory:await inventory()};
}

async function rehearseRestore(snapshot){
  const saved=(snapshot?.tabs||[]).filter(tab=>tab.chatgpt&&tab.url);
  const results=[];
  for(const record of saved){
    let clone=null;
    try{
      clone=await chrome.tabs.create({url:record.url,active:false});
      await waitTab(clone.id,30000);
      const branch=await restoreBranch(clone.id,record);
      const captured=await captureTab(await chrome.tabs.get(clone.id));
      results.push({savedId:record.id,url:record.url,ok:branch.matched!==false,branch,observedHash:captured.state?.latestAssistant?.hash||''});
    }catch(error){results.push({savedId:record.id,url:record.url,ok:false,error:String(error?.message||error)})}
    finally{if(clone?.id)await chrome.tabs.remove(clone.id).catch(()=>null)}
  }
  return{ok:results.every(x=>x.ok),results};
}

const HANDLERS={
  health:async()=>({ok:true,version:VERSION,client:CLIENT,runtimeId:chrome.runtime.id,manifest:chrome.runtime.getManifest()}),
  inventory:async()=>inventory(),
  freeze:async payload=>setLifecycle(Number(payload.tabId),'frozen'),
  unfreeze:async payload=>setLifecycle(Number(payload.tabId),'active'),
  stop:async payload=>stopGeneration(Number(payload.tabId)),
  close:async payload=>(await chrome.tabs.remove(Number(payload.tabId)),{closed:true,tabId:Number(payload.tabId)}),
  activate:async payload=>(await chrome.tabs.update(Number(payload.tabId),{active:true}),{activated:true,tabId:Number(payload.tabId)}),
  open:async payload=>chrome.tabs.create({url:String(payload.url),active:payload.active!==false,pinned:!!payload.pinned}),
  restore_draft:async payload=>restoreDraft(Number(payload.tabId),payload.text||'',payload.scrollY||0),
  handoff:async payload=>handoff(Number(payload.tabId),String(payload.prompt||'')),
  submit:async payload=>submitText(Number(payload.tabId),String(payload.text||''),Number(payload.timeoutMs||120000)),
  restore_manifest:async payload=>restoreManifest(payload.snapshot||{}),
  rehearse_restore:async payload=>rehearseRestore(payload.snapshot||{})
};

async function hello(){
  const manifest=chrome.runtime.getManifest();
  const info={client:CLIENT,href:location.href,userAgent:navigator.userAgent,extensionPage:true,runtimeId:chrome.runtime.id,manifest:{name:manifest.name,version:manifest.version},bridgeVersion:VERSION};
  await post('/api/hello',info);
  document.querySelector('#status').innerHTML=`<span class="ok">browser-native bridge live</span> · ${CLIENT}`;
  document.querySelector('#detail').textContent=JSON.stringify({runtimeId:info.runtimeId,extensionVersion:manifest.version,bridgeVersion:VERSION},null,2);
}

async function loop(){
  for(;;){
    try{
      await hello();
      const response=await get(`/api/next?client=${encodeURIComponent(CLIENT)}&wait=20`);
      if(response.command){
        let result;
        try{
          const message=response.command.message||{};
          const op=String(message.op||message.type||'');
          const handler=HANDLERS[op];
          if(!handler)throw new Error(`unsupported-bridge-op:${op}`);
          result={ok:true,value:await handler(message.payload||message)};
        }catch(error){result={ok:false,error:String(error?.stack||error)}}
        await post('/api/result',{client:CLIENT,id:response.command.id,result});
      }
    }catch(error){
      document.querySelector('#status').innerHTML=`<span class="bad">${String(error?.message||error)}</span>`;
      await sleep(1000);
    }
  }
}

loop();
