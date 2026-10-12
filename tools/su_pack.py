"""Write manifest / installer / readme for a pack folder and (optionally) zip it."""
import time, zipfile, shutil
from lib_su import *


def _crlf(s):
    return s.replace("\r\n", "\n").replace("\n", "\r\n")


# Windows PowerShell 5.1 cannot Test-Path / Copy-Item / Get-FileHash a path over 259 characters (verified on this machine, LongPathsEnabled=0),
# and the longest payload file name (199 characters relative) plus a normal game / pack / backup folder exceeds that. File operations
# therefore go through .NET on extended-length (\\?\) paths; '/' is normalised because Steam's registry path uses forward slashes.
LP_HELPERS = r'''
function ToLongPath([string]$p) {
    $p = $p.Replace('/', '\')
    if ($p.StartsWith('\\?\')) { return $p }
    if ($p.StartsWith('\\')) { return '\\?\UNC\' + $p.Substring(2) }
    return '\\?\' + $p
}
function Test-FileLP([string]$p) { return [System.IO.File]::Exists((ToLongPath $p)) }
function Get-HashLP([string]$p) {
    $fs = [System.IO.File]::OpenRead((ToLongPath $p))
    try {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try { return ([System.BitConverter]::ToString($sha.ComputeHash($fs)) -replace '-', '') } finally { $sha.Dispose() }
    } finally { $fs.Dispose() }
}
function Copy-FileLP([string]$s, [string]$d) {
    [void][System.IO.Directory]::CreateDirectory((ToLongPath (Split-Path -Parent $d)))
    if ([System.IO.File]::Exists((ToLongPath $d))) { [System.IO.File]::SetAttributes((ToLongPath $d), [System.IO.FileAttributes]::Normal) }
    [System.IO.File]::Copy((ToLongPath $s), (ToLongPath $d), $true)
}
'''


def installer_ps1():
    t = open(os.path.join(OLD_PACK, "install.ps1"), encoding="utf-8-sig", newline="").read().replace("\r\n", "\n")

    def sub(old, new):
        nonlocal t
        assert t.count(old) == 1, old
        t = t.replace(old, new)

    # 1. accept the previous pack's patched hash (or any hash listed in also_accept_sha256) as an installable state
    sub("""    if ($currentHash -ne $file.original_sha256 -and -not $Force) {
        $unexpected.Add("$($file.relative_path) => $currentHash")
        continue
    }
""", """    $accepted = @($file.original_sha256) + @($file.also_accept_sha256)
    if (($accepted -notcontains $currentHash) -and -not $Force) {
        $unexpected.Add("$($file.relative_path) => $currentHash")
        continue
    }
""")
    # 2. remember the expected hash and verify after copy
    sub("""        CurrentHash = $currentHash
    })""", """        CurrentHash = $currentHash
        ExpectedHash = $file.patched_sha256
    })""")
    sub("""    Copy-Item -LiteralPath $entry.Source -Destination $entry.Target -Force
    Write-Host "[Patched] $($entry.RelativePath)"
""", """    Copy-Item -LiteralPath $entry.Source -Destination $entry.Target -Force
    $newHash = (Get-FileHash -LiteralPath $entry.Target -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($newHash -ne $entry.ExpectedHash) {
        throw "Hash mismatch after copy: $($entry.RelativePath) (disk full or file locked?). Backup: $backupRoot"
    }
    Write-Host "[Patched] $($entry.RelativePath)"
""")
    sub("""    Write-Host 'Unexpected file hashes detected. Aborting install.' -ForegroundColor Red
""", """    Write-Host 'Unexpected file hashes detected. Aborting install.' -ForegroundColor Red
    Write-Host 'The files below are neither the original game files nor a known earlier patch (game updated by Steam? other mods?).' -ForegroundColor Yellow
    Write-Host 'Fix: Steam > Suzerain > Properties > Installed Files > Verify integrity, then run this installer again.' -ForegroundColor Yellow
    $needMain = @($manifest.files | Where-Object { $_.PSObject.Properties['requires_pack'] } | ForEach-Object { $_.requires_pack } | Select-Object -Unique)
    if ($needMain.Count -gt 0) {
        Write-Host ('This is an add-on pack. If the main pack is not installed yet, install it first (' + ($needMain -join ', ') + '), then run this installer again.') -ForegroundColor Cyan
    }
""")
    # 3. long-path safe file operations (see LP_HELPERS); the backup is verified before the original is overwritten
    sub("""    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
""", """    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
""" + LP_HELPERS)
    sub("""    if (-not (Test-Path $source)) { throw "Patch payload missing: $source" }
    if (-not (Test-Path $target)) { throw "Target file missing: $target" }
""", """    if (-not (Test-FileLP $source)) { throw "Patch payload missing: $source" }
    if (-not (Test-FileLP $target)) { throw "Target file missing: $target" }
""")
    sub("""    $currentHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToUpperInvariant()
""", """    $currentHash = Get-HashLP $target
""")
    sub("""New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
""", """[void][System.IO.Directory]::CreateDirectory((ToLongPath $backupRoot))
""")
    sub("""    $backupTarget = Join-Path $backupRoot $entry.RelativePath
    $backupDir = Split-Path -Parent $backupTarget
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    Copy-Item -LiteralPath $entry.Target -Destination $backupTarget -Force

    $targetDir = Split-Path -Parent $entry.Target
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    Copy-Item -LiteralPath $entry.Source -Destination $entry.Target -Force
    $newHash = (Get-FileHash -LiteralPath $entry.Target -Algorithm SHA256).Hash.ToUpperInvariant()
""", """    $backupTarget = Join-Path $backupRoot $entry.RelativePath
    Copy-FileLP $entry.Target $backupTarget
    if ((Get-HashLP $backupTarget) -ne $entry.CurrentHash) {
        throw "Backup verification failed: $($entry.RelativePath) (disk full?). This file was not overwritten."
    }

    Copy-FileLP $entry.Source $entry.Target
    $newHash = Get-HashLP $entry.Target
""")
    sub("""$installRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $backupRoot 'install_record.json') -Encoding UTF8
""", """[System.IO.File]::WriteAllText((ToLongPath (Join-Path $backupRoot 'install_record.json')), ($installRecord | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($true)))
""")
    return "\ufeff" + _crlf(t)


# the old install.bat only paused on failure, so a double-click run closed the window before the result could be read
INSTALL_BAT = (b"@echo off\r\nsetlocal\r\n"
               b"powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0install.ps1\" %*\r\n"
               b"set EXITCODE=%ERRORLEVEL%\r\necho.\r\n"
               b"if \"%EXITCODE%\"==\"0\" (echo Install finished.) else (echo Install failed with exit code %EXITCODE%.)\r\n"
               b"pause\r\nexit /b %EXITCODE%\r\n")


def write_manifest(out_dir, release_name, variant, files, notes):
    old = json.load(open(os.path.join(OLD_PACK, "patch_manifest.json"), encoding="utf-8-sig"))
    m = {
        "release_name": release_name,
        "variant": variant,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steam_appid": old["steam_appid"],
        "steam_buildid": old["steam_buildid"],
        "catalog_hash": old["catalog_hash"],
        "build_guid": old["build_guid"],
        "support": old["support"],
        "notes": notes,
        "files": files,
    }
    txt = _crlf(json.dumps(m, ensure_ascii=False, indent=2))
    with open(os.path.join(out_dir, "patch_manifest.json"), "w", encoding="utf-8-sig", newline="") as f:
        f.write(txt)
    return m


def file_entries(out_dir, accept_old=None):
    """manifest 'files' list for every bundle under out_dir/AA_REL; original hash always taken from the pristine game file."""
    accept_old = accept_old or {}
    ents = []
    base = os.path.join(out_dir, AA_REL)
    for n in sorted(os.listdir(lp(base))):
        if not n.endswith(".bundle"):
            continue
        p = os.path.join(base, n)
        e = {
            "relative_path": AA_REL + "\\" + n,
            "file_name": n,
            "size": os.path.getsize(lp(p)),
            "original_sha256": sha256_file(os.path.join(AA_GAME, n)),
            "patched_sha256": sha256_file(p),
        }
        extra = [h for h in accept_old.get(n, []) if h not in (e["original_sha256"], e["patched_sha256"])]
        if extra:
            e["also_accept_sha256"] = extra
        ents.append(e)
    return ents


def write_installer(out_dir):
    with open(os.path.join(out_dir, "install.ps1"), "w", encoding="utf-8", newline="") as f:
        f.write(installer_ps1())
    with open(os.path.join(out_dir, "install.bat"), "wb") as f:
        f.write(INSTALL_BAT)


# ---------------------------------------------------------------------------- restore script (all packs)
RESTORE_TAIL = r'''$resolvedGameRoot = Resolve-GameRoot -ProvidedRoot $GameRoot
Assert-Build -ResolvedGameRoot $resolvedGameRoot

$backupBase = Join-Path $resolvedGameRoot '_patch_backup'
$prefix = $manifest.variant + '_'
$dirs = @()
if (Test-Path -LiteralPath $backupBase) {
    $dirs = @(Get-ChildItem -LiteralPath $backupBase -Directory | Where-Object { $_.Name.StartsWith($prefix) } | Sort-Object Name -Descending)
}

# Undo only what this pack installed: a file is restored when it currently equals this pack's patched version, from the
# newest backup whose hash is the original game file (or an earlier known patch listed in also_accept_sha256).
# Files in any other state (already original / earlier patch -> nothing to undo; unknown -> e.g. updated by Steam) are never touched
# unless -Force is given.
# files this pack's installer really replaced (install_record.json sits next to every backup). A file that is in the patched
# state but not listed there was already identical before the install (e.g. shipped unchanged by an earlier pack): nothing to undo.
$recorded = @{}
foreach ($dir in $dirs) {
    $rec = Join-Path $dir.FullName 'install_record.json'
    if (Test-Path -LiteralPath $rec) {
        try {
            $r = Get-Content -LiteralPath $rec -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($f in @($r.files)) { $recorded[[string]$f.RelativePath] = $true }
        } catch {}
    }
}

$restored = 0
$failed = New-Object System.Collections.Generic.List[string]
$unknown = New-Object System.Collections.Generic.List[string]
foreach ($file in $manifest.files) {
    $target = Join-Path $resolvedGameRoot $file.relative_path
    if (-not (Test-FileLP $target)) {
        $failed.Add("target missing: $($file.relative_path)")
        continue
    }
    $accepted = @($file.original_sha256) + @($file.also_accept_sha256)
    $currentHash = Get-HashLP $target
    if ($accepted -contains $currentHash) {
        Write-Host "[Skip] Not patched by this pack (original or earlier patch): $($file.relative_path)"
        continue
    }
    if (($currentHash -ne $file.patched_sha256) -and -not $Force) {
        $unknown.Add($file.relative_path)
        continue
    }
    $done = $false
    foreach ($dir in $dirs) {
        $candidate = Join-Path $dir.FullName $file.relative_path
        if (-not (Test-FileLP $candidate)) { continue }
        $candHash = Get-HashLP $candidate
        if ($accepted -notcontains $candHash) { continue }
        Copy-FileLP $candidate $target
        $newHash = Get-HashLP $target
        if ($newHash -ne $candHash) {
            throw "Hash mismatch after restore: $($file.relative_path) (disk full or file locked?)"
        }
        Write-Host "[Restored] $($file.relative_path)  (from $($dir.Name))"
        $restored++
        $done = $true
        break
    }
    if (-not $done) {
        if (($dirs.Count -gt 0) -and -not $recorded.ContainsKey([string]$file.relative_path)) {
            Write-Host "[Skip] Not replaced by this pack (already identical before install): $($file.relative_path)"
        } else {
            $failed.Add($file.relative_path)
        }
    }
}

$bad = $false
if ($unknown.Count -gt 0) {
    $bad = $true
    Write-Host 'Left untouched (neither this pack version nor a known original; game updated by Steam or other mods?):' -ForegroundColor Yellow
    $unknown | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
}
if ($failed.Count -gt 0) {
    $bad = $true
    Write-Host 'No clean backup was found for:' -ForegroundColor Yellow
    $failed | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
}
if ($bad) {
    Write-Host 'Fix: Steam > Suzerain > Properties > Installed Files > Verify integrity of game files.' -ForegroundColor Yellow
    exit 1
}

Write-Host ''
Write-Host "Restore completed ($restored file(s) restored)."
'''

RESTORE_BAT = (b"@echo off\r\nsetlocal\r\n"
               b"powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0restore.ps1\" %*\r\n"
               b"set EXITCODE=%ERRORLEVEL%\r\necho.\r\n"
               b"if \"%EXITCODE%\"==\"0\" (echo Restore finished.) else (echo Restore failed with exit code %EXITCODE%.)\r\n"
               b"pause\r\nexit /b %EXITCODE%\r\n")


def restore_ps1():
    """restore.ps1 = the installer's prologue (Steam / game-root detection, build assert) + restore logic."""
    t = installer_ps1().lstrip("\ufeff").replace("\r\n", "\n")
    marker = "$resolvedGameRoot = Resolve-GameRoot -ProvidedRoot $GameRoot\n"
    assert t.count(marker) == 1
    head = t[:t.index(marker)]
    return "\ufeff" + _crlf(head + RESTORE_TAIL)


def write_restore(out_dir):
    with open(os.path.join(out_dir, "restore.ps1"), "w", encoding="utf-8", newline="") as f:
        f.write(restore_ps1())
    with open(os.path.join(out_dir, "restore.bat"), "wb") as f:
        f.write(RESTORE_BAT)


def write_readme(out_dir, text):
    with open(os.path.join(out_dir, "README.txt"), "w", encoding="utf-8-sig", newline="") as f:
        f.write(_crlf(text))


def zip_pack(out_dir):
    zp = out_dir.rstrip("\\/") + ".zip"
    if os.path.exists(zp):
        os.remove(zp)
    root = os.path.dirname(out_dir)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dp, dn, fn in os.walk(out_dir):
            for n in sorted(fn):
                full = os.path.join(dp, n)
                z.write(lp(full), os.path.relpath(full, root))      # lp(): paths of the longest bundles exceed MAX_PATH
    return zp
