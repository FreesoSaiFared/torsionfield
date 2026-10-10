import {build} from 'esbuild';
for(const [entry,out] of [['src/app.js','dist/app.js'],['src/worker.js','dist/worker.js']]){
 await build({entryPoints:[entry],outdir:undefined,outfile:out,bundle:true,format:'esm',platform:'browser',target:'es2022',logLevel:'warning'});
}
console.log('LOCAL_WEBLLM_BUNDLE_READY');
