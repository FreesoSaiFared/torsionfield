'use strict';
const listing=document.querySelector('#projects');
const count=document.querySelector('#count');
const filter=document.querySelector('#stage-filter');
let entries=[];
function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function outbound(url,text){const a=node('a',text,'text-link');a.href=url;a.rel='noopener noreferrer';a.target='_blank';return a;}
function render(){
 listing.replaceChildren();
 const visible=entries.filter(x=>filter.value==='all'||filter.value===x.stage);
 count.textContent=visible.length+' / '+entries.length+' ENTRIES';
 if(!visible.length){listing.append(node('p','No projects at this stage.'));return;}
 for(const p of visible){
 const box=node('article',undefined,'project'),body=node('div'),side=node('aside');
 box.id=p.id;
 body.append(node('p',p.category+' / reviewed '+p.reviewed,'overline'));
 const heading=node('h3');heading.append(outbound(p.url,p.name+' ↗'));body.append(heading);
 body.append(node('span',p.stageLabel,'tag'),node('p',p.summary,'summary'),node('h4','Why watch it?'),node('p',p.whyWatch));
 body.append(node('h4','Claims and provenance'));
 const claims=node('ul',undefined,'evidence');
 for(const c of p.claims){const li=node('li');li.append(document.createTextNode(c.text+' '),outbound(c.source,'[source ↗]'),node('small',c.attribution+' / '+c.verification));claims.append(li);}
 body.append(claims,node('p','The stage classification is an editorial judgment; company claims are attributed rather than independently certified.','fine'));
 side.append(node('p','MILESTONE LEDGER','overline'),node('h4','Company-published dates'));
 const table=node('table',undefined,'milestones');
 for(const m of p.milestones){const tr=node('tr');tr.append(node('td',m.name),node('td',m.date),node('td',m.status==='target'?'TARGET':'LISTED','status-'+m.status));table.append(tr);}
 side.append(table,node('p','LISTED means a company-listed milestone, not necessarily an independently verified download. TARGET is a forecast.','fine'),node('h4','Monitor for'));
 const watch=node('ul');for(const item of p.watchFor)watch.append(node('li',item));side.append(watch);
 side.append(node('h4','Research contact'),outbound('mailto:'+p.researchContact,p.researchContact));
 box.append(body,side);listing.append(box);
 }
}
filter.addEventListener('change',render);
fetch('./projects.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).then(d=>{
 if(d.schema!=='torsionfield-watchthese/1'||!Array.isArray(d.projects))throw Error('Invalid manifest');
 entries=d.projects;render();
}).catch(err=>{listing.replaceChildren(node('p','The project register is temporarily unavailable. '+err.message));count.textContent='DATA UNAVAILABLE';});
