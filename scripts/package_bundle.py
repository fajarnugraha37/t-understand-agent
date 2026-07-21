from pathlib import Path
import argparse, zipfile
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(); p.add_argument('--output',default=str(root.parent/'t-understand-v1.0.3-capability-documentation-bundle.zip')); args=p.parse_args()
out=Path(args.output).resolve(); files=[]
for f in root.rglob('*'):
    if not f.is_file() or '__pycache__' in f.parts or f.suffix=='.pyc': continue
    if f.resolve()==out: continue
    files.append(f)
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for f in sorted(files,key=lambda x:x.relative_to(root).as_posix()):
        arc=Path(root.name)/f.relative_to(root)
        info=zipfile.ZipInfo(arc.as_posix(),date_time=(1980,1,1,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=(0o100755 if f.stat().st_mode & 0o111 else 0o100644) << 16
        info.create_system=3
        z.writestr(info,f.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
print({'status':'PASS','output':str(out),'files':len(files),'bytes':out.stat().st_size})
