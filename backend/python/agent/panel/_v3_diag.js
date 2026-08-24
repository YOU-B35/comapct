const fs=require('fs');
const p='d:\\YOTO-SASS\\SaaS-HZ_WEB_Demo\\backend\\python\\agent\\panel\\index.html';
const html=fs.readFileSync(p,'utf8');
const m=html.match(/<script>([\s\S]*?)<\/script>/);
if(!m){console.log('NO_SCRIPT');process.exit(2);}
const js=m[1];
const lines=js.split(/\r?\n/);
// Binary search
function testRange(start,end){
  const slice=lines.slice(start,end).join('\n');
  try{new Function(slice);return true;}catch(e){return false;}
}
let lo=0, hi=lines.length;
while(hi-lo>1){
  const mid=Math.floor((lo+hi)/2);
  if(testRange(lo,mid)) hi=mid; else lo=mid;
}
console.log('TOTAL_LINES='+lines.length);
console.log('FIRST_FAIL_LINE ~ '+(hi));
const context=lines.slice(Math.max(0,hi-3),Math.min(lines.length,hi+3));
console.log(context.map((l,i)=>`${Math.max(1,hi-2)+i}:  ${l}`).join('\n'));
// Try parse actual last script only
try{new Function(js);console.log('OK_ALL');}catch(e){
  console.log('ACTUAL ERR: '+e.message);
  // find via acorn-like: try compiling chunked with vm
  const {execSync}=require('child_process');
  const outTmp=process.env.TEMP+'\\_v3_full.js';
  fs.writeFileSync(outTmp,js);
  try{execSync(`node --check "${outTmp}"`,{stdio:'pipe'});}catch(err){
    console.log('NODE_CHECK:\n'+(err.stdout||'').toString()+(err.stderr||'').toString());
  }
}
