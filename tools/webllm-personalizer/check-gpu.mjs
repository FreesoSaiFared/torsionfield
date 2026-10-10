// Read-only verification of the dedicated WebLLM browser and GPU.
const port=Number(process.argv[2]||9235);
const base='http://127.0.0.1:'+port;
async function cdp(wsUrl,method,params={}){
 return await new Promise((resolve,reject)=>{
  const ws=new WebSocket(wsUrl);
  const timer=setTimeout(()=>{ws.close();reject(Error('CDP_TIMEOUT'))},6000);
  ws.onopen=()=>ws.send(JSON.stringify({id:5,method,params}));
  ws.onmessage=e=>{
   const d=JSON.parse(e.data);
   if(d.id!==5)return;
   clearTimeout(timer);ws.close();
   if(d.error||d.result?.exceptionDetails)reject(Error(JSON.stringify(d.error||d.result.exceptionDetails)));
   else resolve(d.result);
  };
  ws.onerror=()=>{clearTimeout(timer);reject(Error('CDP_SOCKET_FAILED'))};
 });
}
const version=await(await fetch(base+'/json/version')).json();
const info=await cdp(version.webSocketDebuggerUrl,'SystemInfo.getInfo');
const tabs=(await(await fetch(base+'/json')).json()).filter(t=>t.type==='page'&&t.url==='http://127.0.0.1:8989/');
const main=tabs[0];
const observation=main?await cdp(main.webSocketDebuggerUrl,'Runtime.evaluate',{
 expression:'(async()=>{const a=await navigator.gpu?.requestAdapter({powerPreference:"high-performance"});return JSON.stringify({status:document.querySelector("#status")?.textContent,result:document.querySelector("#result")?.textContent,draftDisabled:document.querySelector("#draft")?.disabled,actualAdapterVendor:a?.info?.vendor||"",actualAdapterArchitecture:a?.info?.architecture||"",shaderF16:a?.features.has("shader-f16")||false})})()',
 awaitPromise:true,returnByValue:true
}):null;
const ui=observation?.result?.value?JSON.parse(observation.result.value):{};
const gpu=info?.gpu?.devices?.[0]||{};
const record={
 schema:'torsionfield-webllm-readiness/1',at:new Date().toISOString(),
 primaryGpuVendorId:gpu.vendorId,driver:gpu.driverVendor,driverVersion:gpu.driverVersion,
 webgpu:info?.gpu?.featureStatus?.webgpu,modelTabCount:tabs.length,
 modelLoaded:/MODEL LOADED|INFERENCE VERIFIED|LOCAL GENERATION COMPLETED/.test(ui.status||''),
 inferenceVerified:/INFERENCE VERIFIED|LOCAL GENERATION COMPLETED/.test(ui.status||''),
 status:ui.status||'TARGET_NOT_READY',
 browserPrimaryNvidia:gpu.vendorId===4318,
 actualAdapterVendor:ui.actualAdapterVendor||'unknown',
 actualAdapterArchitecture:ui.actualAdapterArchitecture||'unknown',
 shaderF16:Boolean(ui.shaderF16),
 actualWebgpuHardware:['nvidia','intel','amd','apple'].includes((ui.actualAdapterVendor||'').toLowerCase())&&!/(swiftshader|llvmpipe|lavapipe|softpipe)/i.test(ui.actualAdapterArchitecture||''),
};
record.readyForEditorialInference=record.actualWebgpuHardware&&record.inferenceVerified;
console.log(JSON.stringify(record));
if(!tabs.length)process.exitCode=2;
