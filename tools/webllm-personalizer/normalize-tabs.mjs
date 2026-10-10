// Narrow browser-root normalization: close only one verified idle duplicate.
const port=Number(process.argv[2]||9235);
const url='http://127.0.0.1:'+port;
async function pages(){
 return (await(await fetch(url+'/json')).json()).filter(t=>t.type==='page'&&t.url==='http://127.0.0.1:8989/');
}
async function status(t){
 return await new Promise((resolve,reject)=>{
  const w=new WebSocket(t.webSocketDebuggerUrl);
  const timer=setTimeout(()=>{w.close();reject(Error('TAB_QUERY_TIMEOUT'))},5000);
  w.onopen=()=>w.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression:'JSON.stringify({visibility:document.visibilityState,status:document.querySelector("#status")?.textContent,disabled:document.querySelector("#draft")?.disabled})',returnByValue:true}}));
  w.onmessage=e=>{const d=JSON.parse(e.data);if(d.id!==1)return;clearTimeout(timer);w.close();try{resolve(JSON.parse(d.result.result.value))}catch{reject(Error('INVALID_TAB_RESPONSE'))}};
  w.onerror=()=>{clearTimeout(timer);reject(Error('TAB_QUERY_FAILED'))};
 });
}
let initial=await pages();
if(initial.length===1){console.log('ONE_WORKBENCH_TAB');process.exit(0)}
if(initial.length!==2)throw Error('AMBIGUOUS_WORKBENCH_COUNT '+initial.length);
for(let attempt=0;attempt<36;attempt++){
 const tabs=await pages();if(tabs.length===1){console.log('TAB_NORMALIZED_CONCURRENTLY');process.exit(0)}
 if(tabs.length!==2)throw Error('AMBIGUOUS_WORKBENCH_COUNT '+tabs.length);
 const observed=await Promise.all(tabs.map(async t=>({id:t.id,...await status(t)})));
 const hidden=observed.filter(t=>t.visibility==='hidden'&&t.disabled===false);
 const active=observed.filter(t=>t.visibility==='visible');
 if(hidden.length===1&&active.length===1){
  const response=await fetch(url+'/json/close/'+hidden[0].id);
  if(!response.ok)throw Error('CLOSE_FAILED '+response.status);
  await new Promise(r=>setTimeout(r,250));
  const after=await pages();
  if(after.length!==1)throw Error('NOT_SINGLETON_AFTER_CLOSE '+after.length);
  console.log('VERIFIED_IDLE_DUPLICATE_CLOSED',hidden[0].id);process.exit(0)
 }
 await new Promise(r=>setTimeout(r,500));
}
throw Error('TABS_STILL_BUSY; refusing to close unknown model state');
