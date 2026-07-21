from pathlib import Path
import hashlib
root=Path(__file__).resolve().parents[1]
excluded={'CHECKSUMS.sha256'}
files=[]
for p in root.rglob('*'):
    if p.is_file() and p.name not in excluded and '__pycache__' not in p.parts and not p.suffix=='.pyc': files.append(p)
lines=[]
for p in sorted(files,key=lambda x:x.relative_to(root).as_posix()):
    h=hashlib.sha256(p.read_bytes()).hexdigest(); lines.append(f"{h}  {p.relative_to(root).as_posix()}")
(root/'CHECKSUMS.sha256').write_text('\n'.join(lines)+'\n')
print({'status':'PASS','files':len(lines)})
