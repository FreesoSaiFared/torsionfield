'use strict';
(async function(){
 const target=document.getElementById('feed-items'),status=document.getElementById('feed-state');
 if(!target)return;
 try{
   const [feedResponse,editorResponse]=await Promise.all([
     fetch('/api/research/articles',{headers:{accept:'application/json'}}),
     fetch('/api/research/editorial',{headers:{accept:'application/json'}})
   ]);
   if(!feedResponse.ok||!editorResponse.ok)throw new Error('Source or editorial manifest unavailable');
   const [data,editorial]=await Promise.all([feedResponse.json(),editorResponse.json()]);
   if(!Array.isArray(data.items)||editorial.schema!=='torsionfield-editorial/1'||!editorial.entries)throw new Error('Unexpected manifests');
   const fragment=document.createDocumentFragment();
   const selected=[];
   let awaiting=0;
   for(let rank=0;rank<4;rank++)for(const source of data.sources||[]){
     const candidates=data.items.filter(x=>x.source===source.name);
     const row=candidates[rank];
     if(!row)continue;
     const edit=editorial.entries[row.url];
     if(!edit||edit.editorialStatus!=='reviewed'||edit.sourceTitleAtReview!==row.title||!edit.headline||!edit.relevance){awaiting++;continue;}
     selected.push({row,edit});
   }
   for(const {row:item,edit} of selected){
     const url=new URL(item.url);
     if(url.protocol!=='https:'||!data.sources.some(s=>new URL(s.feed).hostname===url.hostname))continue;
     const article=document.createElement('article');article.className='feed-item';
     const time=document.createElement('time');time.dateTime=item.date||'';
     time.textContent=item.date?new Date(item.date).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}):'RESEARCH';
     const content=document.createElement('div'),heading=document.createElement('h3'),link=document.createElement('a');
     link.href=url.href;link.rel='noopener noreferrer';link.target='_blank';link.textContent=edit.headline+' ↗';
     heading.appendChild(link);content.appendChild(heading);
     const original=document.createElement('p');original.className='original-title';
     original.textContent='ORIGINAL / '+item.title;content.appendChild(original);
     const relevance=document.createElement('p');relevance.className='research-relevance';
     relevance.textContent=edit.relevance;content.appendChild(relevance);
     const topic=document.createElement('p');topic.className='topic-line';
     topic.textContent=item.source.toUpperCase()+' / '+edit.topic;content.appendChild(topic);
     article.append(time,content);fragment.appendChild(article);
   }
   if(!fragment.childElementCount)throw new Error('No current reviewed interpretations');
   target.replaceChildren(fragment);
   status.textContent=selected.length+' INTERPRETED / '+awaiting+' AWAITING REVIEW';
 }catch(e){status.textContent='EDITORIAL REVIEW UNAVAILABLE';console.warn('Research interpretation:',e);}
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
  try{
   const evidenceReply=await fetch('/api/research/evidence',{headers:{accept:'application/json'}});
   if(evidenceReply.ok){
    const audit=await evidenceReply.json();
    if(audit.schema==='torsionfield-evidence-audit/1'&&audit.summary){
     const result=document.createElement('p');result.className='watch-summary';
     result.textContent='PRIMARY-SOURCE CHECKS / '+audit.summary.potentialConflicts+' CONFLICT FLAGS / '+audit.summary.independentlyVerifiedClaims+' CLAIMS INDEPENDENTLY VERIFIED';
     const link=document.createElement('a');link.href='/api/research/evidence';link.textContent='INSPECT THE EVIDENCE RECORD ↗';link.className='read';
     body.append(result,link);
    }
   }
  }catch(e){console.warn('Evidence audit unavailable:',e);}
  target.replaceChildren(body);state.textContent='SOURCE TRACKED';
 }catch(error){
  state.textContent='STATUS UNAVAILABLE';
  console.warn('Upstream source watch:',error);
 }
})();
