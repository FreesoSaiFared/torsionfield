// ==UserScript==
// @name         Torsionfield Autogenic Runtime Bridge
// @namespace    https://torsionfield.de/
// @version      0.2.2
// @description  Connect ChatGPT's page/session to the privileged Torsionfield browser bridge and resident.
// @match        https://chatgpt.com/*
// @match        https://chat.openai.com/*
// @grant        none
// @run-at       document-start
// ==/UserScript==

(() => {
  'use strict';
  const VERSION='0.2.2';
  const CALL='TORSIONFIELD_PAGE_CALL', RESULT='TORSIONFIELD_PAGE_RESULT', PING='TORSIONFIELD_BRIDGE_PING', READY='TORSIONFIELD_BRIDGE_READY';
  const HANDOFF_PATTERNS=[/WHAT I NEED FROM YOU NOW/i,/\bType CONTINUE\b/i,/\b(?:please\s+)?run (?:this|the following) command\b/i,/\bopen (?:DevTools|chrome:\/\/extensions)\b/i,/\breload (?:the )?(?:extension|userscript|browser|Chrome)\b/i,/\brestart (?:the )?(?:browser|Chrome|Chromium)\b/i,/\binstall (?:this|the )?userscript\b/i,/\bsend me (?:the )?(?:log|output|result)\b/i];
  const ACTION_RE=/\[\[TF_ACTION\/1\s*([\s\S]*?)\s*\[\[\/TF_ACTION\]\]/g;
  const processed=new WeakSet(); let recoveryDepth=0,running=false,observer=null,bridgeReady=false,bridgeWait=null;

  function id(){return globalThis.crypto?.randomUUID?.()||`tf-${Date.now()}-${Math.random().toString(16).slice(2)}`;}
  function root(){return document.documentElement;}
  function mark(name,value){const node=root();if(node)node.dataset[name]=String(value);}
  function awaitBridge(timeoutMs=10000){
    if(bridgeReady)return Promise.resolve(true);
    if(bridgeWait)return bridgeWait;
    bridgeWait=new Promise((resolve,reject)=>{
      let done=false;
      const finish=(ok,error)=>{if(done)return;done=true;clearInterval(pulse);clearTimeout(timer);window.removeEventListener('message',onMessage);bridgeWait=null;ok?resolve(true):reject(error)};
      const onMessage=(event)=>{if(event.source===window&&event.data?.channel===READY){bridgeReady=true;mark('tfExtensionBridge','ready');finish(true);}};
      window.addEventListener('message',onMessage);
      const ping=()=>window.postMessage({channel:PING},'*');
      const pulse=setInterval(ping,200); const timer=setTimeout(()=>finish(false,new Error('Torsionfield extension bridge unavailable')),timeoutMs); ping();
    });
    return bridgeWait;
  }
  async function residentCall(path,args={},timeoutMs=300000){
    await awaitBridge();
    return new Promise((resolve,reject)=>{
      const requestId=id(); let settled=false;
      const finish=(ok,value)=>{if(settled)return;settled=true;clearTimeout(timer);window.removeEventListener('message',onMessage);ok?resolve(value):reject(new Error(String(value||'resident bridge error')))};
      const onMessage=(event)=>{const d=event.data;if(event.source!==window||d?.channel!==RESULT||d.id!==requestId)return;finish(Boolean(d.ok),d.ok?d.result:d.error);};
      const timer=setTimeout(()=>finish(false,`resident bridge timeout after ${timeoutMs}ms`),timeoutMs);
      window.addEventListener('message',onMessage);
      window.postMessage({channel:CALL,id:requestId,path,args},'*');
    });
  }
  async function health(){return residentCall('/v1/health',{},20000);}
  async function handshake(){mark('tfAutogenic','connecting');mark('tfAutogenicVersion',VERSION);let lastError=null;for(const delay of [0,500,1500]){if(delay)await new Promise(r=>setTimeout(r,delay));try{const h=await health();mark('tfAutogenic','ready');mark('tfResidentPid',h.pid||'');mark('tfResidentElevated',Boolean(h.elevated));const node=root();if(node)delete node.dataset.tfResidentError;return h;}catch(error){lastError=error;mark('tfAutogenic','connecting');}}mark('tfAutogenic','resident-error');mark('tfResidentError',String(lastError?.message||lastError||'resident unavailable').slice(0,300));throw lastError;}
  function visible(node){if(!node||node.isConnected===false)return false;const style=getComputedStyle(node);if(style.display==='none'||style.visibility==='hidden')return false;const r=node.getBoundingClientRect();return r.width>0&&r.height>0;}
  function composer(){for(const selector of ['#prompt-textarea[contenteditable="true"]','form [contenteditable="true"][role="textbox"]','form [contenteditable="true"]','form textarea']){const nodes=[...document.querySelectorAll(selector)].filter(visible);if(nodes.length)return nodes.at(-1);}return null;}
  function composerText(node){return !node?'':typeof node.value==='string'?node.value:(node.innerText||node.textContent||'');}
  function correlationText(value){return String(value==null?'':value).replace(/\r\n?/g,'\n').replace(/\s+/g,' ').trim();}
  function sendButton(){const node=composer();const form=node?.closest?.('form')||document;for(const selector of ['button[data-testid="send-button"]','button[aria-label="Send prompt"]','button[aria-label="Send message"]','button[aria-label^="Send"]']){const nodes=[...form.querySelectorAll(selector)].filter(visible);if(nodes.length)return nodes.at(-1);}return null;}
  function setComposer(text){const node=composer();if(!node)throw new Error('ChatGPT composer not found');if(composerText(node).trim())throw new Error('HUMAN_DRAFT_PRESENT');node.focus();if(typeof node.value==='string'){const proto=Object.getPrototypeOf(node),descriptor=proto&&Object.getOwnPropertyDescriptor(proto,'value');if(descriptor?.set)descriptor.set.call(node,text);else node.value=text;}else node.textContent=text;try{node.dispatchEvent(new InputEvent('input',{bubbles:true,composed:true,inputType:'insertText',data:text}));}catch(_){node.dispatchEvent(new Event('input',{bubbles:true}));}return node;}
  async function submit(text){const intended=String(text||'');const node=setComposer(intended);let observed='';for(let i=0;i<40;i++){await new Promise(r=>setTimeout(r,50));observed=composerText(composer());if(correlationText(observed)===correlationText(intended))break;}if(correlationText(observed)!==correlationText(intended))throw new Error('INSERTION_NOT_OBSERVED');let button=null;for(let i=0;i<60;i++){button=sendButton();if(button&&!button.disabled)break;await new Promise(r=>setTimeout(r,50));}if(!button||button.disabled)throw new Error('SEND_BUTTON_NOT_READY');button.click();}
  function assistantText(node){return(node?.innerText||node?.textContent||'').trim();}
  function parseActions(text){const out=[];ACTION_RE.lastIndex=0;let m;while((m=ACTION_RE.exec(text)))out.push(JSON.parse(m[1]));return out;}
  async function executeAction(action){if(!action||typeof action!=='object')throw new Error('invalid TF action');const table={exec:'/v1/exec','process.start':'/v1/process/start','process.kill':'/v1/process/kill','process.list':'/v1/process/list','fs.read':'/v1/fs/read','fs.write':'/v1/fs/write','fs.delete':'/v1/fs/delete','browser.launch':'/v1/browser/launch','browser.restart':'/v1/browser/restart','browser.status':'/v1/browser/status'},path=table[String(action.op||'')];if(!path)throw new Error(`unsupported TF action: ${action.op}`);mark('tfAutogenicLastOp',action.op);const result=await residentCall(path,action.args||{});mark('tfAutogenicLastOpStatus','ok');return result;}
  async function closeActionLoop(node,text){const actions=parseActions(text);if(!actions.length)return false;const receipts=[];for(const action of actions){try{receipts.push({id:action.id||null,op:action.op,ok:true,result:await executeAction(action)});}catch(error){mark('tfAutogenicLastOpStatus','error');receipts.push({id:action.id||null,op:action.op,ok:false,error:String(error?.message||error)});}}node.dataset.tfAutogenicExecuted='1';await submit(`TORSIONFIELD MACHINE RESULT /1\n${JSON.stringify(receipts,null,2)}\nContinue the original task. Do not hand machine operations back to the human.`);return true;}
  function isHandoff(text){return HANDOFF_PATTERNS.some(pattern=>pattern.test(text));}
  async function recoverHandoff(node,text){if(recoveryDepth>=4)return;recoveryDepth++;const state=await residentCall('/v1/browser/status',{}).catch(error=>({error:String(error)}));node.dataset.tfAutogenicIntercepted='1';mark('tfAutogenicRecoveryDepth',recoveryDepth);await submit(['TORSIONFIELD AUTONOMY INTERCEPT /1','Your previous answer attempted to hand a machine/browser/software operation to the human.','Do not repeat the handoff. Continue the original task by using the local Torsionfield privileged resident.','When a machine operation is needed, emit one or more exact blocks of this form:','[[TF_ACTION/1','{"id":"short-id","op":"exec","args":{"shell":"command here"}}','[[/TF_ACTION]]','Available ops: exec, process.start, process.kill, process.list, fs.read, fs.write, fs.delete, browser.launch, browser.restart, browser.status.','The userscript will execute the block, insert the machine result, and let you continue.',`Resident/browser state: ${JSON.stringify(state)}`,'Previous attempted handoff follows:',text.slice(0,12000)].join('\n'));}
  async function processAssistant(node){if(!node||processed.has(node)||running)return;const text=assistantText(node);if(!text)return;if(document.querySelector('button[data-testid="stop-button"],button[aria-label^="Stop"]'))return;processed.add(node);running=true;try{if(await closeActionLoop(node,text))return;if(isHandoff(text))await recoverHandoff(node,text);}catch(error){mark('tfAutogenicLoopError',String(error?.message||error).slice(0,300));console.error('[Torsionfield Autogenic]',error);}finally{running=false;}}
  function scan(){const nodes=Array.from(document.querySelectorAll('[data-message-author-role="assistant"]'));if(nodes.length)processAssistant(nodes[nodes.length-1]);}
  function bootstrap(){if(observer)return;const node=root();if(!node){queueMicrotask(bootstrap);return;}observer=new MutationObserver(()=>queueMicrotask(scan));observer.observe(node,{childList:true,subtree:true,characterData:true});handshake().catch(()=>{});scan();}
  globalThis.Torsionfield=Object.freeze({version:VERSION,health,call:residentCall,execute:executeAction,scan,handshake});
  bootstrap();
})();
