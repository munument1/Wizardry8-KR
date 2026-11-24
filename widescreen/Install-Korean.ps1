param(
    [string]$GameDir,
    [switch]$Uninstall,
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class Wiz8KrIni {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool WritePrivateProfileString(string section, string key, string value, string path);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode)]
    public static extern uint GetPrivateProfileString(string section, string key, string fallback, StringBuilder value, uint size, string path);
}
'@
function Hash([string]$Path) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    $stream = [System.IO.File]::OpenRead($Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}
function IniValue([string]$Path) {
    $value = New-Object System.Text.StringBuilder 128
    [void][Wiz8KrIni]::GetPrivateProfileString('Text', 'Cyrillic', '__absent__', $value, 128, $Path)
    return $value.ToString()
}
function SetIni([string]$Path, $Value) {
    if (![Wiz8KrIni]::WritePrivateProfileString('Text', 'Cyrillic', $Value, $Path)) {
        throw 'wiz8wide.ini의 Cyrillic 설정을 변경하지 못했습니다.'
    }
}
function Restore($State, [string]$Backup, [string]$Target) {
    foreach ($entry in $State.files) {
        $dest = Join-Path $Target $entry.path
        if ($entry.original) {
            Copy-Item -LiteralPath (Join-Path $Backup ('originals/' + $entry.path)) -Destination $dest -Force
        } elseif (Test-Path -LiteralPath $dest) {
            Remove-Item -LiteralPath $dest -Force
        }
    }
    $old = if ($State.cyrillic -eq '__absent__') { $null } else { [string]$State.cyrillic }
    SetIni (Join-Path $Target 'wiz8wide.ini') $old
}
try {
    if (!$GameDir) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = '와이드 패치 1.0.3을 설치한 Wizardry 8 폴더를 선택하세요.'
        if ($dialog.ShowDialog() -ne 'OK') { exit 0 }
        $GameDir = $dialog.SelectedPath
    }
    $GameDir = (Resolve-Path -LiteralPath $GameDir).Path
    if (!(Test-Path -LiteralPath (Join-Path $GameDir 'Wiz8.exe') -PathType Leaf)) {
        throw 'Wiz8.exe가 있는 게임 폴더를 선택하세요.'
    }
    if (Get-Process -Name 'Wiz8', 'Wiz8_124_Korean', 'Wiz8_v128', 'Wiz8WideSetup' -ErrorAction SilentlyContinue) {
        throw '게임과 와이드 패치 설치기를 종료한 뒤 다시 실행하세요.'
    }
    $backup = Join-Path $GameDir 'Wizardry8_KR_Wide.backup'
    $statePath = Join-Path $backup 'state.json'
    if ($Uninstall) {
        if (!(Test-Path -LiteralPath $statePath)) { throw '이 호환판의 설치 기록이 없습니다.' }
        $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($entry in $state.files) {
            # Also permits an interrupted install whose target still has the old bytes.
            $current = Hash (Join-Path $GameDir $entry.path)
            if ($current -and $current -ne $entry.installed -and $current -ne $entry.original) {
                throw ('설치 후 변경된 파일이 있어 제거를 중단합니다: ' + $entry.path)
            }
            if ($entry.original -and (Hash (Join-Path $backup ('originals/' + $entry.path))) -ne $entry.original) {
                throw ('백업이 손상되었습니다: ' + $entry.path)
            }
        }
        if ($VerifyOnly) { Write-Host '제거 전 검증 통과'; exit 0 }
        Restore $state $backup $GameDir
        # Keep the backup for manual recovery; move the receipt instead of deleting it.
        Move-Item -LiteralPath $statePath -Destination (Join-Path $backup 'uninstalled.json') -Force
        Write-Host '한글 와이드 호환판을 제거하고 설치 전 파일을 복원했습니다.'
        exit 0
    }
    if (Test-Path -LiteralPath $backup) {
        throw '백업 폴더가 이미 있습니다. 설치된 호환판을 제거한 뒤 백업 폴더를 다른 곳에 보관하고 다시 설치하세요.'
    }
    if ((Hash (Join-Path $GameDir 'Wiz8.exe')) -ne '18a74ff61c65b8a2d4cfa11ffce82ad7fef022a94eaf0c2f217e479e981420d2') {
        throw '지원하는 순정 GOG/Steam 1.24 실행 파일이 아닙니다. 게임 파일 검사로 Wiz8.exe를 복원하세요.'
    }
    $hy = Hash (Join-Path $GameDir 'wiz8hy.dll')
    $hooks = Hash (Join-Path $GameDir 'wiz8hy_hooks.txt')
    $base = $hy -eq '015b9f1b17983a005d84c9dd351d80a8f42409245577c28f5a6a1b60c19f399b' -and
            $hooks -eq '608aa4d17f9860036a6c1d985661fcbf4573fa4af908a9b2d6f092fda8619237'
    $hotfix = $hy -eq '54a0d9426e8b59fa1c69cecc7db190ba495ba5b02c0389e9ab526c880b1b826f' -and
              $hooks -eq 'e0383a1b418e69c99b3a7432e0fbb571c8633ab662e60b22990863137a45fe69'
    if (!$base -and !$hotfix) { throw '와이드 패치 1.0.3 또는 1.0.3 hotfix1과 일치하는 DLL/훅 파일을 먼저 설치하세요.' }
    $officialLoader = 'e5e94ebf38ff79a22f7630b766ea3307911850bf7c3a6c263c0a9af4be65e4ee'
    if ((Hash (Join-Path $GameDir 'version.dll')) -ne $officialLoader) {
        throw '공식 와이드 패치 로더가 아닙니다. 다른 version.dll 모드와 함께 설치할 수 없습니다.'
    }
    $payload = Join-Path $PSScriptRoot 'payload'
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'payload.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $entries = @()
    foreach ($item in $manifest.files) {
        $relative = [string]$item.path
        if ($relative.Contains('..') -or $relative.Contains(':') -or $relative.StartsWith('/') -or
            $relative.StartsWith('\') -or $relative -notmatch '^(Data/|licenses/|version\.dll$)') {
            throw ('허용하지 않는 배포 경로: ' + $relative)
        }
        if ((Hash (Join-Path $payload $relative)) -ne $item.sha256) { throw ('배포 파일이 손상되었습니다: ' + $relative) }
        $destination = Join-Path $GameDir $relative
        if ((Test-Path -LiteralPath $destination) -and !(Test-Path -LiteralPath $destination -PathType Leaf)) {
            throw ('파일 위치에 폴더가 있습니다: ' + $relative)
        }
        $parent = Split-Path -Parent $destination
        while ($parent -and $parent -ne $GameDir) {
            if (Test-Path -LiteralPath $parent -PathType Leaf) { throw ('상위 폴더 위치에 파일이 있습니다: ' + $relative) }
            $parent = Split-Path -Parent $parent
        }
        $entries += [pscustomobject]@{ path=$relative; source=$relative; original=(Hash $destination); installed=$item.sha256 }
    }
    # Wine installs may start through the same loader copied to binkw32.dll.
    # Replace it only if it is exactly the upstream proxy, never the game's Bink library.
    if ((Hash (Join-Path $GameDir 'binkw32.dll')) -eq $officialLoader) {
        $loader = $entries | Where-Object { $_.path -eq 'version.dll' }
        $entries += [pscustomobject]@{path='binkw32.dll'; source='version.dll'; original=$officialLoader; installed=$loader.installed}
    }
    if (!(Test-Path -LiteralPath (Join-Path $GameDir 'wiz8wide.ini') -PathType Leaf)) { throw '와이드 설정 파일이 없습니다.' }
    if ($VerifyOnly) { Write-Host ('설치 전 검증 통과: ' + $entries.Count + '개 파일'); exit 0 }
    $state = [pscustomobject]@{ version='0.3.0-test1'; cyrillic=(IniValue (Join-Path $GameDir 'wiz8wide.ini')); files=$entries }
    # Back up every existing destination before touching any installed game file.
    New-Item -ItemType Directory -Path $backup | Out-Null
    foreach ($entry in $entries) {
        if ($entry.original) {
            $saved = Join-Path $backup ('originals/' + $entry.path)
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $saved) | Out-Null
            Copy-Item -LiteralPath (Join-Path $GameDir $entry.path) -Destination $saved
            if ((Hash $saved) -ne $entry.original) { throw ('백업 검증 실패: ' + $entry.path) }
        }
    }
    Copy-Item -LiteralPath (Join-Path $GameDir 'wiz8wide.ini') -Destination (Join-Path $backup 'wiz8wide.ini.before')
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statePath -Encoding UTF8
    try {
        SetIni (Join-Path $GameDir 'wiz8wide.ini') '0'
        foreach ($entry in $entries) {
            $dest = Join-Path $GameDir $entry.path
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
            Copy-Item -LiteralPath (Join-Path $payload $entry.source) -Destination $dest -Force
            if ((Hash $dest) -ne $entry.installed) { throw ('복사 검증 실패: ' + $entry.path) }
        }
    } catch {
        Restore $state $backup $GameDir
        Move-Item -LiteralPath $statePath -Destination (Join-Path $backup 'rolled-back.json') -Force
        throw
    }
    Write-Host '설치 완료. 순정 Wiz8.exe 또는 기존 Steam/GOG 실행 버튼으로 시작하세요.'
    Write-Host '게임 내 한글 표시와 와이드 화면은 직접 확인이 필요한 시험판입니다.'
} catch {
    Write-Host ('오류: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
