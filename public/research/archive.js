'use strict';
(async()=>{
 const index=document.getElementById('archive-list');
 const count=document.getElementById('result-count');
 const query=document.getElementById('filter-text');
 const select=document.getElementById('filter-source');
 if(!index||!count||!query||!select)return;
 try{
  const [sourcesResponse,editorResponse]=await Promise.all([
   fetch('/api/research/articles',{headers:{accept:'application/json'}}),
   fetch('/api/research/editorial',{headers:{accept:'application/json'}})
  ]);
  if(!sourcesResponse.ok||!editorResponse.ok)throw Error('Research source unavailable');
  const [sources,editorial]=await Promise.all([sourcesResponse.json(),editorResponse.json()]);
  if(!Array.isArray(sources.items)||!Array.isArray(sources.sources)||editorial.schema!=='torsionfield-editorial/1')throw Error('Unexpected research manifest');
  const domainAllow=new Set(sources.sources.map(s=>new URL(s.feed).hostname));
  const reviewed=sources.items.filter(item=>{
   const edit=editorial.entries?.[item.url];
   if(!edit||edit.editorialStatus!=='reviewed'||edit.sourceTitleAtReview!==item.title||!edit.headline||!edit.relevance)return false;
   try{const u=new URL(item.url);return u.protocol==='https:'&&domainAllow.has(u.hostname)}catch{return false}
  }).map(item=>({item,edit:editorial.entries[item.url]}))
    .sort((a,b)=>Date.parse(b.item.date||0)-Date.parse(a.item.date||0));
  const groups=[...new Set(reviewed.map(r=>r.item.source))].sort();
  for(const source of groups){const option=document.createElement('option');option.value=source;option.textContent=source;select.appendChild(option)}
  function render(){
   const text=query.value.trim().toLocaleLowerCase();
   const publisher=select.value;
   const visible=reviewed.filter(({item,edit})=>
    (!publisher||item.source===publisher)&&(!text||
     [item.source,item.title,edit.headline,edit.relevance,edit.topic].some(s=>String(s||'').toLocaleLowerCase().includes(text))));
   const nodes=document.createDocumentFragment();
   visible.forEach(({item,edit},n)=>{
    const row=document.createElement('article');row.className='archive-item';
    const meta=document.createElement('div');meta.className='archive-meta';
    const time=document.createElement('time');time.dateTime=item.date||'';
    time.textContent=item.date?new Date(item.date).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}):'RESEARCH';
    const source=document.createElement('small');source.textContent=item.source.toUpperCase();
    const number=document.createElement('span');number.textContent=String(n+1).padStart(2,'0');
    meta.append(number,time,source);
    const story=document.createElement('div');story.className='archive-story';
    const title=document.createElement('h2'),link=document.createElement('a');
    link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=edit.headline+' ↗';
    title.appendChild(link);
    const original=document.createElement('p');original.className='archive-original';original.textContent='ORIGINAL / '+item.title;
    const relevance=document.createElement('p');relevance.className='archive-relevance';relevance.textContent=edit.relevance;
    const topic=document.createElement('p');topic.className='archive-topic';topic.textContent=edit.topic||'EXTERNAL RESEARCH';
    story.append(title,original,relevance,topic);row.append(meta,story);nodes.appendChild(row);
   });
   if(!visible.length){const p=document.createElement('p');p.className='archive-pending';p.textContent='No reviewed notes match this filter.';nodes.appendChild(p)}
   index.replaceChildren(nodes);
   count.textContent=visible.length+' OF '+reviewed.length+' REVIEWED NOTES';
  }
  query.addEventListener('input',render);select.addEventListener('change',render);render();
 }catch(error){
  count.textContent='INDEX UNAVAILABLE';
  index.replaceChildren();
  const note=document.createElement('p');note.className='archive-pending';
  note.textContent='The research index could not be loaded. The original publishers remain linked from the homepage.';
  index.appendChild(note);console.warn('Research index error:',error);
 }
})();
