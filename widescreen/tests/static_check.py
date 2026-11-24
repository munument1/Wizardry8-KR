from pathlib import Path
import argparse, hashlib, json, struct, zipfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--wide',type=Path,required=True);a=p.parse_args()
chars=struct.unpack('<3299H',(ROOT/'data/korean-map.bin').read_bytes())
strings=json.loads((ROOT/'data/options-ko.json').read_text())
with zipfile.ZipFile(a.wide) as z:
    name=next(n for n in z.namelist() if n.endswith('wiz8hy.dll'))
    dll=z.read(name)
    for en,ko in strings.items():
        needle=(en+'\0').encode('utf-16le')
        assert dll.count(needle)==1,en
        assert dll.find(needle)%2==0,en
        assert len(ko)<=len(en),en
        assert all(ord(c) in chars for c in ko),en
    hooks=z.read(next(n for n in z.namelist() if n.endswith('wiz8hy_hooks.txt'))).decode()
    addresses=[int(line.split()[0],16) for line in hooks.splitlines() if line.strip() and not line.startswith('#')]
    assert len(addresses)>=290
    assert not {0x407ec0,0x55a140,0x55a1e3,0x55a3d4}&set(addresses)
print('PASS: upstream strings, font coverage and hook conflicts',a.wide)
