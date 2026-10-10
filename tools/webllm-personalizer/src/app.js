import * as webllm from '@mlc-ai/web-llm';
const status=document.querySelector('#status'), button=document.querySelector('#draft'), result=document.querySelector('#result');
const MODEL='Qwen3.5-2B-q4f32_1-MLC';
let engine=null;
async function boot(){
 const adapter=await navigator.gpu?.requestAdapter({powerPreference:'high-performance'});
 if(!adapter){status.textContent='WEBLLM DEFERRED: WebGPU unavailable';return;}
 const vendor=(adapter.info?.vendor||'').toLowerCase();
 const architecture=(adapter.info?.architecture||'').toLowerCase();
 const hardware=['nvidia','intel','amd','apple'].includes(vendor)&&!/(swiftshader|llvmpipe|lavapipe|softpipe)/.test(architecture);
 if(!hardware){status.textContent='WEBLLM DEFERRED: Software or unverified WebGPU adapter ('+(vendor||'unknown')+' / '+(architecture||'unknown')+'). Use the native GPU fallback.';result.textContent='No model inference attempted on the software GPU';return;}
 status.textContent='Hardware WebGPU adapter identified. Starting model load ('+MODEL+')';
 const worker=new Worker('./dist/worker.js',{type:'module'});
 engine=await webllm.CreateWebWorkerMLCEngine(worker,MODEL,{initProgressCallback:r=>{status.textContent='Local WebLLM: '+r.text;}});
 status.textContent='MODEL LOADED: '+MODEL+' · inference has not yet passed a timed test';
 button.disabled=false; result.textContent='READY FOR PERSONALIZATION';
}
globalThis.__tfSmokeTest=async()=>{
 if(!engine)return {ready:false,error:'MODEL_NOT_INITIALIZED'};
 const started=performance.now();
 try{
  const response=await Promise.race([
   engine.chat.completions.create({messages:[{role:'user',content:'Reply with exactly TF_READY, nothing else. /no_think'}],max_tokens:48,temperature:0}),
   new Promise((_,reject)=>setTimeout(()=>reject(new Error('SMOKE_TIMEOUT')),45000))
  ]);
  const raw=response.choices?.[0]?.message?.content||'';
  const output=raw.replace(/<think>[\s\S]*?<\/think>\s*/g,'').trim();
  const ready=/\bTF_READY\b/.test(output);
  const receipt={ready,elapsedMs:Math.round(performance.now()-started),output};
  status.textContent=ready?'LOCAL WEBLLM INFERENCE VERIFIED · '+receipt.elapsedMs+' ms':'LOCAL MODEL LOADED; EXPECTED SMOKE OUTPUT NOT VERIFIED';
  return receipt;
 }catch(error){
  try{engine.interruptGenerate()}catch{}
  const receipt={ready:false,elapsedMs:Math.round(performance.now()-started),error:String(error)};
  status.textContent='LOCAL MODEL LOADED; INFERENCE NOT VERIFIED';
  return receipt;
 }
};
button.addEventListener('click',async()=>{
 if(!engine)return;
 button.disabled=true;
 result.textContent='LOCAL DRAFT IN PROGRESS';
 try{
  const prompt='You are the Torsionfield technical editor. From this provided source excerpt, give a plain English article title (10 words max), then a two-sentence relevance note for the Torsionfield project (agent runtimes, browser automation, verification, local-first compute). Do not invent facts. If evidence is insufficient, explicitly say so. Output TITLE: and RELEVANCE: lines. Source:\n'+document.querySelector('#source').value.slice(0,4000);
  const reply=await Promise.race([engine.chat.completions.create({messages:[{role:'user',content:prompt+'\n/no_think'}],max_tokens:240,temperature:0.2}),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Model too slow; draft stopped after 70 seconds')),70000))]);
  const raw=reply.choices?.[0]?.message?.content||'';
  const draft=raw.replace(/<think>[\s\S]*?<\/think>\s*/g,'').trim();
  if(!/^TITLE:\s*\S/m.test(draft)||!/^RELEVANCE:\s*\S/m.test(draft))throw new Error('DRAFT_FORMAT_INCOMPLETE');
  result.textContent=draft;
  status.textContent='LOCAL GENERATION COMPLETED — review this draft against the source';
 }catch(e){engine.interruptGenerate();result.textContent='Draft failed: '+String(e);status.textContent='MODEL LOADED; INFERENCE FAILED OR TIMED OUT — DRAFT UNAVAILABLE'}
 button.disabled=false;
});
if('requestIdleCallback' in window)requestIdleCallback(()=>boot().catch(e=>status.textContent='LOCAL MODEL ERROR: '+e.message),{timeout:3000});
else setTimeout(()=>boot().catch(e=>status.textContent='LOCAL MODEL ERROR: '+e.message),800);
