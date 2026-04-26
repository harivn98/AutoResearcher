# ============================================================
# AutoResearcher - Full Stack Launcher
# Usage:
#   .\start.ps1              # Start everything
#   .\start.ps1 -EvalOnly    # Skip API server, just run eval
#   .\start.ps1 -NoEval      # Start stack + API, skip eval
#   .\start.ps1 -Stop        # Tear down Docker stack
# ============================================================

param(
    [switch]$EvalOnly,
    [switch]$NoEval,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# ------------------------------------------------------------
# Output helpers (ASCII-safe for Windows PowerShell 5.1)
# ------------------------------------------------------------
function Info($msg) { Write-Host "  $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }
function Err($msg) { Write-Host "  [ERR] $msg" -ForegroundColor Red }
function Banner($msg) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
    Write-Host "  $msg" -ForegroundColor DarkCyan
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
}

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
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
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            if ($r.StatusCode -lt 500) {
                Ok "$label is up"
                return
            }
        }
        catch {
        }
        Start-Sleep -Seconds $intervalSec
        Write-Host "    ..."
    }
    Err "$label did not respond within ${timeoutSec}s. Check logs."
    exit 1
}

function Load-Env($path) {
    if (-not (Test-Path $path)) {
        Warn ".env not found at $path - using existing environment"
        return
    }

    Get-Content $path | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+?)\s*=\s*(.*)\s*$') {
            $k = $Matches[1].Trim()
            $v = $Matches[2].Trim()
            $v = $v -replace '\s+#.*$', ''
            $v = $v.Trim('"').Trim("'")
            if (-not [System.Environment]::GetEnvironmentVariable($k, "Process")) {
                [System.Environment]::SetEnvironmentVariable($k, $v, "Process")
            }
        }
    }
}

function Stop-UvicornProcesses {
    Get-WmiObject Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*uvicorn*app.main:app*" } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Ok "Stopped uvicorn (PID $($_.ProcessId))"
    }
}

# ------------------------------------------------------------
# STOP mode
# ------------------------------------------------------------
if ($Stop) {
    Banner "Stopping AutoResearcher stack"
    Set-Location $ROOT

    try {
        docker compose down
        Ok "Docker stack stopped"
    }
    catch {
        Warn "Docker compose down failed or stack was not running"
    }

    Stop-UvicornProcesses
    exit 0
}

# ------------------------------------------------------------
# Pre-flight checks
# ------------------------------------------------------------
Banner "AutoResearcher - Pre-flight checks"

Require-Command python "Install Python 3.10+ from https://python.org"
Require-Command ollama "Install Ollama from https://ollama.com/download"
Require-Command docker "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"

$pyVer = python --version 2>&1
Ok "Python: $pyVer"

# Run docker info, tolerate warnings on stderr (e.g. blkio warning on WSL2)
# Run docker info - use try/catch because $ErrorActionPreference=Stop
# causes PowerShell to throw even on harmless stderr warnings
try {
    $dockerOut = docker info 2>&1
}
catch {
    $dockerOut = $_.Exception.Message
}
if ($LASTEXITCODE -ne 0 -and ($dockerOut -notmatch "WARNING")) {
    Err "Docker daemon is not running. Open Docker Desktop first."
    exit 1
}
Ok "Docker daemon: running"

Load-Env "$ROOT\.env"
Ok "Environment loaded from .env"

$missing = @()
foreach ($k in @("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")) {
    if (-not [System.Environment]::GetEnvironmentVariable($k, "Process")) {
        $missing += $k
    }
}
if ($missing.Count -gt 0) {
    Warn "Missing env vars: $($missing -join ', ')"
    Warn "Create a Langfuse project at http://localhost:3000 and paste the keys into .env"
}

# ------------------------------------------------------------
# Virtual environment
# ------------------------------------------------------------
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
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r "$ROOT\requirements.txt"
Ok "Dependencies ready"

# ------------------------------------------------------------
# Package markers
# ------------------------------------------------------------
Banner "Package structure"
@("app", "app\agents", "app\graph", "app\rag", "app\observability", "scripts") | ForEach-Object {
    $f = "$ROOT\$_\__init__.py"
    if (-not (Test-Path $f)) {
        New-Item -ItemType File -Path $f -Force *> $null
        Info "Created $_\__init__.py"
    }
}
Ok "All __init__.py markers present"

# ------------------------------------------------------------
# Docker stack (Langfuse)
# ------------------------------------------------------------
Banner "Starting Docker stack"
Set-Location $ROOT

docker compose up -d
Ok "Docker compose started"

Wait-Http "http://localhost:3000/api/public/health" "Langfuse" 180 5

# ------------------------------------------------------------
# Ollama
# ------------------------------------------------------------
if (-not $EvalOnly) {
    Banner "Ollama"
    $model = if ([System.Environment]::GetEnvironmentVariable("OLLAMA_MODEL", "Process")) {
        [System.Environment]::GetEnvironmentVariable("OLLAMA_MODEL", "Process")
    }
    else {
        "llama3.2"
    }

    try {
        Invoke-WebRequest "http://localhost:11434" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop *> $null
        Ok "Ollama already running"
    }
    catch {
        Info "Starting Ollama server..."
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 5
        Ok "Ollama started"
    }

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

# ------------------------------------------------------------
# FastAPI server
# ------------------------------------------------------------
if (-not $EvalOnly) {
    Banner "Starting FastAPI server"

    Stop-UvicornProcesses

    $apiProcess = Start-Process `
        -FilePath $venvPython `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" `
        -WorkingDirectory $ROOT `
        -PassThru

    Start-Sleep -Seconds 3
    Wait-Http "http://localhost:8000/health" "FastAPI" 90 5
}

# ------------------------------------------------------------
# Evaluation suite
# ------------------------------------------------------------
if (-not $NoEval) {
    Banner "Evaluation suite"

    Info "Creating eval dataset..."
    & $venvPython -m scripts.create_eval_dataset
    Ok "Dataset ready"

    Info "Running eval pipeline..."
    & $venvPython -m scripts.run_eval_on_dataset
    Ok "Eval complete"
}

# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------
Banner "AutoResearcher status"

if (-not $EvalOnly) {
    Write-Host ""
    Write-Host "  API server:     " -NoNewline
    Write-Host "http://localhost:8000" -ForegroundColor Green
    Write-Host "  API docs:       " -NoNewline
    Write-Host "http://localhost:8000/docs" -ForegroundColor Green
}
Write-Host "  Langfuse UI:    " -NoNewline
Write-Host "http://localhost:3000" -ForegroundColor Green
Write-Host "  MinIO console:  " -NoNewline
Write-Host "http://localhost:9001" -ForegroundColor Green
Write-Host ""
Write-Host "  To stop everything: " -NoNewline
Write-Host ".\start.ps1 -Stop" -ForegroundColor Yellow
Write-Host ""
