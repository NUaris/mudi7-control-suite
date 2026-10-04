module.exports = (function () {
  'use strict';
  function errorText(e) { var s = typeof e === 'string' ? e : e && (e.message || e.error) || '请求失败，请重试。'; return /timeout.*exceeded/i.test(s) ? '请求超时，请检查路由器连接后刷新状态。' : s; }
  function unwrap(v) {
    if (v && v.error && !v.kind) throw new Error(errorText(v.error));
    if (v && v.success === false) throw new Error(v.error || '操作失败');
    if (Array.isArray(v) && typeof v[0] === 'number') { if (v[0] !== 0) throw new Error('路由器请求失败'); return unwrap(v[1]); }
    if (v && v.result) return unwrap(v.result);
    if (v && v.data && !v.kind) return unwrap(v.data);
    return v;
  }
  function rpc(method, kind) {
    return Promise.resolve().then(function () {
      var request = window.$rpcRequest || window.$request;
      if (typeof request !== 'function') throw new Error('管理接口尚未加载，请刷新页面');
      return request('call', ['sid', 'radio-scan', method, { kind: kind }]);
    }).then(unwrap);
  }
  function list(v) { return Array.isArray(v) ? v : []; }
  function value(v) { return typeof v === 'number' && isFinite(v) ? String(v) : '—'; }
  function time(v) { return v > 0 ? new Date(v * 1000).toLocaleString('zh-CN', { hour12: false }) : '尚未扫描'; }
  function merge(a,b) { var x={};Object.keys(a).forEach(function(k){x[k]=a[k];});Object.keys(b||{}).forEach(function(k){x[k]=b[k];});return x; }
  var s={
    page:{padding:'20px',maxWidth:'1100px',margin:'0 auto',color:'inherit',fontSize:'14px',lineHeight:'1.6',boxSizing:'border-box'},
    card:{padding:'20px',marginBottom:'18px',border:'1px solid rgba(128,128,128,.2)',borderRadius:'14px',background:'rgba(128,128,128,.035)'},
    title:{margin:'0',fontSize:'22px',fontWeight:'600'},
    row:{display:'flex',alignItems:'center',gap:'12px',flexWrap:'wrap'},
    button:{background:'transparent',color:'inherit',border:'1px solid rgba(128,128,128,.35)',borderRadius:'7px',padding:'8px 14px',minHeight:'38px',cursor:'pointer',fontSize:'14px'},
    primary:{background:'var(--gl-color-primary, #368ad9)',color:'#fff',borderColor:'var(--gl-color-primary, #368ad9)'},
    hint:{fontSize:'13px',opacity:'.72',marginTop:'10px',overflowWrap:'anywhere'},
    notice:{padding:'12px',borderRadius:'8px',background:'rgba(54,138,217,.07)',marginTop:'14px'},
    table:{width:'100%',borderCollapse:'collapse',textAlign:'left',fontSize:'13px'},
    cell:{padding:'12px 10px',borderBottom:'1px solid rgba(128,128,128,.18)',verticalAlign:'top',overflowWrap:'anywhere'},
    field:{fontSize:'14px',padding:'8px 12px',borderRadius:'7px',border:'1px solid rgba(128,128,128,.35)',background:'transparent',color:'inherit',maxWidth:'100%',boxSizing:'border-box'}
  };
  return {
    name:'RadioScanView',
    data:function(){return {kind:'wifi',results:{wifi:null,cellular:null},fetching:false,starting:false,error:'',timer:null,disposed:false,query:'',band:'',startedKind:'',pollFailures:0};},
    computed:{
      current:function(){return this.results[this.kind] || {};},
      busy:function(){return this.starting || !!this.current.active_kind;},
      wifiRows:function(){var q=this.query.toLowerCase(),band=this.band;return list(this.results.wifi && this.results.wifi.rows).filter(function(r){return (!q || String(r.ssid || '').toLowerCase().indexOf(q)>=0) && (!band || r.band===band);});}
    },
    created:function(){this.load();},
    beforeDestroy:function(){this.disposed=true;clearTimeout(this.timer);},
    methods:{
      schedule:function(){var self=this;clearTimeout(this.timer);if(!this.disposed)this.timer=setTimeout(function(){self.load();},2000);},
      load:function(){
        var self=this,kind=this.kind;if(this.fetching || this.disposed)return;this.fetching=true;
        rpc('get_status',kind).then(function(v){
          if(self.disposed)return;if(!v || v.kind!==kind)throw new Error('扫描状态不完整');
          self.results[kind]=v;self.error='';self.pollFailures=0;
          if(v.active_kind)self.schedule();else self.startedKind='';
          if(self.kind!==kind)self.schedule();
        }).catch(function(e){if(self.disposed)return;self.error=errorText(e);self.pollFailures++;if(self.startedKind && self.pollFailures<5)self.schedule();}).then(function(){self.fetching=false;});
      },
      choose:function(kind){if(this.starting)return;this.kind=kind;this.error='';clearTimeout(this.timer);this.load();},
      scan:function(){
        var self=this,kind=this.kind;if(this.busy || this.fetching)return;this.error='';this.starting=true;
        rpc('start_scan',kind).then(function(){if(self.disposed)return;self.startedKind=kind;self.results[kind]=merge(self.results[kind]||{},{active_kind:kind,busy:true});self.schedule();}).catch(function(e){self.error=errorText(e);}).then(function(){self.starting=false;});
      }
    },
    render:function(h){
      var self=this,current=this.current;
      function button(label,action,disabled,primary){return h('button',{attrs:{type:'button',disabled:disabled},style:merge(s.button,merge(primary?s.primary:{},disabled?{opacity:'.5',cursor:'not-allowed'}:{})),on:{click:action}},label);}
      function table(title,headers,rows,map){
        return h('section',{style:s.card,attrs:{'aria-label':title}},[
          h('h2',{style:{fontSize:'17px',margin:'0 0 14px'}},title),
          rows.length?h('div',{style:{overflowX:'auto'}},[h('table',{style:s.table},[
            h('thead',[h('tr',headers.map(function(x){return h('th',{style:s.cell,attrs:{scope:'col'}},x);} ))]),
            h('tbody',rows.map(function(row,index){return h('tr',{key:index},map(row).map(function(x){return h('td',{style:s.cell},String(x));}));}))
          ])]):h('div',{style:s.hint},current.available?'设备本次没有返回可显示的数据。':'请点击扫描获取设备数据。')
        ]);
      }
      function cellValues(r){return [r.role,r.radio,value(r.channel),r.band?(r.radio.indexOf('NR')===0?'n':'B')+r.band:'—',value(r.pci),value(r.rsrp),value(r.rsrq),value(r.sinr)];}
      var tabs=h('div',{style:merge(s.row,{marginTop:'16px'}),attrs:{role:'group','aria-label':'扫描类型'}},['wifi','cellular'].map(function(k){return h('button',{attrs:{type:'button','aria-pressed':self.kind===k?'true':'false',disabled:self.starting},style:merge(s.button,self.kind===k?s.primary:{}),on:{click:function(){self.choose(k);}}},k==='wifi'?'Wi-Fi 扫描':'蜂窝扫描');}));
      var body;
      if(this.kind==='wifi'){
        body=[
          h('section',{style:s.card,attrs:{'aria-label':'Wi-Fi 筛选'}},[
            h('div',{style:s.row},[
              h('input',{attrs:{type:'search',placeholder:'筛选 SSID','aria-label':'筛选 SSID'},domProps:{value:this.query},style:s.field,on:{input:function(e){self.query=e.target.value;}}}),
              h('select',{attrs:{'aria-label':'筛选频段'},domProps:{value:this.band},style:s.field,on:{change:function(e){self.band=e.target.value;}}},['','2.4 GHz','5 GHz','6 GHz'].map(function(x){return h('option',{domProps:{value:x}},x||'全部频段');})),
              h('span', '显示 '+this.wifiRows.length+' / '+list(current.rows).length+' 个 BSS')
            ]),h('div',{style:s.hint},'同名 SSID 的不同 BSSID 分开显示；信号由强到弱排列。隐藏 SSID 不会被猜测。未启用的频段不保证有扫描结果。')
          ]),
          table('Wi-Fi 扫描结果',['SSID','频道','频段','频率 MHz','信号 dBm','安全','BSSID'],this.wifiRows,function(r){return [r.ssid||'（隐藏 SSID）',value(r.channel),r.band||'—',value(r.frequency),value(r.signal),r.security||'—',r.bssid];})
        ];
      }else{
        var states={SEARCH:'正在搜网',LIMSRV:'有限服务 / 未注册',NOCONN:'已注册 · 空闲',CONNECT:'已注册 · 连接中'};
        body=[
          h('section',{style:s.card,attrs:{'aria-label':'蜂窝状态'}},[
            h('div',{style:s.row},[h('span','当前槽位：'+(current.slot?'SIM '+current.slot:'—')),h('span','运营商：'+(current.operator||'未提供')),h('span','注册状态：'+(states[current.state]||current.state||(current.available?'未提供有效服务小区':'尚未查询')))]),
            current.warning?h('div',{style:s.notice},current.warning):null,
            h('div',{style:s.hint},'这里只查询服务小区和设备可报告的邻区，不切换 SIM、频段或运营商，也不执行全频段搜网、锁塔或重拨。')
          ]),
          table('服务小区 / 5G 载波',['类型','制式','EARFCN/NR-ARFCN','频段','PCI','RSRP dBm','RSRQ dB','SINR dB'],list(current.serving),cellValues),
          table('邻区信号',['类型','制式','EARFCN','频段','PCI','RSRP dBm','RSRQ dB','SINR dB'],list(current.neighbors),cellValues),
          current.neighbor_note?h('div',{style:merge(s.notice,{marginBottom:'18px'})},current.neighbor_note):null
        ];
      }
      return h('main',{style:s.page,class:'radio-scan-view'},[
        h('section',{style:s.card},[
          h('h1',{style:s.title},'无线信号扫描'),tabs,
          h('div',{style:merge(s.row,{marginTop:'18px'})},[
            button(this.busy?'扫描进行中…':this.kind==='wifi'?'开始 Wi-Fi 扫描':'查询蜂窝信号',this.scan,this.busy||this.fetching,true),
            button(this.fetching?'读取中…':'刷新状态',this.load,this.fetching||this.starting,false)
          ]),
          h('div',{style:s.hint},'数据更新：'+time(current.updated_at)+(current.source?' · '+current.source:'')),
          h('div',{style:s.hint},'扫描按需执行，最短间隔 20 秒。Wi-Fi 扫描可能短暂增加无线链路延迟；不会连接到扫描出的网络或修改现有配置。'),
          this.busy?h('div',{style:s.notice,attrs:{role:'status','aria-live':'polite'}},'后台正在查询，每 2 秒读取一次结果；可等待，也可离开此页面。'):null,
          this.error||current.error?h('div',{style:merge(s.notice,{color:'#d18d34'}),attrs:{role:'alert'}},this.error||current.error+(current.updated_at?' 以上保留上次成功数据。':'')):null
        ])
      ].concat(body));
    }
  };
})();
