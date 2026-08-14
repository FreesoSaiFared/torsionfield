/* v6 patch: second independent capture plane through chrome.debugger. */
'use strict';

const TF_REBOOT_V6='0.6.0';
const tfV5CaptureTab=captureTab;

async function captureTabDebuggerFallback(tab){
  const first=await tfV5CaptureTab(tab);
  if(!first.chatgpt||!first.error||tab.frozen||tab.discarded)return first;

  let owned=false;
  try{
    owned=await attachDebugger(tab.id);
    const expression=`(${pageState.toString()})()`;
    const response=await deadline(
      chrome.debugger.sendCommand(
        {tabId:tab.id},
        'Runtime.evaluate',
        {expression,returnByValue:true,awaitPromise:false,userGesture:false}
      ),
      12000,
      `debugger-capture:${tab.id}`
    );
    if(response?.exceptionDetails){
      throw new Error(response.exceptionDetails.text||'Runtime.evaluate exception');
    }
    const value=response?.result?.value;
    if(!value||typeof value!=='object')throw new Error('debugger-capture-missing-value');
    return{
      ...first,
      error:undefined,
      state:value,
      capturePlane:'chrome.debugger.Runtime.evaluate',
      scriptingError:first.error
    };
  }catch(error){
    return{
      ...first,
      error:`scripting=${first.error}; debugger=${String(error?.message||error)}`,
      debuggerError:String(error?.message||error)
    };
  }finally{
    if(owned)await detachDebugger(tab.id);
  }
}

captureTab=captureTabDebuggerFallback;
HANDLERS.health=async()=>({ok:true,version:TF_REBOOT_V6,baseVersion:VERSION,client:CLIENT,runtimeId:chrome.runtime.id,manifest:chrome.runtime.getManifest()});
