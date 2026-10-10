'use strict';
/* Cinematic Matter CM-002 — actual WebAssembly geometry, drawn from DOM text contours. */
(async()=>{
const api=window.CinematicMatterPilot;
const paper=document.getElementById('paper');
const hint=document.createElement('p');hint.className='wasm-status';hint.id='wasm-status';
hint.setAttribute('role','status');hint.textContent='WASM GEOMETRY / LOADING';
document.querySelector('.controls>small').insertAdjacentElement('afterend',hint);
const canvas=document.createElement('canvas');canvas.className='matter-canvas';
canvas.setAttribute('aria-hidden','true');paper.appendChild(canvas);
const ctx=canvas.getContext('2d',{alpha:true,desynchronized:true});
let wasm,ex,frames=0,seedCount=0,seedGroups=[],buffer,lastFrame,dragging=false;
let pointer={x:0,y:0,pull:0},dimensions=[0,0],dpr=1,quality=1;
let lastSnapshot='',lastSegments=[],ready=false;
const COLORS=['#bd4029','#27828a','#bd7540'];
const MASK_STEP=2;
const thicknessControl=document.getElementById('filament-weight');
let lineWeight=Number(thicknessControl.value);
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const pick=(arr,limit)=>Array.from({length:limit},(_,i)=>arr[Math.floor((i+.47)*arr.length/limit)]).filter(Boolean);
async function load(){
 const response=await fetch('./geometry.wasm',{cache:'no-cache'});
 if(!response.ok)throw Error('WASM HTTP '+response.status);
 const data=await response.arrayBuffer();
 const compiled=await WebAssembly.instantiate(data,{});
 wasm=compiled.instance;ex=wasm.exports;
 if(!ex.cm_build||!ex.cm_seed||!ex.cm_output_ptr||!ex.memory)throw Error('WASM ABI incomplete');
 return data.byteLength;
}
function size(){
 const w=paper.clientWidth,h=paper.clientHeight,scale=Math.min(devicePixelRatio||1,2);
 if(w===dimensions[0]&&h===dimensions[1]&&scale===dpr)return;
 dimensions=[w,h];dpr=scale;canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);
 canvas.style.width=w+'px';canvas.style.height=h+'px';ctx.setTransform(dpr,0,0,dpr,0,0);
 if(ready)seedFromText();
}
function letterPoints(mark){
 const w=dimensions[0],h=dimensions[1],bbox=paper.getBoundingClientRect();
 const mask=document.createElement('canvas');mask.width=w;mask.height=h;
 const m=mask.getContext('2d',{willReadFrequently:true});
 const style=getComputedStyle(mark);m.fillStyle='#000';
 m.font=style.font||style.fontSize+' '+style.fontFamily;
 const nodes=[...mark.childNodes].filter(node=>node.nodeType===Node.TEXT_NODE);
 for(const node of nodes){
  for(let i=0;i<node.textContent.length;i++){
   const char=node.textContent[i];if(!char.trim())continue;
   const range=document.createRange();range.setStart(node,i);range.setEnd(node,i+1);
   const r=range.getBoundingClientRect();if(r.width<=0)continue;
   m.fillText(char,r.left-bbox.left,r.bottom-bbox.top-2);
  }
 }
 const pixels=m.getImageData(0,0,w,h).data,points=[];
 for(let y=0;y<h;y+=MASK_STEP)for(let x=0;x<w;x+=MASK_STEP){
  if(pixels[(y*w+x)*4+3]>70)points.push([x/w,y/h]);
 }
 if(!points.length){const r=mark.getBoundingClientRect();
  for(let j=0;j<32;j++)points.push([(r.left-bbox.left+r.width*(j/32))/w,(r.bottom-bbox.top)/h]);}
 return points;
}
function seedFromText(){
 if(!ex)return;
 ex.cm_clear();seedGroups=[];
 const per=Math.floor(ex.cm_capacity()/3)-8;
 for(let group=0;group<3;group++){
  const pixels=letterPoints(document.getElementById('anchor-'+(group+1)));
  for(const [x,y] of pick(pixels,Math.min(per,pixels.length))){
   const id=ex.cm_seed(x,y,group);if(id>=0)seedGroups[id]=group;
  }
 }
 seedCount=ex.cm_count();lastSnapshot='';
 hint.textContent='RUST/WASM / '+seedCount+' GLYPH STRANDS / '+ex.cm_samples()+' VERTICES';
}
function draw(){
 size();
 const state=api.state;
 if(!ready||!seedCount||state.mode==='read'){ctx.clearRect(0,0,...dimensions);canvas.style.pointerEvents='none';return}
 canvas.style.pointerEvents='auto';
 const [w,h]=dimensions,t=state.time;
 const sig=[t,state.lambda,state.revision,pointer.x,pointer.y,pointer.pull,w,h,lineWeight].join('|');
 if(sig===lastSnapshot&&!state.playing)return;
 lastSnapshot=sig;frames++;
 ex.cm_build(t,state.lambda,state.revision,pointer.x,pointer.y,pointer.pull);
 const segments=ex.cm_samples(),raw=new Float32Array(ex.memory.buffer,ex.cm_output_ptr()>>>0,seedCount*segments*3);
 const motion=Math.min(1,Math.max(0,(t-1.4)/3));
 ctx.clearRect(0,0,w,h);lastSegments=[];
 ctx.save();ctx.lineCap='round';ctx.lineJoin='round';
 for(let i=0;i<seedCount;i++){
  const group=seedGroups[i]||0,base=i*segments*3;
  const alpha=raw[base+2],strong=group===2&&state.revision===2;
  ctx.beginPath();
  for(let k=0;k<segments;k++){
   const x=raw[base+k*3]*w,y=raw[base+k*3+1]*h;
   if(k===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
   if(k===Math.floor(segments/2))lastSegments.push({x,y,group});
  }
  ctx.strokeStyle=COLORS[group];
  ctx.lineWidth=(i%9===0?1.85:0.94)*lineWeight;
  ctx.globalAlpha=clamp(alpha*(.45+.55*motion)*(strong?.98:.92),0,1);
  if(strong)ctx.setLineDash([5,7]);else ctx.setLineDash([]);
  ctx.stroke();
 }
 ctx.setLineDash([]);ctx.globalAlpha=1;ctx.restore();
 const gs=Math.max(0,Math.min(1,(t-10)/2.5))*Math.max(0,Math.min(1,(19-t)/2));
 if(gs>0){
  const nodes=[{x:.18,y:.29,id:'C1',label:'MODEL',c:COLORS[0]},{x:.80,y:.27,id:'C2',label:'DERIVED',c:COLORS[1]},{x:.78,y:.79,id:'C3',label:state.revision===2?'DISPUTED':'HYPOTHESIS',c:COLORS[2]},{x:.51,y:.49,id:'DOC',label:'REFERENTIAL CORE',c:'#182126'}];
  ctx.save();ctx.globalAlpha=gs;ctx.font='600 10px monospace';
  for(const n of nodes){const x=n.x*w,y=n.y*h;
   ctx.lineWidth=1;ctx.strokeStyle=n.c;ctx.fillStyle=n.c;
   ctx.beginPath();ctx.arc(x,y,18,0,Math.PI*2);ctx.stroke();
   ctx.beginPath();ctx.arc(x,y,27+(Math.sin(t*.9)*3),0,Math.PI*2);ctx.setLineDash([2,7]);ctx.stroke();ctx.setLineDash([]);
   ctx.beginPath();ctx.arc(x,y,3.5,0,Math.PI*2);ctx.fill();
   ctx.fillText(n.id+' / '+n.label,x+33,y-4);
  }
  ctx.restore();
 }
 if(t>=7&&t<17){ctx.save();ctx.textAlign='left';ctx.font='600 11px monospace';ctx.globalAlpha=.72;
  ctx.fillStyle='#1b2428';ctx.fillText(t<11?'FORM / THE ASSERTION MOVES':'RELATIONS / CLICK TO INSPECT',24,h-69);
  ctx.restore();}
}
function inspectAt(x,y){
 let best=null,dist=17*17;
 for(const item of lastSegments){const dx=item.x-x,dy=item.y-y,d=dx*dx+dy*dy;
  if(d<dist){best=item;dist=d}}
 if(best){const actor=api.actors[best.group];actor.path.dispatchEvent(new MouseEvent('click',{bubbles:true}));return true}
 return false;
}
function cursor(e){const r=canvas.getBoundingClientRect();return {x:clamp((e.clientX-r.left)/r.width,0,1),y:clamp((e.clientY-r.top)/r.height,0,1)}}
canvas.addEventListener('pointerdown',e=>{dragging=true;const q=cursor(e);pointer={...q,pull:.6};canvas.setPointerCapture(e.pointerId);if(api.state.playing)api.stop()});
canvas.addEventListener('pointermove',e=>{if(!dragging)return;const q=cursor(e);pointer={...q,pull:.8};lastSnapshot='';draw()});
canvas.addEventListener('pointerup',e=>{const q=cursor(e);pointer={...q,pull:0};dragging=false;inspectAt(q.x*dimensions[0],q.y*dimensions[1]);lastSnapshot='';draw()});
canvas.addEventListener('pointercancel',()=>{dragging=false;pointer.pull=0});
thicknessControl.addEventListener('input',()=>{
 lineWeight=Number(thicknessControl.value);
 document.getElementById('filament-weight-value').value=lineWeight.toFixed(1)+'×';
 lastSnapshot='';draw();
});
window.addEventListener('resize',()=>{size();lastSnapshot=''});
window.addEventListener('pagehide',()=>{ready=false});
function cycle(){if(ready)draw();requestAnimationFrame(cycle)}
try{
 const bytes=await load();
 size();ready=true;seedFromText();
 hint.title='Optimized Rust wasm32-unknown-unknown; '+bytes+' bytes, no JS geometry fallback while active.';
 document.querySelector('#matter').style.opacity='.19';
 requestAnimationFrame(cycle);
 window.CinematicMatterWasm={exports:ex,get state(){return {ready,seedCount,frames,bytes,lineWeight}},draw,seedFromText,get vertices(){
 return Array.from(new Float32Array(ex.memory.buffer,ex.cm_output_ptr()>>>0,seedCount*ex.cm_samples()*3));
 }};
}catch(err){hint.textContent='WASM UNAVAILABLE / ORIGINAL SVG FALLBACK';console.error('Cinematic Matter WASM',err);canvas.remove();}
})();
