import fs from 'node:fs';
import path from 'node:path';
const port=Number(process.env.TF_WEBLLM_CDP||9235);
const base='http://127.0.0.1:'+port;
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const output=process.env.TF_WEBLLM_RECEIPT||path.resolve(import.meta.dirname,'../../.runtime/webllm-hardware-acceptance.json');
async function cdp(url,method,params={},timeoutMs=12000){
 return await new Promise((resolve,reject)=>{
  const ws=new WebSocket(url);const timer=setTimeout(()=>{ws.close();reject(Error('CDP_TIMEOUT:'+method))},timeoutMs);
  ws.onopen=()=>ws.send(JSON.stringify({id:12,method,params}));
  ws.onmessage=e=>{const d=JSON.parse(e.data);if(d.id!==12)return;clearTimeout(timer);ws.close();if(d.error||d.result?.exceptionDetails)reject(Error(JSON.stringify(d.error||d.result.exceptionDetails)));else resolve(d.result)};
  ws.onerror=()=>{clearTimeout(timer);reject(Error('CDP_WEBSOCKET_ERROR'))};
 });
}
const browser=await(await fetch(base+'/json/version')).json();
const targets=(await(await fetch(base+'/json')).json()).filter(x=>x.type==='page'&&x.url==='http://127.0.0.1:8989/');
if(targets.length!==1)throw Error('OWNED_WORKBENCH_NOT_SINGLETON: '+targets.length);
const ws=targets[0].webSocketDebuggerUrl;
const evalJs=async(expression,timeout=12000)=> (await cdp(ws,'Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},timeout)).result?.value;
const gpu=await cdp(browser.webSocketDebuggerUrl,'SystemInfo.getInfo');
const adapter=JSON.parse(await evalJs('(async()=>{const a=await navigator.gpu?.requestAdapter({powerPreference:"high-performance"});return JSON.stringify({vendor:a?.info?.vendor||"",architecture:a?.info?.architecture||"",shaderF16:a?.features.has("shader-f16")||false})})()'));
const primaryGpu=gpu.gpu?.devices?.[0]||{};
const baseRecord={schema:'torsionfield-webllm-acceptance/1',at:new Date().toISOString(),
 browser:browser.Browser,primaryGpuVendorId:primaryGpu.vendorId,actualAdapter:adapter,
 model:'Qwen3.5-2B-q4f32_1-MLC',source:'owner-localhost',smoke:null,editorial:null,pass:false};
function store(){fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(baseRecord,null,2)+'\n')}
store();
if(adapter.vendor.toLowerCase()!=='nvidia'||adapter.architecture.toLowerCase()!=='ampere')throw Error('HARDWARE_ADAPTER_NOT_CONFIRMED');
console.log('ACTUAL_WEBGPU',JSON.stringify(adapter));
let warm=false;
for(let i=0;i<120;i++){
 const state=JSON.parse(await evalJs('JSON.stringify({status:document.querySelector("#status")?.textContent,enabled:!document.querySelector("#draft")?.disabled})'));
 if(i%12===0)console.log('PRELOAD_STATUS',state.status);
 if(state.enabled){warm=true;break}
 await pause(750);
}
if(!warm)throw Error('MODEL_LOAD_TIMEOUT');
const t0=Date.now();
const smoke=await evalJs('globalThis.__tfSmokeTest()',70000);
baseRecord.smoke={...smoke,wallMs:Date.now()-t0};store();
console.log('SMOKE',JSON.stringify(baseRecord.smoke));
if(!smoke.ready||!/\bTF_READY\b/.test(smoke.output))throw Error('SMOKE_NOT_VERIFIED');
const source='PortSwigger researcher James Kettle reports testing several AI models on open-ended security research. In exploratory runs, the models preferred easily verified, lower-impact findings. Narrowly scoped prompts produced more targeted research. These are study-specific observations, not universal benchmark results.';
const expression='(()=>{const button=document.querySelector("#draft");if(button.disabled)return "MODEL_BUSY";document.querySelector("#source").value='+JSON.stringify(source)+';button.click();return "DRAFT_SUBMITTED"})()';
const submitted=await evalJs(expression);
if(submitted!=='DRAFT_SUBMITTED')throw Error('EDITORIAL_NOT_STARTED: '+submitted);
const t1=Date.now();
for(let i=0;i<90;i++){
 await pause(750);
 const report=JSON.parse(await evalJs('JSON.stringify({status:document.querySelector("#status")?.textContent,body:document.querySelector("#result")?.textContent,enabled:!document.querySelector("#draft")?.disabled})'));
 if(i%12===0)console.log('EDITORIAL_STATUS',report.status);
 if(report.enabled){
  baseRecord.editorial={wallMs:Date.now()-t1,status:report.status,text:report.body};
  break;
 }
}
store();
const result=baseRecord.editorial;
if(!result||!result.status.includes('LOCAL GENERATION COMPLETED')||!/^TITLE:\s*\S/m.test(result.text)||!/^RELEVANCE:\s*\S/m.test(result.text))throw Error('EDITORIAL_DRAFT_NOT_VERIFIED');
baseRecord.pass=true;store();
console.log('ACCEPTED_WEBLLM_HARDWARE_INFERENCE',JSON.stringify(baseRecord));
