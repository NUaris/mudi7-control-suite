"""Deliberately crash ONLY our own UI, verifying the three-strikes stock fallback.
No router, Wi-Fi, cellular, DNS, or proxy configuration is changed.
"""
import os
import signal
import time
from pathlib import Path

def pids(script):
    result=[]
    for entry in Path('/proc').iterdir():
        if entry.name.isdigit():
            try:
                args=(entry/'cmdline').read_bytes().split(b'\0')
                if len(args)>1 and args[0] in (b'python3',b'/usr/bin/python3') and args[1]==script.encode():
                    result.append(int(entry.name))
            except OSError:pass
    return result

for attempt in range(1,4):
    targets=pids('/root/dashboard/main.py');assert len(targets)==1
    previous=targets[0];os.kill(previous,signal.SIGKILL)
    until=time.monotonic()+16
    while time.monotonic()<until:
        if attempt<3 and any(pid!=previous for pid in pids('/root/dashboard/main.py')):break
        if attempt==3 and not Path('/etc/rc.d/S95citydash').exists():break
        time.sleep(.1)
    else:raise RuntimeError('Screen recovery deadline exceeded')
    print('Own UI forced-crash recovery checkpoint',attempt,flush=True)
assert not pids('/root/dashboard/main.py')
assert Path('/etc/rc.d/S99gl_screen').exists() or any(Path('/etc/rc.d').glob('S*gl_screen'))
print('Three-strikes fallback restored factory boot selection',flush=True)
