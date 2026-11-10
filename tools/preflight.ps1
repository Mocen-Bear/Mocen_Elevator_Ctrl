# tools/preflight.ps1 - 本机自检：仓库是否还处于"能演示"的状态
# 用法：powershell -ExecutionPolicy Bypass -File .\tools\preflight.ps1
# 不联网、不依赖额外模块；有任何一项失败就返回退出码 1。

[CmdletBinding()]
param(
    [string]$RepoRoot = ''
)

if (-not $RepoRoot) {
    $here = $PSScriptRoot
    if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
    $RepoRoot = Split-Path -Parent $here
}

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $RepoRoot

$script:failed = 0
function Ok($msg)   { Write-Host ("  [ok]   " + $msg) -ForegroundColor Green }
function Bad($msg)  { Write-Host ("  [FAIL] " + $msg) -ForegroundColor Red; $script:failed++ }
function Warn($msg) { Write-Host ("  [warn] " + $msg) -ForegroundColor Yellow }
function Head($msg) { Write-Host ""; Write-Host $msg -ForegroundColor Cyan }

Write-Host "preflight: $RepoRoot"

# ---------------------------------------------------------------- 1) 目录与关键文件
Head "1) 目录与关键文件"

$requiredDirs = @('android', 'docs', 'firmware', 'mech', 'media', 'packages', 'preview', 'releases', 'tools')
foreach ($d in $requiredDirs) {
    if (Test-Path -LiteralPath $d -PathType Container) { Ok "$d/" } else { Bad "缺目录 $d/" }
}

$requiredFiles = @(
    'README.md',
    'CHANGELOG.md',
    'docs/README.md',
    'docs/BLE_PROTOCOL.md',
    'docs/API.md',
    'docs/SHAFT_MODEL.md',
    'docs/HANDOVER.md',
    'firmware/elevator_1F/elevator_1F.ino',
    'firmware/elevator_2F/elevator_2F.ino',
    'firmware/chime_node/chime_node.ino',
    'android/app/src/main/java/com/mocen/elevator/MainActivity.kt',
    'preview/index.html'
)
foreach ($f in $requiredFiles) {
    if (Test-Path -LiteralPath $f -PathType Leaf) { Ok $f } else { Bad "缺文件 $f" }
}

# ---------------------------------------------------------------- 2) 楼层常量
Head "2) 楼层常量（固件 / App 必须一致）"

function Read-Text($p) { Get-Content -LiteralPath $p -Raw -Encoding UTF8 }

foreach ($pair in @(
        @('firmware/elevator_1F/elevator_1F.ino', '1F'),
        @('firmware/elevator_2F/elevator_2F.ino', '2F'))) {
    $p, $want = $pair
    if (-not (Test-Path -LiteralPath $p)) { continue }
    $m = [regex]::Match((Read-Text $p), 'FLOOR_NAME\s+"([^"]+)"')
    if (-not $m.Success) { Bad "$p 里找不到 FLOOR_NAME" }
    elseif ($m.Groups[1].Value -ne $want) { Bad "$p 的 FLOOR_NAME = $($m.Groups[1].Value)，应为 $want" }
    else { Ok "$p FLOOR_NAME = $want" }
}

$main = 'android/app/src/main/java/com/mocen/elevator/MainActivity.kt'
if (Test-Path -LiteralPath $main) {
    $src = Read-Text $main
    $shaft = [regex]::Match($src, 'shaftFloors\s*=\s*listOf\(([^)]*)\)')
    $dev   = [regex]::Match($src, 'deviceFloors\s*=\s*listOf\(([^)]*)\)')
    if (-not $shaft.Success) { Bad "MainActivity.kt 里找不到 shaftFloors" }
    elseif ($shaft.Groups[1].Value -notmatch '"B"') { Bad ("shaftFloors 应为 B/1F/2F/3F，实际 " + $shaft.Groups[1].Value) }
    else { Ok ("shaftFloors = " + $shaft.Groups[1].Value) }

    if (-not $dev.Success) { Bad "MainActivity.kt 里找不到 deviceFloors" }
    elseif ($dev.Groups[1].Value -notmatch '"1F"' -or $dev.Groups[1].Value -notmatch '"2F"') { Bad ("deviceFloors 应为 1F/2F，实际 " + $dev.Groups[1].Value) }
    else { Ok ("deviceFloors = " + $dev.Groups[1].Value) }
}

# ---------------------------------------------------------------- 3) 旧楼层残留
Head "3) 旧楼层残留"

$stale = @('elevator_3' + 'F', 'ELEV-3' + 'F', 'elevator_4' + 'F', 'ELEV-4' + 'F')
$scanExt = @('.md', '.kt', '.ino', '.html', '.ps1', '.py', '.swift', '.json', '.yml', '.txt')
$hits = @()
Get-ChildItem -LiteralPath . -Recurse -File -Force |
    Where-Object { $scanExt -contains $_.Extension -and $_.FullName -notmatch '[\\/]\.git[\\/]' } |
    ForEach-Object {
        $text = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        if (-not $text) { return }
        foreach ($s in $stale) {
            if ($text.Contains($s)) { $hits += (($_.FullName.Substring((Get-Location).Path.Length + 1)) + " -> " + $s) }
        }
    }

if ($hits.Count -eq 0) {
    Ok "没有 elevator_3F / ELEV-3F / *_4F 之类的旧楼层引用"
} else {
    foreach ($h in $hits) { Warn $h }
    Bad ("旧楼层引用 " + $hits.Count + " 处")
}

# ---------------------------------------------------------------- 4) 文档链接
Head "4) 文档相对链接"

$py = $null
foreach ($cand in @('py', 'python')) {
    $c = Get-Command $cand -ErrorAction SilentlyContinue
    if ($c -and $c.Source -and $c.Source -notmatch 'WindowsApps') { $py = $c.Source; break }
}
if ($py) {
    & $py 'tools/check_links.py'
    if ($LASTEXITCODE -eq 0) { Ok "Markdown 相对链接全部有效" } else { Bad "有失效的 Markdown 链接" }
} else {
    Warn "本机没有可用的 python，跳过链接检查（CI 的 doc-links 会跑这一项）"
}

# ---------------------------------------------------------------- 5) 成品固件
Head "5) 成品固件"

foreach ($bin in @('releases/firmware/elevator_1F.merged.bin', 'releases/firmware/elevator_2F.merged.bin')) {
    if (Test-Path -LiteralPath $bin -PathType Leaf) { Ok $bin } else { Warn "缺 $bin（不影响源码，可直接用 arduino-cli 编）" }
}

# ---------------------------------------------------------------- 结果
Write-Host ""
if ($script:failed -eq 0) {
    Write-Host "preflight: 全部通过" -ForegroundColor Green
    exit 0
} else {
    Write-Host ("preflight: " + $script:failed + " 项失败") -ForegroundColor Red
    exit 1
}
