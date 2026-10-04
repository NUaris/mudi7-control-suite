"""GL-style Chinese screen fork using upstream framebuffer and touch drivers.
Backend controls are shared with the native management webpage, not duplicated.
"""
import argparse
import json
import math
import os
import signal
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import dashboard as hardware
import backend as api

W,H=240,320
SHANGHAI=timezone(timedelta(hours=8))
BG='#101315'; CARD='#242a2d'; LINE='#353c40'; FG='#f4f6f7'; DIM='#a0aaaf'; ACCENT='#46d3b1'; BLUE='#438ded'
BASE=Path(__file__).parent
FONT_PATH=Path('/etc/gl_screen/language/ttf/default_cn_medium.ttf')
if not FONT_PATH.exists(): FONT_PATH=BASE/'default_cn_medium.ttf'
FONTS={}
WALLPAPER=None
for candidate in [Path('/etc/gl_screen/image/wallpaper.png'),BASE/'factory-wallpaper.png']:
    if candidate.exists():
        try:WALLPAPER=Image.open(candidate).convert('RGB').resize((W,H));break
        except OSError:pass

def font(size=14):
    if size not in FONTS: FONTS[size]=ImageFont.truetype(str(FONT_PATH),size)
    return FONTS[size]

def display_text(value):
    # The vendor CJK font has no colour emoji/flag glyphs. Keep backend names
    # untouched for selection, but avoid missing-glyph boxes in their labels.
    return ''.join(c for c in str(value) if (ord(c)>=32 or c=='\n') and not
        (0x1f000<=ord(c)<=0x1faff or 0xfe00<=ord(c)<=0xfe0f or 0xd800<=ord(c)<=0xdfff or ord(c)==0x200d))

def text_width(value,size=14):
    return font(size).getlength(display_text(value))

def shorten(value,width,size=14):
    value=str(value)
    if text_width(value,size)<=width: return value
    while value and text_width(value+'…',size)>width: value=value[:-1]
    return value+'…'

def wrap(value,width,size=14):
    lines=[];line=''
    for char in str(value):
        if char=='\n': lines.append(line);line='';continue
        if line and text_width(line+char,size)>width: lines.append(line);line=char
        else: line+=char
    lines.append(line)
    return lines

def number(value,unit=''):
    return str(value)+unit if isinstance(value,(int,float)) else '—'

def gib(value):
    return ('%.1f GiB'%(value/1073741824)) if isinstance(value,(int,float)) else '未提供'

def dated(value):
    try: return datetime.fromtimestamp(value,SHANGHAI).strftime('%Y-%m-%d %H:%M') if value else '未提供'
    except (ValueError,OSError,TypeError): return '未提供'

class Store:
    def __init__(self):
        self.lock=threading.Lock();self.values={};self.stamps={};self.errors={};self.running=set();self.generation=0

    def snapshot(self):
        with self.lock: return dict(self.values),dict(self.errors),set(self.running),self.generation

    def run(self,key,fn,notice=None):
        with self.lock:
            if key in self.running:return False
            self.running.add(key);self.errors.pop(key,None);self.generation+=1
        def worker():
            try:
                value=fn()
                with self.lock:
                    if value is not None:self.values[key]=value
                    self.stamps[key]=time.monotonic()
                    if notice:self.values['notice']=notice
            except Exception:
                # No exception payload: urllib/subprocess errors may contain secrets.
                with self.lock:self.errors[key]='操作未确认，请在原厂网页核对后重试'
            finally:
                with self.lock:self.running.discard(key);self.generation+=1
        threading.Thread(target=worker,daemon=True).start();return True

class App:
    def __init__(self,store=None,settings=None,guard=None,preview=False):
        self.store=store or Store();self.settings=settings or api.pin_settings();self.guard=guard or api.PinGuard()
        self.locked=self.settings['enabled'];self.pin='';self.pin_message='';self.last_activity=time.monotonic()
        self.page='home';self.page_number=0;self.band='';self.rank='blocked';self.cell_tab='serving'
        self.dialog=None;self.return_page='settings';self.keys='';self.key_layer='letters';self.key_caps=False
        self.target=None;self.selected_group=None;self.buttons=[];self.preview=preview;self.last_refresh={};self.current_notice='';self.notice_at=0

    def values(self): return self.store.snapshot()[0]

    def go(self,page):
        if self.page in ('keyboard','connect_prepare') and page!=self.page:
            self.keys='';self.target=None
        self.page=page;self.page_number=0;self.dialog=None;self.current_notice='';self.refresh(force=True)

    def relock(self):
        self.locked=self.settings['enabled'];self.pin='';self.keys='';self.target=None;self.dialog=None
        self.page='home';self.page_number=0;self.pin_message='';self.last_activity=time.monotonic()

    def confirm(self,title,detail,action):
        if self.locked:return
        self.dialog=(title,detail,action)

    def action(self,fn,notice='已提交，请等待设备应用'):
        if self.locked:return
        if 'action' in self.store.snapshot()[2]:
            self.current_notice='上一项操作正在执行，请稍候';self.notice_at=time.monotonic();return
        self.dialog=None
        def job():
            fn();return None
        self.store.run('action',job,notice)

    def refresh(self,force=False):
        if self.preview:return
        now=time.monotonic()
        tasks={'oc':lambda:api.rpc('openclash','get_status'),
               'agh':lambda:api.rpc('adguardhome','get_config'),
               'repeater':api.repeater_status,'port':api.port_info}
        for key,fn in tasks.items():
            if force or now-self.last_refresh.get(key,-100)>10:
                self.last_refresh[key]=now;self.store.run(key,fn)
        # Scan data stays RAM-only; do not trigger a scan merely by opening a page.
        if self.page in ('wifi','repeater','cellular'):
            kind='cellular' if self.page=='cellular' else 'wifi'
            if force or now-self.last_refresh.get(kind,-100)>2:
                self.last_refresh[kind]=now;self.store.run(kind,lambda:api.scan_status(kind))
        if self.page in ('agh','rank') and (force or now-self.last_refresh.get('stats',-100)>30):
            self.last_refresh['stats']=now;self.store.run('stats',api.agh_stats)
        if self.page in ('groups','nodes') and (force or now-self.last_refresh.get('groups',-100)>15):
            self.last_refresh['groups']=now;self.store.run('groups',api.proxy_groups)

    def scan(self,kind):
        if self.locked:return
        self.action(lambda:api.scan_start(kind),'扫描已提交，请等待结果')

    def connection(self,ap):
        if self.locked:return
        self.target=ap
        def prepare():
            remembered=api.saved_key(ap.get('ssid',''))
            return {'ap':ap,'key':remembered}
        if self.preview:
            self.page='keyboard';self.keys='';return
        self.store.run('connection_prepare',prepare)
        self.page='connect_prepare'

    def connect_confirm(self,ap,password):
        self.confirm('连接 Wi-Fi 中继',str(ap.get('ssid',''))+'\n将替换当前中继连接，网络可能中断。',
            lambda:self.action(lambda:api.repeater_connect(ap,password),'Wi-Fi 中继已连接'))

    def key_press(self,key):
        if key=='删除':self.keys=self.keys[:-1]
        elif key=='大小写':self.key_caps=not self.key_caps
        elif key=='符号':
            layers=['letters','symbols','extra'];self.key_layer=layers[(layers.index(self.key_layer)+1)%3]
        elif key=='空格':
            if len(self.keys)<128:self.keys+=' '
        elif key=='取消':self.keys='';self.target=None;self.go('repeater')
        elif key=='连接':
            if self.target:
                password=self.keys;self.keys='';self.connect_confirm(self.target,password)
        elif len(self.keys)<128:self.keys+=key

    def tap(self,x,y):
        self.last_activity=time.monotonic()
        for rect,fn,label in reversed(self.buttons):
            x0,y0,x1,y1=rect
            if x0<=x<x1 and y0<=y<y1:
                fn();return label
        return None

    def paginate(self,count,size):
        self.page_number=max(0,min(self.page_number,max(0,(count-1)//size)))
        return self.page_number*size

    def page_change(self,delta): self.page_number=max(0,self.page_number+delta)

    def render(self):
        self.buttons=[];self.img=Image.new('RGB',(W,H),BG);self.d=ImageDraw.Draw(self.img)
        self.data,self.errors,self.running,_=self.store.snapshot()
        self.status()
        if self.locked:self.lock_screen();return self.img
        if self.page=='home':self.home()
        elif self.page=='settings':self.menu()
        elif self.page=='oc':self.openclash()
        elif self.page=='mode':self.mode_picker()
        elif self.page=='dns':self.dns_picker()
        elif self.page=='subscription':self.subscription()
        elif self.page=='agh':self.adguard()
        elif self.page=='rank':self.rankings()
        elif self.page in ('wifi','repeater'):self.wifi()
        elif self.page=='cellular':self.cellular()
        elif self.page=='port':self.port()
        elif self.page=='screen':self.screen_settings()
        elif self.page=='groups':self.groups()
        elif self.page=='nodes':self.nodes()
        elif self.page=='keyboard':self.keyboard()
        elif self.page=='connect_prepare':
            self.header('Wi-Fi 中继','repeater');self.paragraph(85,'读取已保存的网络设置…')
        else:self.go('home')
        if self.running:self.d.ellipse((224,27,232,35),fill=ACCENT)
        errors=self.errors.get('action') or self.errors.get(self.page) or self.current_notice
        if errors:self.toast(errors)
        if self.dialog:self.modal()
        return self.img

    def txt(self,x,y,text,size=14,color=FG,width=None):
        text=display_text(shorten(text,width,size) if width else text)
        self.d.text((x,y),text,font=font(size),fill=color,stroke_width=0)

    def center(self,y,text,size=14,color=FG):self.txt((W-text_width(text,size))/2,y,text,size,color)

    def card(self,rect):self.d.rounded_rectangle(rect,radius=11,fill=CARD)

    def button(self,rect,label,fn,active=False,size=14,disabled=False):
        self.d.rounded_rectangle(rect,radius=9,fill=BLUE if active else CARD,
                                 outline=None if active else LINE,width=1)
        x0,y0,x1,y1=rect;self.txt(x0+(x1-x0-text_width(label,size))/2,y0+(y1-y0-size)/2-2,label,size,DIM if disabled else FG)
        if not disabled:self.buttons.append((rect,fn,label))

    def row(self,y,title,detail,fn=None,active=None,height=44):
        self.card((8,y,232,y+height-4));self.txt(18,y+7,title,14,width=170)
        if detail:self.txt(18,y+25,detail,11,DIM,width=190)
        if active is not None:
            self.d.rounded_rectangle((195,y+12,222,y+28),radius=8,fill=ACCENT if active else LINE)
            self.d.ellipse((209 if active else 196,y+14,220 if active else 207,y+25),fill=FG)
        elif fn:self.d.line((215,y+13,220,y+18,215,y+23),fill=DIM,width=2)
        if fn:self.buttons.append(((8,y,232,y+height-4),fn,title))

    def paragraph(self,y,text,size=13,color=DIM,width=208,limit=6):
        lines=wrap(text,width,size)
        for line in lines[:limit]:self.txt(16,y,line,size,color);y+=size+5
        return y

    def status(self):
        self.txt(8,4,datetime.now(SHANGHAI).strftime('%H:%M'),11)
        oc=self.data.get('oc',{});agh=self.data.get('agh',{})
        x=83
        for label,on in [('CL',oc.get('running')),('AGH',agh.get('enabled'))]:
            self.d.rounded_rectangle((x,4,x+26,17),radius=3,outline=ACCENT if on else DIM)
            self.txt(x+2,4,label,9,ACCENT if on else DIM);x+=31
        rep=self.data.get('repeater',{})
        self.txt(150,4,'Wi-Fi' if rep.get('is_connected') else '网络',10,DIM)
        battery=self.data.get('battery')
        if battery:
            pct,plugged=battery;self.d.rounded_rectangle((192,5,230,16),radius=2,outline=DIM)
            self.txt(196,3,('%d%%'%pct),10,ACCENT if plugged else FG)

    def header(self,title,parent='settings'):
        self.d.line((19,30,11,38,19,46),fill=FG,width=2);self.txt(33,30,title,17,width=190)
        self.buttons.append(((0,22,240,65),lambda:self.go(parent),'返回'))
        self.d.line((8,63,232,63),fill=LINE)

    def footer_pages(self,count,size):
        pages=max(1,math.ceil(count/size))
        self.button((8,280,67,312),'上一页',lambda:self.page_change(-1),size=12,disabled=self.page_number==0)
        self.center(288,'%d / %d'%(self.page_number+1,pages),12,DIM)
        self.button((173,280,232,312),'下一页',lambda:self.page_change(1),size=12,disabled=self.page_number>=pages-1)

    def lock_screen(self):
        self.center(33,'屏幕已锁定',20)
        self.center(65,'输入原厂四位屏幕密码',12,DIM)
        if not self.settings['valid']:
            self.paragraph(104,'密码读取异常，保持锁定。请用原厂网页检查屏幕密码。')
            self.button((24,257,216,299),'切回原厂屏幕',lambda:self.switch_stock(),size=14);return
        self.center(96,' '.join('●' if i<len(self.pin) else '○' for i in range(4)),20,ACCENT)
        wait=self.guard.remaining() if not self.preview else 0
        self.center(124,('请等待 %d 秒'%wait) if wait else self.pin_message,12,'#f1b36e')
        for i,label in enumerate(['1','2','3','4','5','6','7','8','9','返回','0','删除']):
            col,row=i%3,i//3;rect=(15+col*72,153+row*37,81+col*72,187+row*37)
            self.button(rect,label,lambda v=label:self.pin_key(v),size=16,disabled=wait>0 and label not in ('返回','删除'))

    def pin_key(self,value):
        if value=='返回':self.pin='';self.switch_stock();return
        if value=='删除':self.pin=self.pin[:-1];return
        if len(self.pin)<4:self.pin+=value
        if len(self.pin)==4:
            ok,message=self.guard.check(self.pin);self.pin='';self.pin_message=message
            if ok:self.locked=False;self.go('home')

    def switch_stock(self):
        if self.preview:return
        # Returning to the independently password-protected stock screen is safe
        # even from our lock screen; it does not change/disable its passcode.
        import subprocess
        subprocess.Popen(['/root/dashboard/toggle.sh','off'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def home(self):
        if WALLPAPER:
            shade=Image.new('RGBA',(W,H),(0,0,0,100))
            self.img=Image.alpha_composite(WALLPAPER.convert('RGBA'),shade).convert('RGB');self.d=ImageDraw.Draw(self.img)
            self.status()
        self.center(34,datetime.now(SHANGHAI).strftime('%H:%M'),50)
        self.center(101,datetime.now(SHANGHAI).strftime('%m月%d日  %A').replace('Monday','星期一').replace('Tuesday','星期二').replace('Wednesday','星期三').replace('Thursday','星期四').replace('Friday','星期五').replace('Saturday','星期六').replace('Sunday','星期日'),13,DIM)
        rep=self.data.get('repeater',{});self.row(138,'互联网',(rep.get('ssid') or 'Wi-Fi 中继') if rep.get('is_connected') else '查看 Wi-Fi 中继连接',lambda:self.go('repeater'),height=51)
        oc=self.data.get('oc',{});agh=self.data.get('agh',{})
        self.button((8,195,116,237),'OpenClash',lambda:self.go('oc'),size=13)
        self.button((124,195,232,237),'AdGuard',lambda:self.go('agh'),size=14)
        self.txt(17,242,'运行中' if oc.get('running') else '未运行',12,ACCENT if oc.get('running') else DIM)
        self.txt(140,242,'已开启' if agh.get('enabled') else '已关闭',12,ACCENT if agh.get('enabled') else DIM)
        self.button((8,270,116,310),'锁屏',self.relock,size=14,disabled=not self.settings['enabled'])
        self.button((124,270,232,310),'设置',lambda:self.go('settings'),active=True)

    def menu(self):
        self.header('设置','home')
        items=[('OpenClash','开关 / 模式 / 节点 / 订阅','oc'),('AdGuard Home','开关 / 域名前五排行','agh'),
               ('Wi-Fi 信号扫描','SSID / 频道 / 信号强度','wifi'),('蜂窝信号扫描','服务小区 / 邻区','cellular'),
               ('Wi-Fi 中继','选择并连接无线网络','repeater'),('Ethernet 网口','LAN / WAN 切换','port'),
               ('屏幕与锁屏','沿用原厂密码 / 自动锁定','screen'),('原厂屏幕','保留原厂界面与所有设置','stock')]
        start=self.paginate(len(items),4)
        for i,(title,detail,page) in enumerate(items[start:start+4]):
            fn=(lambda:self.confirm('切回原厂屏幕','当前功能不会卸载，原厂密码保持不变。',self.switch_stock)) if page=='stock' else lambda p=page:self.go(p)
            self.row(74+i*49,title,detail,fn,height=48)
        self.footer_pages(len(items),4)

    def openclash(self):
        self.header('OpenClash');v=self.data.get('oc',{});busy=v.get('busy') or 'action' in self.running
        items=[('服务开关','运行中' if v.get('running') else '已停用',lambda:self.confirm('切换 OpenClash','网络与 DNS 可能短暂中断，是否继续？',lambda:self.action(lambda:api.oc_set(enabled=not v.get('enabled')))),v.get('enabled')),
               ('运行模式',{'rule':'规则','global':'全局','direct':'直连'}.get(v.get('mode'),'读取中'),lambda:self.go('mode'),None),
               ('策略组 / 节点','选择当前代理节点',lambda:self.go('groups'),None),
               ('DNS 模式',v.get('operation_mode','读取中'),lambda:self.go('dns'),None),
               ('IPv6 代理','同时启用 IPv6 DNS' if v.get('ipv6_enabled') else '未开启',lambda:self.confirm('切换 IPv6 代理','与网页使用同一配置，应用期间可能断网。',lambda:self.action(lambda:api.oc_set(ipv6_enabled=not v.get('ipv6_enabled')))),v.get('ipv6_enabled')),
               ('订阅信息','到期时间 / 剩余流量',lambda:self.go('subscription'),None)]
        start=self.paginate(len(items),4)
        for i,(a,b,fn,on) in enumerate(items[start:start+4]):self.row(74+i*49,a,b,None if busy else fn,on,height=48)
        if busy:self.txt(12,266,'设置正在应用…',11,ACCENT)
        self.footer_pages(len(items),4)

    def mode_picker(self):
        self.header('运行模式','oc');current=self.data.get('oc',{}).get('mode')
        for i,(key,title,detail) in enumerate([('rule','规则模式','按域名规则直连或代理'),('global','全局模式','流量通过所选全局策略'),('direct','直连模式','不使用代理节点')]):
            self.row(83+i*58,title,detail,lambda k=key:self.confirm('应用运行模式','将应用 '+k+'，期间网络可能短暂中断。',lambda:self.action(lambda:api.oc_set(mode=k))),key==current,height=54)

    def dns_picker(self):
        self.header('DNS 模式','oc');current=self.data.get('oc',{}).get('operation_mode')
        for i,key in enumerate(['fake-ip','redir-host']):self.row(90+i*62,key,'保留 AGH 与 OpenClash 协同',lambda k=key:self.confirm('应用 DNS 模式','将应用 '+k+'，现有连接可能中断。',lambda:self.action(lambda:api.oc_set(operation_mode=k))),key==current,height=55)

    def subscription(self):
        self.header('订阅信息','oc');v=self.data.get('oc',{}).get('subscription') or {}
        used=(v.get('upload',0)+v.get('download',0)) if v.get('available') else None
        total=v.get('total');remaining=max(0,total-used) if total and used is not None else None
        self.row(80,'剩余流量',gib(remaining),height=55);self.row(138,'已用 / 总额度',gib(used)+' / '+gib(total),height=55)
        self.row(196,'到期时间',dated(v.get('expire')),height=55)
        if v.get('error') or v.get('stale'):self.txt(12,254,'缓存可能过期，请刷新后核对',11,'#f1b36e',width=214)
        self.button((24,278,216,312),'刷新订阅信息',lambda:self.action(lambda:api.rpc('openclash','refresh_subscription',{}),'订阅信息刷新已提交'),active=True,size=13,disabled=v.get('refreshing',False))

    def adguard(self):
        self.header('AdGuard Home');v=self.data.get('agh',{});s=self.data.get('stats',{})
        self.row(77,'广告过滤',('已开启' if v.get('enabled') else '已关闭'),lambda:self.confirm('切换广告过滤','将同步修正 DNS 链路，是否继续？',lambda:self.action(lambda:api.agh_set(not v.get('enabled')))),v.get('enabled'),height=51)
        self.row(136,'DNS 请求 / 拦截',number(s.get('num_dns_queries'))+' / '+number(s.get('num_blocked_filtering')),height=51)
        self.row(195,'域名前五排行','被拦截域名 / 请求域名',lambda:self.go('rank'),height=51)
        self.button((24,278,216,312),'刷新统计',lambda:self.store.run('stats',api.agh_stats),size=13)

    def rankings(self):
        self.header('域名前五排行','agh')
        self.button((8,72,116,102),'拦截排行',lambda:setattr(self,'rank','blocked'),self.rank=='blocked',size=13)
        self.button((124,72,232,102),'请求排行',lambda:setattr(self,'rank','queried'),self.rank=='queried',size=13)
        values=api.array(self.data.get('stats',{}).get('top_'+self.rank+'_domains'))[:5]
        if not values:self.paragraph(132,'暂无排行数据；请检查服务是否开启。')
        for i,item in enumerate(values):
            domain,count=next(iter(item.items())) if isinstance(item,dict) and item else ('—',0)
            y=111+i*39;self.card((8,y,232,y+36));self.txt(14,y+3,str(i+1),11,ACCENT)
            self.txt(30,y+2,domain,11,width=184);self.txt(30,y+19,number(count)+' 次',10,DIM)

    def wifi(self):
        repeater=self.page=='repeater';self.header('Wi-Fi 中继' if repeater else 'Wi-Fi 扫描')
        value=self.data.get('wifi',{});busy=bool(value.get('active_kind')) or 'action' in self.running
        self.button((8,72,115,102),'扫描中…' if busy else '扫描 Wi-Fi',lambda:self.scan('wifi'),active=True,size=12,disabled=busy)
        self.button((124,72,232,102),self.band or '全部频段',self.cycle_band,size=12)
        rep=self.data.get('repeater',{})
        caption='扫描失败，显示上次成功数据' if value.get('error') else (('当前：'+(rep.get('ssid') or '未连接')) if repeater else 'SSID · 频道 · 信号')
        self.txt(10,109,caption,11,DIM,width=220)
        rows=[r for r in api.array(value.get('rows')) if not self.band or r.get('band')==self.band]
        start=self.paginate(len(rows),3)
        if not rows:self.paragraph(157,value.get('error') or '尚无数据，请扫描；不会自动连接。')
        for i,ap in enumerate(rows[start:start+3]):
            ssid=ap.get('ssid') or '隐藏 SSID';detail='频道 %s · %s · %s dBm'%(ap.get('channel','—'),ap.get('band','—'),ap.get('signal','—'))
            fn=(lambda a=ap:self.connection(a)) if repeater and ap.get('ssid') else lambda a=ap:self.ap_detail(a)
            self.row(129+i*47,ssid,detail,fn,height=46)
        self.footer_pages(len(rows),3)

    def ap_detail(self,ap):
        self.confirm(ap.get('ssid') or '隐藏 SSID','BSSID：'+ap.get('bssid','—')+'\n安全：'+ap.get('security','—')+'\n频道：'+str(ap.get('channel','—')),lambda:setattr(self,'dialog',None))

    def cycle_band(self):
        bands=['','2.4 GHz','5 GHz','6 GHz'];self.band=bands[(bands.index(self.band)+1)%4];self.page_number=0

    def cellular(self):
        self.header('蜂窝信号扫描');v=self.data.get('cellular',{});busy=bool(v.get('active_kind')) or 'action' in self.running
        self.button((8,72,115,102),'查询中…' if busy else '查询信号',lambda:self.scan('cellular'),active=True,size=12,disabled=busy)
        self.button((124,72,232,102),'服务小区' if self.cell_tab=='serving' else '邻区信号',self.cycle_cells,size=12)
        caption='查询失败，显示上次成功数据' if v.get('error') else (v.get('operator') or '运营商未提供')+' · '+v.get('state','')
        self.txt(10,109,caption,11,DIM,width=220)
        rows=api.array(v.get(self.cell_tab));start=self.paginate(len(rows),2)
        if not rows:self.paragraph(149,'本次未返回有效数据；不代表周围没有基站。')
        for i,r in enumerate(rows[start:start+2]):
            y=130+i*68;self.card((8,y,232,y+62));band=r.get('band');prefix='n' if str(r.get('radio','')).startswith('NR') else 'B'
            self.txt(15,y+4,str(r.get('radio','—'))+' '+(prefix+str(band) if band else ''),13)
            self.txt(15,y+23,'频道 '+str(r.get('channel','—'))+' · PCI '+str(r.get('pci','—')),11,DIM)
            self.txt(15,y+42,'RSRP '+number(r.get('rsrp'))+' · RSRQ '+number(r.get('rsrq'))+' · SINR '+number(r.get('sinr')),10,ACCENT,width=209)
        self.footer_pages(len(rows),2)

    def cycle_cells(self):self.cell_tab='neighbors' if self.cell_tab=='serving' else 'serving';self.page_number=0

    def port(self):
        self.header('Ethernet 网口');v=self.data.get('port',{});mode=v.get('mode')
        self.row(81,'当前网口角色',mode.upper() if mode in ('lan','wan') else '读取中',height=53)
        self.paragraph(148,'LAN：连接电脑等下游设备。\nWAN：连接上游网络。\n切换会重启相关网络，网线连接可能断开。',size=13,limit=6)
        for i,target in enumerate(['lan','wan']):
            self.button((8+i*116,260,116+i*116,304),target.upper(),lambda t=target:self.confirm('切换为 '+t.upper(),'网线连接可能中断。请确认另有 Wi-Fi/SSH 管理通道。',lambda:self.action(lambda:api.port_set(t),'网口模式已确认')),active=mode==target,disabled=not mode or 'action' in self.running)

    def screen_settings(self):
        self.header('屏幕与锁屏');enabled=self.settings['enabled'];seconds=self.settings['timeout']
        self.row(80,'屏幕密码','已启用 · 沿用原厂四位密码' if enabled else '原厂当前未启用',height=54)
        self.row(140,'自动锁定',('%d 秒无操作'%seconds) if seconds else '沿用原厂：不自动锁定',height=54)
        self.paragraph(209,'切回原厂屏幕后，在原厂网页“系统 → 显示管理”修改密码、亮度和锁屏时间；不另存密码。',size=12,limit=4)
        self.button((24,273,216,311),'立即锁屏',self.relock,active=True,disabled=not enabled)

    def groups(self):
        self.header('选择策略组','oc');rows=api.array(self.data.get('groups'));start=self.paginate(len(rows),4)
        if not rows:self.paragraph(117,'策略组读取中，或核心尚未启动。')
        for i,g in enumerate(rows[start:start+4]):
            def choose(group=g):self.selected_group=group;self.go('nodes')
            self.row(76+i*48,g['name'],g.get('now') or '未选择',choose,height=46)
        self.footer_pages(len(rows),4)

    def nodes(self):
        group=next((x for x in api.array(self.data.get('groups')) if self.selected_group and x.get('name')==self.selected_group.get('name')),self.selected_group or {})
        self.header('选择节点','groups');rows=api.array(group.get('all'));start=self.paginate(len(rows),4)
        for i,node in enumerate(rows[start:start+4]):
            self.row(76+i*48,node,'当前选择' if node==group.get('now') else '',lambda n=node:self.confirm('切换代理节点',n+'\n现有连接可能中断。',lambda:self.action(lambda:api.proxy_select(group['name'],n),'代理节点已确认')),node==group.get('now'),height=46)
        self.footer_pages(len(rows),4)

    def keyboard(self):
        self.header('输入 Wi-Fi 密码','repeater');self.txt(10,71,(self.target or {}).get('ssid',''),12,DIM,width=220)
        self.card((8,92,232,124));self.txt(15,99,'•'*min(24,len(self.keys)),14)
        rows={'letters':['qwertyuiop','asdfghjkl','zxcvbnm'],'symbols':['1234567890','-_/:;()&@"',".,?!'~#$%^"],
              'extra':['+*=<>[]{}','\\|`','0123456789']}[self.key_layer]
        for row,chars in enumerate(rows):
            chars=chars.upper() if self.key_caps and self.key_layer=='letters' else chars
            offset=(W-len(chars)*23)//2
            for col,c in enumerate(chars):self.button((offset+col*23,137+row*33,offset+col*23+22,166+row*33),c,lambda k=c:self.key_press(k),size=14)
        for i,label in enumerate(['大小写','符号','空格','删除']):self.button((6+i*59,240,62+i*59,268),label,lambda k=label:self.key_press(k),size=10)
        self.button((8,278,116,312),'取消',lambda:self.key_press('取消'),size=13)
        self.button((124,278,232,312),'连接',lambda:self.key_press('连接'),active=True,size=13)

    def toast(self,text):
        self.d.rounded_rectangle((5,243,235,277),radius=8,fill='#60442a')
        lines=wrap(text,218,11)
        for i,line in enumerate(lines[:2]):self.txt(11,246+i*14,line,11)

    def modal(self):
        title,detail,action=self.dialog
        overlay=Image.new('RGBA',(W,H),(0,0,0,145));self.img=Image.alpha_composite(self.img.convert('RGBA'),overlay).convert('RGB');self.d=ImageDraw.Draw(self.img)
        self.d.rounded_rectangle((9,73,231,273),radius=13,fill=CARD,outline=LINE)
        self.txt(20,88,title,16,width=198);self.paragraph(119,detail,12,FG,width=195,limit=6)
        self.buttons=[]
        self.button((20,228,111,260),'取消',lambda:setattr(self,'dialog',None),size=13)
        self.button((129,228,220,260),'确认',action,active=True,size=13)

    def tick(self):
        now=time.monotonic()
        with self.store.lock:notice=self.store.values.pop('notice',None)
        if self.locked or self.page!='connect_prepare':
            with self.store.lock:self.store.values.pop('connection_prepare',None)
        if notice:self.current_notice=notice;self.notice_at=now
        if self.current_notice and now-self.notice_at>5:self.current_notice=''
        if not self.locked and self.settings['enabled'] and self.settings['timeout'] and now-self.last_activity>=self.settings['timeout']:self.relock()
        if self.page=='connect_prepare':
            data,errors,running,_=self.store.snapshot()
            if 'connection_prepare' not in running:
                prepared=data.get('connection_prepare')
                if prepared and prepared.get('ap')==self.target:
                    key=prepared.get('key');ap=prepared['ap']
                    with self.store.lock:self.store.values.pop('connection_prepare',None)
                    self.page='repeater'
                    if key is not None or ap.get('open') is True:self.connect_confirm(ap,key or '')
                    else:self.page='keyboard';self.keys=''
                elif errors.get('connection_prepare'):self.go('repeater');self.current_notice='无法读取网络设置，请重试'
        self.refresh()

def demo_store():
    store=Store();store.values={'oc':{'enabled':True,'running':True,'mode':'rule','operation_mode':'fake-ip','ipv6_enabled':True,'subscription':{'available':True,'total':100*1073741824,'download':12*1073741824,'upload':1073741824,'expire':1893456000}},
      'agh':{'enabled':True},'battery':(82,False),'repeater':{'ssid':'示例家庭 Wi-Fi','state_s':'connected','is_connected':True},
      'port':{'name':'wan','mode':'lan'},'wifi':{'rows':[{'ssid':'示例家庭 Wi-Fi','channel':149,'band':'5 GHz','signal':-48,'bssid':'00:11:22:33:44:55'},{'ssid':'示例访客网络','channel':6,'band':'2.4 GHz','signal':-62},{'ssid':'示例办公室','channel':36,'band':'5 GHz','signal':-72}]},
      'cellular':{'operator':'示例运营商','state':'NOCONN','serving':[{'radio':'LTE','channel':3740,'pci':450,'band':8,'rsrp':-82,'rsrq':-10,'sinr':19}],'neighbors':[{'radio':'LTE','channel':3590,'pci':224,'rsrp':-90,'rsrq':-9}]},
      'stats':{'num_dns_queries':3200,'num_blocked_filtering':420,'top_blocked_domains':[{f'ads{i}.example.com':120-i*10} for i in range(1,6)],'top_queried_domains':[{f'www{i}.example.com':220-i*10} for i in range(1,6)]},
      'groups':[{'name':'主代理策略','now':'示例节点 A','all':['示例节点 A','示例节点 B','DIRECT']} ]}
    return store

def preview(directory):
    out=Path(directory);out.mkdir(parents=True,exist_ok=True)
    app=App(demo_store(),{'enabled':True,'valid':True,'pin':'','timeout':60},preview=True)
    app.render().save(out/'lock.png');app.locked=False
    pages=['home','settings','oc','mode','dns','subscription','agh','rank','wifi','repeater','cellular','port','screen','groups','nodes','keyboard']
    app.selected_group=app.values()['groups'][0];app.target=app.values()['wifi']['rows'][0]
    panels=[]
    for page in pages:
        app.page=page;app.page_number=0;image=app.render();image.save(out/(page+'.png'));panels.append((page,image))
    app.page='settings';app.page_number=1;image=app.render();image.save(out/'settings-2.png');panels.append(('settings-2',image))
    app.page='port';app.confirm('切换为 WAN','网线连接可能中断，请确认另一条管理通道。',lambda:None)
    image=app.render();image.save(out/'confirmation.png');panels.append(('confirmation',image))
    sheet=Image.new('RGB',(W*4,H*math.ceil(len(panels)/4)),BG)
    for i,(_,image) in enumerate(panels):sheet.paste(image,((i%4)*W,(i//4)*H))
    sheet.save(out/'contact-sheet.png')

def live():
    app=App();hardware._stop=False
    signal.signal(signal.SIGTERM,hardware._on_term);signal.signal(signal.SIGINT,hardware._on_term)
    reader=threading.Thread(target=hardware._touch_reader,daemon=True);reader.start()
    last_frame=None;was_asleep=hardware.is_screen_asleep();last_settings=0;last_battery=0
    while not hardware._stop:
        now=time.monotonic();asleep=hardware.is_screen_asleep()
        if asleep and not was_asleep:app.relock()
        if was_asleep and not asleep:app.relock()
        was_asleep=asleep
        if now-last_settings>10:
            # Reuse current vendor settings; enabling the password locks at once.
            new=api.pin_settings()
            changed=new['enabled']!=app.settings['enabled'] or new['pin']!=app.settings['pin']
            app.settings=new;last_settings=now
            if changed:app.relock()
        if now-last_battery>15:
            battery=hardware.get_battery()
            with app.store.lock:app.store.values['battery']=battery
            last_battery=now
        with hardware.touch_state.lock:
            touch=hardware.touch_state
            release=touch.release_pending;have=touch.have_pos;dx,dy=touch.release_dx,touch.release_dy
            x,y=touch.down_x,touch.down_y;touch.release_pending=False
            error=touch.error
        if error:raise RuntimeError('触摸输入不可用，恢复原厂屏幕')
        if release and have and not asleep:
            if abs(dx)<15 and abs(dy)<15:app.tap(x,y)
            elif not app.locked and not app.dialog and app.page!='keyboard':
                app.last_activity=now
                if abs(dx)>45:app.page_change(1 if dx<0 else -1)
                elif abs(dy)>50:app.page_change(1 if dy<0 else -1)
        switch=Path('/tmp/dashboard_ui_switch_request')
        if switch.exists():
            switch.unlink()
            if app.locked:app.switch_stock()
            else:app.confirm('切回原厂屏幕','原厂屏幕密码保持不变。',app.switch_stock)
        if not asleep and not app.settings.get('always_on',True) and app.settings['timeout'] and now-app.last_activity>=app.settings['timeout']:
            app.relock()
            import subprocess
            subprocess.run(['/root/dashboard/screen_sleep.sh','off'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
            asleep=True;was_asleep=True
        app.tick()
        if not asleep:
            image=app.render();pixels=image.tobytes()
            if pixels!=last_frame:hardware.write_frame(image);last_frame=pixels
        time.sleep(.08)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--preview');args=parser.parse_args()
    if args.preview:preview(args.preview)
    else:live()
