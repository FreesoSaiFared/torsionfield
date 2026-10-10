'use strict';
/* CM-001: semantic actors are projected from genuine HTML, never substituted for it. */
const $=id=>document.getElementById(id);
const paper=$('paper'), article=$('article'), svg=$('matter'), layer=$('filaments');
const state={time:0,lambda:.4,revision:1,mode:'read',playing:false,selected:null,clockOrigin:0,raf:null,voice:false};
const actors=[
 {id:'filament-c1',anchor:'anchor-1',title:'Claim C1',parents:['claim-1','source-1'],kind:'defines',color:'#bc553e',pose:[.48,.37,.35,.27,.24,.37,.17,.26],graph:[.53,.20,.62,.26,.73,.29,.81,.27]},
 {id:'filament-c2',anchor:'anchor-2',title:'Claim C2',parents:['claim-2','source-1'],kind:'derived',color:'#377b85',pose:[.50,.43,.53,.56,.60,.67,.76,.83],graph:[.51,.49,.64,.41,.73,.50,.87,.60]},
 {id:'filament-c3',anchor:'anchor-3',title:'Claim C3',parents:['claim-3','source-2'],kind:'hypothesis',color:'#bd7745',pose:[.48,.43,.44,.59,.34,.76,.24,.83],graph:[.52,.78,.63,.68,.71,.84,.85,.81]}
];
const ns='http://www.w3.org/2000/svg';
for(const actor of actors){const path=document.createElementNS(ns,'path');path.id=actor.id;path.tabIndex=0;path.setAttribute('role','button');path.setAttribute('aria-label','Inspect '+actor.title);path.addEventListener('click',()=>inspect(actor));path.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect(actor)}});layer.appendChild(path);actor.path=path}
const figure=document.createElementNS(ns,'path');figure.setAttribute('class','expressive');layer.insertBefore(figure,layer.firstChild);
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x)};
const mix=(a,b,t)=>a+(b-a)*t;
const tween=(from,to,t)=>from.map((x,i)=>mix(x,to[i],smooth(t)));
function anchorCurve(actor,w,h){
 const anchor=$(actor.anchor),r=anchor.getBoundingClientRect(),origin=paper.getBoundingClientRect();
 const left=clamp(r.left-origin.left,12,w-12),right=clamp(r.right-origin.left,12,w-12),y=clamp(r.bottom-origin.top+3,12,h-12);
 return [left,y,mix(left,right,.34),y,mix(left,right,.67),y,right,y];
}
function scale(curve,w,h){return curve.map((n,i)=>n*(i%2?h:w))}
function coordinates(actor,w,h,t){
 const a=anchorCurve(actor,w,h),p=scale(actor.pose,w,h),g=scale(actor.graph,w,h);
 const deformation=(state.lambda-.4)*h*.09;
 for(const i of [1,3,5,7])p[i]+=deformation*(i===1?.3:1);
 if(t<=6)return tween(a,p,t/6);
 if(t<=13)return tween(p,g,(t-6)/7);
 if(t<=18)return g;
 return tween(g,a,(t-18)/2);
}
const pathFor=c=>'M'+c[0].toFixed(1)+','+c[1].toFixed(1)+' C'+c[2].toFixed(1)+','+c[3].toFixed(1)+' '+c[4].toFixed(1)+','+c[5].toFixed(1)+' '+c[6].toFixed(1)+','+c[7].toFixed(1);

function updateExplanation(){
 $('damping-value').value=state.lambda.toFixed(2);
 $('model-value').textContent=Math.exp(-state.lambda*4).toFixed(3);
 $('prediction').firstChild.textContent='At t=4 with λ='+state.lambda.toFixed(2)+', the model predicts ';
 $('claim-status').textContent=state.revision===2?'disputed by a hypothetical note':'unverified';
}
function setMode(mode){
 state.mode=mode;
 for(const id of ['read','watch','investigate'])$(id).setAttribute('aria-pressed',String(id===mode));
 if(mode==='read'){stop();state.time=0}
 if(mode==='investigate')stop();
 render();
}
function render(){
 const w=paper.clientWidth,h=paper.clientHeight,t=clamp(state.time,0,20);
 svg.setAttribute('viewBox','0 0 '+w+' '+h);
 svg.style.visibility=state.mode==='read'?'hidden':'visible';
 paper.classList.toggle('faded',state.mode!=='read'&&t>=2&&t<18);
 article.style.opacity=state.mode==='read'?1:(t<=2?1:t<5?1-.97*smooth((t-2)/3):t<17?.03:.03+.97*smooth((t-17)/3));
 $('scene').textContent=t<2?'DOCUMENT':t<7?'METAMORPHOSIS':t<11?'EMBODIMENT':t<17?'ARGUMENT FIELD':'RECONSTRUCTION';
 $('clock').value='00:'+String(Math.floor(t)).padStart(2,'0');
 $('time').value=t;
 for(const actor of actors){
   const path=actor.path;
   path.setAttribute('d',pathFor(coordinates(actor,w,h,t)));
   path.setAttribute('stroke',actor.color);
   const disputed=actor.id==='filament-c3'&&state.revision===2;
   path.setAttribute('stroke-dasharray',disputed?'8 7':actor.kind==='hypothesis'?'3 8':'none');
   path.setAttribute('opacity',state.mode==='read'?0:t<1?t*.8:.95);
 }
 const cx=w*.50,cy=h*.22,r=Math.min(w,h)*.07;
 figure.setAttribute('d','M'+(cx+r)+','+cy+' A'+r+','+r+' 0 1 0 '+(cx-r)+','+cy+' A'+r+','+r+' 0 1 0 '+(cx+r)+','+cy);
 figure.setAttribute('opacity',t<2?0:t<9?Math.min((t-2)/3,1):Math.max(0,1-(t-9)/3));
}
function inspect(actor){
 stop();state.mode='investigate';
 for(const id of ['read','watch','investigate'])$(id).setAttribute('aria-pressed',String(id==='investigate'));
 state.selected=actor;
 document.querySelectorAll('mark.selected').forEach(x=>x.classList.remove('selected'));
 $(actor.anchor).classList.add('selected');
 const parents=actor.parents.map(id=>id.startsWith('claim-')?'Claim '+id.slice(-1):'Source '+id.slice(-1));
 $('inspector-title').textContent=actor.title+' / '+actor.kind.toUpperCase();
 $('inspector-body').textContent='Actor '+actor.id+'. Lineage: '+parents.join(' + ')+'. Passage: “'+$(actor.anchor).textContent+'”. '+(actor.id==='filament-c3'&&state.revision===2?'Version 2 disputes this extrapolation.':'The projection does not validate the claim.');
 $('reveal').disabled=false;
 render();
}
function speak(){
 if(!('speechSynthesis' in window))return;
 speechSynthesis.cancel();
 const u=new SpeechSynthesisUtterance('A toy model predicts exponential decay. Increasing damping changes its envelope. But extrapolation beyond the model is not established. Select the filament to inspect its original claim.');
 u.rate=.9;u.lang='en-US';speechSynthesis.speak(u);
}
function stop(){
 state.playing=false;
 if(state.raf!==null)cancelAnimationFrame(state.raf);
 state.raf=null;
}
function tick(now){
 if(!state.playing)return;
 state.time=clamp((now-state.clockOrigin)/1000,0,20);
 render();
 if(state.time>=20){stop();return}
 state.raf=requestAnimationFrame(tick);
}
function play(){
 stop();state.mode='watch';
 for(const id of ['read','watch','investigate'])$(id).setAttribute('aria-pressed',String(id==='watch'));
 if(state.time>=20)state.time=0;
 state.clockOrigin=performance.now()-state.time*1000;
 state.playing=true;
 if($('voice').checked)speak();
 state.raf=requestAnimationFrame(tick);
 render();
}
$('read').addEventListener('click',()=>setMode('read'));
$('watch').addEventListener('click',play);
$('investigate').addEventListener('click',()=>setMode('investigate'));
$('play').addEventListener('click',play);
$('pause').addEventListener('click',()=>{stop();if('speechSynthesis' in window)speechSynthesis.cancel()});
$('reconstruct').addEventListener('click',()=>{stop();if('speechSynthesis' in window)speechSynthesis.cancel();setMode('read')});
$('time').addEventListener('input',e=>{stop();state.mode='investigate';state.time=Number(e.target.value);render()});
$('damping').addEventListener('input',e=>{state.lambda=Number(e.target.value);updateExplanation();render()});
$('revision').addEventListener('change',e=>{state.revision=Number(e.target.value);updateExplanation();render()});
$('reveal').addEventListener('click',()=>{
 if(!state.selected)return;
 const anchor=$(state.selected.anchor);setMode('read');anchor.classList.add('selected');anchor.scrollIntoView({block:'center',behavior:'auto'});anchor.focus?.();
});
window.addEventListener('resize',render);
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});
if(matchMedia('(prefers-reduced-motion: reduce)').matches){$('voice').checked=false}
updateExplanation();render();
window.CinematicMatterPilot={state,actors,coordinates,render,stop,play};
