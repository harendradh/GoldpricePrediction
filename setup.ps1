# ChangePilot Studio - first-time installer
#
# Run once after cloning / receiving the project.
# Recreates Python venv + installs dependencies + npm install.
#
#   .\setup.ps1                   default setup (no seed)
#   .\setup.ps1 -Seed             also seed the demo DB
#   .\setup.ps1 -SkipNode         skip npm install (backend only)

[CmdletBinding()]
param(
  [switch]$Seed,
  [switch]$SkipNode
)

$ErrorActionPreference = "Stop"
$Root         = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir   = Join-Path $Root "backend"
$FrontendDir  = Join-Path $Root "frontend"
$VenvDir      = Join-Path $BackendDir ".venv"
$VenvPy       = Join-Path $VenvDir "Scripts\python.exe"

function Banner($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

Banner "ChangePilot Studio · first-time setup"
Write-Host "Project root: $Root" -ForegroundColor DarkGray
Write-Host ""

# ─── Verify Python ───────────────────────────────────────────
Banner "Step 1/4 · Verify Python 3.11+"
$pythonExe = $null
foreach ($candidate in @("python", "py -3.11", "py -3")) {
  try {
    $v = & $candidate.Split()[0] $candidate.Split()[1..($candidate.Split().Count-1)] --version 2>&1
    if ($LASTEXITCODE -eq 0 -and $v -match "Python 3\.(1[1-9]|[2-9][0-9])") {
      $pythonExe = $candidate
      Write-Host "  Using: $candidate ($v)" -ForegroundColor Green
      break
    }
  } catch {}
}
if (-not $pythonExe) {
  Write-Host "  ERROR: Python 3.11+ not found. Install from https://www.python.org/downloads/" -ForegroundColor Red
  exit 1
}

# ─── Create venv ─────────────────────────────────────────────
Banner "Step 2/4 · Create Python virtual environment"
if (Test-Path $VenvDir) {
  Write-Host "  venv already exists at $VenvDir · keeping" -ForegroundColor DarkGray
} else {
  Write-Host "  Creating venv at $VenvDir ..."
  & $pythonExe.Split()[0] $pythonExe.Split()[1..($pythonExe.Split().Count-1)] -m venv $VenvDir
  Write-Host "  done." -ForegroundColor Green
}

Write-Host "  Upgrading pip..."
& $VenvPy -m pip install -U pip --quiet
Write-Host "  Installing project dependencies (this takes 2-3 minutes the first time)..."
Push-Location $BackendDir
try {
  & $VenvPy -m pip install -e . --quiet
  Write-Host "  done." -ForegroundColor Green
} finally {
  Pop-Location
}

# ─── Setup portable Node ─────────────────────────────────────
Banner "Step 3/4 · Detect Node.js"
$portableNode = Get-ChildItem (Join-Path $Root ".tools") -Filter "node-v*-win-x64" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
if ($portableNode) {
  $env:Path = "$($portableNode.FullName);$env:Path"
  $nv = & node --version 2>&1
  Write-Host "  Using portable Node from .tools/: $nv" -ForegroundColor Green
} else {
  try {
    $nv = & node --version 2>&1
    Write-Host "  Using system Node: $nv" -ForegroundColor Green
  } catch {
    Write-Host "  WARNING: Node.js not found. Frontend install will be skipped." -ForegroundColor Yellow
    Write-Host "  Install Node 20 LTS or unzip a portable Node into .tools\node-v20.18.0-win-x64\" -ForegroundColor Yellow
    $SkipNode = $true
  }
}

# ─── npm install ─────────────────────────────────────────────
if (-not $SkipNode) {
  Banner "Step 4/4 · Install frontend dependencies (npm install)"
  Push-Location $FrontendDir
  try {
    if (Test-Path "node_modules") {
      Write-Host "  node_modules exists · running npm install (will update if needed)..." -ForegroundColor DarkGray
    } else {
      Write-Host "  Installing fresh (this takes 1-2 minutes)..."
    }
    & npm install --silent
    Write-Host "  done." -ForegroundColor Green
  } finally {
    Pop-Location
  }
} else {
  Banner "Step 4/4 · Skipped (no Node)"
}

# ─── Optional seed ───────────────────────────────────────────
if ($Seed) {
  Banner "Bonus · Seed demo data into atlas.db"
  & $VenvPy (Join-Path $BackendDir "scripts\seed_demo.py")
}

# ─── Done ────────────────────────────────────────────────────
Banner "Setup complete"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit backend\.env with your Databricks credentials"
Write-Host "  2. Start the app: .\start.ps1"
Write-Host "  3. Open the UI: http://127.0.0.1:5173"
Write-Host "  4. Open the API docs: http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Verify the content layer:" -ForegroundColor White
Write-Host "  backend\.venv\Scripts\python.exe Tests\consistency\consistency_tests.py"
Write-Host ""
