const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=__dirname;
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',addEventListener(){},setAttribute(){}});return elements.get(id)}
const ctx=vm.createContext({console,location:{hash:''},history:{replaceState(){}},document:{getElementById:element,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync(path.join(root,'screens.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(path.join(root,'atlas.js'),'utf8'),ctx);
const screens=JSON.parse(vm.runInContext('JSON.stringify(SCREENS)',ctx));
const ids=new Set(screens.map(s=>s.id));
assert.equal(ids.size,screens.length,'Duplicate screen IDs');
let links=0;
for(const s of screens){
 assert(s.title&&s.role&&s.subtitle&&s.rules.length&&s.blocks.length&&s.actions.length,s.id+' incomplete');
 for(const id of [...s.actions.map(a=>a.to),...s.blocks.filter(b=>b.kind==='list').flatMap(b=>b.rows.map(r=>r.target).filter(Boolean))]){assert(ids.has(id),s.id+' -> '+id);links++}
 const html=vm.runInContext(`phone(BY_ID[${JSON.stringify(s.id)}])`,ctx);
 assert(html.includes(`data-screen="${s.id}"`));
 assert(!html.includes('undefined'),s.id+' undefined content');
 const domIds=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
 assert.equal(new Set(domIds).size,domIds.length,s.id+' duplicate input IDs');
 vm.runInContext(`state.id=${JSON.stringify(s.id)}; state.view='focus'; render()`,ctx);
 assert(element('stage').innerHTML.includes(s.title));
}
vm.runInContext("navigate('U04','P05',true)",ctx);
assert(element('stage').innerHTML.includes('Алиса Иванова'));
assert(!element('stage').innerHTML.includes('Алексей Иванов · 24'));
vm.runInContext("navigate('P06','U04',true)",ctx);
assert(element('stage').innerHTML.includes('Алиса Иванова'));
vm.runInContext("navigate('P06','P07',true)",ctx);
assert(element('stage').innerHTML.includes('Максим Иванов'));
vm.runInContext("state.view='all';state.role='';state.search='';render()",ctx);
assert.equal([...element('stage').innerHTML.matchAll(/data-screen="/g)].length,screens.length);
vm.runInContext("state.role='Родитель';render()",ctx);
assert.equal([...element('stage').innerHTML.matchAll(/data-screen="/g)].length,10);
for(const p of ['index.html','atlas.css','readability.css','assets/verum-logo.png','SPEC.md',...['01-participant','02-parent','03-coach','04-organizer','05-admin','06-states'].map(n=>'boards/'+n+'.png')])assert(fs.existsSync(path.join(root,p)),p+' missing');
const roles=Object.fromEntries([...new Set(screens.map(s=>s.role))].map(r=>[r,screens.filter(s=>s.role===r).length]));
console.log(JSON.stringify({result:'PASS',screens:screens.length,links,roles,checks:['screen completeness','unique IDs','all transition targets','render all 89 screens','unique input IDs','child context: Alice and Maxim','role filter','local asset existence']},null,2));
