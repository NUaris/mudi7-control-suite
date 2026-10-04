"""Preserve chosen backlight and check security before switching the screen."""
import json
from pathlib import Path
import backend

s=backend.pin_settings()
assert s['enabled'] and s['valid'] and not s['native_lockout']
base=Path('/sys/class/backlight/soc:backlight')
maximum=int((base/'max_brightness').read_text())
current=int((base/'brightness').read_text())
if not 0<current<=maximum:
    percent=int(backend.uci('gl_screen.generic.BRIGHTNESS','50'))
    assert 1<=percent<=100
    current=max(1,round(maximum*percent/100))
saved=Path('/root/dashboard/.backlight_saved')
saved.write_text(str(current));saved.chmod(0o600)
print(json.dumps({'screen_preflight':True,'original_pin_enabled':True,'brightness_preserved':True}))
