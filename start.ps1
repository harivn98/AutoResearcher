# ============================================================
#  AutoResearcher — Full Stack Launcher
#  Usage:
#    .\start.ps1              # Start everything
#    .\start.ps1 -EvalOnly    # Skip API server, just run eval
#    .\start.ps1 -NoEval      # Start stack + API, skip eval
#    .\start.ps1 -Stop        # Tear down Docker stack
# ============================================================
param(
    [switch]$EvalOnly,
    [switch]$NoEval,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Colours ─────────────────────────────────────────────────
function Info  ($msg) { Write-Host "  $msg"   -ForegroundColor Cyan }
function Ok    ($msg) { Write-Host "  ✔ $msg" -ForegroundColor Green }
function Warn  ($msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Err   ($msg) { Write-Host "  ✘ $msg" -ForegroundColor Red }
function Banner($msg) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
    Write-Host "  $msg"   -ForegroundColor DarkCyan
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
}

# ── Helpers ─────────────────────────────────────────────────
function Require-Command($cmd, $hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Err "$cmd not found. $hint"
        exit 1
    }
}

function Wait-Http($url, $label, $timeoutSec = 120, $intervalSec = 5) {
    Info "Waiting for $label at $url ..."
    $deadline = (Get-Date).AddSeconds($timeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -lt 500) { Ok "$label is up"; return }
        }
        catch {}
        Start-Sleep $intervalSec
        Write-Host "    ..." -NoNewline
    }
    Err "$label did not respond within ${timeoutSec}s. Check Docker logs."
    exit 1
}

function Load-Env($path) {
    if (-not (Test-Path $path)) { Warn ".env not found at $path — using existing environment"; return }
    Get-Content $path | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+?)\s*=\s*(.*)\s*$') {
            $k = $Matches[1].Trim(); $v = $Matches[2].Trim().Trim('"').Trim("'")
            if (-not [System.Environment]::GetEnvironmentVariable($k)) {
                [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

# ════════════════════════════════════════════════════════════
#  STOP mode
# ════════════════════════════════════════════════════════════
if ($Stop) {
    Banner "Stopping AutoResearcher stack"
    Set-Location $ROOT
    docker compose down
    Ok "Docker stack stopped."

    # Kill uvicorn if we started it
    Get-Process -Name python -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*uvicorn*" } |
    ForEach-Object { Stop-Process -Id $_.Id -Force; Ok "Stopped uvicorn (PID $($_.Id))" }
    exit 0
}

# ════════════════════════════════════════════════════════════
#  PRE-FLIGHT CHECKS
# ════════════════════════════════════════════════════════════
Banner "AutoResearcher — Pre-flight checks"

Require-Command python  "Install Python 3.10+ from https://python.org"
Require-Command ollama  "Install Ollama from https://ollama.com/download"
Require-Command docker  "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"

$pyVer = python --version 2>&1
Ok "Python: $pyVer"

# Check Docker is actually running (daemon responsive)
try { docker info *>$null; Ok "Docker daemon: running" }
catch { Err "Docker daemon is not running. Open Docker Desktop first."; exit 1 }

# Load .env
Load-Env "$ROOT\.env"
Ok "Environment loaded from .env"

# Validate required secrets
$missing = @()
foreach ($k in @("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")) {
    if (-not [System.Environment]::GetEnvironmentVariable($k)) { $missing += $k }
}
if ($missing.Count -gt 0) {
    Warn "Missing env vars: $($missing -join ', ')"
    Warn "Follow README Step 6 to create a Langfuse project and paste keys into .env"
}

# ════════════════════════════════════════════════════════════
#  VIRTUAL ENVIRONMENT
# ════════════════════════════════════════════════════════════
Banner "Virtual environment"

$venvPython = "$ROOT\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Info "Creating virtual environment..."
    python -m venv "$ROOT\.venv"
    Ok "Virtual environment created"
}
else {
    Ok "Virtual environment found"
}

Info "Installing / verifying dependencies..."
& $venvPython -m pip install --upgrade pip -q
& $venvPython -m pip install -r "$ROOT\requirements.txt" -q
Ok "Dependencies ready"

# ════════════════════════════════════════════════════════════
#  DOCKER STACK (Langfuse)
# ════════════════════════════════════════════════════════════
if (-not $EvalOnly) {
    Banner "Starting Docker stack (Langfuse)"
    Set-Location $ROOT
    docker compose up -d
    Ok "Docker compose started"
    Wait-Http "http://localhost:3000/api/public/health" "Langfuse" -timeoutSec 180
}

# ════════════════════════════════════════════════════════════
#  OLLAMA
# ════════════════════════════════════════════════════════════
if (-not $EvalOnly) {
    Banner "Ollama"
    $model = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "llama3.2" }

    # Check if Ollama server is up; start it if not
    try { Invoke-WebRequest "http://localhost:11434" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop *>$null; Ok "Ollama already running" }
    catch {
        Info "Starting Ollama server..."
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep 3
        Ok "Ollama started"
    }

    # Pull model if not present
    $pulled = ollama list 2>$null | Select-String $model
    if (-not $pulled) {
        Info "Pulling model: $model (this may take a few minutes)..."
        ollama pull $model
        Ok "Model $model ready"
    }
    else {
        Ok "Model $model already present"
    }
}

# ════════════════════════════════════════════════════════════
#  ENSURE __init__.py PACKAGE MARKERS EXIST
# ════════════════════════════════════════════════════════════
if (-not $EvalOnly) {
    Banner "Package structure"
    @("app", "app\agents", "app\graph", "app\rag", "app\observability", "scripts") | ForEach-Object {
        $f = "$ROOT\$_\__init__.py"
        if (-not (Test-Path $f)) { New-Item $f -Force *>$null; Info "Created $_\__init__.py" }
    }
    Ok "All __init__.py markers present"
}

# ════════════════════════════════════════════════════════════
#  FASTAPI SERVER
# ════════════════════════════════════════════════════════════
if (-not $EvalOnly -and -not $NoEval) {
    Banner "Starting FastAPI server"
    $apiJob = Start-Job -ScriptBlock {
        param($root, $venvPy)
        Set-Location $root
        & $venvPy -m uvicorn app.main:app --reload --port 8000 2>&1
    } -ArgumentList $ROOT, $venvPython

    Wait-Http "http://localhost:8000/health" "FastAPI" -timeoutSec 60
}

# ════════════════════════════════════════════════════════════
#  EVALUATION SUITE
# ════════════════════════════════════════════════════════════
if (-not $NoEval) {
    Banner "Evaluation suite"

    Info "Seeding eval dataset..."
    & $venvPython -m scripts.seed_eval_dataset
    Ok "Dataset seeded"

    Info "Running eval pipeline..."
    & $venvPython -m scripts.run_eval_on_dataset
    Ok "Eval complete"
}

# ════════════════════════════════════════════════════════════
#  SUMMARY
# ════════════════════════════════════════════════════════════
Banner "AutoResearcher is running"
if (-not $EvalOnly) {
    Write-Host ""
    Write-Host "  API server:    " -NoNewline; Write-Host "http://localhost:8000"      -ForegroundColor Green
    Write-Host "  API docs:      " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Green
    Write-Host "  Langfuse UI:   " -NoNewline; Write-Host "http://localhost:3000"      -ForegroundColor Green
    Write-Host "  MinIO console: " -NoNewline; Write-Host "http://localhost:9001"      -ForegroundColor Green
    Write-Host ""
    Write-Host "  To stop everything: " -NoNewline; Write-Host ".\start.ps1 -Stop" -ForegroundColor Yellow
}
Write-Host ""
