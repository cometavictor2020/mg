# 1. Terminal 1: Backend (FastAPI)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\comet\Documents\mg; .\venv\Scripts\Activate.ps1; python -m uvicorn backend.api.main:app --reload --port 8000"

# 2. Terminal 2: Frontend (React + Vite)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\comet\Documents\mg\frontend; npm run dev"

# Esperar 3 segundos para el despliegue
Start-Sleep -Seconds 3

# 3. Abrir navegador
Start-Process "http://localhost:5173"