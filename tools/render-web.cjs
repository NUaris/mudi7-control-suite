// Render the actual custom Vue render functions with synthetic data only.
// No router connection, GL token, real subscription, Wi-Fi or browsing history.
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm');
const {chromium}=require('playwright-core');
const root=path.resolve(__dirname,'..'),out=path.join(root,'docs/screenshots/web');
fs.mkdirSync(out,{recursive:true});
const stamp=Math.floor(Date.UTC(2026,9,5,4)/1000);
function escape(x){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function h(tag,data,children){
  if(arguments.length===2&&(typeof data==='string'||typeof data==='number'||Array.isArray(data))){children=data;data={};}
  return {tag,data:data||{},children};
}
function html(n){
  if(n==null||n===false)return '';
  if(Array.isArray(n))return n.map(html).join('');
  if(typeof n!=='object')return escape(n);
  const d=n.data,attrs={...(d.attrs||{})};
  if(d.class)attrs.class=d.class;
  if(d.style)attrs.style=Object.entries(d.style).map(([k,v])=>k.replace(/[A-Z]/g,c=>'-'+c.toLowerCase())+':'+v).join(';');
  if(d.domProps?.checked)attrs.checked=true;
  if(d.domProps?.value!==undefined)attrs.value=d.domProps.value;
  const a=Object.entries(attrs).filter(([,v])=>v!==false&&v!==null&&v!==undefined).map(([k,v])=>' '+k+'="'+escape(v===true?'':v)+'"').join('');
  return '<'+n.tag+a+'>'+html(n.children)+(new Set(['input','br','hr','img']).has(n.tag)?'':'</'+n.tag+'>');
}
function load(file,values){
  const c={module:{exports:{}},window:{location:{hostname:'router.example'}},Date,Promise,setTimeout,clearTimeout};
  vm.runInNewContext(fs.readFileSync(path.join(root,file),'utf8'),c);
  const v=c.module.exports,x=Object.assign(v.data(),values);
  for(const [k,f]of Object.entries(v.methods||{}))x[k]=f.bind(x);
  for(const [k,f]of Object.entries(v.computed||{}))Object.defineProperty(x,k,{get:()=>f.call(x)});
  return html(v.render.call(x,h));
}
const status={installed:true,enabled:true,running:true,boot_enabled:true,mode:'rule',operation_mode:'fake-ip',ipv6_enabled:true,ipv6_dns:true,
  core_version:'Mihomo · 示例版本',config_name:'example.yaml',dashboard_port:9090,dashboard_path:'/ui/metacubexd/',dns_chain:'dnsmasq:53 → AGH:3053 → OpenClash:7874',
  subscription:{available:true,upload:1073741824,download:12*1073741824,total:100*1073741824,expire:Math.floor(Date.UTC(2030,0,1,0)/1000),updated_at:stamp}};
const wifi={kind:'wifi',available:true,updated_at:stamp,source:'原厂 repeater 扫描',rows:[
  {ssid:'示例家庭 Wi-Fi',channel:149,band:'5 GHz',frequency:5745,signal:-48,security:'WPA2/3 (RSN)',bssid:'02:00:00:00:00:01'},
  {ssid:'示例访客网络',channel:6,band:'2.4 GHz',frequency:2437,signal:-62,security:'开放网络',bssid:'02:00:00:00:00:02'},
  {ssid:'示例办公室',channel:36,band:'5 GHz',frequency:5180,signal:-72,security:'WPA2/3 (RSN)',bssid:'02:00:00:00:00:03'}]};
const cellular={kind:'cellular',available:true,slot:1,operator:'示例运营商',state:'NOCONN',updated_at:stamp,source:'QENG / COPS 只读查询',
  serving:[{role:'服务小区',radio:'LTE',channel:3740,band:8,pci:450,rsrp:-82,rsrq:-10,sinr:19}],
  neighbors:[{role:'同频邻区',radio:'LTE',channel:3740,pci:224,rsrp:-90,rsrq:-9,sinr:12},{role:'异频邻区',radio:'LTE',channel:3590,pci:118,rsrp:-96,rsrq:-12,sinr:8}]};
function rankings(title,prefix,count){return '<section class="rank"><h2>'+title+'</h2><table><thead><tr><th>域名</th><th>次数</th></tr></thead><tbody>'+Array.from({length:5},(_,i)=>'<tr><td>'+prefix+(i+1)+'.example.com</td><td>'+(count-i*20)+'</td></tr>').join('')+'</tbody></table></section>';}
const views={
  openclash:load('gl-sdk4-ui-openclash.common.js',{status,draft:{enabled:true,mode:'rule',operation_mode:'fake-ip',ipv6_enabled:true},lastUpdated:'12:00:00'}),
  'radio-wifi':load('gl-sdk4-ui-radio-scan.common.js',{kind:'wifi',results:{wifi,cellular}}),
  'radio-cellular':load('gl-sdk4-ui-radio-scan.common.js',{kind:'cellular',results:{wifi,cellular}}),
  'agh-rankings': '<main><h1>AdGuard Home · 前五排行</h1><p>统计接口示意，非原厂网页截图；数据均为示例。</p><div class="ranks">'+rankings('请求域名 TOP 5','www',300)+rankings('拦截域名 TOP 5','ads',120)+'</div></main>'
};
(async()=>{
  const executablePath=process.env.DOCS_BROWSER_PATH;
  const browser=await chromium.launch(executablePath?{executablePath,headless:true}:{channel:'chrome',headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1200,height:850},deviceScaleFactor:1,locale:'zh-CN',timezoneId:'Asia/Shanghai'});
    await page.route('**/*',route=>route.abort()); // These previews must never contact a router or external website.
    for(const [name,body]of Object.entries(views)){
      const content='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>'+name+'</title><style>'+
        'body{margin:0;background:#f4f6f8;color:#25333c;font:14px "Microsoft YaHei","Noto Sans CJK SC",sans-serif;--gl-color-primary:#368ad9}'+
        '.banner{padding:12px 24px;background:#e8f3fd;border-bottom:1px solid #c9dfef;color:#315e7e}.rank{background:white;padding:20px;border:1px solid #dfe5e9;border-radius:14px;flex:1}.ranks{display:flex;gap:20px}main{padding:20px;max-width:1100px;margin:auto}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:14px;border-bottom:1px solid #e3e7eb}'+
        '</style><div class="banner">Mudi7 Control Suite · 源码渲染 / 示例数据 · 非实机验收截图</div>'+body+'</html>';
      fs.writeFileSync(path.join(out,name+'.html'),content);
      await page.setContent(content,{waitUntil:'load'});
      await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});
    }
  }finally{await browser.close();}
  console.log('Synthetic web documentation screenshots rendered:',Object.keys(views).length);
})().catch(e=>{console.error(e.message);process.exitCode=1;});
