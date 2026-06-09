# ChangePilot Studio - one-command launcher (Windows / PowerShell)
#
#   Usage:
#     .\start.ps1                start backend + React UI
#     .\start.ps1 -Backend       backend only
#     .\start.ps1 -Frontend      React UI only (backend must already be running)
#     .\start.ps1 -Install       install python + npm deps then exit
#     .\start.ps1 -Test          run pytest then exit
#     .\start.ps1 -Stop          stop running servers
#     .\start.ps1 -Clean         drop venv + node_modules + atlas.db

[CmdletBinding()]
param(
  [switch]$Backend,
  [switch]$Frontend,
  [switch]$Install,
  [switch]$Test,
  [switch]$Stop,
  [switch]$Clean,
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
$EnvFile = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $BackendDir ".env.example"

# --- styling helpers (ASCII-only · avoids Windows-cp1252 decode issues) ---
function Banner($msg) { Write-Host ""; Write-Host "--- $msg ---" -ForegroundColor DarkGray }
function Ok($msg)    { Write-Host "  [OK]  $msg" -ForegroundColor Green }
function Info($msg)  { Write-Host "   >   $msg" -ForegroundColor Cyan }
function Warn($msg)  { Write-Host "  [!]   $msg" -ForegroundColor Yellow }
function Fail($msg)  { Write-Host "  [X]   $msg" -ForegroundColor Red; exit 1 }

# --- stop ---
function Stop-Atlas {
  Banner "Stopping ChangePilot Studio processes"
  $found = 0
  Get-Process -Name python -ErrorAction SilentlyContinue | ForEach-Object {
    try {
      $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
      if ($cmdline -match "ChangePilot-Studio" -or $cmdline -match "atlas-tier3" -or $cmdline -match "uvicorn app.main") {
        Info "stopping python PID $($_.Id)"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        $found++
      }
    } catch {}
  }
  Get-Process -Name node -ErrorAction SilentlyContinue | ForEach-Object {
    try {
      $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
      if ($cmdline -match "ChangePilot-Studio.+frontend" -or $cmdline -match "atlas-tier3.+frontend" -or $cmdline -match "vite") {
        Info "stopping node PID $($_.Id)"
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        $found++
      }
    } catch {}
  }
  if ($found -eq 0) { Info "no atlas processes were running" } else { Ok "$found process(es) stopped" }
}

if ($Stop)  { Stop-Atlas; exit 0 }

# --- clean ---
if ($Clean) {
  Stop-Atlas
  Banner "Cleaning .venv + node_modules + atlas.db"
  if (Test-Path $VenvDir) { Remove-Item -Recurse -Force $VenvDir; Ok ".venv removed" }
  $nm = Join-Path $FrontendDir "node_modules"
  if (Test-Path $nm) { Remove-Item -Recurse -Force $nm; Ok "node_modules removed" }
  $db = Join-Path $BackendDir "atlas.db"
  if (Test-Path $db) { Remove-Item -Force $db; Ok "atlas.db removed" }
  exit 0
}

# --- prereq checks ---
Banner "ChangePilot Studio launcher"
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) { Fail "python not on PATH. Install Python 3.11+ from python.org" }
Info "system python: $(& python --version 2>&1)"

# --- env file ---
if (-not (Test-Path $EnvFile)) {
  if (Test-Path $EnvExample) {
    Copy-Item $EnvExample $EnvFile
    Ok ".env created from .env.example"
    Warn "fill in DATABRICKS_HOST / DATABRICKS_TOKEN / GITHUB_TOKEN before posting real comments"
  } else {
    Fail ".env.example missing - cannot bootstrap"
  }
} else {
  Ok ".env present"
}

# --- backend venv + deps ---
if (-not (Test-Path $VenvPy)) {
  Banner "Creating virtual environment"
  Push-Location $BackendDir
  python -m venv .venv
  Pop-Location
  Ok ".venv created"
}

function Test-PyDepsInstalled {
  # Check core deps only — google.adk may not be installed in all setups
  $check = & $VenvPy -c "import fastapi, sqlalchemy, yaml, structlog, httpx; print('ok')" 2>&1
  return ($check -match "^ok$")
}

if ($Install -or -not (Test-PyDepsInstalled)) {
  Banner "Installing backend dependencies (3-5 min on first run)"
  Push-Location $BackendDir
  & $VenvPy -m pip install --quiet --upgrade pip
  & $VenvPy -m pip install --quiet -e ".[dev]"
  Pop-Location
  if (Test-PyDepsInstalled) { Ok "python deps installed" } else { Fail "python dependency install failed" }
}

# --- Node resolution (portable .tools\ first, then system PATH) ---
# We resolve node.exe explicitly so npm on PATH is NOT required.
$NodeExe = $null
$portableNodeDir = Get-ChildItem -Path (Join-Path $Root '.tools') -Directory -Filter 'node-v*-win-x64' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($portableNodeDir -and (Test-Path (Join-Path $portableNodeDir.FullName 'node.exe'))) {
  $NodeExe = Join-Path $portableNodeDir.FullName 'node.exe'
  Info "using portable node: $NodeExe"
} else {
  # Try system node via PATH
  $nc = Get-Command node -ErrorAction SilentlyContinue
  if ($nc) { $NodeExe = $nc.Source; Info "using system node: $NodeExe" }
}

if (-not $NodeExe) {
  Warn "Node.js not found. React UI won't start."
  Warn "Unzip Node 20 LTS into .tools\node-v20.18.0-win-x64\ or install from nodejs.org"
}

if ($Install) { exit 0 }

# --- tests ---
if ($Test) {
  Banner "Running smoke tests"
  Push-Location $BackendDir
  & $VenvPy -m pytest -v
  Pop-Location
  exit 0
}

# --- decide what to start ---
$startBackend = $true
$startFrontend = $true
if ($Backend -and -not $Frontend) { $startFrontend = $false }
if ($Frontend -and -not $Backend) { $startBackend = $false }

# --- backend ---
if ($startBackend) {
  Banner "Starting backend on http://127.0.0.1:$BackendPort"
  # Use 127.0.0.1 (not 0.0.0.0) so health-poll doesn't hit IPv6 ::1 on Windows
  $bArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", $BackendPort, "--reload")
  $env:PYTHONPATH = $Root
  $proc = Start-Process -PassThru -FilePath $VenvPy -ArgumentList $bArgs `
            -WorkingDirectory $BackendDir `
            -RedirectStandardOutput (Join-Path $Root "backend.log") `
            -RedirectStandardError  (Join-Path $Root "backend.err.log")
  Info "backend pid $($proc.Id)  (logs -> backend.log / backend.err.log)"
  $ready = $false
  # 17 skills load on startup - allow up to 90s (first cold start with big deps can be slow)
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    if ($i -eq 15) { Info "still starting... (skill registry loading - normal, ~10s)" }
  }
  if ($ready) { Ok "backend up - /health OK ($($i+1)s)" } else {
    Warn "backend did not respond after 90s"
    Warn "Check logs: Get-Content backend.err.log -Tail 20"
  }
}

# --- React frontend ---
if ($startFrontend) {
  $ViteJs = Join-Path $FrontendDir "node_modules\vite\bin\vite.js"

  if (-not $NodeExe) {
    Warn "Skipping frontend: Node not found."
  } elseif (-not (Test-Path $ViteJs)) {
    Warn "Skipping frontend: node_modules not installed. Run: .\start.ps1 -Install"
  } else {
    Banner "Starting React frontend on http://127.0.0.1:$FrontendPort"
    # Pass vite.js path quoted so spaces in folder names don't split the argument
    $viteArg = """$ViteJs"" --host 127.0.0.1 --port $FrontendPort"
    $proc = Start-Process -PassThru -FilePath $NodeExe `
              -ArgumentList $viteArg `
              -WorkingDirectory $FrontendDir `
              -RedirectStandardOutput (Join-Path $Root "frontend.log") `
              -RedirectStandardError  (Join-Path $Root "frontend.err.log")
    Info "frontend pid $($proc.Id)  (logs -> frontend.log / frontend.err.log)"
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
      Start-Sleep -Seconds 1
      try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$FrontendPort/" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
      } catch {}
    }
    if ($ready) { Ok "React frontend up ($($i+1)s)" } else {
      Warn "Vite slow - check: Get-Content frontend.err.log -Tail 15"
    }
  }
}

# --- summary ---
Banner "ChangePilot Studio is running"
if ($startBackend)  { Write-Host "  Backend API  -> http://127.0.0.1:$BackendPort/docs   (Swagger)" -ForegroundColor White }
if ($startFrontend -and $nodeCmd -and $npmCmd) {
  Write-Host "  React UI     -> http://127.0.0.1:$FrontendPort/" -ForegroundColor White
  Write-Host ""
  Write-Host "  Tip: use 127.0.0.1 (not 'localhost') if you see ERR_SSL_PROTOCOL_ERROR." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Stop with:    .\start.ps1 -Stop" -ForegroundColor DarkGray
Write-Host "  Run tests:    .\start.ps1 -Test" -ForegroundColor DarkGray
Write-Host "  Clean state:  .\start.ps1 -Clean" -ForegroundColor DarkGray
Write-Host ""
