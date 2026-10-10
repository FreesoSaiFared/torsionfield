#!/usr/bin/env node
/** Real-Brave acceptance for a field-note page at desktop and mobile widths.
 * Isolated temporary browser; local mode reproduces same-origin CSP without deploy.
 * Usage: node tools/verify-responsive-article.mjs --local|--live [--path=/articles/webgpu-nvidia-linux/]
 */
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {existsSync,mkdtempSync,readFileSync,rmSync,openSync,closeSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve,sep,extname,dirname} from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const dirnameHere=dirname(fileURLToPath(import.meta.url));
const root=resolve(dirnameHere,'../public');
const option=process.argv.includes('--live')?'live':'local';
const article=process.argv.find(x=>x.startsWith('--path='))?.slice(7)||'/articles/webgpu-nvidia-linux/';
if(!article.startsWith('/')||article.includes('..')||!article.endsWith('/'))throw Error('INVALID_ARTICLE_ROUTE');
const expectedFieldnote=article==='/articles/webgpu-nvidia-linux/';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'application/javascript; charset=utf-8','.json':'application/json; charset=utf-8'};
let server=null,child=null,profile=null,logFd=null,client=null;
function startServer(){
 return new Promise((resolvePromise,reject)=>{
  const srv=createServer(async(req,res)=>{
   try{
    const pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);
    let target=resolve(root,'.'+pathname);
    if(!target.startsWith(root+sep)&&target!==root)throw Error('PATH_OUTSIDE_ROOT');
    if(pathname.endsWith('/'))target=join(target,'index.html');
    const body=await readFile(target);
    res.writeHead(200,{'Content-Type':mime[extname(target)]||'application/octet-stream',
       'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'",
       'Cache-Control':'no-store'});
    res.end(body);
   }catch(error){res.writeHead(404);res.end('Not found')}
  });
  srv.once('error',reject);
  srv.listen(0,'127.0.0.1',()=>resolvePromise(srv));
 });
}
function makeClient(url){
 return new Promise((resolvePromise,reject)=>{
  const ws=new WebSocket(url);
  const pending=new Map();let id=0;
  ws.onopen=()=>resolvePromise({send(method,params={},ms=8500){
    return new Promise((resolve,reject)=>{
     const n=++id,timer=setTimeout(()=>{pending.delete(n);reject(Error('CDP_TIMEOUT '+method))},ms);
     pending.set(n,{resolve,reject,timer});
     ws.send(JSON.stringify({id:n,method,params}));
    });
   },close(){ws.close()}});
  ws.onerror=()=>reject(Error('CDP_WEBSOCKET_FAILURE'));
  ws.onmessage=event=>{
   const data=JSON.parse(event.data);if(!data.id)return;
   const p=pending.get(data.id);if(!p)return;pending.delete(data.id);clearTimeout(p.timer);
   if(data.error||data.result?.exceptionDetails)p.reject(Error(JSON.stringify(data.error||data.result.exceptionDetails)));
   else p.resolve(data.result);
  };
 });
}
async function waitBrowser(profileName,childProcess){
 const p=join(profileName,'DevToolsActivePort');
 for(let i=0;i<90;i++){
  if(childProcess.exitCode!==null)throw Error('BRAVE_EXITED_'+childProcess.exitCode);
  if(existsSync(p)){
   const port=Number(readFileSync(p,'utf8').split(/\r?\n/)[0]);
   if(Number.isInteger(port)&&port>0)return port;
  }
  await pause(200);
 }
 throw Error('BRAVE_CDP_START_TIMEOUT');
}
async function pageClient(port,url){
 const pages=await(await fetch('http://127.0.0.1:'+port+'/json')).json();
 const matches=pages.filter(p=>p.type==='page'&&p.url===url);
 if(matches.length!==1)throw Error('ARTICLE_TAB_COUNT_'+matches.length);
 return makeClient(matches[0].webSocketDebuggerUrl);
}
const examine=()=> {
 const source=document.querySelector('.essay-body h1');
 const code=document.querySelector('.essay-body code');
 const computed=code?getComputedStyle(code):null;
 const sheets=[...document.styleSheets].map(s=>s.href||'');
 return {ready:document.readyState,title:document.title,
   width:innerWidth,visualWidth:visualViewport?.width||innerWidth,
   scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,
   heading:source?.textContent||'',sectionCount:document.querySelectorAll('.essay-body h2').length,
   sourceLinks:document.querySelectorAll('.essay-body a').length,
   csp:document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content||null,
   externalCSS:sheets.some(s=>s.endsWith('/articles/webgpu-nvidia-linux/field-note.css')),
   codeOverflow:computed?.overflowWrap||null,codeWordBreak:computed?.wordBreak||null};
};
async function measure(cdp,width,mobile){
 await cdp.send('Emulation.setDeviceMetricsOverride',{width,height:850,deviceScaleFactor:1,mobile});
 await pause(550);
 const v=await cdp.send('Runtime.evaluate',{expression:'('+examine.toString()+')()',returnByValue:true});
 return v.result.value;
}
const receipt={schema:'torsionfield-responsive-field-note/1',timestamp:new Date().toISOString(),
  mode:option,article,tests:{},pass:false};
try{
 let targetURL='https://torsionfield.de'+article;
 if(option==='local'){
  server=await startServer();
  targetURL='http://127.0.0.1:'+server.address().port+article;
 }
 const response=await fetch(targetURL,{redirect:'error'});
 if(response.status!==200)throw Error('ARTICLE_HTTP_'+response.status);
 receipt.contentSecurityPolicy=response.headers.get('content-security-policy')||'';
 profile=mkdtempSync(join(tmpdir(),'tf-responsive-'));
 logFd=openSync(join(profile,'brave.log'),'w');
 const browser='/opt/brave.com/brave/brave';
 child=spawn(browser,['--headless','--no-sandbox','--disable-dev-shm-usage','--no-first-run',
    '--no-default-browser-check','--disable-extensions','--disable-background-networking',
    '--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,
    '--window-size=1280,850',targetURL],
    {stdio:['ignore',logFd,logFd]});
 const port=await waitBrowser(profile,child);
 client=await pageClient(port,targetURL);
 await client.send('Page.enable');await client.send('Runtime.enable');
 let ready=false;
 for(let i=0;i<30;i++){
  const d=await client.send('Runtime.evaluate',{expression:'document.readyState',returnByValue:true});
  if(d.result.value==='complete'){ready=true;break}
  await pause(250);
 }
 if(!ready)throw Error('ARTICLE_DID_NOT_LOAD');
 receipt.tests.desktop=await measure(client,1280,false);
 receipt.tests.mobile390=await measure(client,390,true);
 receipt.tests.mobile320=await measure(client,320,true);
 const metrics=Object.values(receipt.tests);
 receipt.pass=metrics.every(r=>r.ready==='complete'&&r.heading.length>=12&&r.sectionCount>=4&&
   r.scrollWidth<=r.visualWidth+1&&r.clientWidth<=r.visualWidth+1);
 if(expectedFieldnote)receipt.pass=receipt.pass&&receipt.contentSecurityPolicy.includes("style-src 'self'")&&metrics.every(r=>
    r.externalCSS&&r.codeOverflow==='anywhere'&&r.codeWordBreak==='break-all');
 console.log('RESPONSIVE_ARTICLE_RESULT',JSON.stringify(receipt));
 if(!receipt.pass)process.exitCode=2;
}catch(error){
 receipt.error=String(error);console.error('RESPONSIVE_ARTICLE_FAILURE',JSON.stringify(receipt));
 process.exitCode=3;
}finally{
 client?.close();
 if(child&&child.exitCode===null){child.kill('SIGTERM');await Promise.race([new Promise(r=>child.once('exit',r)),pause(3000)]);
  if(child.exitCode===null){child.kill('SIGKILL');await Promise.race([new Promise(r=>child.once('exit',r)),pause(1500)])}}
 if(logFd!==null)closeSync(logFd);
 if(server)await new Promise(r=>server.close(r));
 if(profile){try{rmSync(profile,{recursive:true,force:true})}catch{}}
 const output=resolve(dirnameHere,'../.runtime/responsive-'+option+'-'+article.replace(/[^a-z0-9]+/gi,'-')+'.json');
 const {writeFileSync,mkdirSync}=await import('node:fs');
 mkdirSync(dirname(output),{recursive:true});writeFileSync(output,JSON.stringify(receipt,null,2)+'\n');
 console.log('RESPONSIVE_RECEIPT',output,'ACCEPTED',receipt.pass);
}
