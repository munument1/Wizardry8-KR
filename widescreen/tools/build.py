#!/usr/bin/env python3
"""Build only the MIT loader + our Korean adapter; never build/copy wiz8hy.dll."""
from pathlib import Path
import argparse, hashlib, json, re, shutil, struct, subprocess
ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = '20d0faf87f037f0327baee254b020c060f0d5e2d'
MINHOOK = '8af6b4acae5a9388fd742b56fa79ece89d96f823'
MAP_SHA = '255dda924f50f26fe7502c14507f0332eb5b2a1e545bf87674db4fd0d187efa5'

def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--toolchain', type=Path, required=True, help='llvm-mingw bin folder')
    p.add_argument('--upstream', type=Path, help='existing pinned checkout (otherwise cloned into build/)')
    a = p.parse_args()
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    upstream = (a.upstream or build / 'upstream').resolve()
    if not upstream.exists():
        run('git', 'clone', 'https://github.com/abr17/wiz8-widescreen.git', upstream)
        run('git', '-C', upstream, 'checkout', '--detach', UPSTREAM)
    actual = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != UPSTREAM:
        raise SystemExit(f'Use upstream commit {UPSTREAM}; got {actual}')
    if subprocess.check_output(['git', '-C', str(upstream), 'status', '--porcelain', '--untracked-files=no'], text=True).strip():
        raise SystemExit('Upstream checkout must be clean')
    run('git', '-C', upstream, 'submodule', 'update', '--init', 'third_party/minhook', 'drivers/srdd_d3d11')
    mh = upstream / 'third_party/minhook'
    if subprocess.check_output(['git', '-C', str(mh), 'rev-parse', 'HEAD'], text=True).strip() != MINHOOK:
        raise SystemExit('Unexpected MinHook revision')
    stage = build / 'loader'
    for folder in ('include', 'sdk'):
        shutil.copytree(upstream / 'drivers/srdd_d3d11' / folder, stage / 'drivers/srdd_d3d11' / folder, dirs_exist_ok=True)
    shutil.copytree(upstream / 'src', stage / 'src', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'src', stage / 'src', dirs_exist_ok=True)
    data = (ROOT / 'data/korean-map.bin').read_bytes()
    if hashlib.sha256(data).hexdigest() != MAP_SHA or len(data) != 3299 * 2:
        raise SystemExit('Korean map integrity mismatch')
    chars = struct.unpack('<3299H', data)
    translations = json.loads((ROOT / 'data/options-ko.json').read_text(encoding='utf-8'))
    h = ['#pragma once', '#include <stdint.h>', 'static const uint16_t kKoreanMap[] = {']
    h += [','.join(f'0x{x:04x}' for x in chars[i:i+16])+',' for i in range(0, len(chars), 16)]
    h += ['};', 'struct OptionText { const wchar_t* english; const wchar_t* korean; };',
          'static const OptionText kOptionText[] = {']
    for en, ko in translations.items():
        if len(ko) > len(en) or any(ord(c) not in chars for c in ko):
            raise SystemExit(f'Option cannot be rendered: {en}')
        def wide(s): return 'L"' + ''.join(f'\\u{ord(c):04x}' if ord(c)>127 else c for c in s) + '"'
        h.append('{'+wide(en)+','+wide(ko)+'},')
    h += ['};']
    (stage / 'src/korean_data.h').write_text('\n'.join(h)+'\n', encoding='ascii')
    hook = stage / 'src/hooks_hybrid.cpp'
    s = hook.read_text()
    old = '    g_hybridHooks = install ? install(g_runtime.gameDir) : -1;'
    new = '''    KoreanPreflight(g_runtime.gameDir);
    g_hybridHooks = install ? install(g_runtime.gameDir) : -1;
    if (g_hybridHooks < 290) {
        MessageBoxA(nullptr, "Widescreen engine installation failed.", "Wizardry 8 Korean", MB_OK | MB_ICONERROR);
        ExitProcess(1);
    }
    KoreanInstall(dll);'''
    if s.count(old) != 1: raise SystemExit('Upstream hook structure changed')
    hook.write_text('#include "korean.h"\n'+s.replace(old,new))
    # Preserve the entire upstream loader (Wine/Bink startup, diagnostics and filename hooks).
    cc = a.toolchain / ('i686-w64-mingw32-clang.exe' if __import__('os').name=='nt' else 'i686-w64-mingw32-clang')
    cxx = a.toolchain / ('i686-w64-mingw32-clang++.exe' if __import__('os').name=='nt' else 'i686-w64-mingw32-clang++')
    objects=[]
    for name in ['buffer.c', 'hook.c', 'trampoline.c', 'hde/hde32.c']:
        obj = stage / (Path(name).stem+'.o')
        run(cc, '-O2', '-c', mh/'src'/name, '-I'+str(mh/'include'), '-o', obj)
        objects.append(obj)
    sources = sorted((stage/'src').glob('*.cpp'))
    out = build / 'version.dll'
    run(cxx, '-shared', '-O2', '-std=c++17', '-Wall', '-Wextra', '-Wno-unused-parameter',
        '-DWIN32_LEAN_AND_MEAN', '-DNOMINMAX', '-DWIZ8WS_VERSION="1.0.3+KR0.3.0-test1"',
        '-I'+str(mh/'include'), *sources, *objects, stage/'src/version.def',
        '-static', '-static-libgcc', '-s', '-lbcrypt', '-ladvapi32', '-o', out)
    shutil.copyfile(upstream/'LICENSE', build/'Widescreen-MIT-LICENSE.txt')
    shutil.copyfile(mh/'LICENSE.txt', build/'MinHook-LICENSE.txt')
    shutil.copyfile(upstream/'drivers/srdd_d3d11/LICENSE', build/'D3D11-SDK-MIT-LICENSE.txt')
    print('Built',out,hashlib.sha256(out.read_bytes()).hexdigest())
if __name__ == '__main__': main()
