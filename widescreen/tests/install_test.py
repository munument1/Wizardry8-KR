"""Windows integration tests: hashes, rollback/removal, Bink proxy and preserved settings."""
from pathlib import Path
import hashlib, os, shutil, subprocess, sys, tempfile
package=Path(sys.argv[1]).resolve(); original=Path(sys.argv[2]).resolve(); wide=Path(sys.argv[3]).resolve()

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def invoke(root,game,*args,ok=True):
    env=dict(os.environ)
    if os.name=='nt': env.pop('PSModulePath',None) # pwsh 7 module paths are not Windows PowerShell 5 modules
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
        '-File',str(root/'Install-Korean.ps1'),'-GameDir',str(game),*args],capture_output=True,env=env)
    if (p.returncode==0)!=ok:raise AssertionError((p.returncode,p.stdout.decode(errors='replace'),p.stderr.decode(errors='replace')))
    return p
with tempfile.TemporaryDirectory(prefix='wiz8kr-') as temp:
    temp=Path(temp);root=temp/'package';shutil.copytree(package,root)
    game=temp/'한글 경로 with spaces';shutil.copytree(wide,game)
    shutil.copyfile(original,game/'Wiz8.exe')
    (game/'Data/Strings').mkdir(parents=True,exist_ok=True)
    (game/'Data/Strings/STRINGDATA.DAT').write_bytes(b'pre-existing translation')
    (game/'Saves').mkdir();(game/'Saves/untouched.sav').write_bytes(b'save data')
    (game/'wiz8wide.ini').write_text('[Display]\nWidth=1920\n[Text]\nCyrillic=auto\n',encoding='ascii')
    # A Wine-created install starts via a copy of the official version proxy.
    shutil.copyfile(game/'version.dll',game/'binkw32.dll')
    exe_hash=sha(game/'Wiz8.exe');hy_hash=sha(game/'wiz8hy.dll');version_hash=sha(game/'version.dll')
    invoke(root,game,'-VerifyOnly')
    assert not (game/'Wizardry8_KR_Wide.backup').exists()
    # Unknown executable, mismatched hooks and foreign loader all refuse before mutations.
    for filename in ['Wiz8.exe','wiz8hy_hooks.txt','version.dll']:
        path=game/filename;old=path.read_bytes();path.write_bytes(b'unsupported')
        invoke(root,game,ok=False);assert not (game/'Wizardry8_KR_Wide.backup').exists()
        path.write_bytes(old)
    # Payload integrity check.
    path=root/'payload/Data/Strings/STRINGDATA.DAT';old=path.read_bytes();path.write_bytes(b'corrupt')
    invoke(root,game,ok=False);assert not (game/'Wizardry8_KR_Wide.backup').exists();path.write_bytes(old)
    # A directory at a target filename must be rejected without changing anything.
    blocked=game/'Data/FONTS/dialog_font.sti';blocked.mkdir(parents=True)
    invoke(root,game,ok=False);assert not (game/'Wizardry8_KR_Wide.backup').exists();blocked.rmdir()
    invoke(root,game)
    assert sha(game/'Wiz8.exe')==exe_hash and sha(game/'wiz8hy.dll')==hy_hash
    assert sha(game/'version.dll')==sha(root/'payload/version.dll')==sha(game/'binkw32.dll')
    assert 'Cyrillic=0' in (game/'wiz8wide.ini').read_text()
    assert (game/'Data/Strings/STRINGDATA.DAT').read_bytes()==old
    assert (game/'Saves/untouched.sav').read_bytes()==b'save data'
    invoke(root,game,ok=False) # no accidental overwrite of first backup
    # User changes to unrelated INI settings survive uninstall.
    with (game/'wiz8wide.ini').open('a') as f:f.write('\n[User]\nKeep=1\n')
    path=game/'Data/Strings/STRINGDATA.DAT';installed=path.read_bytes();path.write_bytes(b'edited after install')
    invoke(root,game,'-Uninstall',ok=False);assert path.read_bytes()==b'edited after install'
    path.write_bytes(installed)
    invoke(root,game,'-Uninstall','-VerifyOnly')
    invoke(root,game,'-Uninstall')
    assert sha(game/'version.dll')==version_hash==sha(game/'binkw32.dll')
    assert (game/'Data/Strings/STRINGDATA.DAT').read_bytes()==b'pre-existing translation'
    ini=(game/'wiz8wide.ini').read_text();assert 'Cyrillic=auto' in ini and 'Keep=1' in ini
    assert sha(game/'Wiz8.exe')==exe_hash and sha(game/'wiz8hy.dll')==hy_hash
    assert (game/'Saves/untouched.sav').read_bytes()==b'save data'
print('PASS: Windows install/verify/rejection/uninstall, CP949 paths, Bink proxy, existing data, INI and saves')
