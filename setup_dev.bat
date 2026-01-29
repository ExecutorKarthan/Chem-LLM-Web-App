@echo off
SETLOCAL EnableDelayedExpansion

echo.
echo =====================================
echo LLM Explorer - Dev Setup (Windows)
echo =====================================
echo.

REM ===============================
REM 1️⃣ Find Python
REM ===============================
set "PYTHON_CMD="
for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | findstr /i "WindowsApps" >nul
    if errorlevel 1 (
        set "PYTHON_CMD=%%P"
        goto FoundPython
    )
)

:FoundPython
if "%PYTHON_CMD%"=="" (
    echo ERROR: Python not found in PATH!
    echo Make sure Python is installed from python.org and added to PATH.
    pause
    exit /b 1
)
echo Found Python: %PYTHON_CMD%
echo.

REM ===============================
REM 2️⃣ Locate backend folder
REM ===============================
set "BACKEND_DIR="
for /f "delims=" %%F in ('dir /s /b manage.py 2^>nul') do (
    set "BACKEND_DIR=%%~dpF"
    goto BackendFound
)

:BackendFound
if "!BACKEND_DIR!"=="" (
    echo ERROR: Could not find backend folder with manage.py
    pause
    exit /b 1
)
echo Backend folder found: !BACKEND_DIR!
cd /d "!BACKEND_DIR!"

REM ===============================
REM 3️⃣ Set up virtual environment
REM ===============================
if exist venv (
    echo Removing old virtual environment...
    rmdir /s /q venv
)

echo Creating new virtual environment...
"%PYTHON_CMD%" -m venv venv

REM Activate venv
call venv\Scripts\activate.bat

REM Upgrade pip, setuptools, wheel
python -m pip install --upgrade pip setuptools wheel

REM Install Python dependencies
if exist requirements.txt (
    echo Installing Python dependencies...
    pip install -r requirements.txt
) else (
    echo WARNING: requirements.txt not found!
)
echo.

REM ===============================
REM 4️⃣ Generate Django secret key
REM ===============================
for /f "delims=" %%K in ('python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"') do set "DJANGO_SECRET_KEY=%%K"
(
echo DJANGO_SECRET_KEY=!DJANGO_SECRET_KEY!
echo DJANGO_DEBUG=True
) > backend_project\.env
echo Secret key written to backend_project\.env
echo.

REM ===============================
REM 5️⃣ Run database migrations
REM ===============================
echo Running database migrations...
python manage.py migrate --noinput
echo.

REM ===============================
REM 6️⃣ Setup Frontend (Node.js + npm)
REM ===============================
echo [Frontend Setup] Checking Node.js...
node -v >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    pause
    exit /b 1
)
for /f "delims=" %%v in ('node -v') do set "NODE_VERSION=%%v"
echo Node.js detected: !NODE_VERSION!
echo.

REM Move to frontend folder
set "FRONTEND_DIR=%~dp0frontend"
if not exist "!FRONTEND_DIR!" (
    echo ERROR: Frontend folder not found!
    pause
    exit /b 1
)
cd /d "!FRONTEND_DIR!"

if not exist node_modules (
    echo Installing frontend dependencies...
    call npm install
) else (
    echo Node modules already installed, skipping...
)
echo Frontend setup complete!
echo.

REM ===============================
REM 7️⃣ Return to backend and start Django server
REM ===============================
cd /d "!BACKEND_DIR!"
echo Starting Django server at http://localhost:8000 ...
call python manage.py runserver 8000

pause