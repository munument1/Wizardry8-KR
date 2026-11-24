"""Recover the known retail EXE only in a private temporary test fixture.
Never package, publish, or upload this fixture or any executable from it.
"""
from pathlib import Path
import argparse, hashlib, struct, zipfile
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
with zipfile.ZipFile(a.source) as z:b=bytearray(z.read('Wiz8_124_Korean.exe'))
pe=struct.unpack_from('<I',b,60)[0];o=pe+24;st=o+struct.unpack_from('<H',b,pe+20)[0]
b[0x7ec0:0x7ec5]=bytes.fromhex('56578b3da0');b[0x15a1e3:0x15a1e8]=bytes.fromhex('25ffff0000');b[0x15a3d4:0x15a3da]=bytes.fromhex('81e2ffff0000')
struct.pack_into('<H',b,pe+6,7);struct.pack_into('<I',b,o+56,0x409261);b[st+7*40:st+8*40]=bytes(40);b=b[:3580513]
assert hashlib.sha256(b).hexdigest()=='18a74ff61c65b8a2d4cfa11ffce82ad7fef022a94eaf0c2f217e479e981420d2'
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(b)
