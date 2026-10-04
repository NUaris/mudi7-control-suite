"""Check tracked publication files without printing potential secret values."""
import re
import subprocess
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parents[1]
raw=subprocess.check_output(['git','ls-files','-z'],cwd=root)
files=[root/name.decode('utf-8') for name in raw.split(b'\0') if name]
if not files:raise SystemExit('Stage the intended publication files before auditing')
issues=[]
rules={
    'GitHub credential':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'API credential':re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b'),
    'Subscription client URL':re.compile(r'https?://[^\s\"\'<>]+/api/v1/client/[A-Za-z0-9_-]{16,}'),
    'Literal Basic authorization':re.compile(r'Basic\s+[A-Za-z0-9+/]{24,}={0,2}'),
    'Private key':re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
    'Bcrypt credential hash':re.compile(r'\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}'),
}
for file in files:
    relative=file.relative_to(root).as_posix()
    if file.suffix.lower() in {'.ttf','.ttc','.pem','.key','.tgz','.pyc'} or relative.endswith('.tar.gz') or '.authorization' in relative:
        issues.append((relative,'forbidden publication file type'))
    if relative.startswith(('private/','backups/')):issues.append((relative,'private directory'))
    if file.suffix.lower()=='.png':
        with Image.open(file) as im:
            if im.info.get('exif'):issues.append((relative,'unexpected EXIF'))
        continue
    try:content=file.read_text(encoding='utf-8')
    except UnicodeDecodeError:issues.append((relative,'unreviewed binary'));continue
    for label,pattern in rules.items():
        if pattern.search(content):issues.append((relative,label))
    if file.suffix.lower()=='.md':
        targets=re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)',content)+re.findall(r'(?:src|href)="([^"]+)"',content)
        for target in targets:
            if target.startswith(('#','http:','https:','mailto:')):continue
            path=target.split('#')[0]
            if path and not (file.parent/path).exists():issues.append((relative,'broken local link: '+path))
for relative,label in issues:print(relative+': '+label)
if issues:raise SystemExit('Public-file audit failed; no secret values printed')
print('Public-file audit passed:',len(files),'tracked files; no forbidden file types, matched credential forms, EXIF or broken documentation links')
print('This pattern check is not a comprehensive security audit. Synthetic screenshot provenance was reviewed separately.')
