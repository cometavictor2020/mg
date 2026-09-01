@echo off
echo Iniciando entorno MotorGuardian...

:: 1. Terminal 1: Base de datos (MySQL)
start "MySQL" cmd /k ""C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --defaults-file="C:\ProgramData\MySQL\MySQL Server 8.4\my.ini" --console"

:: Esperar a que MySQL termine de inicializar
timeout /t 3 /nobreak >nul

:: 2. Terminal 2: Backend (FastAPI)
start "FastAPI Backend" cmd /k "cd /d C:\Users\comet\Documents\mg && call venv\Scripts\activate.bat && python -m uvicorn backend.api.main:app --reload --port 8000"

:: 3. Terminal 3: Frontend (React + Vite)
start "React Frontend" cmd /k "cd /d C:\Users\comet\Documents\mg\frontend && npm run dev"

:: Esperar 3 segundos a que los servicios inicien
timeout /t 3 /nobreak >nul

:: 4. Abrir el navegador
start http://localhost:5173