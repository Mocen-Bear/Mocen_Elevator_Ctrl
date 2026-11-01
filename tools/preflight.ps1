# ============================================================================
#  preflight.ps1 - pre-demo sanity check (one command, no dependencies)
# ----------------------------------------------------------------------------
#  Usage:
#     powershell -ExecutionPolicy Bypass -File .\preflight.ps1
#     powershell -ExecutionPolicy Bypass -File .\preflight.ps1 -Compile   (slower)
#
#  What it checks:
#    1. every preview page the demo needs exists
#    2. every package folder matches its .zip BYTE FOR BYTE (extract + SHA-256)
#    3. the main package copies still match the source docs (hashes)
#    4. the Android APK is NOT older than the sources (stale-APK trap)
#    5. firmware floor names + button pins + servo angles + timing are the agreed ones
#    6. stale leftovers: any "ELEV-1F" anywhere, two versions of one package on disk, orphan zips
#    7. (with -Compile) both elevator sketches + the chime node still compile
#
#  Exit code 0 = all green, 1 = at least one FAIL. WARN alone does not fail.
# ============================================================================
param([switch]$Compile)

$ErrorActionPreference = 'Continue'
$root = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
Set-Location -LiteralPath $root

$script:Pass = 0; $script:Fail = 0; $script:Warn = 0
function Ok  ($m) { $script:Pass++; Write-Host ("  [ OK ] " + $m) }
function Bad ($m) { $script:Fail++; Write-Host ("  [FAIL] " + $m) -ForegroundColor Red }
function Wrn ($m) { $script:Warn++; Write-Host ("  [WARN] " + $m) -ForegroundColor Yellow }
function Head($m) { Write-Host ""; Write-Host ("== " + $m) -ForegroundColor Cyan }

function Sha16($p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.Substring(0, 16) }
function Read-Text($p) { Get-Content -LiteralPath $p -Raw -Encoding UTF8 }
function Bytes($n) { if ($n -ge 1MB) { "{0:N2} MB" -f ($n / 1MB) } else { "{0:N0} B" -f $n } }

Write-Host ""
Write-Host "PRE-DEMO PREFLIGHT" -ForegroundColor White
Write-Host ("repo: " + $root)
Write-Host ("time: " + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))

# ---------------------------------------------------------------- 1) preview
Head "1) Preview pages (what you open on stage)"
$pv = Join-Path $root 'preview'
$expected = @(
  'index.html', 'deck.html', 'storyboard.html',
  'elevator_ui_preview.html', 'elevator_3d_preview.html',
  'floor_display_reader.html', 'rssi_floor_sim.html', 'chime_calib.html',
  'ble_console.html', 'teammate_app_mock.html', 'monitor_live.html'
)
# Check EVERY .html that is actually on disk (so a newly added page is covered automatically),
# and ALSO the must-exist list (a glob alone would not notice a page being deleted).
$found = @(Get-ChildItem -LiteralPath $pv -Filter *.html -File | Sort-Object Name)
$foundNames = @($found | ForEach-Object { $_.Name })
$missing = @($expected | Where-Object { $foundNames -notcontains $_ })
foreach ($f in $found) { Ok ("preview/{0}   {1}" -f $f.Name, (Bytes $f.Length)) }
foreach ($m in $missing) { Bad ("preview/{0}   MISSING - a page the demo needs is gone" -f $m) }

# ------------------------------------------------- 2) packages: folder vs zip
Head "2) Packages: folder vs .zip, byte for byte"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zips = Get-ChildItem -LiteralPath $root -Filter '*_v*.zip' -File
if (-not $zips) { Bad "no *_v*.zip found in repo root" }
foreach ($z in $zips) {
  $dirName = $z.Name -replace '_v[\d\.]+\.zip$', ''
  $dir = Join-Path $root $dirName
  if (-not (Test-Path -LiteralPath $dir)) { Bad ("{0}: no folder named '{1}'" -f $z.Name, $dirName); continue }
  $tmp = Join-Path $env:TEMP ('preflight_' + [guid]::NewGuid().ToString('N'))
  $problems = @()
  try {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($z.FullName, $tmp)
    # Compare by RELATIVE PATH, not by file name: a package may legitimately hold many
    # same-named files (项目资料/ ships a whole git repo -> several _版本信息.md + a .git tree).
    # -Force so hidden entries (.git\**, .gitignore) are enumerated on both sides.
    $zipRoot = $tmp
    $topDirs = @(Get-ChildItem -LiteralPath $tmp -Directory -Force)
    $topFiles = @(Get-ChildItem -LiteralPath $tmp -File -Force)
    if ($topDirs.Count -eq 1 -and $topFiles.Count -eq 0) { $zipRoot = $topDirs[0].FullName }
    $zLen = $zipRoot.TrimEnd('\').Length
    $inZip = @(Get-ChildItem -LiteralPath $zipRoot -Recurse -File -Force)
    $zipMap = @{}
    foreach ($e in $inZip) { $zipMap[$e.FullName.Substring($zLen).TrimStart('\')] = (Sha16 $e.FullName) }
    $dLen = $dir.TrimEnd('\').Length
    $folderFiles = @(Get-ChildItem -LiteralPath $dir -Recurse -File -Force)
    $folderMap = @{}
    foreach ($f in $folderFiles) { $folderMap[$f.FullName.Substring($dLen).TrimStart('\')] = (Sha16 $f.FullName) }
    foreach ($k in @($folderMap.Keys)) {
      if (-not $zipMap.ContainsKey($k)) { $problems += ("missing from the zip: " + $k); continue }
      if ($zipMap[$k] -ne $folderMap[$k]) { $problems += ("content differs: " + $k) }
    }
    foreach ($k in @($zipMap.Keys)) {
      if (-not $folderMap.ContainsKey($k)) { $problems += ("in the zip but not in the folder: " + $k) }
    }
    $nested = if ($zipRoot -ne $tmp) { "  [zip keeps a top folder - fine]" } else { "" }
    if ($problems.Count -eq 0) { Ok ("{0}   {1} file(s), {2}{3}" -f $z.Name, $folderFiles.Count, (Bytes $z.Length), $nested) }
    else {
      $shown = ($problems | Select-Object -First 8) -join ' | '
      $more = if ($problems.Count -gt 8) { " ... (+" + ($problems.Count - 8) + " more)" } else { "" }
      Bad (("{0} -> " -f $z.Name) + $shown + $more)
    }
  } catch {
    Bad (("{0}: " -f $z.Name) + $_.Exception.Message)
  } finally {
    if (Test-Path -LiteralPath $tmp) { Remove-Item -Recurse -Force -LiteralPath $tmp }
  }
}

# ------------------------------------ 3) main package copies still match source
Head "3) Source docs vs the copies inside the packages"
# ASCII-only predicate (PowerShell 5.1 reads BOM-less UTF-8 as ANSI, so no CJK
# literals here): a package folder is a folder holding a cover file named "_*".
$pkgDirs = @(Get-ChildItem -LiteralPath $root -Directory | Where-Object {
  @(Get-ChildItem -LiteralPath $_.FullName -File | Where-Object { $_.Name -like '_*' }).Count -gt 0
})
foreach ($doc in @('HANDOVER.md', 'BLE_PROTOCOL.md', 'NAV_APP_UI_SPEC.md', 'SHAFT_MODEL.md', 'API.md', 'IOS_INTEGRATION.md')) {
  $src = Join-Path $root $doc
  if (-not (Test-Path -LiteralPath $src)) { Bad ("$doc is missing at the repo root"); continue }
  $found = @()
  foreach ($d in $pkgDirs) {
    $cp = Join-Path $d.FullName $doc
    if (Test-Path -LiteralPath $cp) { $found += @{ Dir = $d.Name; Path = $cp } }
  }
  if ($found.Count -eq 0) { Wrn ("$doc is not inside any package (fine if it is not shipped)") ; continue }
  foreach ($f in $found) {
    if ((Sha16 $src) -eq (Sha16 $f.Path)) { Ok ("{0} == {1}/{0}   {2}" -f $doc, $f.Dir, (Sha16 $src)) }
    else { Bad ("{0} DIFFERS from {1}/{0}  (source {2} vs package {3})" -f $doc, $f.Dir, (Sha16 $src), (Sha16 $f.Path)) }
  }
}

# 3b) any web page shipped inside a package must be byte-identical to preview\<same name>
# (the 3D shaft page in 发给队友 is a copy of preview/monitor_live.html - keep them in sync)
$genHtml = @('代码浏览_离线版.html')   # generated single-file code bundle - not a copy of a preview page
foreach ($d in $pkgDirs) {
  foreach ($h in @(Get-ChildItem -LiteralPath $d.FullName -File -Filter '*.html')) {
    if ($genHtml -contains $h.Name) {
      Ok ("{0}/{1}: generated offline bundle, not a preview copy - skipped" -f $d.Name, $h.Name)
      continue
    }
    $src = Join-Path (Join-Path $root 'preview') $h.Name
    if (-not (Test-Path -LiteralPath $src)) {
      Wrn ("{0}/{1}: no source under preview\ - not checked" -f $d.Name, $h.Name)
    } elseif ((Sha16 $src) -eq (Sha16 $h.FullName)) {
      Ok ("preview/{0} == {1}/{0}   {2}" -f $h.Name, $d.Name, (Sha16 $src))
    } else {
      Bad ("{0}/{1} DIFFERS from preview\{1}  (source {2} vs package {3})" -f $d.Name, $h.Name, (Sha16 $src), (Sha16 $h.FullName))
    }
  }
}

# ------------------------------------------------------ 4) APK freshness trap
Head "4) Android APK is newer than the sources (stale-APK trap)"
$apk = Join-Path $root 'android\app\build\outputs\apk\debug\app-debug.apk'
if (-not (Test-Path -LiteralPath $apk)) {
  Bad "app-debug.apk not built yet -> android: gradle assembleDebug"
} else {
  $apkItem = Get-Item -LiteralPath $apk
  $srcRoot = Join-Path $root 'android\app\src'
  $newer = @()
  if (Test-Path -LiteralPath $srcRoot) {
    $newer = @(Get-ChildItem -LiteralPath $srcRoot -Recurse -File | Where-Object { $_.LastWriteTime -gt $apkItem.LastWriteTime })
  }
  foreach ($g in @('build.gradle', 'app\build.gradle', 'settings.gradle')) {
    $gp = Join-Path $root (Join-Path 'android' $g)
    if ((Test-Path -LiteralPath $gp) -and ((Get-Item -LiteralPath $gp).LastWriteTime -gt $apkItem.LastWriteTime)) {
      $newer += (Get-Item -LiteralPath $gp)
    }
  }
  if ($newer.Count -gt 0) {
    Bad ("APK ({0}, built {1}) is OLDER than {2} source file(s), e.g. {3} -> rebuild: gradle assembleDebug" -f `
      (Bytes $apkItem.Length), $apkItem.LastWriteTime.ToString('MM-dd HH:mm'), $newer.Count, $newer[0].Name)
  } else {
    Ok ("app-debug.apk   {0}, built {1}  (newer than all sources)" -f (Bytes $apkItem.Length), $apkItem.LastWriteTime.ToString('MM-dd HH:mm'))
  }
}

# ------------------------------------------------------ 5) firmware constants
Head "5) Firmware constants (floor name / pins / timing)"
$fw = Join-Path $root 'firmware'
$expect = @(
  @{ Name = 'elevator_2F'; Floor = '2F' },
  @{ Name = 'elevator_3F'; Floor = '3F' }
)
foreach ($e in $expect) {
  $ino = Join-Path $fw ($e.Name + '\' + $e.Name + '.ino')
  if (-not (Test-Path -LiteralPath $ino)) { Bad ("firmware\{0}\{0}.ino missing" -f $e.Name); continue }
  $t = Read-Text $ino
  $bad = @()
  if ($t -notmatch ('FLOOR_NAME\s+"' + $e.Floor + '"')) { $bad += ('FLOOR_NAME != "' + $e.Floor + '"') }
  if ($t -notmatch 'UP_PIN\s+13')   { $bad += 'UP_PIN != 13 (D13)' }
  if ($t -notmatch 'DOWN_PIN\s+12') { $bad += 'DOWN_PIN != 12 (D12)' }
  if ($t -notmatch 'ANGLE_REST\s+90')   { $bad += 'ANGLE_REST != 90' }
  if ($t -notmatch 'ANGLE_PRESS\s+100') { $bad += 'ANGLE_PRESS != 100' }
  if ($t -notmatch 'SWEEP_MS\s+350') { $bad += 'SWEEP_MS != 350' }
  if ($t -notmatch 'HOLD_MS\s+600')  { $bad += 'HOLD_MS != 600' }
  if ($bad.Count -eq 0) { Ok ("{0}: FLOOR_NAME={1}, D13=UP, D12=DOWN, 90->100 deg, 350/600 ms" -f $e.Name, $e.Floor) }
  else { Bad (("{0}: " -f $e.Name) + ($bad -join ' | ')) }
}
$chime = Join-Path $fw 'chime_node\chime_node.ino'
if (Test-Path -LiteralPath $chime) {
  $ct = Read-Text $chime
  if ($ct -match 'FREQ_HI_HZ\s+1900') { Ok "chime_node: FREQ_HI_HZ = 1900 (not the invalid 5200)" }
  else { Wrn "chime_node: FREQ_HI_HZ is not 1900 - re-check the Nyquist note" }
} else { Wrn "chime_node sketch not found (optional add-on)" }

# ------------------------------------------------------------- 6) stale junk
Head "6) Stale leftovers"
$skip = '\\(build|\.gradle|\.idea|node_modules|\.git)\\'
$self = 'preflight.ps1'                     # this file quotes the forbidden string on purpose
# 代码浏览_离线版.html is a GENERATED single-file bundle: it embeds every doc of the repo,
# including the "a wrong device name must not ship" notes themselves. Every file it embeds is
# scanned on its own, so excluding this one from the code scan loses nothing.
# In CODE the device name "ELEV-1F" must never appear -> that is a hard FAIL.
# In DOCS a mention is usually the "must not ship this" note itself, so those are only
# reported, and only when the line does not look like such a note.
$neg  = '残留|有无|没有|不许|不能|禁止|never|forbid|do not ship'
$codeExt = @('.ino', '.kt', '.kts', '.xml', '.html', '.json', '.gradle', '.properties')
$docExt  = @('.md', '.txt')
# NOTE: PowerShell 5.1 silently ignores -Include together with -LiteralPath,
# so enumerate once and filter by extension here instead.
$allFiles  = @(Get-ChildItem -LiteralPath $root -Recurse -File |
  Where-Object { $_.FullName -notmatch $skip -and $_.Name -ne $self -and $_.Name -ne '代码浏览_离线版.html' })
$codeFiles = @($allFiles | Where-Object { $codeExt -contains $_.Extension })
$docFiles  = @($allFiles | Where-Object { $docExt -contains $_.Extension })
$badCode = @($codeFiles | Select-String -Pattern 'ELEV-1F' -SimpleMatch)
if ($badCode.Count -eq 0) {
  Ok ("no device named 'ELEV-1F' in code/config (" + $codeFiles.Count + " files: .ino/.kt/.xml/.html/.json)")
} else {
  Bad ("'ELEV-1F' appears in " + $badCode.Count + " code/config place(s) - a wrong device name would ship:")
  $badCode | Select-Object -First 6 | ForEach-Object { Write-Host ("         " + $_.Path + ":" + $_.LineNumber) }
}
$docHits = @($docFiles | Select-String -Pattern 'ELEV-1F' -SimpleMatch)
$real = @($docHits | Where-Object { $_.Line -notmatch $neg })
if ($docHits.Count -eq 0) {
  Ok ("no 'ELEV-1F' in any doc (" + $docFiles.Count + " files scanned)")
} elseif ($real.Count -eq 0) {
  Ok ("'ELEV-1F' appears in docs only as 'must-not-ship' notes (" + $docHits.Count + " mention(s), nothing to fix)")
} else {
  Wrn ("'ELEV-1F' appears in docs outside a warning - please eyeball " + $real.Count + " line(s):")
  $real | Select-Object -First 6 | ForEach-Object { Write-Host ("         " + $_.Path + ":" + $_.LineNumber) }
}
# 6b) one package must not have two versions on disk (发给队友_v1.0.zip + _v1.1.zip = the old one was not deleted)
$byBase = @{}
foreach ($z in $zips) {
  $base = $z.Name -replace '_v[\d\.]+\.zip$', ''
  if (-not $byBase.ContainsKey($base)) { $byBase[$base] = @() }
  $byBase[$base] = @($byBase[$base]) + $z.Name
}
$dup = @()
foreach ($k in @($byBase.Keys)) { if (@($byBase[$k]).Count -gt 1) { $dup += (@($byBase[$k]) -join ' + ') } }
if ($dup.Count -gt 0) { Wrn ("same package has several versions on disk (delete the old one): " + ($dup -join '; ')) }
else { Ok "no duplicate package versions on disk" }
foreach ($z in $zips) {
  $dirName = $z.Name -replace '_v[\d\.]+\.zip$', ''
  if (-not (Test-Path -LiteralPath (Join-Path $root $dirName))) { Wrn ("orphan zip (no folder): " + $z.Name) }
}

# ------------------------------------------------------------- 7) compile
Head ("7) Firmware compiles" + $(if ($Compile) { "" } else { "  (skipped, add -Compile)" }))
if ($Compile) {
  $cli = 'D:\arduino-cli\arduino-cli.exe'
  if (-not (Test-Path -LiteralPath $cli)) {
    Wrn "arduino-cli not found at $cli - skipped"
  } else {
    foreach ($sk in @('elevator_2F', 'elevator_3F', 'chime_node')) {
      $dir = Join-Path $fw $sk
      if (-not (Test-Path -LiteralPath $dir)) { Wrn ("firmware\$sk missing - skipped"); continue }
      $out = & $cli compile --fqbn esp32:esp32:esp32:PartitionScheme=huge_app $dir 2>&1
      $use = ($out | Select-String -Pattern 'Sketch uses' | Select-Object -First 1)
      if ($LASTEXITCODE -eq 0 -and $use) { Ok ("{0}  {1}" -f $sk, ($use.Line -replace '\s+', ' ').Trim()) }
      else { Bad "$sk FAILED to compile"; $out | Select-Object -Last 4 | ForEach-Object { Write-Host ("         " + $_) } }
    }
  }
}

# ------------------------------------------------------------- summary
Write-Host ""
Write-Host ("RESULT:  {0} passed,  {1} failed,  {2} warning(s)" -f $script:Pass, $script:Fail, $script:Warn) `
  -ForegroundColor $(if ($script:Fail -gt 0) { 'Red' } elseif ($script:Warn -gt 0) { 'Yellow' } else { 'Green' })
if ($script:Fail -gt 0) {
  Write-Host ""
  Write-Host "Fix every [FAIL] before you leave. [WARN] items are judgement calls." -ForegroundColor Yellow
  exit 1
}
Write-Host "Ready for demo day." -ForegroundColor Green
exit 0
