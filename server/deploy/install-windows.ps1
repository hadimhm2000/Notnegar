<#
  Notnegar installer for Windows Server 2016 / 2019 / 2022 / 2025 and Windows 10 / 11.

  Run in PowerShell as Administrator:

    Set-ExecutionPolicy Bypass -Scope Process -Force
    [Net.ServicePointManager]::SecurityProtocol = 'Tls12'
    irm https://raw.githubusercontent.com/hadimhm2000/Notnegar/main/server/deploy/install-windows.ps1 -OutFile install.ps1
    .\install.ps1

  Installs Python 3.11, ffmpeg, LilyPond, the Vazirmatn font, PyTorch (CPU), Demucs, CREPE and
  Basic Pitch into C:\notnegar, then registers a startup task that runs the server on port 8000.
  Running it again updates the code and keeps settings (C:\notnegar\notnegar.env) and data.
#>
param(
  [string]$InstallDir = "C:\notnegar",
  [int]$Port = 8000,
  [string]$Source = "",          # local folder with the repository (otherwise downloaded from GitHub)
  [switch]$NoService,            # do not register / start the startup task
  [switch]$SkipModels,           # do not pre-download model weights
  [switch]$SkipBasicPitch
)

$ErrorActionPreference = "Stop"
# copies of downloads that are blocked in some countries (GitLab, Meta's CDN), kept in this repository's release
$Mirror = "https://github.com/hadimhm2000/Notnegar/releases/download/deps"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Say($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host ""; Write-Host "ERROR: $msg" -ForegroundColor Red; throw $msg }

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Fail "Run PowerShell as Administrator (right-click PowerShell > Run as administrator)."
}

$Tools = Join-Path $InstallDir "tools"
$Dl = Join-Path $InstallDir "downloads"
$Logs = Join-Path $InstallDir "logs"
$Data = Join-Path $InstallDir "data"
$Models = Join-Path $InstallDir "models"
$App = Join-Path $InstallDir "app"
New-Item -ItemType Directory -Force -Path $InstallDir, $Tools, $Dl, $Logs, $Data, $Models | Out-Null

function Get-File([string[]]$Urls, [string]$Name) {
  $dest = Join-Path $Dl $Name
  if ((Test-Path $dest) -and ((Get-Item $dest).Length -gt 100000)) { return $dest }
  foreach ($u in $Urls) {
    for ($i = 1; $i -le 3; $i++) {
      try {
        Write-Host "    downloading $u"
        Invoke-WebRequest -Uri $u -OutFile $dest -UseBasicParsing -TimeoutSec 600
        if ((Get-Item $dest).Length -gt 10000) { return $dest }
      } catch {
        Write-Host "    failed ($i): $($_.Exception.Message)" -ForegroundColor Yellow
        Start-Sleep -Seconds (3 * $i)
      }
    }
  }
  Fail "Could not download $Name. Download it manually from: $($Urls -join ' or ') and save it as $dest, then run this script again."
}

function Add-MachinePath([string]$dir) {
  $p = [Environment]::GetEnvironmentVariable("Path", "Machine")
  if (($p -split ";") -notcontains $dir) {
    [Environment]::SetEnvironmentVariable("Path", "$p;$dir", "Machine")
  }
  if (($env:Path -split ";") -notcontains $dir) { $env:Path = "$dir;$env:Path" }
}

# ---------------------------------------------------------------- Python 3.11
Say "Python 3.11"
function Find-Python311 {
  $cands = @((Join-Path $InstallDir "python311\python.exe"), "C:\Program Files\Python311\python.exe")
  foreach ($hive in @("HKLM:\SOFTWARE\Python\PythonCore\3.11\InstallPath", "HKCU:\SOFTWARE\Python\PythonCore\3.11\InstallPath",
                      "HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore\3.11\InstallPath")) {
    $k = Get-ItemProperty -Path $hive -ErrorAction SilentlyContinue
    if ($k) {
      if ($k.ExecutablePath) { $cands += $k.ExecutablePath }
      if ($k."(default)") { $cands += (Join-Path $k."(default)" "python.exe") }
    }
  }
  foreach ($c in $cands) {
    if ($c -and (Test-Path $c)) {
      $v = & $c -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
      if ($v -eq "3.11") { return $c }
    }
  }
  return $null
}
$Py = Find-Python311
if (-not $Py) {
  $exe = Get-File @("https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe") "python-3.11.9-amd64.exe"
  $target = Join-Path $InstallDir "python311"
  $p = Start-Process -FilePath $exe -ArgumentList "/quiet InstallAllUsers=1 TargetDir=`"$target`" PrependPath=0 Include_test=0 Include_launcher=0 Include_doc=0 Shortcuts=0" -Wait -PassThru
  $Py = Find-Python311
  if (-not $Py) { Fail "Python installation failed (exit code $($p.ExitCode))." }
}
& $Py --version
Write-Host "    $Py"

# ---------------------------------------------------------------- ffmpeg
Say "ffmpeg"
$ffBin = Get-ChildItem -Path (Join-Path $Tools "ffmpeg") -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $ffBin) {
  $zip = Get-File @("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", "$Mirror/ffmpeg-release-essentials.zip",
                    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip") "ffmpeg.zip"
  Expand-Archive -Path $zip -DestinationPath (Join-Path $Tools "ffmpeg") -Force
  $ffBin = Get-ChildItem -Path (Join-Path $Tools "ffmpeg") -Recurse -Filter ffmpeg.exe | Select-Object -First 1
}
$FfDir = $ffBin.DirectoryName
Add-MachinePath $FfDir
& (Join-Path $FfDir "ffmpeg.exe") -version | Select-Object -First 1

# ---------------------------------------------------------------- LilyPond
Say "LilyPond"
$lyVer = "2.24.4"
$lyExe = Get-ChildItem -Path (Join-Path $Tools "lilypond") -Recurse -Filter lilypond.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $lyExe) {
  $zip = Get-File @("$Mirror/lilypond-$lyVer-mingw-x86_64.zip",
                    "https://gitlab.com/lilypond/lilypond/-/releases/v$lyVer/downloads/lilypond-$lyVer-mingw-x86_64.zip") "lilypond-$lyVer.zip"
  Expand-Archive -Path $zip -DestinationPath (Join-Path $Tools "lilypond") -Force
  $lyExe = Get-ChildItem -Path (Join-Path $Tools "lilypond") -Recurse -Filter lilypond.exe | Select-Object -First 1
}
$LyDir = $lyExe.DirectoryName
Add-MachinePath $LyDir
& (Join-Path $LyDir "lilypond.exe") --version | Select-Object -First 1

# ---------------------------------------------------------------- Persian font (optional; Tahoma is the fallback)
Say "Vazirmatn font"
$fontsDir = Join-Path $env:WINDIR "Fonts"
if (-not (Test-Path (Join-Path $fontsDir "Vazirmatn-Regular.ttf"))) {
  try {
    $zip = Get-File @("https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/vazirmatn-v33.003.zip",
                      "$Mirror/vazirmatn-v33.003.zip") "vazirmatn.zip"
    $fx = Join-Path $Tools "vazirmatn"
    Expand-Archive -Path $zip -DestinationPath $fx -Force
    foreach ($w in @("Regular", "Bold")) {
      $f = Get-ChildItem -Path $fx -Recurse -Filter "Vazirmatn-$w.ttf" | Where-Object { $_.FullName -notmatch "Variable|UI|Round|NL" } | Select-Object -First 1
      if ($f) {
        Copy-Item $f.FullName -Destination $fontsDir -Force
        New-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" -Name "Vazirmatn $w (TrueType)" -Value $f.Name -PropertyType String -Force | Out-Null
      }
    }
    Write-Host "    installed"
  } catch {
    Write-Host "    skipped: $($_.Exception.Message). Persian text will use Tahoma." -ForegroundColor Yellow
  }
} else { Write-Host "    already installed" }

# ---------------------------------------------------------------- application code
Say "Notnegar code"
$tmpApp = Join-Path $InstallDir "app.new"
if (Test-Path $tmpApp) { Remove-Item $tmpApp -Recurse -Force }
if ($Source) {
  Copy-Item -Path $Source -Destination $tmpApp -Recurse -Force
} else {
  $zip = Join-Path $Dl "notnegar-main.zip"
  if (Test-Path $zip) { Remove-Item $zip -Force }
  $zip = Get-File @("https://github.com/hadimhm2000/Notnegar/archive/refs/heads/main.zip") "notnegar-main.zip"
  $x = Join-Path $InstallDir "app.extract"
  if (Test-Path $x) { Remove-Item $x -Recurse -Force }
  Expand-Archive -Path $zip -DestinationPath $x -Force
  $inner = Get-ChildItem -Path $x -Directory | Select-Object -First 1
  Move-Item -Path $inner.FullName -Destination $tmpApp
  Remove-Item $x -Recurse -Force
  Remove-Item $zip -Force
}
if (-not (Test-Path (Join-Path $tmpApp "server\notnegar\app.py"))) { Fail "Downloaded code is incomplete." }
Get-ScheduledTask -TaskName "Notnegar" -ErrorAction SilentlyContinue | Stop-ScheduledTask -ErrorAction SilentlyContinue
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$InstallDir*" } | Stop-Process -Force -ErrorAction SilentlyContinue
if (Test-Path $App) { Remove-Item $App -Recurse -Force }
Move-Item -Path $tmpApp -Destination $App
$Server = Join-Path $App "server"

# ---------------------------------------------------------------- settings
Say "Settings"
$EnvFile = Join-Path $InstallDir "notnegar.env"
if (-not (Test-Path $EnvFile)) {
  Copy-Item (Join-Path $Server ".env.example") $EnvFile
  Add-Content -Path $EnvFile -Value "`r`n# Windows install locations`r`nNOTNEGAR_DATA=$Data`r`nTORCH_HOME=$Models`r`n"
  Write-Host "    created $EnvFile"
} else {
  Write-Host "    keeping $EnvFile"
  # settings whose old defaults made processing slow
  $envText = Get-Content $EnvFile -Raw
  $envNew = $envText -replace "(?m)^NOTNEGAR_CREPE_MODEL=full\s*$", "NOTNEGAR_CREPE_MODEL=tiny"
  if ($envNew -notmatch "(?m)^NOTNEGAR_DEMUCS_MODEL_MELODY=") { $envNew = $envNew.TrimEnd() + "`r`nNOTNEGAR_DEMUCS_MODEL_MELODY=htdemucs`r`n" }
  if ($envNew -ne $envText) { Set-Content -Path $EnvFile -Value $envNew -Encoding UTF8; Write-Host "    updated speed settings" }
}

# ---------------------------------------------------------------- Python packages
Say "Python packages (PyTorch, Demucs, CREPE...) - this takes a while"
$Venv = Join-Path $InstallDir "venv"
$VPy = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VPy)) { & $Py -m venv $Venv; if ($LASTEXITCODE) { Fail "venv failed" } }
& $VPy -m pip install --upgrade pip --quiet
& $VPy -m pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE) {
  Write-Host "    download.pytorch.org unreachable; installing the CPU build from PyPI instead" -ForegroundColor Yellow
  & $VPy -m pip install torch==2.3.1 torchaudio==2.3.1
  if ($LASTEXITCODE) { Fail "PyTorch installation failed (neither download.pytorch.org nor PyPI was reachable)." }
}
& $VPy -m pip install -r (Join-Path $Server "requirements.txt") -r (Join-Path $Server "requirements-ml.txt")
if ($LASTEXITCODE) { Fail "Package installation failed." }
if (-not $SkipBasicPitch) {
  & $VPy -m pip install "basic-pitch==0.4.0" "numpy<2"
  if ($LASTEXITCODE) { Write-Host "    basic-pitch skipped (optional)" -ForegroundColor Yellow }
}

# ---------------------------------------------------------------- start script
Say "Start script"
$Start = Join-Path $InstallDir "start.cmd"
@"
@echo off
set PATH=$FfDir;$LyDir;%PATH%
set NOTNEGAR_ENV_FILE=$EnvFile
set NOTNEGAR_DATA=$Data
set TORCH_HOME=$Models
set PYTHONIOENCODING=utf-8
cd /d "$Server"
"$VPy" -m uvicorn notnegar.app:app --host 0.0.0.0 --port $Port --proxy-headers >> "$Logs\server.log" 2>&1
"@ | Set-Content -Path $Start -Encoding ASCII
Write-Host "    $Start"

if (-not $SkipModels) {
  Say "Model weights"
  $env:TORCH_HOME = $Models
  $ckpt = Join-Path $Models "hub\checkpoints"
  if (-not (Get-ChildItem -Path $ckpt -Filter *.th -ErrorAction SilentlyContinue)) {
    try {
      $mz = Get-File @("$Mirror/demucs-models.zip") "demucs-models.zip"
      Expand-Archive -Path $mz -DestinationPath $Models -Force
      Write-Host "    Demucs weights installed from the mirror"
    } catch { Write-Host "    mirror unavailable; downloading from the original host" -ForegroundColor Yellow }
  }
  & $VPy (Join-Path $Server "scripts\download_models.py")
  if ($LASTEXITCODE) { Write-Host "    model download failed; it will be retried on the first song" -ForegroundColor Yellow }
}

# ---------------------------------------------------------------- startup task + firewall
if (-not $NoService) {
  Say "Startup task and firewall"
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Start`""
  $trigger = New-ScheduledTaskTrigger -AtStartup
  $settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
              -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  $principalT = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
  Register-ScheduledTask -TaskName "Notnegar" -Action $action -Trigger $trigger -Settings $settings -Principal $principalT -Force | Out-Null
  if (-not (Get-NetFirewallRule -DisplayName "Notnegar $Port" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Notnegar $Port" -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
  }
  Start-ScheduledTask -TaskName "Notnegar"

  Say "Waiting for the server"
  $ok = $false
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 3
    try { $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 5; $ok = $true; break } catch {}
  }
  if (-not $ok) { Fail "The server did not start. See $Logs\server.log" }
  $h | Format-List
  $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notmatch "^(127\.|169\.254\.)" } | Select-Object -First 1).IPAddress
  Write-Host ""
  Write-Host "Notnegar is running:  http://$($ip):$Port" -ForegroundColor Green
  Write-Host "Settings: $EnvFile   Logs: $Logs\server.log   Restart: Stop-ScheduledTask Notnegar; Start-ScheduledTask Notnegar"
}
