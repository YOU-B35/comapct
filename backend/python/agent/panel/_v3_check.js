const fs=require('fs');
const p='d:\\YOTO-SASS\\SaaS-HZ_WEB_Demo\\backend\\python\\agent\\panel\\index.html';
const html=fs.readFileSync(p,'utf8');
const m=html.match(/<script>([\s\S]*?)<\/script>/);
if(!m){console.log('NO_SCRIPT_TAG');process.exit(2);}
const js=m[1];
const out=process.env.TEMP+'\\panel_v3_chk.js';
fs.writeFileSync(out,js,'utf8');
try{new Function(js);console.log('JS_OK, script_bytes='+js.length+', html_lines='+html.split(/\r?\n/).length);process.exit(0);}
catch(e){console.log('JS_ERR: '+e.message);process.exit(1);}
