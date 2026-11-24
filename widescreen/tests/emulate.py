"""Execute compiled 32-bit adapter instructions with simulated Win32 calls.
Requires unicorn and pefile. This is not a game/Windows/CRT integration test.
"""
from pathlib import Path
import argparse, struct
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EIP,UC_X86_REG_ESP,UC_X86_REG_EAX
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('hybrid',type=Path);p.add_argument('--negative',choices=['bad-site','missing-string']);a=p.parse_args()
u=Uc(UC_ARCH_X86,UC_MODE_32)
def dword(at):return struct.unpack('<I',u.mem_read(at,4))[0]
def asciiz(at):
    out=bytearray()
    while (b:=u.mem_read(at,1))!=b'\0':out+=b;at+=1
    return bytes(out)
def wide_len(at):
    n=0
    while u.mem_read(at+n*2,2)!=b'\0\0':n+=1
    return n
imports={};nextstub=0x70000000
u.mem_map(nextstub,0x10000);u.mem_map(0x71000000,0x200000);u.mem_map(0x72000000,0x10000)
u.mem_map(0x400000,0x200000)
for at,b in [(0x407ec0,bytes.fromhex('56578b3da0b15e006a08ffd7')),(0x55a1e3,bytes.fromhex('25ffff0000')),(0x55a3d4,bytes.fromhex('81e2ffff0000'))]:u.mem_write(at,b)
def load(path,resolve=False):
    global nextstub
    pe=pefile.PE(str(path));base=pe.OPTIONAL_HEADER.ImageBase
    u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095)
    u.mem_write(base,pe.get_memory_mapped_image())
    if resolve:
        for dll in pe.DIRECTORY_ENTRY_IMPORT:
            for imp in dll.imports:
                name=imp.name.decode() if imp.name else str(imp.ordinal)
                addr=nextstub;nextstub+=16;imports[addr]=name
                u.mem_write(imp.address,struct.pack('<I',addr));u.mem_write(addr,b'\xc3')
    return pe,base
adapter,base=load(ROOT/'build/emulator-test.dll',True)
hybrid,hbase=load(a.hybrid)
exports={e.name.decode():base+e.address for e in adapter.DIRECTORY_ENTRY_EXPORT.symbols}
exitcode=None
# APIs touched by Install/Create. All other imports are errors if executed.
stdcall={'VirtualProtect':4,'FlushInstructionCache':3,'GetCurrentProcess':0,'ExitProcess':1,'OutputDebugStringA':1}
def hook(uc,addr,size,_):
    global exitcode
    if addr==0x72000000:uc.emu_stop();return
    if addr not in imports:return
    name=imports[addr];sp=uc.reg_read(UC_X86_REG_ESP);ret=dword(sp)
    arg=lambda n:dword(sp+4+4*n)
    result=0
    if name=='VirtualProtect':u.mem_write(arg(3),struct.pack('<I',0x20));result=1
    elif name=='FlushInstructionCache':result=1
    elif name=='GetCurrentProcess':result=0xffffffff
    elif name=='ExitProcess':exitcode=arg(0);uc.emu_stop();return
    elif name=='OutputDebugStringA':print('Adapter failure:',asciiz(arg(0)).decode());result=0
    elif name=='fopen':result=0 # skip log file I/O
    elif name=='wcslen':result=wide_len(arg(0))
    elif name=='strlen':result=len(asciiz(arg(0)))
    elif name=='strcmp':result=0 if asciiz(arg(0))==asciiz(arg(1)) else 1
    elif name=='memcmp':result=0 if u.mem_read(arg(0),arg(2))==u.mem_read(arg(1),arg(2)) else 1
    elif name in ('memcpy','memmove'):u.mem_write(arg(0),bytes(u.mem_read(arg(1),arg(2))));result=arg(0)
    elif name=='memset':u.mem_write(arg(0),bytes([arg(1)&255])*arg(2));result=arg(0)
    elif name in ('_snprintf','snprintf'):
        # Only Note's ASCII log path is formatted on these tested paths.
        u.mem_write(arg(0),b'wiz8kr.log\0');result=10
    elif name=='__iob_func':result=0x72001000
    elif name in ('fprintf','vfprintf'):result=0
    else:raise AssertionError('unexpected executed import '+name)
    uc.reg_write(UC_X86_REG_EAX,result&0xffffffff)
    uc.reg_write(UC_X86_REG_ESP,sp+4+4*stdcall.get(name,0));uc.reg_write(UC_X86_REG_EIP,ret)
u.hook_add(UC_HOOK_CODE,hook,begin=0x70000000,end=0x70010000)
u.hook_add(UC_HOOK_CODE,hook,begin=0x72000000,end=0x72000000)
def call(addr,*args):
    stack=0x711ff000
    u.mem_write(stack,struct.pack('<'+'I'*(1+len(args)),0x72000000,*args))
    u.reg_write(UC_X86_REG_ESP,stack)
    u.emu_start(addr,0,count=20000000)
    if u.reg_read(UC_X86_REG_EIP)!=0x72000000 and exitcode is None:raise AssertionError('instruction budget exceeded')
    return u.reg_read(UC_X86_REG_EAX)
if a.negative=='bad-site':u.mem_write(0x55a1e3,b'\x90')
if a.negative=='missing-string':
    needle=('View distance\0').encode('utf-16le');at=bytes(u.mem_read(hbase,hybrid.OPTIONAL_HEADER.SizeOfImage)).index(needle);u.mem_write(hbase+at,b'X\0')
before=bytes(u.mem_read(0x400000,0x200000))
call(exports['TestInstall'],hbase)
if a.negative:
    assert exitcode==1,exitcode
    assert bytes(u.mem_read(0x400000,0x200000))==before,'failure must not write game memory'
    print('PASS: refused',a.negative,'before game-memory edits')
else:
    assert exitcode is None
    assert u.mem_read(0x407ec0,1)==b'\xe9'
    assert u.mem_read(0x55a1e3,5)==bytes.fromhex('0fb7c001c0')
    assert u.mem_read(0x55a3d4,6)==bytes.fromhex('0fb7d201d290')
    table=call(0x407ec0);assert struct.unpack('<H',u.mem_read(table,2))[0]==3299
    assert bytes(u.mem_read(dword(table+4),6598))==(ROOT/'data/korean-map.bin').read_bytes()
    assert call(exports['TestLocaleCode'])==949
    import json
    image=bytes(u.mem_read(hbase,hybrid.OPTIONAL_HEADER.SizeOfImage))
    for ko in json.loads((ROOT/'data/options-ko.json').read_text()).values():assert (ko+'\0').encode('utf-16le') in image
    print('PASS: compiled x86 adapter; 3299-slot allocation/map, CP949 locale request, NPC edits, all 16 translations')
