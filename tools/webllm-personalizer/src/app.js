import * as webllm from '@mlc-ai/web-llm';
const status=document.querySelector('#status'), button=document.querySelector('#draft'), result=document.querySelector('#result');
const MODEL='SmolLM2-360M-Instruct-q4f32_1-MLC';
let engine=null;
async function boot(){
 const gpu=!!navigator.gpu && !!(await navigator.gpu.requestAdapter());
 if(!gpu){status.textContent='WebGPU unavailable — model not loaded';return;}
 status.textContent='WebGPU available. Starting background model load ('+MODEL+')';
 const worker=new Worker('./dist/worker.js',{type:'module'});
 engine=await webllm.CreateWebWorkerMLCEngine(worker,MODEL,{initProgressCallback:r=>{status.textContent='Local WebLLM: '+r.text;}});
 status.textContent='MODEL LOADED: '+MODEL+' · inference has not yet passed a timed test';
 button.disabled=false; result.textContent='READY FOR PERSONALIZATION';
}
button.addEventListener('click',async()=>{
 if(!engine)return;
 button.disabled=true;
 result.textContent='LOCAL DRAFT IN PROGRESS';
 try{
  const prompt='You are the Torsionfield technical editor. From this provided source excerpt, give a plain English article title (10 words max), then a two-sentence relevance note for the Torsionfield project (agent runtimes, browser automation, verification, local-first compute). Do not invent facts. If evidence is insufficient, explicitly say so. Output TITLE: and RELEVANCE: lines. Source:\n'+document.querySelector('#source').value.slice(0,4000);
  const reply=await Promise.race([engine.chat.completions.create({messages:[{role:'user',content:prompt}],max_tokens:96,temperature:0.35}),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Model too slow; draft stopped after 70 seconds')),70000))]);
  result.textContent=reply.choices?.[0]?.message?.content||'No draft returned';
  status.textContent='LOCAL GENERATION COMPLETED — review this draft against the source';
 }catch(e){engine.interruptGenerate();result.textContent='Draft failed: '+String(e);status.textContent='MODEL LOADED; INFERENCE FAILED OR TIMED OUT — DRAFT UNAVAILABLE'}
 button.disabled=false;
});
if('requestIdleCallback' in window)requestIdleCallback(()=>boot().catch(e=>status.textContent='LOCAL MODEL ERROR: '+e.message),{timeout:3000});
else setTimeout(()=>boot().catch(e=>status.textContent='LOCAL MODEL ERROR: '+e.message),800);
