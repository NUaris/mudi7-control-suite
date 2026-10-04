import os
import pathlib
import sys
from lupa import LuaRuntime

base = pathlib.Path(__file__).parent
lua = LuaRuntime(unpack_returned_tuples=True)
for filename in ['radio-parse.lua', 'radio-scan.lua', 'radio-scan-rpc.lua', 'mudi7-wifi-scan.lua', 'mudi7-cellular-scan.lua']:
    lua.execute('assert(load(...))', (base / filename).read_text(encoding='utf-8'))
parser = lua.execute((base / 'radio-parse.lua').read_text(encoding='utf-8'))
lua.globals().p = parser
lua.execute('''
assert(p.clean('a\\nb')=='a b')
assert(p.clean('中文SSID')=='中文SSID')
local rows=p.wifi({survey={
 {ssid='<script>"x"</script>', bssid='AA:BB:CC:DD:EE:FF', channel=149, freq=5745, signal=-50,rsn={}},
 {ssid='duplicate', bssid='aa:bb:cc:dd:ee:ff', channel=149, freq=5745, signal=-70},
 {ssid='',bssid='AA:BB:CC:DD:EE:00',channel=1,freq=2412,signal=-40,rsn={cipher='CCMP'}},
 {ssid='six',bssid='AA:BB:CC:DD:EE:01',channel=5,freq=5975,signal=-32768},
 {ssid='bad',bssid='bad',channel=1,freq=2412,signal=-40}}})
assert(#rows==3 and rows[1].signal==-40 and rows[2].ssid=='<script>"x"</script>')
assert(rows[2].security=='开放/未知' and rows[1].security=='WPA2/3 (RSN)' and rows[3].band=='6 GHz' and rows[3].signal==nil)
local lte=p.cells('+QENG: "servingcell","NOCONN","LTE","FDD",460,00,ABC,120,1650,3,5,5,AB,-95,-12,-65,18,1,2,3', '+QENG: "neighbourcell intra","LTE",1650,121,-14,-100,-70,10', '+COPS: 0,0,"中国移动",7')
assert(lte.state=='NOCONN' and lte.operator=='中国移动' and #lte.serving==1 and lte.serving[1].channel==1650 and lte.serving[1].rsrp==-95 and lte.serving[1].sinr==18)
assert(#lte.neighbors==1 and lte.neighbors[1].rsrq==-14 and lte.neighbors[1].rsrp==-100)
assert(lte.serving[1].cell_id==nil and lte.serving[1].tac==nil)
local sa=p.cells('+QENG: "servingcell","CONNECT","NR5G-SA","TDD",460,00,ABC,123,AB,633984,78,100,-98,-11,20,30,1','', '')
assert(sa.serving[1].channel==633984 and sa.serving[1].band==78 and sa.serving[1].rsrp==-98)
local nsa=p.cells('+QENG: "servingcell","NOCONN"\\n+QENG: "LTE","FDD",460,00,ABC,12,1650,3,5,5,AB,-95,-12,-65,18\\n+QENG: "NR5G-NSA",460,00,123,-98,20,-11,633984,78,100,30','+QENG: "neighbourcell intra","NR5G",1,2,3', '')
assert(#nsa.serving==2 and nsa.serving[2].rsrp==-98 and nsa.serving[2].rsrq==-11 and nsa.serving[2].sinr==20 and #nsa.neighbors==0 and #nsa.neighbor_note>0)
local unavailable=p.cells('+QENG: "servingcell","SEARCH"','', '')
assert(#unavailable.serving==0 and unavailable.state=='SEARCH')
''')
print('Lua syntax, UTF-8, Wi-Fi dedup/security, LTE/SA/NSA/neighbor/sentinel/privacy tests passed')
