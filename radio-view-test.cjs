const fs = require('fs'), vm = require('vm'), assert = require('assert');
const ctx = {module:{exports:{}},window:{},Promise,Date,setTimeout,clearTimeout};
vm.runInNewContext(fs.readFileSync(__dirname+'/gl-sdk4-ui-radio-scan.common.js','utf8'),ctx);
const view=ctx.module.exports;
function h(tag,data,children) {
  if (arguments.length===2 && (typeof data==='string'||Array.isArray(data))) {children=data;data={};}
  assert(!data || !data.domProps || !data.domProps.innerHTML);
  return {tag,data,children};
}
function instance(kind, result) {
  const x=Object.assign(view.data(),{kind});x.results[kind]=result;
  for(const [k,f] of Object.entries(view.computed)) Object.defineProperty(x,k,{get:()=>f.call(x)});
  Object.assign(x,view.methods);return x;
}
const w=instance('wifi',{kind:'wifi',available:true,rows:[{ssid:'<script>alert(1)</script>',bssid:'aa:bb:cc:dd:ee:ff',channel:149,band:'5 GHz',frequency:5745,signal:-50,security:'WPA2/3 (RSN)'}]});
let output=JSON.stringify(view.render.call(w,h));
assert(output.includes('<script>alert(1)</script>') && output.includes('149') && output.includes('5745'));
w.query='missing';assert(w.wifiRows.length===0);w.query='';w.band='2.4 GHz';assert(w.wifiRows.length===0);
const c=instance('cellular',{kind:'cellular',available:true,slot:1,serving:{},neighbors:{},warning:'没有有效服务小区',error:'失败：保留缓存',updated_at:1});
output=JSON.stringify(view.render.call(c,h));assert(output.includes('没有有效服务小区')&&output.includes('没有返回可显示的数据')&&output.includes('以上保留上次成功数据'));
console.log('Vue render, empty-object arrays, stale warning, filter and text escaping tests passed');
