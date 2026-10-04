"""Render documentation screenshots using synthetic data, never router APIs."""
import argparse
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'screen-custom'), str(ROOT/'screen-upstream')]
import mudi_ui as ui

parser = argparse.ArgumentParser()
parser.add_argument('--font', help='Local CJK TTF/TTC; not copied into the repository')
parser.add_argument('--wallpaper', help='Optional local wallpaper; not copied into the repository')
args = parser.parse_args()
if args.font:
    ui.FONT_PATH = Path(args.font).resolve()
    ui.FONTS.clear()
if args.wallpaper:
    ui.WALLPAPER = Image.open(args.wallpaper).convert('RGB').resize((ui.W,ui.H))
if not ui.FONT_PATH.exists():
    parser.error('Provide --font or run on firmware containing the native CJK font')
out = ROOT/'docs/screenshots/screen'
ui.preview(out)
app = ui.App(ui.demo_store(), {'enabled':True,'valid':True,'pin':'','timeout':60}, preview=True)
app.locked = False
app.page='oc';app.page_number=1;app.render().save(out/'oc-2.png');app.page_number=0
app.page = 'rank';app.rank = 'queried';app.render().save(out/'rank-queried.png')
app.page = 'cellular';app.cell_tab = 'neighbors';app.render().save(out/'cellular-neighbors.png')
app.page = 'connect_prepare';app.render().save(out/'connect-prepare.png')
app.page = 'keyboard';app.target = app.values()['wifi']['rows'][0]
for layer in ['symbols','extra']:
    app.key_layer = layer;app.render().save(out/('keyboard-'+layer+'.png'))
app.key_layer='letters';app.key_caps=True;app.render().save(out/'keyboard-uppercase.png')
app.page='nodes';app.selected_group=app.values()['groups'][0]
app.confirm('切换代理节点','示例节点 B\n现有连接可能中断。',lambda:None)
app.render().save(out/'node-confirm.png');app.dialog=None
app.page = 'repeater';app.confirm('连接 Wi-Fi 中继','示例家庭 Wi-Fi\n将替换当前中继连接，网络可能中断。',lambda:None)
app.render().save(out/'repeater-confirm.png')
app.dialog = None;app.page = 'wifi'
app.ap_detail(app.values()['wifi']['rows'][0]);app.render().save(out/'wifi-detail.png')
app.dialog = None;app.page = 'settings';app.confirm('切回原厂屏幕','当前功能不会卸载，原厂密码保持不变。',lambda:None)
app.render().save(out/'stock-confirm.png')
print('Synthetic screen documentation images rendered:',len(list(out.glob('*.png'))))
