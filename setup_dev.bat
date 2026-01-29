@echo off
REM ========================================
REM Windows Dev Environment Setup Script
REM ========================================

echo.
echo =====================================
echo LLM Explorer - Dev Setup (Windows)
echo =====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from nodejs.org
    pause
    exit /b 1
)

echo [1/6] Checking Python and Node.js... OK
echo.

REM ========================================
REM Backend Setup
REM ========================================

echo [2/6] Setting up Django backend...
cd backend

REM Create virtual environment if it doesn't exist
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo Installing Python dependencies...
pip install --quiet --upgrade pip
pip install --quiet django djangorestframework django-cors-headers python-dotenv whitenoise google-generativeai
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies
    pause
    exit /b 1
)

echo.
echo [3/6] Generating Django secret key...

REM Create .env file with generated secret key in backend_project/ subdirectory
python -c "from django.core.management.utils import get_random_secret_key; print(f'DJANGO_SECRET_KEY={get_random_secret_key()}\nDJANGO_DEBUG=True')" > backend_project\.env
if errorlevel 1 (
    echo ERROR: Failed to generate secret key
    pause
    exit /b 1
)

echo Secret key generated and saved to backend_project/.env
echo.

echo [4/6] Running database migrations...
python manage.py migrate --noinput
if errorlevel 1 (
    echo WARNING: Database migration had issues (this is usually OK for first run)
)

echo.
echo Backend setup complete!
echo.

REM ========================================
REM Frontend Setup
REM ========================================

cd ..\frontend

echo [5/6] Setting up React frontend...
if not exist "node_modules\" (
    echo Installing Node.js dependencies...
    call npm install
    if errorlevel 1 (
        echo ERROR: Failed to install Node.js dependencies
        pause
        exit /b 1
    )
) else (
    echo Node modules already installed, skipping...
)

echo.
echo Frontend setup complete!
echo.

REM ========================================
REM Root dependencies
REM ========================================

cd ..

echo [6/6] Installing root dependencies...
if not exist "node_modules\concurrently\" (
    echo Installing concurrently for dev server...
    call npm install
)

echo.
echo =====================================
echo Setup Complete!
echo =====================================
echo.
echo To start the dev servers, run:
echo   npm run dev
echo.
echo This will start:
echo   - Django backend on http://localhost:8000
echo   - Vite frontend on http://localhost:32775
echo.
echo Press any key to exit...
pause >nul