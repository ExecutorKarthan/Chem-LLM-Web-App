# ========================================
# Windows Dev Environment Setup Script (PowerShell)
# ========================================

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "LLM Explorer - Dev Setup (Windows)" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[1/6] Python detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from python.org" -ForegroundColor Yellow
    pause
    exit 1
}

# Check Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "[1/6] Node.js detected: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Node.js is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Node.js from nodejs.org" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host ""

# ========================================
# Backend Setup
# ========================================

Write-Host "[2/6] Setting up Django backend..." -ForegroundColor Yellow
Set-Location backend

# Create virtual environment
if (-Not (Test-Path "venv")) {
    Write-Host "  Creating virtual environment..." -ForegroundColor Gray
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        pause
        exit 1
    }
}

# Activate virtual environment
& .\venv\Scripts\Activate.ps1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "You may need to allow script execution: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
    pause
    exit 1
}

# Install dependencies
Write-Host "  Installing Python dependencies..." -ForegroundColor Gray
pip install --quiet --upgrade pip
pip install --quiet django djangorestframework django-cors-headers python-dotenv whitenoise google-generativeai

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install Python dependencies" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "[3/6] Generating Django secret key..." -ForegroundColor Yellow

# Generate secret key and create .env file in backend_project/ subdirectory
$secretKey = python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
$envContent = @"
DJANGO_SECRET_KEY=$secretKey
DJANGO_DEBUG=True
"@

Set-Content -Path "backend_project\.env" -Value $envContent
Write-Host "  Secret key generated and saved to backend_project/.env" -ForegroundColor Green

Write-Host ""
Write-Host "[4/6] Running database migrations..." -ForegroundColor Yellow
python manage.py migrate --noinput

if ($LASTEXITCODE -ne 0) {
    Write-Host "  WARNING: Database migration had issues (usually OK for first run)" -ForegroundColor Yellow
}

Write-Host "  Backend setup complete!" -ForegroundColor Green
Write-Host ""

# ========================================
# Frontend Setup
# ========================================

Set-Location ..\frontend

Write-Host "[5/6] Setting up React frontend..." -ForegroundColor Yellow

if (-Not (Test-Path "node_modules")) {
    Write-Host "  Installing Node.js dependencies..." -ForegroundColor Gray
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install Node.js dependencies" -ForegroundColor Red
        pause
        exit 1
    }
} else {
    Write-Host "  Node modules already installed, skipping..." -ForegroundColor Gray
}

Write-Host "  Frontend setup complete!" -ForegroundColor Green
Write-Host ""

# ========================================
# Root dependencies
# ========================================

Set-Location ..

Write-Host "[6/6] Installing root dependencies (concurrently)..." -ForegroundColor Yellow

if (-Not (Test-Path "node_modules\concurrently")) {
    npm install
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the dev servers, run:" -ForegroundColor Cyan
Write-Host "  npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "This will start:" -ForegroundColor Gray
Write-Host "  - Django backend on http://localhost:8000" -ForegroundColor Gray
Write-Host "  - Vite frontend on http://localhost:32775" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")