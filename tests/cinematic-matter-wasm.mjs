import {createServer} from 'node:http';
import {spawn} from 'node:child_process';
import {mkdtempSync,readFileSync,writeFileSync,rmSync,mkdirSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve,extname} from 'node:path';
const root=resolve(import.meta.dirname,'../public'),artifacts=resolve(import.meta.dirname,'../artifacts/cinematic-matter');
mkdirSync(artifacts,{recursive:true});
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.wasm':'application/wasm'};
const server=createServer((req,res)=>{
 const path=resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]).replace(/\/$/,'/index.html'));
 if(!path.startsWith(root+'/')||!existsSync(path)){res.writeHead(404).end();return}
 res.setHeader('Content-Type',mime[extname(path)]||'application/octet-stream');res.setHeader('Content-Security-Policy',"default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self' 'wasm-unsafe-eval'; frame-ancestors 'none'");
 res.end(readFileSync(path));
});
await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
const url=process.env.CM_URL||'http://127.0.0.1:'+server.address().port+'/cinematic-matter/';
const profile=mkdtempSync(join(tmpdir(),'cm-wasm-'));
const chrome=spawn('chromium',['--headless=new','--no-first-run','--no-default-browser-check','--disable-gpu','--window-size=1420,1080','--remote-debugging-port=0','--user-data-dir='+profile,url],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function wait(fn){for(let i=0;i<140;i++){try{const result=await fn();if(result)return result}catch{}await sleep(100)}throw Error('Wait timeout')}
let ws,seq=0;const pending=new Map();const checks=[];
function send(method,params={}){const id=++seq;return new Promise((resolve,reject)=>{const timeout=setTimeout(()=>{pending.delete(id);reject(Error('CDP timed out'))},10000);pending.set(id,{resolve,reject,timeout});ws.send(JSON.stringify({id,method,params}))})}
async function evaluate(expression){const response=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(response.result.exceptionDetails)throw Error(JSON.stringify(response.result.exceptionDetails));return response.result.result.value}
function assert(label,value){checks.push({label,pass:Boolean(value)});if(!value)throw Error('FAILED: '+label)}
try{
 const port=await wait(()=>Number(readFileSync(join(profile,'DevToolsActivePort'),'utf8').split('\n')[0]));
 const tab=await wait(async()=>{const r=await fetch('http://127.0.0.1:'+port+'/json/list');return (await r.json()).find(x=>x.type==='page'&&x.url.includes('cinematic-matter'))});
 ws=new WebSocket(tab.webSocketDebuggerUrl);
 await new Promise((yes,no)=>{ws.addEventListener('open',yes,{once:true});ws.addEventListener('error',no,{once:true})});
 ws.addEventListener('message',event=>{const msg=JSON.parse(event.data),entry=pending.get(msg.id);if(!entry)return;clearTimeout(entry.timeout);pending.delete(msg.id);msg.error?entry.reject(Error(msg.error.message)):entry.resolve(msg)});
 await send('Runtime.enable');await send('Page.enable');
 await wait(()=>evaluate("Boolean(window.CinematicMatterWasm?.state.ready&&window.CinematicMatterWasm?.state.seedCount>50)"));
 const meta=await evaluate("({wasm:window.CinematicMatterWasm.state,claims:document.querySelectorAll('article mark').length,engine:document.querySelector('#wasm-status').textContent})");
 assert('actual WASM module loads',meta.wasm.ready);
 assert('glyphs produce hundreds of seeds',meta.wasm.seedCount>=150);
 assert('canonical three HTML claims present',meta.claims===3);
 assert('colors and meanings visible during playback',await evaluate("document.querySelectorAll('.claim-key span').length===3"));
 const weight=await evaluate("(()=>{const w=window.CinematicMatterWasm;const initial=w.state.lineWeight;let control=document.querySelector('#filament-weight');control.value='2.5';control.dispatchEvent(new Event('input',{bubbles:true}));const changed=w.state.lineWeight;const label=document.querySelector('#filament-weight-value').value;control.value='1.7';control.dispatchEvent(new Event('input',{bubbles:true}));return {initial,changed,label,restored:w.state.lineWeight,explainer:document.querySelector('.plain-explainer')?.textContent.includes('ringing bell')}})()");
 assert('filament weight control changes actual Canvas rendering and restores default',weight.initial===1.7&&weight.changed===2.5&&weight.restored===1.7&&weight.label==='2.5×'&&weight.explainer);
 await evaluate("document.querySelector('.workbench').scrollIntoView({block:'start'})");
 const snapshots=[];
 for(const t of [0,4,8,13,19.8]){
  const check=await evaluate("(()=>{const p=window.CinematicMatterPilot; p.state.mode='watch';p.state.time="+t+";p.render();window.CinematicMatterWasm.draw();const v=window.CinematicMatterWasm.vertices;return {time:"+t+",sum:v.slice(0,750).reduce((a,b)=>a+b,0),head:v.slice(0,9)}})()");
  snapshots.push(check);
  if(t===4||t===8||t===13){const s=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});writeFileSync(join(artifacts,'wasm-'+t+'s.png'),Buffer.from(s.result.data,'base64'))}
 }
 assert('five distinct cinematic states',new Set(snapshots.map(x=>x.sum.toFixed(3))).size===5);
 const deterministic=await evaluate("(()=>{let p=window.CinematicMatterPilot;p.state.time=8;window.CinematicMatterWasm.draw();let a=window.CinematicMatterWasm.vertices.slice(0,900);p.state.time=13;window.CinematicMatterWasm.draw();p.state.time=8;window.CinematicMatterWasm.draw();let b=window.CinematicMatterWasm.vertices.slice(0,900);return a.every((x,i)=>x===b[i])})()");
 assert('random-access seek is deterministic',deterministic);
 const counter=await evaluate("(()=>{let p=window.CinematicMatterPilot;p.state.time=8;window.CinematicMatterWasm.draw();let a=window.CinematicMatterWasm.vertices.slice(0,750);let slider=document.querySelector('#damping');slider.value='.85';slider.dispatchEvent(new Event('input',{bubbles:true}));window.CinematicMatterWasm.draw();let b=window.CinematicMatterWasm.vertices.slice(0,750);return {changed:a.some((x,i)=>x!==b[i]),value:document.querySelector('#model-value').textContent}})()");
 assert('assumption modifies mathematics and geometry',counter.changed&&counter.value==='0.033');
 const dispute=await evaluate("(()=>{let select=document.querySelector('#revision');select.value='2';select.dispatchEvent(new Event('change',{bubbles:true}));let p=window.CinematicMatterPilot;p.state.time=13;window.CinematicMatterWasm.draw();document.querySelector('#filament-c3').dispatchEvent(new MouseEvent('click',{bubbles:true}));return {status:document.querySelector('#claim-status').textContent,body:document.querySelector('#inspector-body').textContent,mode:p.state.mode}})()");
 assert('revision changes explicit evidence status',dispute.status.includes('disputed')&&dispute.body.includes('Source 2')&&dispute.mode==='investigate');
 const pos=await evaluate("(()=>{let p=window.CinematicMatterPilot;p.state.mode='watch';p.state.time=13;p.render();window.CinematicMatterWasm.draw();let v=window.CinematicMatterWasm.vertices,r=document.querySelector('#paper').getBoundingClientRect(),mid=13*3;return {x:r.left+v[mid]*r.width,y:r.top+v[mid+1]*r.height}})()");
 await send('Input.dispatchMouseEvent',{type:'mousePressed',x:pos.x,y:pos.y,button:'left',clickCount:1});
 await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:pos.x,y:pos.y,button:'left',clickCount:1});
 const inspect=await evaluate("({mode:window.CinematicMatterPilot.state.mode,body:document.querySelector('#inspector-body').textContent})");
 assert('clicking WASM geometry reveals source lineage',inspect.mode==='investigate'&&inspect.body.includes('Source 1'));
 const restored=await evaluate("(()=>{document.querySelector('#reconstruct').click();return {mode:window.CinematicMatterPilot.state.mode,html:document.querySelector('#article').style.opacity,visible:document.querySelector('#matter').style.visibility}})()");
 assert('read mode reconstructs normal selectable HTML',restored.mode==='read'&&restored.html==='1'&&restored.visible==='hidden');
 const report={time:new Date().toISOString(),experiment:'CINEMATIC-MATTER-WASM-002',meta,snapshots,checks,passed:checks.every(x=>x.pass)};
 writeFileSync(join(artifacts,'wasm-test-receipt.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report,null,2));
}catch(err){console.error(err.stack);process.exitCode=1}
finally{for(const p of pending.values())clearTimeout(p.timeout);try{ws?.close()}catch{};chrome.kill('SIGTERM');server.close();await sleep(300);rmSync(profile,{force:true,recursive:true})}
