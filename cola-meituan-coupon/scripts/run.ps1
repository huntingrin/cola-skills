# Cola 美团领券 · 入口（Windows）：powershell -ExecutionPolicy Bypass -File run.ps1 <命令> [参数]
# 找 Python 3.8+（只用标准库）；没有就免管理员装一个到 %USERPROFILE%\.cola\runtime\python，再执行 mt.py。
$ErrorActionPreference = "SilentlyContinue"
$ProgressPreference = "SilentlyContinue"   # 关掉进度条，否则 PowerShell 5 下载极慢
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$Dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RT = Join-Path $env:USERPROFILE ".cola\runtime\python"
$PYV = "3.12.7"; $TAG = "20241016"

function Test-Py($p) {
  if (-not $p) { return $false }
  # 微软商店的 python.exe 占位壳（WindowsApps）一调用就弹商店，跳过
  if ($p -like "*\WindowsApps\*") { return $false }
  & $p -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" 2>$null | Out-Null
  return ($LASTEXITCODE -eq 0)
}
function Find-Py {
  $c = @((Join-Path $RT "python.exe"))
  foreach ($n in "python", "python3") { $x = (Get-Command $n -All -ErrorAction SilentlyContinue | % Source); if ($x) { $c += $x } }
  $py = (Get-Command py -ErrorAction SilentlyContinue).Source
  if ($py) { $x = & $py -3 -c "import sys;print(sys.executable)" 2>$null; if ($x) { $c += $x } }
  foreach ($p in $c) { if ((Test-Path $p) -and (Test-Py $p)) { return $p } }
  return $null
}
function Install-Py {
  $arch = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "i686" }
  $f = "cpython-$PYV+$TAG-$arch-pc-windows-msvc-install_only.tar.gz"
  $tmp = Join-Path $env:TEMP ("colapy" + (Get-Random)); New-Item -ItemType Directory $tmp | Out-Null
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  foreach ($base in "https://registry.npmmirror.com/-/binary/python-build-standalone/$TAG", "https://github.com/astral-sh/python-build-standalone/releases/download/$TAG") {
    $u = "$base/" + $f.Replace("+", "%2B")
    [Console]::Error.WriteLine("[setup] 下载 Python $PYV：$base")
    try {
      Invoke-WebRequest $u -OutFile "$tmp\py.tgz" -UseBasicParsing -TimeoutSec 600 -ErrorAction Stop
      $c = (Invoke-WebRequest "$u.sha256" -UseBasicParsing -TimeoutSec 60 -ErrorAction Stop).Content
      if ($c -is [byte[]]) { $c = [Text.Encoding]::ASCII.GetString($c) }
      $want = ($c.Trim() -split "\s+")[0]
      $got = (Get-FileHash "$tmp\py.tgz" -Algorithm SHA256).Hash.ToLower()
      if ($got -eq $want.Trim().ToLower()) {
        tar -xzf "$tmp\py.tgz" -C $tmp
        if (Test-Path $RT) { Remove-Item $RT -Recurse -Force }
        New-Item -ItemType Directory (Split-Path $RT) -Force | Out-Null
        Move-Item "$tmp\python" $RT
        Remove-Item $tmp -Recurse -Force; return $true
      }
      [Console]::Error.WriteLine("[setup] 校验没通过，换下一个源")
    } catch { [Console]::Error.WriteLine("[setup] 下载失败，换下一个源") }
  }
  Remove-Item $tmp -Recurse -Force; return $false
}

$PY = Find-Py
if (-not $PY) { if (Install-Py) { $PY = Find-Py } }
if (-not $PY) { "电脑上缺个运行环境，我没装上，你把这段报错截图发给鲁班。"; exit 1 }
& $PY -B (Join-Path $Dir "mt.py") @args
exit $LASTEXITCODE
