/* v7 focus repair: management pages must not displace real work. */
'use strict';
(async()=>{
  try{
    await sleep(150);
    const self=await chrome.tabs.getCurrent();
    if(!self?.active)return;
    const tabs=await chrome.tabs.query({windowId:self.windowId});
    const candidates=tabs
      .filter(tab=>tab.id!==self.id&&!String(tab.url||'').startsWith('chrome-extension://'))
      .sort((a,b)=>Number(b.lastAccessed||0)-Number(a.lastAccessed||0));
    const target=candidates[0];
    if(!target)return;
    await chrome.tabs.update(target.id,{active:true});
    await event('chronicle.restored-displaced-active',target,{chronicleTabId:self.id});
    if(CHAT_RE.test(target.url||'')){
      await sleep(500);
      await capture(await chrome.tabs.get(target.id),'chronicle-focus-restore');
    }
  }catch(error){
    await safePost('/event',{client:CLIENT,type:'chronicle.focus-restore-error',error:String(error?.message||error),ts:Date.now()}).catch(()=>{});
  }
})();
