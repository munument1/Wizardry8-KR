#!/usr/bin/env python3
"""Assemble Korean overlay, excluding game EXEs and all non-MIT widescreen components."""
from pathlib import Path
import argparse, hashlib, json, shutil, struct, zipfile
ROOT = Path(__file__).resolve().parents[1]
KR_SOURCE_SHA = '1e4e98ab90aaf0f17adcd56ca863a8ebfc0cd08a6537017edd39c3d17afab411'

def main():
    p=argparse.ArgumentParser();p.add_argument('--korean-zip',type=Path,required=True);a=p.parse_args()
    if hashlib.sha256(a.korean_zip.read_bytes()).hexdigest() != KR_SOURCE_SHA:
        raise SystemExit('Use the pinned 1.24 v0.2.9-test2 Korean archive')
    out=ROOT/'build/package'
    if out.exists(): shutil.rmtree(out)
    payload=out/'payload';payload.mkdir(parents=True)
    with zipfile.ZipFile(a.korean_zip) as z:
        assert z.testzip() is None
        for name in z.namelist():
            if not name.startswith(('Data/', 'licenses/')) or name.endswith('/'): continue
            assert '..' not in Path(name).parts
            target=payload/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
    shutil.copyfile(ROOT/'build/version.dll',payload/'version.dll')
    shutil.copyfile(ROOT/'data/Pretendard-OFL.txt',payload/'licenses/Pretendard-OFL.txt')
    for name in ('Install-Korean.ps1','install.cmd','uninstall.cmd'):
        shutil.copyfile(ROOT/name,out/name)
    shutil.copyfile(ROOT/'README.md',out/'설치안내.md')
    (out/'licenses').mkdir()
    for name in ('Widescreen-MIT-LICENSE.txt','MinHook-LICENSE.txt','D3D11-SDK-MIT-LICENSE.txt'):
        shutil.copyfile(ROOT/'build'/name,out/'licenses'/name)
    shutil.copyfile(ROOT/'LICENSE',out/'licenses/Korean-adapter-MIT-LICENSE.txt')
    files=[]
    for f in sorted(payload.rglob('*')):
        if f.is_file(): files.append(dict(path=f.relative_to(payload).as_posix(),sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
    (out/'payload.json').write_text(json.dumps(dict(version='0.3.0-test1',files=files),indent=2)+'\n')
    # Keep the complete adapter/build/installer sources with the test deliverable.
    # All game binaries and upstream widescreen binaries remain excluded.
    for source in sorted(ROOT.rglob('*')):
        relative=source.relative_to(ROOT)
        if not source.is_file() or any(part in {'build','__pycache__'} for part in relative.parts): continue
        destination=out/'source/widescreen'/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination)

    archive=ROOT/'build/위저드리8_1.24_와이드호환_한글패치_v0.3.0-test1.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file(): z.write(f,f.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any(n.lower().endswith('.exe') or Path(n).name.lower() in {'wiz8hy.dll','srdd_d3d11.dll','wiz8hy_hooks.txt'} for n in z.namelist())
    print(archive)
    print(hashlib.sha256(archive.read_bytes()).hexdigest())
if __name__=='__main__':main()
