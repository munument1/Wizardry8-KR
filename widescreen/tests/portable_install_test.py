"""Run installer file operations under PowerShell on Linux, with only INI WinAPI simulated.
Native Windows integration remains a separate CI test (install_test.py).
"""
from pathlib import Path
import argparse, os, shutil, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--pwsh',type=Path,required=True);p.add_argument('--original',type=Path,required=True);p.add_argument('--wide',type=Path,required=True);a=p.parse_args()
# The native INI functions are the only platform API used with explicit -GameDir.
shim=r'''using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
public static class Wiz8KrIni {
 public static uint GetPrivateProfileString(string section,string key,string fallback,StringBuilder value,uint size,string path) {
  string current="";string found=fallback;
  foreach(string raw in File.ReadAllLines(path)) {
   string line=raw.Trim();if(line.StartsWith("[")&&line.EndsWith("]"))current=line.Substring(1,line.Length-2);
   int pos=line.IndexOf('=');if(current.Equals(section,StringComparison.OrdinalIgnoreCase)&&pos>=0&&line.Substring(0,pos).Trim().Equals(key,StringComparison.OrdinalIgnoreCase))found=line.Substring(pos+1).Trim();
  }
  value.Append(found);return (uint)found.Length;
 }
 public static bool WritePrivateProfileString(string section,string key,string value,string path) {
  var lines=new List<string>(File.ReadAllLines(path));string current="";int end=-1;bool exists=false;
  for(int i=0;i<lines.Count;i++) {
   string line=lines[i].Trim();if(line.StartsWith("[")&&line.EndsWith("]")) {
    if(current.Equals(section,StringComparison.OrdinalIgnoreCase)&&end<0)end=i;
    current=line.Substring(1,line.Length-2);if(current.Equals(section,StringComparison.OrdinalIgnoreCase))exists=true;
   }
   int pos=line.IndexOf('=');if(current.Equals(section,StringComparison.OrdinalIgnoreCase)&&pos>=0&&line.Substring(0,pos).Trim().Equals(key,StringComparison.OrdinalIgnoreCase)) {
    if(value==null)lines.RemoveAt(i);else lines[i]=key+"="+value;
    File.WriteAllLines(path,lines);return true;
   }
  }
  if(value!=null) {
   if(!exists){lines.Add("["+section+"]");lines.Add(key+"="+value);}
   else lines.Insert(end<0?lines.Count:end,key+"="+value);
  }
  File.WriteAllLines(path,lines);return true;
 }
}'''
with tempfile.TemporaryDirectory(prefix='wiz8-ps-test-') as t:
 t=Path(t);package=t/'package';shutil.copytree(ROOT/'build/package',package)
 script=package/'Install-Korean.ps1';s=script.read_text(encoding='utf-8-sig');begin=s.index("Add-Type @'\n")+len("Add-Type @'\n");end=s.index("\n'@",begin)
 script.write_text(s[:begin]+shim+s[end:],encoding='utf-8-sig')
 wrapper=t/'powershell.exe';wrapper.write_text('#!/bin/sh\nexec "'+str(a.pwsh.resolve())+'" "$@"\n');wrapper.chmod(0o755)
 env=dict(os.environ,PATH=str(t)+os.pathsep+os.environ['PATH'])
 subprocess.run([__import__('sys').executable,str(ROOT/'tests/install_test.py'),str(package),str(a.original),str(a.wide)],env=env,check=True)
print('PASS: installer file operations under PowerShell; native INI API simulated')
