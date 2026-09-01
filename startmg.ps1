# 1. Terminal 1: Base de datos (MySQL)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& 'C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe' --defaults-file='C:\ProgramData\MySQL\MySQL Server 8.4\my.ini' --console"

# Esperar a que MySQL termine de inicializar
Start-Sleep -Seconds 3

# 2. Terminal 2: Backend (FastAPI)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\comet\Documents\mg; .\venv\Scripts\Activate.ps1; python -m uvicorn backend.api.main:app --reload --port 8000"

# 3. Terminal 3: Frontend (React + Vite)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\comet\Documents\mg\frontend; npm run dev"

# Esperar 3 segundos para el despliegue
Start-Sleep -Seconds 3

# 3. Abrir navegador
Start-Process "http://localhost:5173"