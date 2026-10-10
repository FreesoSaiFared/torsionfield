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