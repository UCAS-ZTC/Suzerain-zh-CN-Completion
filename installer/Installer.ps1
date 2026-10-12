<#
  Suzerain 汉化安装器（图形界面，Windows PowerShell 5.1 + WinForms）

  用法：双击“启动安装器.bat”。
  程序会在 本文件夹、本文件夹下的 packs 子文件夹、上一级文件夹 里找各个汉化包（Suzerain_CN_Plus_* 文件夹），
  列出来让你勾选。安装 / 还原时调用各个包自带的 install.ps1 / restore.ps1：哈希校验、先备份再覆盖、可还原，
  这些逻辑都在包里（已在沙盒里测过），本程序不重复实现，也不会使用 -Force。

  命令行（给测试用）：
    Installer.ps1 -Headless -GameRoot <游戏目录> [-Scenario "install:plus,maplabels;restore:plus;restoreall"] -Yes [-OutJson 结果.json]
    Installer.ps1 -SelfTest -GameRoot <游戏目录> -Scenario ... [-ScreenshotDir 目录] [-OutJson 结果.json]   （驱动真实界面，截图后退出）
    Installer.ps1 -Offscreen -GameRoot <游戏目录>   （真实界面和真实弹窗，窗口放在屏幕外，给自动化点击测试用）
  Scenario 的每一步：install:<组件代号,...|*>  restore:<组件代号,...|*>  restoreall  status
  组件代号：plus、maplabels、tutorialimg、sceneui、programtext、programwords
#>
[CmdletBinding()]
param(
    [string]$GameRoot = '',
    [string]$PacksRoot = '',
    [switch]$Headless,
    [switch]$SelfTest,
    [switch]$Offscreen,       # 测试用：真实界面（真实弹窗），但窗口放在屏幕外，供自动化点击
    [string]$Scenario = '',
    [switch]$Yes,
    [string]$OutJson = '',
    [string]$ScreenshotDir = '',
    [string]$LogDir = ''
)

$ErrorActionPreference = 'Stop'
$script:Version = '2026-10-12'
$script:AppRoot = $PSScriptRoot
$script:AppId = '1207650'
$script:AutoYes = ($Yes.IsPresent -or $SelfTest.IsPresent)

# =====================================================================================================================
# 核心逻辑（界面和命令行共用；状态检测在后台线程里也用同一份代码）
# =====================================================================================================================
$CoreCode = @'
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
function Read-JsonFile([string]$Path) {
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

# ---- 找汉化包：含 patch_manifest.json + install.ps1 + restore.ps1 且 release_name 以 Suzerain_CN_Plus_ 开头的文件夹 ----
function Find-Packs {
    param([string[]]$Roots)
    $byVariant = @{}
    foreach ($root in $Roots) {
        if (-not $root) { continue }
        if (-not (Test-Path -LiteralPath $root)) { continue }
        foreach ($d in @(Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue)) {
            $mp = Join-Path $d.FullName 'patch_manifest.json'
            if (-not (Test-Path -LiteralPath $mp)) { continue }
            if (-not (Test-Path -LiteralPath (Join-Path $d.FullName 'install.ps1'))) { continue }
            if (-not (Test-Path -LiteralPath (Join-Path $d.FullName 'restore.ps1'))) { continue }
            try { $m = Read-JsonFile $mp } catch { continue }
            $rel = [string]$m.release_name
            $var = [string]$m.variant
            if ((-not $var) -or (-not $rel.StartsWith('Suzerain_CN_Plus_'))) { continue }
            if ($byVariant.ContainsKey($var)) { continue }
            $fileMap = @{}
            $requires = New-Object System.Collections.ArrayList
            foreach ($f in @($m.files)) {
                $fileMap[[string]$f.file_name] = $f
                $rp = $f.PSObject.Properties['requires_pack']
                if ($rp -and $rp.Value -and ($requires -notcontains [string]$rp.Value)) { [void]$requires.Add([string]$rp.Value) }
            }
            $byVariant[$var] = [pscustomobject]@{
                Variant = $var; Name = $rel; Dir = $d.FullName; Manifest = $m
                Files = @($m.files); FileMap = $fileMap; Requires = @($requires)
                Deps = (New-Object System.Collections.ArrayList); MissingBase = (New-Object System.Collections.ArrayList)
                BaseOrig = @{}; CoveredBy = @{}
                Order = 99; Title = $rel; Risk = '?'; Short = ''; Desc = ''
            }
        }
    }
    return $byVariant
}

# ---- 包与包之间的“叠加”关系：A 的某个文件的 original_sha256 等于 B 的 patched_sha256，说明 A 建立在 B 之上 ----
function Link-Packs {
    param($ByVariant)
    $byName = @{}
    foreach ($p in $ByVariant.Values) { $byName[$p.Name] = $p }
    foreach ($a in $ByVariant.Values) {
        foreach ($b in $ByVariant.Values) {
            if ($a.Variant -eq $b.Variant) { continue }
            foreach ($fa in $a.Files) {
                $name = [string]$fa.file_name
                $fb = $b.FileMap[$name]
                if (-not $fb) { continue }
                if (([string]$fa.original_sha256 -eq [string]$fb.patched_sha256) -and ([string]$fa.patched_sha256 -ne [string]$fb.patched_sha256)) {
                    if ($a.Deps -notcontains $b.Variant) { [void]$a.Deps.Add($b.Variant) }
                    $a.BaseOrig[$name] = [string]$fb.original_sha256
                    if (-not $b.CoveredBy.ContainsKey($name)) { $b.CoveredBy[$name] = New-Object System.Collections.ArrayList }
                    [void]$b.CoveredBy[$name].Add([string]$fa.patched_sha256)
                }
            }
        }
        foreach ($rn in $a.Requires) {
            if ($byName.ContainsKey($rn)) {
                if ($a.Deps -notcontains $byName[$rn].Variant) { [void]$a.Deps.Add($byName[$rn].Variant) }
            } else {
                [void]$a.MissingBase.Add($rn)
            }
        }
    }
}

# ---- 找游戏（与各包 install.ps1 里的逻辑一致，但不会弹出提问）----
function Get-SteamRoots {
    $roots = New-Object System.Collections.Generic.List[string]
    $registrySpecs = @(
        @{ Path = 'HKCU:\Software\Valve\Steam'; Name = 'SteamPath' },
        @{ Path = 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam'; Name = 'InstallPath' },
        @{ Path = 'HKLM:\SOFTWARE\Valve\Steam'; Name = 'InstallPath' }
    )
    foreach ($spec in $registrySpecs) {
        try {
            $value = (Get-ItemProperty -Path $spec.Path -Name $spec.Name -ErrorAction Stop).($spec.Name)
            if ($value) { $roots.Add($value) }
        } catch {}
    }
    foreach ($path in @(
        ${env:ProgramFiles(x86)} + '\Steam',
        $env:ProgramFiles + '\Steam',
        'C:\Program Files (x86)\Steam',
        'C:\Program Files\Steam'
    )) {
        if ($path -and (Test-Path -LiteralPath $path)) { $roots.Add($path) }
    }
    return @($roots | Select-Object -Unique)
}
function Get-LibraryPaths([string]$SteamRoot) {
    $paths = New-Object System.Collections.Generic.List[string]
    if (Test-Path -LiteralPath (Join-Path $SteamRoot 'steamapps')) { $paths.Add($SteamRoot) }
    $libraryFile = Join-Path $SteamRoot 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $libraryFile) {
        foreach ($line in (Get-Content -LiteralPath $libraryFile)) {
            if ($line -match '^\s*"path"\s*"(.+)"') {
                $lib = $matches[1] -replace '\\\\', '\'
                if (Test-Path -LiteralPath (Join-Path $lib 'steamapps')) { $paths.Add($lib) }
            }
        }
    }
    return @($paths | Select-Object -Unique)
}
function Find-GameCandidates([string]$AppId) {
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($steamRoot in @(Get-SteamRoots)) {
        foreach ($lib in @(Get-LibraryPaths $steamRoot)) {
            $acf = Join-Path $lib ('steamapps\appmanifest_' + $AppId + '.acf')
            if (-not (Test-Path -LiteralPath $acf)) { continue }
            $content = Get-Content -LiteralPath $acf -Raw
            if ($content -match '"installdir"\s+"([^"]+)"') {
                $cand = Join-Path $lib ('steamapps\common\' + $matches[1])
                if (Test-Path -LiteralPath (Join-Path $cand 'Suzerain.exe')) { $candidates.Add($cand) }
            }
        }
    }
    return @($candidates | Select-Object -Unique)
}

# ---- 游戏目录检查：是不是游戏根目录、版本（catalog.hash / build-guid）是否和补丁一致 ----
function Get-GameInfo {
    param([string]$Root, $Manifest)
    $r = [pscustomobject]@{ Root = $Root; Valid = $false; VersionOk = $false; Message = '' }
    if ((-not $Root) -or (-not (Test-Path -LiteralPath $Root))) { $r.Message = '目录不存在。请点“浏览”选择游戏文件夹，或点“自动检测”。'; return $r }
    if (-not (Test-Path -LiteralPath (Join-Path $Root 'Suzerain.exe'))) { $r.Message = '这个文件夹里没有 Suzerain.exe，不是游戏根目录。'; return $r }
    $cat = Join-Path $Root 'Suzerain_Data\StreamingAssets\aa\catalog.hash'
    $boot = Join-Path $Root 'Suzerain_Data\boot.config'
    if ((-not (Test-Path -LiteralPath $cat)) -or (-not (Test-Path -LiteralPath $boot))) { $r.Message = '缺少 catalog.hash 或 boot.config，游戏文件不完整。'; return $r }
    $r.Valid = $true
    $ch = (Get-Content -LiteralPath $cat -Raw).Trim()
    $guid = ''
    if ((Get-Content -LiteralPath $boot -Raw) -match '(?m)^build-guid=(.+)$') { $guid = $matches[1].Trim() }
    if ($Manifest) {
        if (($ch -eq [string]$Manifest.catalog_hash) -and ($guid -eq [string]$Manifest.build_guid)) {
            $r.VersionOk = $true
            $r.Message = '游戏版本与补丁一致（catalog.hash、build-guid 都对得上）。'
        } else {
            $r.Message = '游戏版本与补丁不一致（游戏可能被 Steam 更新过）：补丁不适用，安装和还原都会被拒绝。'
        }
    } else {
        $r.Message = '没有找到任何汉化包，无法核对版本。'
    }
    return $r
}

function Get-BackupDirs([string]$Game, [string]$Variant) {
    $base = Join-Path $Game '_patch_backup'
    if (-not (Test-Path -LiteralPath $base)) { return @() }
    return @(Get-ChildItem -LiteralPath $base -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name.StartsWith($Variant + '_') } | Sort-Object Name -Descending | ForEach-Object { $_.Name })
}

# ---- 状态：逐文件算哈希，和清单里的 原版 / 补丁后 / 旧版 哈希比 ----
#   P 已是本包的补丁版   T 被叠在它上面的附加包覆盖   O 原版   L 旧版汉化包   N 原版但本包需要的“主包版本”还没装   U 不认识   M 文件不存在
function Get-StatusText([string]$Code, $Cnt, [int]$Total, [string]$BaseTitle = '') {
    switch ($Code) {
        'installed' { return '已安装' }
        'none'      { return '未安装' }
        'partial'   { return ('部分安装（{0}/{1}）' -f ($Cnt.P + $Cnt.T), $Total) }
        'needbase'  { if ($BaseTitle) { return ('未安装（需先装' + $BaseTitle + '）') } else { return '未安装（需先装被它叠加的组件）' } }
        'legacy'    { return '检测到旧版汉化包（可覆盖升级）' }
        'mismatch'  { return ('文件与预期不符（{0} 个）' -f $Cnt.U) }
        'missing'   { return ('游戏文件缺失（{0} 个）' -f $Cnt.M) }
        default     { return $Code }
    }
}
function Get-PackStatus {
    param([string]$Game, $Pack, $Cache, $ByVariant = $null)
    $cnt = @{ P = 0; T = 0; O = 0; L = 0; N = 0; U = 0; M = 0 }
    $unknown = New-Object System.Collections.ArrayList
    foreach ($f in $Pack.Files) {
        $path = Join-Path $Game ([string]$f.relative_path)
        if (-not (Test-FileLP $path)) { $cnt.M++; [void]$unknown.Add([string]$f.relative_path); continue }
        if ($Cache.ContainsKey($path)) { $h = $Cache[$path] } else { $h = Get-HashLP $path; $Cache[$path] = $h }
        $name = [string]$f.file_name
        if ($h -eq [string]$f.patched_sha256) { $cnt.P++ }
        elseif ($Pack.CoveredBy.ContainsKey($name) -and ($Pack.CoveredBy[$name] -contains $h)) { $cnt.T++ }
        elseif ($h -eq [string]$f.original_sha256) { $cnt.O++ }
        elseif (@($f.also_accept_sha256) -contains $h) { $cnt.L++ }
        elseif ($Pack.BaseOrig.ContainsKey($name) -and ($h -eq $Pack.BaseOrig[$name])) { $cnt.N++ }
        else { $cnt.U++; [void]$unknown.Add([string]$f.relative_path) }
    }
    $total = @($Pack.Files).Count
    $inst = $cnt.P + $cnt.T
    if ($cnt.M -gt 0) { $code = 'missing' }
    elseif ($cnt.U -gt 0) { $code = 'mismatch' }
    elseif ($inst -eq $total) { $code = 'installed' }
    elseif (($cnt.L -gt 0)) { $code = 'legacy' }
    elseif ($inst -eq 0) { if ($cnt.N -gt 0) { $code = 'needbase' } else { $code = 'none' } }
    else { $code = 'partial' }
    # 叠在别的组件之上的附加包：状态里写出它依赖的组件名（去掉标题末尾的“（实验性）”之类括号）
    $baseTitle = ''
    if ($code -eq 'needbase') {
        $names = @()
        foreach ($d in @($Pack.Deps)) {
            if ($ByVariant -and $ByVariant.ContainsKey($d)) { $names += ([string]$ByVariant[$d].Title -replace '（[^）]*）$', '') } else { $names += [string]$d }
        }
        $baseTitle = ($names -join '、')
    }
    return [pscustomobject]@{
        Variant = $Pack.Variant; Code = $code; Text = (Get-StatusText $code $cnt $total $baseTitle)
        Installed = $inst; Total = $total; P = $cnt.P; T = $cnt.T; O = $cnt.O; L = $cnt.L; N = $cnt.N; U = $cnt.U; M = $cnt.M
        Unknown = @($unknown); Backups = @(Get-BackupDirs $Game $Pack.Variant)
    }
}
function Get-AllStatus {
    param([string]$Game, $ByVariant)
    $cache = @{}
    $res = @{}
    foreach ($p in $ByVariant.Values) { $res[$p.Variant] = Get-PackStatus -Game $Game -Pack $p -Cache $cache -ByVariant $ByVariant }
    return $res
}

# ---- 计划：安装时把“需要先装”的补进来，还原时把“叠在上面”的先还原 ----
function Get-DepOrder {
    param($ByVariant, [string[]]$Variants)
    $remaining = New-Object System.Collections.ArrayList
    foreach ($v in $Variants) { [void]$remaining.Add($v) }
    $placed = New-Object System.Collections.ArrayList
    while ($remaining.Count -gt 0) {
        $moved = $false
        foreach ($v in @($remaining | Sort-Object { $ByVariant[$_].Order })) {
            $blocked = $false
            foreach ($d in @($ByVariant[$v].Deps)) { if ($remaining -contains $d) { $blocked = $true } }
            if (-not $blocked) { [void]$placed.Add($v); $remaining.Remove($v); $moved = $true }
        }
        if (-not $moved) { foreach ($v in @($remaining)) { [void]$placed.Add($v) }; break }
    }
    return @($placed)
}
function Get-InstallPlan {
    param($ByVariant, $Status, [string[]]$Selected)
    $want = New-Object System.Collections.ArrayList
    $added = New-Object System.Collections.ArrayList
    foreach ($v in $Selected) { if ($ByVariant.ContainsKey($v) -and ($want -notcontains $v)) { [void]$want.Add($v) } }
    $i = 0
    while ($i -lt $want.Count) {
        $v = $want[$i]; $i++
        foreach ($d in @($ByVariant[$v].Deps)) {
            if (($want -notcontains $d) -and ($Status[$d].Code -ne 'installed')) { [void]$want.Add($d); [void]$added.Add($d) }
        }
    }
    $order = @(Get-DepOrder $ByVariant @($want))
    $run = @($order | Where-Object { $Status[$_].Code -ne 'installed' })
    $skip = @($order | Where-Object { $Status[$_].Code -eq 'installed' })
    return [pscustomobject]@{ Order = $order; Run = $run; Skipped = $skip; Added = @($added) }
}
function Get-RestorePlan {
    param($ByVariant, $Status, [string[]]$Selected)
    $want = New-Object System.Collections.ArrayList
    $added = New-Object System.Collections.ArrayList
    foreach ($v in $Selected) { if ($ByVariant.ContainsKey($v) -and ($want -notcontains $v)) { [void]$want.Add($v) } }
    $i = 0
    while ($i -lt $want.Count) {
        $v = $want[$i]; $i++
        foreach ($p in $ByVariant.Values) {
            if (($p.Deps -contains $v) -and ($want -notcontains $p.Variant) -and ($Status[$p.Variant].Installed -gt 0)) {
                [void]$want.Add($p.Variant); [void]$added.Add($p.Variant)
            }
        }
    }
    $todo = @($want | Where-Object { $Status[$_].Installed -gt 0 })
    $skip = @($want | Where-Object { $Status[$_].Installed -le 0 })
    $order = @(Get-DepOrder $ByVariant $todo)
    [array]::Reverse($order)
    return [pscustomobject]@{ Order = $order; Run = $order; Skipped = $skip; Added = @($added) }
}
function Get-PlanBlockers {
    param($ByVariant, $Status, $Plan)
    $msgs = New-Object System.Collections.ArrayList
    foreach ($v in $Plan.Run) {
        $p = $ByVariant[$v]; $st = $Status[$v]
        foreach ($mb in $p.MissingBase) {
            [void]$msgs.Add(('「{0}」需要先安装 {1}，但在安装器能找到的文件夹里没有它。请把它的文件夹放在本安装器旁边或 packs 子文件夹里。' -f $p.Title, $mb))
        }
        if ($st.Code -eq 'mismatch') {
            [void]$msgs.Add(('「{0}」有 {1} 个游戏文件与预期不符（被其他补丁改过，或游戏已更新）。包自带的安装脚本会拒绝覆盖它们。请先在 Steam 里“验证游戏文件完整性”（会把所有补丁文件换回原版），再回来安装。' -f $p.Title, $st.U))
        }
        if ($st.Code -eq 'missing') {
            [void]$msgs.Add(('「{0}」要改的游戏文件有 {1} 个不存在。请先在 Steam 里“验证游戏文件完整性”。' -f $p.Title, $st.M))
        }
    }
    return @($msgs)
}

# ---- 执行：把每个包自带的 install.ps1 / restore.ps1 当子进程跑，读它的输出（不使用 -Force）----
function New-Task {
    param($Pack, [string]$Verb)
    if ($Verb -eq 'install') { $scr = 'install.ps1'; $vt = '安装' } else { $scr = 'restore.ps1'; $vt = '还原' }
    return [pscustomobject]@{ Variant = $Pack.Variant; Title = $Pack.Title; Verb = $Verb; VerbText = $vt; Dir = $Pack.Dir; Script = $scr }
}
function Get-OutEncoding {
    try { return [Console]::OutputEncoding } catch {}
    try { return [System.Text.Encoding]::GetEncoding([System.Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage) } catch {}
    return [System.Text.Encoding]::UTF8
}
function Start-PackProcess {
    param($Task, [string]$Game)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $scriptPath = Join-Path $Task.Dir $Task.Script
    $psi.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $scriptPath + '" -GameRoot "' + $Game.TrimEnd('\') + '"'
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.RedirectStandardInput = $true
    $enc = Get-OutEncoding
    $psi.StandardOutputEncoding = $enc
    $psi.StandardErrorEncoding = $enc
    [void]$psi.EnvironmentVariables.Remove('PSModulePath')
    $p = [System.Diagnostics.Process]::Start($psi)
    $p.StandardInput.Close()
    return [pscustomobject]@{
        Proc = $p; OutTask = $p.StandardOutput.ReadLineAsync(); ErrTask = $p.StandardError.ReadLineAsync(); OutDone = $false; ErrDone = $false
    }
}
function Read-ProcLines {
    param($Run, [scriptblock]$Emit)
    while ((-not $Run.OutDone) -and $Run.OutTask.IsCompleted) {
        $line = $null
        try { $line = $Run.OutTask.Result } catch { $Run.OutDone = $true; break }
        if ($null -eq $line) { $Run.OutDone = $true } else { & $Emit $line; $Run.OutTask = $Run.Proc.StandardOutput.ReadLineAsync() }
    }
    while ((-not $Run.ErrDone) -and $Run.ErrTask.IsCompleted) {
        $line = $null
        try { $line = $Run.ErrTask.Result } catch { $Run.ErrDone = $true; break }
        if ($null -eq $line) { $Run.ErrDone = $true } else { & $Emit $line; $Run.ErrTask = $Run.Proc.StandardError.ReadLineAsync() }
    }
}
function Test-ProcDone {
    param($Run)
    return ($Run.Proc.HasExited -and $Run.OutDone -and $Run.ErrDone)
}
'@
. ([scriptblock]::Create($CoreCode))

# =====================================================================================================================
# 组件说明（按 variant 对应；以后加新包，没写说明也能显示，只是用包名当标题）
# =====================================================================================================================
$script:PackMeta = @{
    plus = @{
        Order = 1; Title = '主汉化包'; Risk = '低'
        Short = '对白、典籍、新闻、地图图标、决议、成就、战争条目等全部数据文字'
        Desc = "游戏里几乎所有数据文字：对白脚本、实体库（典籍、新闻、地图图标、决议、报告）、成就、战争单位与目标、教程弹窗等。`r`n" +
               "要改 258 个资源文件，约 205 MB。其他组件都以它为基础，地图标注包必须在它之后安装。`r`n" +
               "风险：低。只换文本资源，做法与原来的旧汉化包一致。实测（2026-10-12，作者的机器）：启动、读档、对白、典籍、新闻、日志、国家 / 城市面板正常；没测新开一局、成就界面、战争界面。"
    }
    maplabels = @{
        Order = 2; Title = '地图中文标注包'; Risk = '低'
        Short = '48 张地图与地名贴图：英文地名旁边标注中文（1,127 处）'
        Desc = "世界地图、索德兰、里齐亚、帕雷、伦堡战争图，以及帕雷 / 齐勒 / 赫吉岛的叠加层、图鉴里的地区地图。英文原样保留，中文写在旁边。`r`n" +
               "必须先装主汉化包：其中 2 个资源文件（世界地图、帕雷地图所在）主包也改过，本包在主包版本之上再加标注。`r`n" +
               "风险：低。只换贴图。实测（2026-10-12，作者的机器）：索德兰及周边的主地图上英文地名旁有中文；其余贴图（里齐亚、战争地图、图鉴地区图等）没有逐张看过。"
    }
    tutorialimg = @{
        Order = 3; Title = '战争教程图片包'; Risk = '低'
        Short = '11 张含英文的战争教程截图重绘成中文'
        Desc = "战争教程弹窗里的 11 张截图原本是英文，重绘成中文（另有 5 张生产面板整屏截图没做）。只换贴图。`r`n" +
               "风险：低。只换贴图。实测（2026-10-12，作者的机器）：装上后启动、读档正常；这些图只在里齐亚的战争教程里出现，没进过战争，图片本身还没在游戏里看过。"
    }
    sceneui = @{
        Order = 4; Title = '场景界面包'; Risk = '中'
        Short = '菜单、设置、存档、战争界面、状态效果、片尾名单等 835 个界面字符串'
        Desc = "菜单、设置、存档、战争界面、状态效果、片尾名单等 835 个界面字符串（改 3 个场景资源文件）。没装它，这些界面是英文。`r`n" +
               "风险：中。旧汉化包的作者报告过「读档闪退」，原因不明。实测（2026-10-12，作者的机器）：7 次启动都读了档，没有闪退；主菜单、设置、暂停菜单和索德兰的各个面板都是中文；没测里齐亚场景和战争界面。建议单独安装，进游戏读一次档再决定留不留。"
    }
    programtext = @{
        Order = 5; Title = '程序内文案包（实验性）'; Risk = '高'
        Short = '编译进程序的 144 条文案（确认弹窗、存档提示、屏幕通知、战争头顶文字）'
        Desc = "这些文字只存在于游戏程序自带的字符串表里（global-metadata.dat），只替换这一个文件，文件大小不变。`r`n" +
               "风险：高（实验性）。改的是程序自带的字符串表，做错了游戏可能无法启动；可以随时还原。实测（2026-10-12，作者的机器）：启动、读档正常，退出 / 返回主菜单确认弹窗、读取窗口、国家 / 城市面板的几条文案显示为中文；其余条目没有逐条看过。建议最后装。"
    }
    programwords = @{
        Order = 6; Title = '程序内单词包（实验性）'; Risk = '高'
        Short = '17 个零散单词（弹窗按钮「是 / 否」、面板「首都 / 政府 / 人口」等）'
        Desc = "在程序内文案包的基础上，再把程序里 17 个单独的常用词改成中文：弹窗按钮 Yes / No，读取 / 选项标题，窗口模式和帧率的取值，国家 / 城市面板的首都 / 政府 / 人口等。`r`n" +
               "必须先装程序内文案包（改的是同一个文件）：安装时自动先装它，还原时自动先还原本包。`r`n" +
               "风险：高（实验性）。单个词被程序里所有用到它的地方共用，代码里若有拿它做比较或查找键的用法会失灵，而且不报错。实测（2026-10-12，作者的机器）：读取、弹窗按钮、信息面板、设置的保存和读回都正常；窗口 / 无边框窗口两种模式没有点应用试过。"
    }
}
function Set-PackMeta {
    param($ByVariant)
    foreach ($p in $ByVariant.Values) {
        $m = $script:PackMeta[$p.Variant]
        if ($m) { $p.Order = $m.Order; $p.Title = $m.Title; $p.Risk = $m.Risk; $p.Short = $m.Short; $p.Desc = $m.Desc }
        else { $p.Short = '（没有说明）'; $p.Desc = '这个组件没有内置说明，请看它文件夹里的 README.txt。' }
    }
}

# =====================================================================================================================
# 启动：找包、找游戏
# =====================================================================================================================
function Resolve-Variants {
    param([string]$Arg)
    if ((-not $Arg) -or ($Arg.Trim() -eq '*')) { return @($script:AllPacks.Keys | Sort-Object { $script:AllPacks[$_].Order }) }
    return @($Arg -split '[,;\s]+' | Where-Object { $_ })
}

$roots = New-Object System.Collections.ArrayList
if ($PacksRoot) { [void]$roots.Add($PacksRoot) }
[void]$roots.Add((Join-Path $script:AppRoot 'packs'))
[void]$roots.Add($script:AppRoot)
$parent = Split-Path -Parent $script:AppRoot
if ($parent) { [void]$roots.Add($parent) }
$script:AllPacks = Find-Packs @($roots)
Link-Packs $script:AllPacks
Set-PackMeta $script:AllPacks
$script:AnyManifest = $null
if ($script:AllPacks.ContainsKey('plus')) { $script:AnyManifest = $script:AllPacks['plus'].Manifest }
elseif ($script:AllPacks.Count -gt 0) { $script:AnyManifest = ($script:AllPacks.Values | Select-Object -First 1).Manifest }

$script:Game = ''
if ($GameRoot) { $script:Game = $GameRoot.Trim().Trim('"').TrimEnd('\') }
else {
    $cands = @(Find-GameCandidates $script:AppId)
    if ($cands.Count -gt 0) { $script:Game = $cands[0] }
}

if (-not $LogDir) { $LogDir = Join-Path $env:LOCALAPPDATA 'SuzerainCN_Installer\logs' }
try { [void][System.IO.Directory]::CreateDirectory($LogDir) } catch {}
$script:LogFile = Join-Path $LogDir ('installer_{0}.log' -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
function Write-LogFile([string]$s) {
    try { [System.IO.File]::AppendAllText($script:LogFile, $s + "`r`n", (New-Object System.Text.UTF8Encoding($true))) } catch {}
}

function Get-ScenarioSteps {
    $steps = New-Object System.Collections.ArrayList
    foreach ($raw in ($Scenario -split ';')) {
        $s = $raw.Trim()
        if (-not $s) { continue }
        $parts = $s -split ':', 2
        $arg = ''
        if ($parts.Count -gt 1) { $arg = $parts[1] }
        [void]$steps.Add([pscustomobject]@{ Text = $s; Verb = $parts[0].Trim().ToLower(); Arg = $arg })
    }
    return @($steps)
}
function ConvertTo-StatusSnapshot($Status) {
    $o = [ordered]@{}
    foreach ($v in ($Status.Keys | Sort-Object { $script:AllPacks[$_].Order })) {
        $s = $Status[$v]
        $o[$v] = [ordered]@{ code = $s.Code; text = $s.Text; installed = $s.Installed; total = $s.Total; backups = @($s.Backups).Count }
    }
    return $o
}
function Save-OutJson($Obj) {
    if (-not $OutJson) { return }
    $json = $Obj | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($OutJson, $json, (New-Object System.Text.UTF8Encoding($false)))
}

# =====================================================================================================================
# 命令行模式（测试用）：不弹窗，同样的计划 / 阻止 / 执行逻辑
# =====================================================================================================================
function Invoke-Headless {
    if ($script:AllPacks.Count -eq 0) { Write-Host '没有找到任何汉化包文件夹。'; return 3 }
    $info = Get-GameInfo $script:Game $script:AnyManifest
    Write-Host ('游戏目录: {0}' -f $script:Game)
    Write-Host ('  {0}' -f $info.Message)
    if (-not $info.Valid) { return 3 }
    $log = { param($l) Write-Host ('    ' + $l); Write-LogFile $l }
    $results = New-Object System.Collections.ArrayList
    $status = Get-AllStatus -Game $script:Game -ByVariant $script:AllPacks
    foreach ($v in ($status.Keys | Sort-Object { $script:AllPacks[$_].Order })) { Write-Host ('  {0,-12} {1}' -f $v, $status[$v].Text) }
    [void]$results.Add([ordered]@{ step = 'initial'; ok = $true; status = (ConvertTo-StatusSnapshot $status) })
    $ok = $true
    foreach ($step in (Get-ScenarioSteps)) {
        Write-Host ('--- 步骤: {0}' -f $step.Text)
        $plan = $null; $blockers = @(); $verb = $null
        switch ($step.Verb) {
            'install'    { $verb = 'install'; $plan = Get-InstallPlan $script:AllPacks $status (Resolve-Variants $step.Arg) }
            'restore'    { $verb = 'restore'; $plan = Get-RestorePlan $script:AllPacks $status (Resolve-Variants $step.Arg) }
            'restoreall' { $verb = 'restore'; $plan = Get-RestorePlan $script:AllPacks $status @($status.Keys | Where-Object { $status[$_].Installed -gt 0 }) }
            'status'     { }
            default      { Write-Host ('未知步骤: ' + $step.Text); $ok = $false; break }
        }
        if (-not $ok) { break }
        $entry = [ordered]@{ step = $step.Text; ok = $true; plan = @(); added = @(); skipped = @(); blockers = @() }
        if ($plan) {
            $entry.plan = @($plan.Run); $entry.added = @($plan.Added); $entry.skipped = @($plan.Skipped)
            if ($verb -eq 'install') { $blockers = @(Get-PlanBlockers $script:AllPacks $status $plan) }
            $entry.blockers = $blockers
            Write-Host ('  计划: {0}   自动加入: {1}   跳过: {2}' -f (@($plan.Run) -join ' -> '), (@($plan.Added) -join ','), (@($plan.Skipped) -join ','))
            if ($blockers.Count -gt 0) {
                foreach ($b in $blockers) { Write-Host ('  [阻止] ' + $b) }
                $entry.ok = $false; $ok = $false
            } elseif (-not $Yes) {
                Write-Host '  （没有 -Yes：只显示计划，不执行）'
            } else {
                foreach ($v in $plan.Run) {
                    $t = New-Task $script:AllPacks[$v] $verb
                    Write-Host ('  [{0}] {1}' -f $t.VerbText, $t.Title)
                    $run = Start-PackProcess $t $script:Game
                    while (-not (Test-ProcDone $run)) { Read-ProcLines $run $log; Start-Sleep -Milliseconds 100 }
                    Read-ProcLines $run $log
                    $code = $run.Proc.ExitCode
                    if ($code -ne 0) { Write-Host ('  [失败] 退出码 {0}' -f $code); $entry.ok = $false; $ok = $false; break }
                }
            }
        }
        $status = Get-AllStatus -Game $script:Game -ByVariant $script:AllPacks
        foreach ($v in ($status.Keys | Sort-Object { $script:AllPacks[$_].Order })) { Write-Host ('  {0,-12} {1}' -f $v, $status[$v].Text) }
        $entry.status = (ConvertTo-StatusSnapshot $status)
        [void]$results.Add($entry)
        if (-not $ok) { break }
    }
    Save-OutJson ([ordered]@{ game = $script:Game; ok = $ok; steps = @($results) })
    if ($ok) { return 0 } else { return 1 }
}

if ($Headless) {
    $rc = Invoke-Headless
    exit $rc
}

# =====================================================================================================================
# 图形界面
# =====================================================================================================================
try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    try {
        Add-Type -Namespace SuzNative -Name Dpi -MemberDefinition '[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
        [void][SuzNative.Dpi]::SetProcessDPIAware()
    } catch {}
    [System.Windows.Forms.Application]::EnableVisualStyles()
    $g = [System.Drawing.Graphics]::FromHwnd([IntPtr]::Zero)
    $script:Scale = $g.DpiX / 96.0
    $g.Dispose()
} catch {
    Write-Host ('无法加载界面组件：' + $_.Exception.Message)
    exit 2
}
function Px([double]$n) { return [int][Math]::Round($n * $script:Scale) }

$script:Status = @{}
$script:GameInfo = $null
$script:Busy = $false
$script:Queue = New-Object System.Collections.ArrayList
$script:Run = $null
$script:CurTask = $null
$script:RunFailed = $false
$script:RefreshPS = $null
$script:RefreshHandle = $null
$script:SelfTestFailed = $false
$script:StepBlocked = $false

function Add-Log {
    param([string]$Text)
    Write-LogFile $Text
    if ($script:txtLog) {
        $script:txtLog.AppendText($Text + "`r`n")
        $script:txtLog.SelectionStart = $script:txtLog.TextLength
        $script:txtLog.ScrollToCaret()
    }
}
function Set-StatusText([string]$Text) { if ($script:lblStatus) { $script:lblStatus.Text = $Text } }
$script:ChildFiles = 0
function Add-ChildLine {
    # 各包自带脚本的输出：完整内容一律写进日志文件；窗口里把逐文件的行（[Patched] / [Restored] / [Skip]，主汉化包有 258 行）合并成进度
    param([string]$Line)
    Write-LogFile ('    ' + $Line)
    if ($Line -match '^\s*\[(Patched|Restored|Skip)\]') {
        $script:ChildFiles++
        if ($script:CurTask) { Set-StatusText ('正在{0}：{1}（已处理 {2} 个文件）…' -f $script:CurTask.VerbText, $script:CurTask.Title, $script:ChildFiles) }
        return
    }
    if ($script:txtLog) {
        $script:txtLog.AppendText('    ' + $Line + "`r`n")
        $script:txtLog.SelectionStart = $script:txtLog.TextLength
        $script:txtLog.ScrollToCaret()
    }
}
function Show-Msg {
    param([string]$Text, [string]$Title = 'Suzerain 汉化安装器', [string]$Buttons = 'OK', [string]$Icon = 'Information')
    if (-not $Title) { $Title = 'Suzerain 汉化安装器' }
    Add-Log ('[提示] ' + ($Text -replace "`r?`n", ' / '))
    if ($script:AutoYes) { if ($Buttons -eq 'YesNo') { return 'Yes' } else { return 'OK' } }
    return [System.Windows.Forms.MessageBox]::Show($script:Form, $Text, $Title, [System.Windows.Forms.MessageBoxButtons]::$Buttons, [System.Windows.Forms.MessageBoxIcon]::$Icon).ToString()
}
function Invoke-Safe {
    param([scriptblock]$Body)
    try { & $Body } catch {
        $msg = $_.Exception.Message
        Add-Log ('[内部错误] ' + $msg)
        Add-Log ([string]$_.ScriptStackTrace)
        $script:SelfTestFailed = $true
        if (-not $script:AutoYes) { [void][System.Windows.Forms.MessageBox]::Show($msg, '出错了', 'OK', 'Error') }
    }
}

function Get-StatusColor([string]$Code) {
    switch ($Code) {
        'installed' { return [System.Drawing.Color]::FromArgb(226, 244, 226) }
        'mismatch'  { return [System.Drawing.Color]::FromArgb(250, 224, 224) }
        'missing'   { return [System.Drawing.Color]::FromArgb(250, 224, 224) }
        'partial'   { return [System.Drawing.Color]::FromArgb(255, 244, 214) }
        'needbase'  { return [System.Drawing.Color]::FromArgb(255, 244, 214) }
        'legacy'    { return [System.Drawing.Color]::FromArgb(255, 244, 214) }
        default     { return [System.Drawing.Color]::White }
    }
}
function Get-CheckedVariants {
    $r = @()
    foreach ($it in $script:lv.Items) { if ($it.Checked) { $r += [string]$it.Tag } }
    return $r
}
function Set-Checked {
    param([string[]]$Variants)
    foreach ($it in $script:lv.Items) { $it.Checked = ($Variants -contains [string]$it.Tag) }
}
function Update-List {
    $checked = @{}
    foreach ($it in $script:lv.Items) { if ($it.Checked) { $checked[[string]$it.Tag] = $true } }
    $selTag = $null
    if ($script:lv.SelectedItems.Count -gt 0) { $selTag = [string]$script:lv.SelectedItems[0].Tag }
    $script:lv.BeginUpdate()
    $script:lv.Items.Clear()
    foreach ($p in ($script:AllPacks.Values | Sort-Object Order)) {
        $st = $script:Status[$p.Variant]
        $it = New-Object System.Windows.Forms.ListViewItem($p.Title)
        if ($st) {
            [void]$it.SubItems.Add($st.Text)
            [void]$it.SubItems.Add($p.Risk)
            [void]$it.SubItems.Add([string]$st.Total)
            [void]$it.SubItems.Add([string]@($st.Backups).Count)
            $it.BackColor = Get-StatusColor $st.Code
        } else {
            [void]$it.SubItems.Add($(if ($script:GameInfo -and $script:GameInfo.Valid) { '检测中…' } else { '—' }))
            [void]$it.SubItems.Add($p.Risk)
            [void]$it.SubItems.Add([string]@($p.Files).Count)
            [void]$it.SubItems.Add('')
        }
        [void]$it.SubItems.Add($p.Short)
        $it.Tag = $p.Variant
        $it.Checked = $checked.ContainsKey($p.Variant)
        [void]$script:lv.Items.Add($it)
        if ($selTag -and ($selTag -eq $p.Variant)) { $it.Selected = $true }
    }
    if (($script:lv.SelectedItems.Count -eq 0) -and ($script:lv.Items.Count -gt 0)) { $script:lv.Items[0].Selected = $true }
    $script:lv.EndUpdate()
}
function Show-Detail {
    if ($script:lv.SelectedItems.Count -eq 0) { $script:txtDetail.Text = ''; return }
    $p = $script:AllPacks[[string]$script:lv.SelectedItems[0].Tag]
    $st = $script:Status[$p.Variant]
    $lines = New-Object System.Collections.ArrayList
    [void]$lines.Add(('{0}    ({1})' -f $p.Title, $p.Name))
    [void]$lines.Add($p.Desc)
    [void]$lines.Add('')
    $dep = '无'
    if ($p.Deps.Count -gt 0) { $dep = '先安装 ' + (($p.Deps | ForEach-Object { $script:AllPacks[$_].Title }) -join '、') }
    [void]$lines.Add(('风险：{0}    要改的文件：{1} 个    依赖：{2}' -f $p.Risk, @($p.Files).Count, $dep))
    if ($st) {
        [void]$lines.Add(('状态：{0}    （已是补丁版 {1}，被附加包覆盖 {2}，原版 {3}，旧版 {4}，其他 {5}）' -f $st.Text, $st.P, $st.T, $st.O, $st.L, ($st.U + $st.M + $st.N)))
        if (@($st.Backups).Count -gt 0) { [void]$lines.Add('备份（游戏目录\_patch_backup）：' + (@($st.Backups) -join '，')) }
        if (@($st.Unknown).Count -gt 0) { [void]$lines.Add('不认识的文件示例：' + (@($st.Unknown | Select-Object -First 2) -join '；')) }
    }
    $script:txtDetail.Text = ($lines -join "`r`n")
}
function Update-Info {
    if (-not $script:GameInfo) { $script:lblInfo.Text = ''; return }
    $script:lblInfo.Text = $script:GameInfo.Message
    if ($script:GameInfo.Valid -and $script:GameInfo.VersionOk) { $script:lblInfo.ForeColor = [System.Drawing.Color]::FromArgb(0, 110, 40) }
    else { $script:lblInfo.ForeColor = [System.Drawing.Color]::Firebrick }
}
function Update-ActionState {
    $ready = ($script:GameInfo -and $script:GameInfo.Valid -and $script:GameInfo.VersionOk -and ($script:AllPacks.Count -gt 0) -and (-not $script:Busy))
    $script:btnInstall.Enabled = $ready
    $script:btnRestore.Enabled = $ready
    $script:btnRestoreAll.Enabled = $ready
    $script:btnRefresh.Enabled = ($script:GameInfo -and $script:GameInfo.Valid -and (-not $script:Busy))
    $script:btnBackup.Enabled = ($script:GameInfo -and $script:GameInfo.Valid)
}
function Set-BusyUi([bool]$Busy) {
    $script:pb.Visible = $Busy
    $script:lv.Enabled = (-not $Busy)
    $script:btnBrowse.Enabled = (-not $Busy)
    $script:btnDetect.Enabled = (-not $Busy)
    $script:txtGame.Enabled = (-not $Busy)
    foreach ($b in @($script:btnAll, $script:btnRecommend, $script:btnNone)) { $b.Enabled = (-not $Busy) }
    Update-ActionState
}

function Start-Refresh {
    if ($script:Busy) { return }
    if ($script:RefreshHandle) { return }
    if ((-not $script:GameInfo) -or (-not $script:GameInfo.Valid)) { return }
    $ps = [powershell]::Create()
    # 结果装进一个对象里再取出：直接返回哈希表时，EndInvoke 给的是被引擎“拆包”的哈希表，.BaseObject 会被当成键名取到 $null
    $body = { param($core, $game, $byVariant) . ([scriptblock]::Create($core)); [pscustomobject]@{ Status = (Get-AllStatus -Game $game -ByVariant $byVariant) } }
    [void]$ps.AddScript($body.ToString())
    [void]$ps.AddArgument($CoreCode)
    [void]$ps.AddArgument($script:Game)
    [void]$ps.AddArgument($script:AllPacks)
    $script:RefreshPS = $ps
    $script:RefreshHandle = $ps.BeginInvoke()
    Set-StatusText '正在检测各组件的安装状态…'
    $script:pb.Visible = $true
}
function Set-GameRoot {
    param([string]$Path)
    $p = $Path.Trim().Trim('"').TrimEnd('\')
    $script:Game = $p
    $script:txtGame.Text = $p
    $script:GameInfo = Get-GameInfo $p $script:AnyManifest
    $script:Status = @{}
    Update-Info
    Update-List
    Show-Detail
    Update-ActionState
    if ($script:GameInfo.Valid) { Add-Log ('游戏目录：' + $p); Start-Refresh } else { Add-Log ('游戏目录不可用：' + $script:GameInfo.Message) }
}

function Test-GameReady {
    $script:StepBlocked = $true     # 下面任何一个 return $false 都算“被拦下”；全部通过再清掉
    if ((-not $script:GameInfo) -or (-not $script:GameInfo.Valid)) { [void](Show-Msg '还没有可用的游戏目录。请点“浏览”选择，或点“自动检测”。' '' 'OK' 'Warning'); return $false }
    if (-not $script:GameInfo.VersionOk) { [void](Show-Msg ($script:GameInfo.Message) '' 'OK' 'Warning'); return $false }
    if (@(Get-Process -Name 'Suzerain' -ErrorAction SilentlyContinue).Count -gt 0) {
        [void](Show-Msg '检测到游戏正在运行。请先退出游戏再操作（运行中替换文件可能失败或损坏）。' '' 'OK' 'Warning'); return $false
    }
    if ($script:RefreshHandle) { [void](Show-Msg '正在检测安装状态，请几秒后再试。' '' 'OK' 'Information'); return $false }
    $script:StepBlocked = $false
    return $true
}
function Start-Run {
    param($Tasks)
    $script:Queue = New-Object System.Collections.ArrayList
    foreach ($t in $Tasks) { [void]$script:Queue.Add($t) }
    $script:RunFailed = $false
    $script:Run = $null
    $script:Busy = $true
    Set-BusyUi $true
    Set-StatusText '正在执行，请不要关闭本窗口…'
}
function Complete-Run {
    $script:Busy = $false
    Set-BusyUi $false
    $script:pb.Visible = $false
    if ($script:RunFailed) {
        Add-Log '[提示] 有步骤失败，请看上面的日志。如果提示“拒绝访问 / Access denied”，请右键「启动安装器.bat」→ 以管理员身份运行；需要时可以在 Steam 里“验证游戏文件完整性”回到原版。'
        Set-StatusText '有步骤失败，详见日志'
    } else {
        Add-Log '[完成] 全部步骤已执行。'
        Set-StatusText '就绪'
    }
    Start-Refresh
}
function Invoke-Tick {
    if ($script:RefreshHandle -and $script:RefreshHandle.IsCompleted) {
        $ps = $script:RefreshPS; $h = $script:RefreshHandle
        $script:RefreshPS = $null; $script:RefreshHandle = $null
        try {
            $res = $ps.EndInvoke($h)
            foreach ($e in $ps.Streams.Error) { Add-Log ('[状态检测错误] ' + $e.ToString()) }
            if (($res.Count -gt 0) -and ($res[0].Status -is [hashtable])) { $script:Status = $res[0].Status }
            else { Add-Log '[状态检测失败] 后台检测没有返回结果。' }
        } catch { Add-Log ('[状态检测失败] ' + $_.Exception.Message) }
        finally { $ps.Dispose() }
        if (-not $script:Busy) { $script:pb.Visible = $false; Set-StatusText '就绪' }
        Update-List; Show-Detail; Update-ActionState
    }
    if ($script:Busy) {
        if ($script:Run) {
            Read-ProcLines $script:Run { param($l) Add-ChildLine $l }
            if (Test-ProcDone $script:Run) {
                $code = $script:Run.Proc.ExitCode
                $t = $script:CurTask
                $script:Run.Proc.Dispose()
                $script:Run = $null
                if ($script:ChildFiles -gt 0) { Add-Log ('    （共处理 {0} 个文件，逐个文件的明细在日志文件里）' -f $script:ChildFiles) }
                if ($code -eq 0) { Add-Log ('[完成] {0}：{1}' -f $t.VerbText, $t.Title) }
                else {
                    Add-Log ('[失败] {0}：{1}（退出码 {2}）。后面的步骤已取消。' -f $t.VerbText, $t.Title, $code)
                    $script:Queue.Clear()
                    $script:RunFailed = $true
                }
            }
        }
        if (-not $script:Run) {
            if ($script:Queue.Count -gt 0) {
                $t = $script:Queue[0]
                $script:Queue.RemoveAt(0)
                $script:CurTask = $t
                $script:ChildFiles = 0
                Add-Log ''
                Add-Log ('[{0}] {1} …' -f $t.VerbText, $t.Title)
                try { $script:Run = Start-PackProcess $t $script:Game }
                catch { Add-Log ('[失败] 无法启动脚本：' + $_.Exception.Message); $script:Queue.Clear(); $script:RunFailed = $true }
            } else {
                Complete-Run
            }
        }
    }
}

function Format-PlanLines {
    param($Plan, [string]$Verb)
    $i = 0
    $lines = @()
    foreach ($v in $Plan.Run) {
        $i++
        $extra = ''
        if ($Plan.Added -contains $v) { $extra = '（自动加入）' }
        $lines += ('  {0}. {1}{2}' -f $i, $script:AllPacks[$v].Title, $extra)
    }
    return ($lines -join "`r`n")
}
function Invoke-InstallSelected {
    if ($script:Busy) { return }
    $sel = @(Get-CheckedVariants)
    if ($sel.Count -eq 0) { [void](Show-Msg '请先在列表里勾选要安装的组件。'); return }
    if (-not (Test-GameReady)) { return }
    $plan = Get-InstallPlan $script:AllPacks $script:Status $sel
    $blk = @(Get-PlanBlockers $script:AllPacks $script:Status $plan)
    if ($blk.Count -gt 0) { $script:StepBlocked = $true; [void](Show-Msg ($blk -join "`r`n`r`n") '无法安装' 'OK' 'Warning'); return }
    if ($plan.Run.Count -eq 0) { [void](Show-Msg '所选组件都已经是“已安装”状态，没有需要做的事。'); return }
    $text = "将按顺序安装：`r`n" + (Format-PlanLines $plan 'install') + "`r`n`r`n"
    $text += "每个组件安装前，会把被替换的游戏文件备份到 游戏目录\_patch_backup，并校验备份无误才覆盖；任何时候都可以在本程序里还原。`r`n"
    $hi = @($plan.Run | Where-Object { $script:AllPacks[$_].Risk -eq '高' })
    $mid = @($plan.Run | Where-Object { $script:AllPacks[$_].Risk -eq '中' })
    if ($hi.Count -gt 0) { $text += "`r`n注意：「" + (($hi | ForEach-Object { $script:AllPacks[$_].Title }) -join '」「') + "」是实验性的，风险高：改的是程序自带字符串表，做错游戏可能无法启动（可还原）。只在作者的一台机器上实测过部分界面，其余没有逐条验证。`r`n" }
    if ($mid.Count -gt 0) { $text += "`r`n注意：「" + (($mid | ForEach-Object { $script:AllPacks[$_].Title }) -join '」「') + "」有风险（见说明），只在作者的一台机器上实测过部分界面。`r`n" }
    if ((-not ($plan.Order -contains 'plus')) -and ($script:Status['plus']) -and ($script:Status['plus'].Code -ne 'installed') -and ($script:AllPacks.ContainsKey('plus'))) {
        $text += "`r`n提示：主汉化包还没安装；附加包只改各自负责的那部分。`r`n"
    }
    $text += "`r`n继续吗？"
    if ((Show-Msg $text '确认安装' 'YesNo' 'Question') -ne 'Yes') { return }
    Add-Log ''
    Add-Log ('==== 开始安装：' + (($plan.Run | ForEach-Object { $_ }) -join ' -> ') + ' ====')
    Start-Run @($plan.Run | ForEach-Object { New-Task $script:AllPacks[$_] 'install' })
}
function Invoke-RestoreVariants {
    param([string[]]$Variants, [string]$What)
    if ($script:Busy) { return }
    if (-not (Test-GameReady)) { return }
    $plan = Get-RestorePlan $script:AllPacks $script:Status $Variants
    if ($plan.Run.Count -eq 0) { [void](Show-Msg '所选组件当前都没有安装，没有需要还原的。'); return }
    $text = "将按顺序还原（先还原叠在上面的）：`r`n" + (Format-PlanLines $plan 'restore') + "`r`n`r`n"
    $text += "还原会把游戏文件换回安装前的备份（原版，或之前装过的旧版本）。备份在 游戏目录\_patch_backup，不会被删除。`r`n"
    if ($plan.Added.Count -gt 0) { $text += "`r`n其中带「自动加入」的是：它们叠在所选组件之上，必须先还原。`r`n" }
    $text += "`r`n继续吗？"
    if ((Show-Msg $text ('确认还原' + $What) 'YesNo' 'Question') -ne 'Yes') { return }
    Add-Log ''
    Add-Log ('==== 开始还原：' + (($plan.Run | ForEach-Object { $_ }) -join ' -> ') + ' ====')
    Start-Run @($plan.Run | ForEach-Object { New-Task $script:AllPacks[$_] 'restore' })
}
function Invoke-RestoreSelected {
    $sel = @(Get-CheckedVariants)
    if ($sel.Count -eq 0) { [void](Show-Msg '请先在列表里勾选要还原的组件。'); return }
    Invoke-RestoreVariants $sel ''
}
function Invoke-RestoreAll {
    $all = @($script:Status.Keys | Where-Object { $script:Status[$_].Installed -gt 0 })
    if ($all.Count -eq 0) { [void](Show-Msg '当前没有任何组件处于“已安装”状态。'); return }
    Invoke-RestoreVariants $all '（全部）'
}

function Open-Folder([string]$Path) {
    if (Test-Path -LiteralPath $Path) { [void][System.Diagnostics.Process]::Start('explorer.exe', '"' + $Path + '"') }
    else { [void](Show-Msg ('文件夹还不存在：' + $Path)) }
}

# ---- 自测：用同样的按钮处理函数跑一遍场景并截图（不弹窗）----
function Wait-Idle {
    $deadline = (Get-Date).AddMinutes(10)
    while (($script:Busy -or $script:RefreshHandle) -and ((Get-Date) -lt $deadline)) {
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 40
    }
    [System.Windows.Forms.Application]::DoEvents()
    if ($script:Busy -or $script:RefreshHandle) { $script:SelfTestFailed = $true; Add-Log '[自测] 等待超时' }
}
function Save-Shot {
    param([string]$Name)
    if (-not $ScreenshotDir) { return }
    [void][System.IO.Directory]::CreateDirectory($ScreenshotDir)
    [System.Windows.Forms.Application]::DoEvents()
    $bmp = New-Object System.Drawing.Bitmap($script:Form.Width, $script:Form.Height)
    $script:Form.DrawToBitmap($bmp, (New-Object System.Drawing.Rectangle(0, 0, $script:Form.Width, $script:Form.Height)))
    $bmp.Save((Join-Path $ScreenshotDir ($Name + '.png')), [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}
function Invoke-SelfTest {
    Wait-Idle
    Save-Shot 'step00_initial'
    $results = New-Object System.Collections.ArrayList
    [void]$results.Add([ordered]@{ step = 'initial'; ok = $true; status = (ConvertTo-StatusSnapshot $script:Status) })
    $n = 0
    foreach ($step in (Get-ScenarioSteps)) {
        $n++
        Add-Log ('[自测] 步骤 {0}: {1}' -f $n, $step.Text)
        $script:RunFailed = $false
        $script:StepBlocked = $false
        switch ($step.Verb) {
            'install'    { Set-Checked (Resolve-Variants $step.Arg); Invoke-InstallSelected }
            'restore'    { Set-Checked (Resolve-Variants $step.Arg); Invoke-RestoreSelected }
            'restoreall' { Invoke-RestoreAll }
            'status'     { Start-Refresh }
        }
        Wait-Idle
        Save-Shot ('step{0:00}_{1}' -f $n, ($step.Text -replace '[^A-Za-z0-9]+', '_'))
        [void]$results.Add([ordered]@{ step = $step.Text; ok = ((-not $script:RunFailed) -and (-not $script:StepBlocked)); blocked = $script:StepBlocked; status = (ConvertTo-StatusSnapshot $script:Status) })
    }
    Save-OutJson ([ordered]@{ game = $script:Game; ok = (-not $script:SelfTestFailed); steps = @($results) })
    $script:Form.Close()
}

# ---- 窗口 ----
function New-Btn {
    param([string]$Text, [int]$Width = 112)
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $Text
    $b.Size = New-Object System.Drawing.Size((Px $Width), (Px 32))
    $b.Margin = New-Object System.Windows.Forms.Padding(0, 0, (Px 8), 0)
    $b.UseVisualStyleBackColor = $true
    return $b
}
function Show-Gui {
    $fontUi = New-Object System.Drawing.Font('Microsoft YaHei UI', 9)
    $fontMono = New-Object System.Drawing.Font('Consolas', 9)
    $script:Form = New-Object System.Windows.Forms.Form
    $form = $script:Form
    $form.Text = 'Suzerain 汉化安装器'
    $form.Font = $fontUi
    $form.StartPosition = 'CenterScreen'
    # 窗口大小不超过当前屏幕的可用区域（小屏 / 高缩放比例的笔记本也能完整看到按钮）
    $wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $fw = [Math]::Min((Px 1040), ($wa.Width - 24))
    $fh = [Math]::Min((Px 800), ($wa.Height - 56))
    $mw = [Math]::Min((Px 900), $fw)
    $mh = [Math]::Min((Px 640), $fh)
    $form.ClientSize = New-Object System.Drawing.Size($fw, $fh)
    $form.MinimumSize = New-Object System.Drawing.Size($mw, $mh)
    if ($SelfTest -or $Offscreen) {
        $form.StartPosition = 'Manual'
        $form.Location = New-Object System.Drawing.Point(-3000, -3000)
        $form.ShowInTaskbar = $false
    }

    $root = New-Object System.Windows.Forms.TableLayoutPanel
    $root.Dock = 'Fill'
    $root.ColumnCount = 1
    $root.RowCount = 6
    $root.Padding = New-Object System.Windows.Forms.Padding((Px 10))
    [void]$root.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('Percent', 100)))
    [void]$root.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', (Px 92))))
    [void]$root.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', (Px 40))))
    [void]$root.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Percent', 38)))
    [void]$root.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', (Px 150))))
    [void]$root.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', (Px 46))))
    [void]$root.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Percent', 62)))

    # -- 游戏目录
    $grp = New-Object System.Windows.Forms.GroupBox
    $grp.Text = '游戏目录'
    $grp.Dock = 'Fill'
    $tl = New-Object System.Windows.Forms.TableLayoutPanel
    $tl.Dock = 'Fill'
    $tl.ColumnCount = 3
    $tl.RowCount = 2
    $tl.Padding = New-Object System.Windows.Forms.Padding((Px 6), (Px 2), (Px 6), 0)
    [void]$tl.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('Percent', 100)))
    [void]$tl.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('AutoSize')))
    [void]$tl.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle('AutoSize')))
    [void]$tl.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Absolute', (Px 34))))
    [void]$tl.RowStyles.Add((New-Object System.Windows.Forms.RowStyle('Percent', 100)))
    $script:txtGame = New-Object System.Windows.Forms.TextBox
    $script:txtGame.Dock = 'Fill'
    $script:txtGame.Margin = New-Object System.Windows.Forms.Padding(0, (Px 4), (Px 8), 0)
    $script:btnBrowse = New-Btn '浏览…' 90
    $script:btnBrowse.Margin = New-Object System.Windows.Forms.Padding(0, (Px 1), (Px 8), 0)
    $script:btnDetect = New-Btn '自动检测' 100
    $script:btnDetect.Margin = New-Object System.Windows.Forms.Padding(0, (Px 1), 0, 0)
    $script:lblInfo = New-Object System.Windows.Forms.Label
    $script:lblInfo.Dock = 'Fill'
    $script:lblInfo.TextAlign = 'MiddleLeft'
    $script:lblInfo.Text = ''
    [void]$tl.Controls.Add($script:txtGame, 0, 0)
    [void]$tl.Controls.Add($script:btnBrowse, 1, 0)
    [void]$tl.Controls.Add($script:btnDetect, 2, 0)
    [void]$tl.Controls.Add($script:lblInfo, 0, 1)
    $tl.SetColumnSpan($script:lblInfo, 3)
    $grp.Controls.Add($tl)

    # -- 预设按钮行
    $fp1 = New-Object System.Windows.Forms.FlowLayoutPanel
    $fp1.Dock = 'Fill'
    $fp1.WrapContents = $false
    $lbl = New-Object System.Windows.Forms.Label
    $lbl.Text = '勾选要安装 / 还原的组件：'
    $lbl.AutoSize = $true
    $lbl.Margin = New-Object System.Windows.Forms.Padding(0, (Px 9), (Px 16), 0)
    $script:btnRecommend = New-Btn '推荐组合' 96
    $script:btnAll = New-Btn '全选' 70
    $script:btnNone = New-Btn '清空' 70
    foreach ($c in @($lbl, $script:btnRecommend, $script:btnAll, $script:btnNone)) { [void]$fp1.Controls.Add($c) }
    $lblHint = New-Object System.Windows.Forms.Label
    $lblHint.Text = '推荐组合 = 主汉化包 + 地图中文标注包 + 战争教程图片包（风险低的三项）'
    $lblHint.AutoSize = $true
    $lblHint.ForeColor = [System.Drawing.Color]::DimGray
    $lblHint.Margin = New-Object System.Windows.Forms.Padding((Px 8), (Px 9), 0, 0)
    [void]$fp1.Controls.Add($lblHint)

    # -- 组件列表
    $script:lv = New-Object System.Windows.Forms.ListView
    $script:lv.Dock = 'Fill'
    $script:lv.View = 'Details'
    $script:lv.CheckBoxes = $true
    $script:lv.FullRowSelect = $true
    $script:lv.GridLines = $true
    $script:lv.HideSelection = $false
    $script:lv.MultiSelect = $false
    [void]$script:lv.Columns.Add('组件', (Px 190))
    [void]$script:lv.Columns.Add('状态', (Px 210))
    [void]$script:lv.Columns.Add('风险', (Px 50))
    [void]$script:lv.Columns.Add('文件', (Px 50))
    [void]$script:lv.Columns.Add('备份', (Px 50))
    [void]$script:lv.Columns.Add('简介', (Px 520))

    # -- 说明
    $script:txtDetail = New-Object System.Windows.Forms.TextBox
    $script:txtDetail.Dock = 'Fill'
    $script:txtDetail.Multiline = $true
    $script:txtDetail.ReadOnly = $true
    $script:txtDetail.ScrollBars = 'Vertical'
    $script:txtDetail.BackColor = [System.Drawing.SystemColors]::Window

    # -- 操作按钮
    $fp2 = New-Object System.Windows.Forms.FlowLayoutPanel
    $fp2.Dock = 'Fill'
    $fp2.WrapContents = $false
    $fp2.Padding = New-Object System.Windows.Forms.Padding(0, (Px 6), 0, 0)
    $script:btnInstall = New-Btn '安装所选' 120
    $script:btnRestore = New-Btn '还原所选' 120
    $script:btnRestoreAll = New-Btn '全部还原' 110
    $script:btnRefresh = New-Btn '刷新状态' 100
    $script:btnBackup = New-Btn '打开备份文件夹' 140
    $script:btnLog = New-Btn '打开日志文件夹' 140
    $script:btnHelp = New-Btn '帮助' 70
    foreach ($c in @($script:btnInstall, $script:btnRestore, $script:btnRestoreAll, $script:btnRefresh, $script:btnBackup, $script:btnLog, $script:btnHelp)) { [void]$fp2.Controls.Add($c) }
    $script:pb = New-Object System.Windows.Forms.ProgressBar
    $script:pb.Style = 'Marquee'
    $script:pb.MarqueeAnimationSpeed = 30
    $script:pb.Size = New-Object System.Drawing.Size((Px 120), (Px 14))
    $script:pb.Margin = New-Object System.Windows.Forms.Padding((Px 12), (Px 9), 0, 0)
    $script:pb.Visible = $false
    [void]$fp2.Controls.Add($script:pb)

    # -- 日志
    $script:txtLog = New-Object System.Windows.Forms.TextBox
    $script:txtLog.Dock = 'Fill'
    $script:txtLog.Multiline = $true
    $script:txtLog.ReadOnly = $true
    $script:txtLog.ScrollBars = 'Both'
    $script:txtLog.WordWrap = $false
    $script:txtLog.Font = $fontMono
    $script:txtLog.BackColor = [System.Drawing.SystemColors]::Window

    [void]$root.Controls.Add($grp, 0, 0)
    [void]$root.Controls.Add($fp1, 0, 1)
    [void]$root.Controls.Add($script:lv, 0, 2)
    [void]$root.Controls.Add($script:txtDetail, 0, 3)
    [void]$root.Controls.Add($fp2, 0, 4)
    [void]$root.Controls.Add($script:txtLog, 0, 5)

    $ss = New-Object System.Windows.Forms.StatusStrip
    $script:lblStatus = New-Object System.Windows.Forms.ToolStripStatusLabel
    $script:lblStatus.Text = '就绪'
    [void]$ss.Items.Add($script:lblStatus)
    $lblVer = New-Object System.Windows.Forms.ToolStripStatusLabel
    $lblVer.Text = ('版本 ' + $script:Version + '   找到 ' + $script:AllPacks.Count + ' 个组件')
    $lblVer.Alignment = 'Right'
    $lblVer.Spring = $true
    $lblVer.TextAlign = 'MiddleRight'
    [void]$ss.Items.Add($lblVer)
    $form.Controls.Add($root)
    $form.Controls.Add($ss)

    # -- 事件
    $script:btnBrowse.Add_Click({ Invoke-Safe {
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = '选择 Suzerain 游戏文件夹（里面有 Suzerain.exe）'
        if ($script:Game -and (Test-Path -LiteralPath $script:Game)) { $dlg.SelectedPath = $script:Game }
        if ($dlg.ShowDialog($script:Form) -eq 'OK') { Set-GameRoot $dlg.SelectedPath }
    } })
    $script:btnDetect.Add_Click({ Invoke-Safe {
        $c = @(Find-GameCandidates $script:AppId)
        if ($c.Count -eq 0) { [void](Show-Msg '没有在 Steam 的库里找到 Suzerain。请点“浏览”手动选择游戏文件夹。' '' 'OK' 'Warning'); return }
        if ($c.Count -gt 1) { Add-Log ('检测到多个安装，使用第一个；其余：' + ($c[1..($c.Count - 1)] -join '；')) }
        Set-GameRoot $c[0]
    } })
    $script:txtGame.Add_Leave({ Invoke-Safe {
        if ($script:txtGame.Text.Trim().Trim('"').TrimEnd('\') -ne $script:Game) { Set-GameRoot $script:txtGame.Text }
    } })
    $script:btnRecommend.Add_Click({ Invoke-Safe { Set-Checked @('plus', 'maplabels', 'tutorialimg') } })
    $script:btnAll.Add_Click({ Invoke-Safe { Set-Checked @($script:AllPacks.Keys) } })
    $script:btnNone.Add_Click({ Invoke-Safe { Set-Checked @() } })
    $script:lv.Add_SelectedIndexChanged({ Invoke-Safe { Show-Detail } })
    $script:btnInstall.Add_Click({ Invoke-Safe { Invoke-InstallSelected } })
    $script:btnRestore.Add_Click({ Invoke-Safe { Invoke-RestoreSelected } })
    $script:btnRestoreAll.Add_Click({ Invoke-Safe { Invoke-RestoreAll } })
    $script:btnRefresh.Add_Click({ Invoke-Safe { Set-GameRoot $script:Game } })
    $script:btnBackup.Add_Click({ Invoke-Safe { Open-Folder (Join-Path $script:Game '_patch_backup') } })
    $script:btnLog.Add_Click({ Invoke-Safe { Open-Folder (Split-Path -Parent $script:LogFile) } })
    $script:btnHelp.Add_Click({ Invoke-Safe {
        [void](Show-Msg ("使用方法：`r`n1. 关闭游戏。`r`n2. 勾选要安装的组件（第一次建议只装「主汉化包」，进游戏确认正常后再逐个加）。`r`n3. 点「安装所选」。`r`n" +
            "4. 不想要了：勾选对应组件，点「还原所选」；想全部回到原版，点「全部还原」。`r`n`r`n" +
            "安装前会备份被替换的文件到 游戏目录\_patch_backup，备份校验无误才覆盖。游戏被 Steam 更新后补丁会失效：先在 Steam 里「验证游戏文件完整性」，再重新安装。`r`n`r`n" +
            "日志保存在：" + (Split-Path -Parent $script:LogFile)) '帮助')
    } })
    $form.Add_FormClosing({
        param($s, $e)
        if ($script:Busy) { $e.Cancel = $true; [void][System.Windows.Forms.MessageBox]::Show('正在安装 / 还原，请等它完成后再关闭（中途关闭可能留下写了一半的文件）。', '请稍等', 'OK', 'Warning') }
    })
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 150
    $timer.Add_Tick({ Invoke-Safe { Invoke-Tick } })
    $timer.Start()
    $form.Add_Shown({ Invoke-Safe {
        Add-Log ('Suzerain 汉化安装器 ' + $script:Version + '；找到 ' + $script:AllPacks.Count + ' 个组件：' + ((@($script:AllPacks.Values | Sort-Object Order | ForEach-Object { $_.Title })) -join '、'))
        Add-Log ('日志文件：' + $script:LogFile)
        if ($script:AllPacks.Count -eq 0) {
            [void](Show-Msg '没有找到任何汉化包。请把 Suzerain_CN_Plus_* 文件夹放在本安装器旁边，或放进本文件夹下的 packs 子文件夹。' '' 'OK' 'Warning')
        }
        if ($script:Game) { Set-GameRoot $script:Game }
        else {
            $script:GameInfo = Get-GameInfo '' $script:AnyManifest
            Update-Info; Update-List; Update-ActionState
            Add-Log '没有自动找到游戏，请点“浏览”选择游戏文件夹。'
        }
        if (($script:Game) -and ($script:GameInfo.Valid) -and (-not $SelfTest)) {
            # 第一次打开：还没装主包时默认勾上它
            Set-Checked @('plus')
        }
        if ($SelfTest) { Invoke-SelfTest }
    } })
    [void]$form.ShowDialog()
    $timer.Stop()
    $timer.Dispose()
}

try {
    Show-Gui
} catch {
    $m = $_.Exception.Message + "`r`n" + $_.ScriptStackTrace
    Write-LogFile ('[致命错误] ' + $m)
    try { [void][System.Windows.Forms.MessageBox]::Show($m, 'Suzerain 汉化安装器 出错了', 'OK', 'Error') } catch {}
    exit 1
}
if ($SelfTest -and $script:SelfTestFailed) { exit 1 }
exit 0
