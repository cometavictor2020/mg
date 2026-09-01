import os
import subprocess
import time
import webbrowser

# Rutas del proyecto
BASE_DIR = r"C:\Users\comet\Documents\mg"
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
VENV_ACTIVATE = os.path.join(BASE_DIR, "venv", "Scripts", "activate.bat")
MYSQLD = r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe"
MYSQL_INI = r"C:\ProgramData\MySQL\MySQL Server 8.4\my.ini"

# 1. Levantamos la base de datos (MySQL) en una nueva ventana CMD
mysql_cmd = f'start "MySQL" cmd /k ""{MYSQLD}" --defaults-file="{MYSQL_INI}" --console"'
subprocess.Popen(mysql_cmd, shell=True)

# Pausa para que MySQL termine de inicializar
time.sleep(3)

# 2. Levantamos el Backend (FastAPI) en una nueva ventana CMD
backend_cmd = f'start "FastAPI Backend" cmd /k "cd /d "{BASE_DIR}" && call "{VENV_ACTIVATE}" && python -m uvicorn backend.api.main:app --reload --port 8000"'
subprocess.Popen(backend_cmd, shell=True)

# 3. Levantamos el Frontend (React + Vite) en otra ventana CMD
frontend_cmd = f'start "React Frontend" cmd /k "cd /d "{FRONTEND_DIR}" && npm run dev"'
subprocess.Popen(frontend_cmd, shell=True)

# Pausa para dar tiempo a que los servidores inicien
time.sleep(3)

# 4. Abrimos el navegador en localhost:5173
webbrowser.open("http://localhost:5173")