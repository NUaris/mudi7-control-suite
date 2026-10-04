import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import backend as api
import mudi_ui as ui

class ScreenTests(unittest.TestCase):
    def make(self,enabled=True):
        return ui.App(ui.demo_store(),{'enabled':enabled,'valid':True,'pin':'','timeout':60},preview=True)

    def test_render_and_hit_bounds(self):
        app=self.make(False)
        for page in ['home','settings','oc','mode','dns','subscription','agh','rank','wifi','repeater','cellular','port','screen','groups','nodes','keyboard']:
            app.page=page;app.selected_group=app.values()['groups'][0];app.target=app.values()['wifi']['rows'][0]
            im=app.render();self.assertEqual(im.size,(240,320))
            for (x0,y0,x1,y1),fn,label in app.buttons:
                self.assertTrue(0<=x0<x1<=240 and 0<=y0<y1<=320,(page,label))

    def test_locked_no_network_controls(self):
        app=self.make();app.page='port';app.render()
        labels=[b[2] for b in app.buttons]
        self.assertNotIn('WAN',labels);self.assertNotIn('LAN',labels)
        with patch.object(app.store,'run') as run:
            app.action(lambda:1);app.scan('wifi');app.connection({'ssid':'x'});run.assert_not_called()

    def test_idle_relocks_and_clears_credentials(self):
        app=self.make();app.locked=False;app.page='keyboard';app.keys='private-key'
        app.last_activity=0
        with patch.object(ui.time,'monotonic',return_value=100):app.tick()
        self.assertTrue(app.locked);self.assertEqual(app.keys,'');self.assertEqual(app.page,'home')

    def test_pin_cooldown_and_success(self):
        with tempfile.TemporaryDirectory() as d:
            clock=[1000];path=Path(d)/'tries.json'
            guard=api.PinGuard(lambda:{'valid':True,'pin':'1234'},path,lambda:clock[0])
            for _ in range(5):self.assertFalse(guard.check('1111')[0])
            self.assertEqual(guard.remaining(),60);self.assertFalse(guard.check('1234')[0])
            clock[0]+=61;self.assertTrue(guard.check('1234')[0]);self.assertEqual(guard.remaining(),0)
            self.assertNotIn('1234',path.read_text())

    def test_modal_blocks_background(self):
        app=self.make(False);app.page='port';calls=[]
        app.confirm('WAN','将断网',lambda:calls.append(1));app.render()
        self.assertEqual([b[2] for b in app.buttons],['取消','确认'])
        app.tap(172,243);self.assertEqual(calls,[1])

    def test_pin_hittest_unlock(self):
        with tempfile.TemporaryDirectory() as d:
            app=self.make();app.guard=api.PinGuard(lambda:{'valid':True,'pin':'1234'},Path(d)/'tries')
            for digit in '1234':
                app.render();box=next(b[0] for b in app.buttons if b[2]==digit)
                app.tap((box[0]+box[2])//2,(box[1]+box[3])//2)
            self.assertFalse(app.locked);self.assertEqual(app.page,'home')
            app.relock();self.assertTrue(app.locked)

    def test_wifi_password_mask_and_ascii_keyboard(self):
        app=self.make(False);app.page='keyboard';app.target={'ssid':'SSID'};app.keys='private-key'
        for layer in ['letters','symbols','extra']:
            app.key_layer=layer;app.render()
        app.key_press('删除');self.assertEqual(app.keys,'private-ke')
        app.relock();self.assertEqual(app.keys,'')

    def test_port_payload_preserves_vlan_and_mac(self):
        info={'name':'wan','mode':'lan','state':{'vlan_mode':'Standard','pvid':6},'macaddr':{'mode':'default','macaddr':'00:11:22:33:44:55'}}
        wan=api.port_payload('wan',info,{})
        self.assertEqual(wan['macaddr'],info['macaddr'])
        info['mode']='wan';lan=api.port_payload('lan',info,{'vlan_mode':'Standard','pvid':6})
        self.assertEqual(lan['pvid'],6)
        with self.assertRaises(RuntimeError):api.port_payload('lan',info,{})
        with self.assertRaises(ValueError):api.port_payload('evil',info,{})

    def test_rpc_allowlist(self):
        with self.assertRaises(ValueError):api.rpc('system','exec',{'cmd':'foo'})

    def test_current_pin_quoted_decoding(self):
        values={'gl_screen.generic.PASSCODE':'"1234"','gl_screen.generic.ENABLE_PASSCODE':'1','gl_screen.generic.AUTO_LOCK_TIME':'60'}
        with patch.object(api,'uci',lambda k,d='':values.get(k,d)),patch.object(api,'rpc',return_value={'unlock_attempt_exceed_limit':False}):
            result=api.pin_settings();self.assertTrue(result['valid']);self.assertEqual(result['pin'],'1234')

    def test_respects_native_lockout(self):
        with tempfile.TemporaryDirectory() as d:
            guard=api.PinGuard(lambda:{'valid':True,'pin':'1234','native_lockout':True},Path(d)/'tries')
            self.assertFalse(guard.check('1234')[0])

    def test_repeater_duration_is_not_connection_state(self):
        with patch.object(api,'rpc',return_value={'connected':'5d,10h','state_s':'connected','bssid':'00:11:22:33:44:55'}):
            self.assertTrue(api.repeater_status()['is_connected'])

    def test_connection_key_only_on_stdin(self):
        ap={'ssid':'test','bssid':'00:11:22:33:44:55'}
        class Result: returncode=0;stdout=b'{"err_code":0}'
        with patch.object(api,'scan_status',return_value={'rows':[ap]}),patch.object(api,'repeater_status',return_value=dict(ap,is_connected=True)),patch.object(api.subprocess,'run',return_value=Result()) as run:
            api.repeater_connect(ap,'private-pass')
            argv=run.call_args.args[0];self.assertNotIn('private-pass',' '.join(argv))
            self.assertEqual(json_load(run.call_args.kwargs['input'])['key'],'private-pass')

def json_load(v):
    import json
    return json.loads(v)

if __name__=='__main__':unittest.main()
