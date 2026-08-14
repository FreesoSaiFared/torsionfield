/* v5 patch: capture each ChatGPT tab while it is active in its own window. */
'use strict';

const TF_REBOOT_V5='0.5.0';

async function inventorySequentialActive(){
  const before=await deadline(chrome.windows.getAll({populate:true,windowTypes:['normal','popup']}),5000,'v5-windows-before');
  const originalActive=new Map();
  const tabs=[];
  const activation=[];

  for(const win of before){
    const active=(win.tabs||[]).find(tab=>tab.active);
    if(active)originalActive.set(win.id,active.id);
  }

  for(const win of before){
    for(const initial of win.tabs||[]){
      if(!CHAT_RE.test(initial.url||'')){
        tabs.push(await captureTab(initial));
        continue;
      }
      let tab=initial;
      try{
        const was={frozen:!!tab.frozen,discarded:!!tab.discarded,active:!!tab.active,autoDiscardable:tab.autoDiscardable};
        tab=await chrome.tabs.update(tab.id,{active:true,autoDiscardable:false});
        tab=await waitExecutable(tab.id,30000);
        await sleep(250);
        tab=await chrome.tabs.get(tab.id);
        const captured=await captureTab(tab);
        captured.v5Activation=was;
        tabs.push(captured);
        activation.push({tabId:tab.id,ok:!captured.error,before:was,after:{frozen:!!tab.frozen,discarded:!!tab.discarded,active:!!tab.active,autoDiscardable:tab.autoDiscardable},error:captured.error||null});
      }catch(error){
        const current=await chrome.tabs.get(initial.id).catch(()=>initial);
        const captured=await captureTab(current);
        captured.error=captured.error||String(error?.message||error);
        captured.v5Activation={frozen:!!initial.frozen,discarded:!!initial.discarded,active:!!initial.active,autoDiscardable:initial.autoDiscardable};
        tabs.push(captured);
        activation.push({tabId:initial.id,ok:false,before:captured.v5Activation,error:String(error?.message||error)});
      }
    }
  }

  const restoreErrors=[];
  for(const [windowId,tabId] of originalActive.entries()){
    try{await chrome.tabs.update(tabId,{active:true})}
    catch(error){restoreErrors.push({windowId,tabId,error:String(error?.message||error)})}
  }
  await sleep(250);

  let groups=[];
  try{if(chrome.tabGroups?.query)groups=await deadline(chrome.tabGroups.query({}),5000,'v5-tabGroups')}catch(_){}
  const after=await deadline(chrome.windows.getAll({populate:false,windowTypes:['normal','popup']}),5000,'v5-windows-after');
  return{
    schema:'TF_BROWSER_INVENTORY/5',
    version:TF_REBOOT_V5,
    baseVersion:VERSION,
    client:CLIENT,
    runtimeId:chrome.runtime.id,
    manifest:{name:chrome.runtime.getManifest().name,version:chrome.runtime.getManifest().version},
    capturedAt:Date.now(),
    activation,
    restoreErrors,
    windows:after.map(win=>({id:win.id,focused:win.focused,top:win.top,left:win.left,width:win.width,height:win.height,state:win.state,type:win.type,incognito:win.incognito,alwaysOnTop:win.alwaysOnTop})),
    groups,
    tabs
  };
}

HANDLERS.inventory=async()=>inventorySequentialActive();
HANDLERS.health=async()=>({ok:true,version:TF_REBOOT_V5,baseVersion:VERSION,client:CLIENT,runtimeId:chrome.runtime.id,manifest:chrome.runtime.getManifest()});
