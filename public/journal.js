'use strict';
(async function(){
 const target=document.getElementById('feed-items'),status=document.getElementById('feed-state');
 if(!target)return;
 try{
   const resp=await fetch('/research-feed.json',{headers:{'accept':'application/json'}});
   if(!resp.ok)throw new Error('Feed HTTP '+resp.status);
   const data=await resp.json();
   if(!Array.isArray(data.items)||!data.items.length)throw new Error('No entries');
   const fragment=document.createDocumentFragment();
   const sample=[];for(let j=0;j<3;j++)for(const source of data.sources||[]){const item=data.items.filter(x=>x.source===source.name)[j];if(item)sample.push(item)}
   for(const item of sample){
     const url=new URL(item.url);
     if(url.protocol!=='https:'||!data.sources?.some(s=>new URL(s.feed).hostname===url.hostname))continue;
     const row=document.createElement('article');row.className='feed-item';
     const time=document.createElement('time');time.dateTime=item.date||'';time.textContent=item.date?new Date(item.date).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}):'RESEARCH';
     const content=document.createElement('div'),heading=document.createElement('h3'),link=document.createElement('a');
     link.href=url.href;link.rel='noopener noreferrer';link.target='_blank';link.textContent=item.title+' ↗';
     heading.appendChild(link);content.appendChild(heading);
     const label=document.createElement('p');label.textContent=(item.source||'EXTERNAL RESEARCH').toUpperCase()+' / ORIGINAL SOURCE';content.appendChild(label);
     row.append(time,content);fragment.appendChild(row);
   }
   if(!fragment.childElementCount)throw new Error('No valid source links');
   target.replaceChildren(fragment);status.textContent='SOURCE CONNECTED';
 }catch(e){status.textContent='SOURCE UNAVAILABLE';console.warn('Research feed:',e);}
})();

(async function(){
 const target=document.getElementById('watch-items'),state=document.getElementById('watch-state');
 if(!target)return;
 try{
  const response=await fetch('/api/research/hitchhikers',{headers:{accept:'application/json'}});
  if(!response.ok)throw new Error('Watch HTTP '+response.status);
  const data=await response.json();
  if(data.schema!=='torsionfield-source-watch/1'||!Array.isArray(data.events))throw new Error('Invalid watch format');
  const body=document.createDocumentFragment();
  const summary=document.createElement('p');summary.className='watch-summary';
  summary.textContent='UPSTREAM '+data.upstreamSha.slice(0,12)+' / '+data.relevantCount+' RELEVANT FILE(S) IN LAST REVISION';
  body.appendChild(summary);
  const events=(data.changed.length?data.changed:data.events).slice(0,5);
  for(const item of events){
   const url=new URL(item.url);
   if(url.hostname!=='github.com'||!url.pathname.startsWith('/steveash/hitchhikers-guide-to-ai-native-engineering/'))continue;
   const row=document.createElement('div');row.className='watch-event';
   const label=document.createElement('small');label.textContent='SOURCE REVISION / '+item.change.toUpperCase();
   const anchor=document.createElement('a');anchor.href=url.href;anchor.rel='noopener noreferrer';anchor.target='_blank';anchor.textContent=item.path+' ↗';
   row.append(label,anchor);body.appendChild(row);
  }
  const caution=document.createElement('p');caution.className='muted';
  caution.textContent=data.auditFindings.length+' independent verification checks recorded; ingestion does not imply endorsement.';
  body.appendChild(caution);
  target.replaceChildren(body);state.textContent='SOURCE TRACKED';
 }catch(error){
  state.textContent='STATUS UNAVAILABLE';
  console.warn('Upstream source watch:',error);
 }
})();
