# ========================================
# Windows Django Dev Environment Setup Script
# ========================================

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "LLM Explorer - Dev Setup (Windows)" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# ========================================
# Python Check
# ========================================

Write-Host "Checking Python installation..." -ForegroundColor Cyan

$PYTHON_V = py -0p --list-paths | Select-String -Pattern "3\.(0|1|2|3|4|5|6|7|8|9|10|11|12|13)"
if (-not $PYTHON_V) {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    exit 1
}
foreach ($version in $PYTHON_V) {
    if($version -notmatch " -V:3.14" -and $version -notmatch " -V:3.13t"){
        $PYTHON_CMD = $version -replace '.*([a-zA-Z]:\\[^ ]+).*', '$1'
        Write-Host "Python 3.13 detected: $PYTHON_CMD" -ForegroundColor Green
        break
    } 
}
if (-not $PYTHON_CMD) {
    Write-Host "WARNING: Python found but not version 3.13: $PYTHON_CMD" -ForegroundColor Yellow
    exit 1
}
Write-Host "Found Python: $PYTHON_CMD" -ForegroundColor Green

# ========================================
# Node.js Check
# ========================================

try {
    $nodeVersion = node --version
    Write-Host "[1/6] Node.js detected: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Node.js is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Node.js from nodejs.org" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""

# ========================================
# Backend Setup (Django)
# ========================================

Write-Host "[2/6] Setting up Django backend..." -ForegroundColor Yellow
Set-Location backend

# Remove old venv if exists
if (Test-Path "venv") {
    Write-Host "  Removing old virtual environment..." -ForegroundColor Gray
    Remove-Item -Recurse -Force venv
}

# Create virtual environment with Python 3.13
Write-Host "  Creating virtual environment with Python 3.13..." -ForegroundColor Gray
& $PYTHON_CMD -m venv venv

$VENV_PYTHON = ".\venv\Scripts\python.exe"
$venvVersion = & $VENV_PYTHON --version
Write-Host "  Venv Python: $venvVersion" -ForegroundColor Green

# Upgrade pip, setuptools, wheel
Write-Host "  Upgrading pip, setuptools, wheel..." -ForegroundColor Gray
& $VENV_PYTHON -m pip install --upgrade pip setuptools wheel

# Install backend dependencies from requirements.txt
Write-Host "  Installing Python dependencies from requirements.txt..." -ForegroundColor Gray
$requirementsPath = "requirements.txt"

if (-Not (Test-Path $requirementsPath)) {
    Write-Host "ERROR: requirements.txt not found at $requirementsPath" -ForegroundColor Red
    pause
    exit 1
}

& $VENV_PYTHON -m pip install -r $requirementsPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install Python dependencies from requirements.txt" -ForegroundColor Red
    pause
    exit 1
}

# ========================================
# Django Secret Key
# ========================================

Write-Host "[3/6] Generating Django secret key..." -ForegroundColor Yellow

$secretKey = & $VENV_PYTHON -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

@"
DJANGO_SECRET_KEY=$secretKey
DJANGO_DEBUG=True
"@ | Set-Content backend_project\.env

Write-Host "  Secret key saved to backend_project/.env" -ForegroundColor Green

# ========================================
# Database Migrations
# ========================================

Write-Host "[4/6] Running database migrations..." -ForegroundColor Yellow
& $VENV_PYTHON manage.py migrate --noinput

Write-Host "  Backend setup complete!" -ForegroundColor Green
Write-Host ""

# ========================================
# Frontend Setup (React)
# ========================================

Set-Location ..\frontend
Write-Host "[5/6] Setting up React frontend..." -ForegroundColor Yellow

if (-Not (Test-Path "node_modules")) {
    Write-Host "  Installing Node.js dependencies..." -ForegroundColor Gray
    npm install
} else {
    Write-Host "  Node modules already installed, skipping..." -ForegroundColor Gray
}

Write-Host "  Frontend setup complete!" -ForegroundColor Green
Write-Host ""

# ========================================
# Root dependencies
# ========================================

Set-Location ..
Write-Host "[6/6] Installing root dependencies..." -ForegroundColor Yellow

if (-Not (Test-Path "node_modules\concurrently")) {
    npm install
}

Write-Host ""
Write-Host "====================================="
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "====================================="

# Starting from script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Search recursively for manage.py
$BackendPath = Get-ChildItem -Path $ScriptDir -Recurse -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName "manage.py")
} | Select-Object -First 1

if (-not $BackendPath) {
    Write-Error "❌ Could not find backend folder with manage.py"
    exit 1
}

$BackendPath = $BackendPath.FullName
Write-Host "✅ Backend folder found: $BackendPath"
cd $BackendPath

# Search for a venv folder containing Activate.ps1
$VenvPath = Get-ChildItem -Path $BackendPath -Recurse -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName "Scripts\Activate.ps1")
} | Select-Object -First 1

if (-not $VenvPath) {
    Write-Error "❌ Could not find virtual environment folder"
    exit 1
}

$ActivateScript = Join-Path $VenvPath.FullName "Scripts\Activate.ps1"
Write-Host "✅ Activating virtual environment: $ActivateScript"
& $ActivateScript

# Optional: run migrations to ensure DB is ready
python manage.py migrate

Write-Host "✅ Setup complete. Starting Django server at http://localhost:8000..."

# Start Django server (blocking; script will stay running here)
python manage.py runserver 8000
